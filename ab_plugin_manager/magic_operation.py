import asyncio
from abc import ABC
from asyncio import Task, to_thread
from functools import wraps, partial
from typing import Callable, Iterable, Union, Awaitable, Collection, Optional, NamedTuple, Self, Type

from ab_plugin_manager.abc import PluginManager, OperationStep
from ab_plugin_manager.magic_plugin import operation as operation_decorator
from ab_plugin_manager.run_operation import call_all_as_wrappers, call_all, call_all_parallel_async, \
    call_all_as_wrappers_async


def _is_method(fn) -> bool:
    import inspect
    # TODO: Find a more accurate way to detect a method...
    args = inspect.getargs(fn.__code__).args
    return len(args) > 0 and args[0] == "self"


class MagicOperation[TImpl: Callable]:
    """
    Базовый класс для объявлений операций.

    >>> op: MagicOperation = MagicOperation("my_op")

    Получить шаги объявленной таким образом операции можно вызвав её метод ``get_steps``:

    >>> op.get_steps()

    такой вызов эквивалентен прямому обращению к `PluginManager`'у:

    >>> PluginManager.current().get_operation_sequence("my_op")

    В плагинах, наследующихся от `MagicPlugin` и модулях-плагинах можно использовать декоратор `implementation` чтобы
    пометить функцию/метод как реализацию операции, не зависимо от названия:

    >>> @op.implementation
    >>> def foo(...):
    >>>     ...
    >>>
    >>> # Декоратор `operation` с исходным именем операции будет работать так же
    >>> from ab_plugin_manager.magic_plugin import operation
    >>> @operation("my_op")
    >>> def bar(...):
    >>>     ...
    >>>
    >>> # Функция с именем, совпадающим с именем операции, будет так же считаться её реализацией
    >>> def my_op(...):
    >>>     ...
    """
    __slots__ = ("operation",)

    operation: str

    def __init__(self, operation: str):
        self.operation = operation

    def get_steps(self) -> Iterable[OperationStep]:
        return PluginManager.current().get_operation_sequence(self.operation)

    def implementation(self, fn: TImpl):
        return operation_decorator(self.operation)(fn)


class MagicOperationResultCheck[TResult](NamedTuple):
    check: Callable[[TResult], bool]
    message: str


class MagicOperationResultCheckError(AssertionError):
    def __init__(self, operation: MagicOperation, check: MagicOperationResultCheck):
        super().__init__(f"Некорректный результат операции {operation}: {check.message}")
        self.operation = operation
        self.check = check


class MagicOperationWithResultProcessing[TResult, TImpl: Callable](MagicOperation[TImpl], ABC):
    """
    Операция, возвращающая какой-то результат и позволяющая добавлять статические проверки этого результата.
    """

    __slots__ = ("_checks",)

    _checks: list[MagicOperationResultCheck[TResult]]

    def __init__(self, operation: str):
        super().__init__(operation)
        self._checks = []

    def _process_result(self, res: TResult) -> TResult:
        for check in self._checks:
            if not check.check(res):
                raise MagicOperationResultCheckError(operation=self, check=check)

        return res

    async def _aprocess_result(self, res: TResult) -> TResult:
        return await to_thread(self._process_result, res)

    def with_check(self, check: MagicOperationResultCheck[TResult]) -> Self:
        self._checks.append(check)
        return self

    def returning_not_none(self) -> Self:
        return self.with_check(MagicOperationResultCheck(lambda it: it is not None, "Результат не должен быть None"))

    def returning_instance_of(self, ty: Type[TResult]) -> Self:
        return self.with_check(
            MagicOperationResultCheck(
                lambda it: isinstance(it, ty),
                f"Результат должен быть экземпляром {ty}"
            )
        )


class CallAllOperation[*TARgs](MagicOperation[Callable[[*TARgs], None]]):
    def __call__(self, *args: *TARgs, **kwargs) -> None:
        call_all(self.get_steps(), *args, **kwargs)


class WrapperCallOperation[*TARgs, TResult](
    MagicOperationWithResultProcessing[
        TResult,
        Callable[[Callable[[TResult, *TARgs], TResult], Optional[TResult], *TARgs], TResult],
    ]
):
    """
    Операция, рекурсивно вызывающая все шаги.

    >>> op: WrapperCallOperation = ...
    >>>
    >>> @op.implementation
    >>> def foo(nxt, prev, *args, **kwargs):
    >>>     thing = ...(prev)
    >>>     # `nxt(...)` вызовет следующие шаги и вернёт окончательный результат следующего шага
    >>>     # или `thing` если этот шаг последний и следующего зан им нет
    >>>     thing = nxt(thing, *args, **kwargs)
    >>>     return ...(thing)

    Типичный вариант реализации операции такого типа - создание объекта если он не был создан на предыдущем шаге:

    >>> def make_thing(...):
    >>>     ...
    >>> @op.implementation
    >>> def bar_raw(nxt, thing, *args, **kwargs):
    >>>     if thing is None:
    >>>         thing = ...make_thing(...) or None
    >>>     return nxt(thing, *args, **kwargs)

    Это можно сделать проще, при помощи декоратора ``factory_implementation``:

    >>> @op.factory_implementation
    >>> def bar(*args, **kwargs):
    >>>     return ...make_thing(...) or None

    Выполнить операцию можно при помощи оператора вызова функции или через методы `invoke`/`ainvoke`:

    >>> async def mine(*args, **kwargs):
    >>>     op(*args, **kwargs)
    >>>     op.invoke(*args, **kwargs)
    >>>     # `ainvoke` выполнит операцию в executor'е
    >>>     await op.ainvoke(*args, **kwargs)
    """

    def invoke(self, *args: *TARgs, **kwargs) -> TResult:
        return self._process_result(call_all_as_wrappers(self.get_steps(), None, *args, **kwargs))

    async def ainvoke(self, *args: *TARgs, **kwargs) -> TResult:
        return await asyncio.to_thread(partial(self.invoke, *args, **kwargs))

    __call__ = invoke

    def factory_implementation(self, fn: Callable[[*TARgs], TResult]):
        if _is_method(fn):
            @wraps(fn)
            def impl(self, nxt, prev, *args, **kwargs):
                return nxt(prev if prev is not None else fn(self, *args, **kwargs), *args, **kwargs)
        else:
            @wraps(fn)
            def impl(nxt, prev, *args, **kwargs):
                return nxt(prev if prev is not None else fn(*args, **kwargs), *args, **kwargs)

        return self.implementation(impl)


class AsyncWrapperCallOperation[*TARgs, TResult](
    MagicOperationWithResultProcessing[
        TResult,
        Callable[
            [Callable[[Optional[TResult], *TARgs], Awaitable[TResult]], *TARgs],
            Awaitable[Optional[TResult]]
        ]
    ]
):
    """
    Операция, рекурсивно вызывающая асинхронные функции.

    Аналог `WrapperCallOperation` для асинхронных функций.

    >>> op: AsyncWrapperCallOperation = ...
    >>>
    >>> @op.implementation
    >>> async def foo(nxt, prev, *args, **kwargs):
    >>>     thing = ...(prev)
    >>>     thing = await nxt(thing, *args, **kwargs)
    >>>     return ...(thing)

    Типичный вариант реализации операции такого типа - создание объекта если он не был создан на предыдущем шаге:

    >>> def make_thing(...):
    >>>     ...
    >>>
    >>> @op.implementation
    >>> async def bar_raw(nxt, thing, *args, **kwargs):
    >>>     if thing is None:
    >>>         thing = await ...make_thing(...) or None
    >>>     return await nxt(thing, *args, **kwargs)
    >>>
    >>> @op.factory_implementation
    >>> async def bar(*args, **kwargs):
    >>>     return await ...make_thing(...) or None

    >>> async def foo(*args, **kwargs):
    >>>     await op(*args, **kwargs)
    """

    async def ainvoke(self, *args, **kwargs):
        res = await call_all_as_wrappers_async(self.get_steps(), None, *args, **kwargs)
        return self._process_result(res)

    __call__ = ainvoke

    def factory_implementation(self, fn: Callable[[*TARgs], Awaitable[TResult]]):
        if _is_method(fn):
            @wraps(fn)
            async def impl(self, nxt, prev, *args: *TARgs, **kwargs):
                return await nxt(
                    prev if prev is not None else await fn(self, *args, **kwargs),
                    *args, **kwargs
                )
        else:
            @wraps(fn)
            async def impl(nxt, prev, *args: *TARgs, **kwargs):
                return await nxt(prev if prev is not None else await fn(*args, **kwargs), *args, **kwargs)

        return self.implementation(impl)


class CallAllAsyncConcurrentOperation[*TArgs, TResult](
    MagicOperation[Union[Callable[[*TArgs], TResult], Callable[[*TArgs], Awaitable[TResult]]]]
):
    """
    Операция, все шаги которой выполняются асинхронно (но с учётом зависимостей).
    """
    async def __call__(self, *args: *TArgs, **kwargs) -> Collection[Task[TResult]]:
        return await call_all_parallel_async(self.get_steps(), *args, **kwargs)
