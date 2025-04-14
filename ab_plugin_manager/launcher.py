import asyncio
import signal
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from logging import getLogger
from typing import Collection, Optional, Awaitable

from ab_plugin_manager.abc import Plugin
from ab_plugin_manager.operations import bootstrap, setup_cli_arguments, receive_cli_arguments
from ab_plugin_manager.plugin_manager import PluginManagerImpl
from ab_plugin_manager.run_operation import call_all_parallel_async

__all__ = ["launch_application"]

_logger = getLogger('launcher')

_HANDLED_SIGNALS = (
    signal.SIGINT,
    signal.SIGTERM,
)


async def _wait_for_interrupt() -> None:
    """
    Возвращает значение при получении приложением сигнала прерывания (SIGINT или SIGTERM).

    Task с вызовом этой функции желательно отменить как только слушать сигналы становится не нужно, так как для
    достижения поведения, близкого к корректному, эта функция вынуждена творить какую-то грязь.
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def handle_signal(sig, _frame):
        _logger.info("Получен сигнал: %s", signal.Signals(sig).name)
        loop.call_soon_threadsafe(future.set_result, None)

    try:
        timeout = 1
        while True:
            for sig in _HANDLED_SIGNALS:
                # :facepalm:
                # add_signal_handler не добавляет ещё один обработчик, а заменяет другой обработчик если он был.
                # Способа проверить, был ли обработчик заменён кем-то ещё нет, поэтому просто периодически ставим свой
                # обработчик заново.
                loop.add_signal_handler(sig, handle_signal, sig, None)

            done, _ = await asyncio.wait([future], timeout=timeout)

            if len(done) > 0:
                return await done.pop()

            # Если кто-то ещё и установит свой обработчик, то, скорее всего ближе к началу работы программы.
            # Так что делаем повторные попытки реже со временем, что бы не слишком грузить процессор.
            timeout *= 2
    except NotImplementedError:
        _logger.debug("add_signal_handler не поддерживается")

        # Код для работы под Windows. Позаимствовано и адаптировано из исходников Uvicorn.
        for sig in _HANDLED_SIGNALS:
            signal.signal(sig, handle_signal)

        # Некоторые библиотеки, например, сервер uvicorn пытаются назначать свои обработчики сигналов, не обращая
        # внимания на обработчики, зарегистрированные ранее.
        # Так что, мы игнорируем то, что они пытаются зарегистрировать вместо наших обработчиков.
        signal_orig = signal.signal

        def _signal(signalnum, handler):
            if signalnum in _HANDLED_SIGNALS:
                _logger.debug(
                    "Обработчик сигнала %s проигнорирован: %s",
                    signal.Signals(signalnum).name,
                    handler
                )
                return None

            return signal_orig(signalnum, handler)

        signal.signal = _signal

        try:
            await future
            return
        finally:
            signal.signal = signal_orig


async def _run_with_interrupts(future: Awaitable):
    """
    Ждёт завершения переданного Awaitable, одновременно слушая сигналы прерывания.

    Raises:
        InterruptedError
    """
    interrupt_task = asyncio.create_task(_wait_for_interrupt())

    try:
        (completed, *_), __ = await asyncio.wait(
            [future, interrupt_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if completed is interrupt_task:
            raise InterruptedError()
        else:
            await completed
    finally:
        interrupt_task.cancel()


def launch_application(
        core_plugins: Collection[Plugin],
        *,
        canonical_launch_command=None
):
    """
    Запускает приложение с заданным набором плагинов ядра.

    Args:
        core_plugins:
            коллекция плагинов ядра
        canonical_launch_command:
            имя команды, используемой для запуска приложения (используется для вывода справки)
    """
    pm = PluginManagerImpl(core_plugins)

    asyncio_debug, executor_max_workers = False, None

    def parse_args(strict: bool):
        ap = ArgumentParser(add_help=strict, prog=canonical_launch_command)

        ap.add_argument(
            '--asyncio-debug',
            action='store_true',
            dest='asyncio_debug',
            help="Включить отладку asyncio",
        )
        ap.add_argument(
            '--executor-max-workers', '-w',
            dest='executor_max_workers',
            metavar='<N>',
            help="Максимальное кол-во потоков в рабочем пуле.",
            default=None,
            required=False,
            type=int,
        )

        setup_cli_arguments(ap)

        if strict:
            args = ap.parse_args()
        else:
            args, _ = ap.parse_known_args()

        receive_cli_arguments(args)

        nonlocal asyncio_debug, executor_max_workers
        asyncio_debug = args.asyncio_debug
        executor_max_workers = args.executor_max_workers

    async def run_async_operations() -> None:
        executor = ThreadPoolExecutor(
            max_workers=executor_max_workers,
        )
        asyncio.get_running_loop().set_default_executor(executor)

        run_tasks: Optional[Collection[asyncio.Task]] = None

        try:
            init_tasks = await call_all_parallel_async(pm.get_operation_sequence('init'))

            try:
                await _run_with_interrupts(asyncio.gather(*init_tasks))
            except InterruptedError:
                _logger.info("Получен сигнал прерывания в процессе инициализации.")
                return

            _logger.info("Инициализация завершена.")

            run_tasks = await call_all_parallel_async(pm.get_operation_sequence('run'))
            try:
                await _run_with_interrupts(asyncio.gather(*run_tasks))
            except InterruptedError:
                _logger.info("Получен сигнал прерывания.")
                return
            finally:
                for task in run_tasks:
                    task.cancel()
        finally:
            _logger.debug("Начинаю выполнение операции terminate...")

            terminate_tasks = await call_all_parallel_async(pm.get_operation_sequence('terminate'))
            try:
                await _run_with_interrupts(asyncio.gather(*terminate_tasks))
            except InterruptedError:
                _logger.info("Получен ещё один сигнал прерывания. Пытаюсь завершиться быстрее.")
                return

            _logger.debug("Операция terminate завершена.")

            if run_tasks is not None:
                _logger.debug(
                    "Жду завершения задач: %s",
                    [task.get_name() for task in run_tasks if not task.done()]
                )

                # TODO: Нужно проверить, корректно ли отрабатывает следующий блок...
                try:
                    await _run_with_interrupts(asyncio.gather(*run_tasks, return_exceptions=True))
                except InterruptedError:
                    _logger.info("Получен ещё один сигнал прерывания. Пытаюсь завершиться быстрее.")
                else:
                    _logger.debug("Все задачи выполнены, завершаюсь штатно.")

    with pm.as_current():
        parse_args(False)
        bootstrap()
        parse_args(True)

        asyncio.run(run_async_operations(), debug=asyncio_debug)
