from argparse import ArgumentParser
from logging import getLogger
from typing import Awaitable, Callable, Iterable, Literal

from ab_plugin_manager.abc import OperationStep
from ab_plugin_manager.magic_operation import MagicOperation
from ab_plugin_manager.magic_plugin import MagicPlugin, step_name, before, operation
from ab_plugin_manager.operations import run as run_op

default_job_op = MagicOperation[Callable[..., None | Awaitable[None]]]('default_job')
"""
Задачи, которые нужно запускать по-умолчанию при запуске приложения.
"""

job_op = MagicOperation[Callable[..., Awaitable[None]]]('job')
"""
Задачи, которые нужно запускать только по явному запросу (через параметр командной строки).
"""

type JobRunMode = Literal['run', 'job', 'default_job']


def apply_run_mode(plugin: MagicPlugin, mode: JobRunMode, member: str):
    """
    Позволяет выбирать, как запускается один из методов плагина - как реализация операции run, операции job или
    операции default_job.

    Функция предназначена в первую очередь для универсальных плагинов ядра, которые можно настраивать под потребности
    конкретного приложения через параметры конструктора.
    """
    if mode == 'run' and member == 'run':
        return

    member_value = getattr(type(plugin), member)
    setattr(
        plugin,
        member,
        operation(mode)(member_value).__get__(plugin),
    )


class JobsPlugin(MagicPlugin):
    """
    Добавляет возможность управлять тем, какие задачи выполняет конкретный процесс приложения, без изменения общей конфигурации.

    Плагин добавляет две операции (job и default_job), шаги которых добавляются или не добавляются в список шагов
    операции run, в зависимости от параметров командной строки.
    Каждый шаг этих операций называется задачей (job).
    Названием задачи считается название шага (step_name).
    """

    name = "jobs"
    version = "0.1.0"

    _logger = getLogger(name)

    _run_default_jobs: bool = True
    _job_settings: list[str] = []

    def setup_cli_arguments(self, ap: ArgumentParser, *_args, **_kwargs):
        ap.add_argument(
            '--job',
            type=str,
            action='append',
            help="Запускает определённую задачу.\n"
                 "Предотвращает запуск задач по-умолчанию, если не передан флаг --run-default-jobs.\n"
                 "Используйте --job list-jobs чтобы посмотреть список доступных задач",
        )
        ap.add_argument(
            '--no-default-jobs',
            action='store_true',
            help="Не запускать задачи по умолчанию, если ни одной задачи не запущено явно (через параметр --job).",
        )
        ap.add_argument(
            '--run-default-jobs',
            action='store_true',
            help="Запускать задачи по-умолчанию если есть задачи, запущенные явно (через параметр --job).",
        )

    def receive_cli_arguments(self, args, *_args, **_kwargs):
        if (jobs := args.job) is not None and len(jobs) > 0:
            self._job_settings = jobs
            self._run_default_jobs = args.run_default_jobs
        else:
            self._run_default_jobs = not args.no_default_jobs

    @step_name('list-jobs')
    @job_op.implementation
    def list_jobs(self, *_args, **_kwargs):
        if len(default_jobs := list(default_job_op.get_steps())) > 0:
            print('Default jobs:')
            for job in default_jobs:
                print(f"{job.name} (registered by {job.plugin})")
        if len(jobs := list(job_op.get_steps())) > 0:
            print('Optional jobs:')
            for job in jobs:
                print(f"{job.name} (registered by {job.plugin})")

    def _jobs_to_run_steps(self) -> Iterable[OperationStep]:
        running_default_job_names = set()

        if self._run_default_jobs:
            for step in default_job_op.get_steps():
                yield step
                running_default_job_names.add(step.name)

        if len(job_settings := self._job_settings) > 0:
            jobs: dict[str, OperationStep] = {
                step.name: step
                for step in job_op.get_steps()
            }

            if not self._run_default_jobs:
                for step in default_job_op.get_steps():
                    if step.name in jobs:
                        self._logger.warning("Задача %s конфликтует с одноимённой задачей по-умолчанию", step.name)
                    else:
                        jobs[step.name] = step

            running_jobs: set[str] = set()

            for setting in job_settings:
                job_name = setting

                if job_name in running_default_job_names:
                    self._logger.warning("Задача %s уже запущена по-умолчанию", job_name)
                    continue

                if job_name in running_jobs:
                    self._logger.warning("Задача %s уже запущена", job_name)
                    continue

                try:
                    job_step = jobs[job_name]
                except KeyError:
                    raise Exception(f"Неизвестная задача {job_name}") from None

                yield job_step
                running_jobs.add(job_name)

    def get_operation_steps(self, op_name: str) -> Iterable[OperationStep]:
        if op_name == run_op.operation:
            return self._jobs_to_run_steps()

        return super().get_operation_steps(op_name)
