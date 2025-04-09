import asyncio
from asyncio import Task
from functools import wraps, partial
from typing import Callable, Iterable, Union, Awaitable, Collection

from ab_plugin_manager.abc import PluginManager, OperationStep
from ab_plugin_manager.magic_plugin import operation as operation_decorator
from ab_plugin_manager.run_operation import call_all_as_wrappers, call_all, call_all_parallel_async, \
    call_all_as_wrappers_async


def _is_method(fn) -> bool:
    import inspect
    # TODO: Find a more accurate way to detect a method...
    return inspect.getargs(fn.__code__).args[0] == "self"


class MagicOperation[TImpl: Callable]:
    """

    TODO: Добавить документацию

    >>> op: MagicOperation = ...
    >>>
    >>> @op.implementation
    >>> def foo(...):
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


class CallAllOperation[*TARgs](MagicOperation[Callable[[*TARgs], None]]):
    def __call__(self, *args: TARgs, **kwargs) -> None:
        call_all(self.get_steps(), *args, **kwargs)


class WrapperCallOperation[*TARgs, TResult](
    MagicOperation[Callable[[Callable[[TResult, *TARgs], TResult], *TARgs], TResult]]
):
    """

    TODO: Добавить документацию

    >>> op: WrapperCallOperation = ...
    >>>
    >>> @op.implementation
    >>> def foo(nxt, prev, *args, **kwargs):
    >>>     thing = ...(prev)
    >>>     thing = nxt(thing, *args, **kwargs)
    >>>     return ...(thing)

    Типичный вариант реализации операции такого типа - создание объекта если он не был создан на предыдущем шаге:

    >>> @op.implementation
    >>> def bar_raw(nxt, thing, *args, **kwargs):
    >>>     if thing is None:
    >>>         thing = ...make_thing(...) or None
    >>>     return nxt(thing, *args, **kwargs)

    Это можно сделать проще, при помощи декоратора ``factory_implementation``:

    >>> @op.factory_implementation
    >>> def bar(*args, **kwargs):
    >>>     return ...make_thing(...) or None

    >>> op(*args, **kwargs)
    """

    def invoke(self, *args: TARgs, **kwargs) -> TResult:
        return call_all_as_wrappers(self.get_steps(), None, *args, **kwargs)

    async def ainvoke(self, *args: TARgs, **kwargs) -> TResult:
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
    MagicOperation[Callable[[Callable[[TResult, *TARgs], Awaitable[TResult]], *TARgs], Awaitable[TResult]]]
):
    """

    TODO: Добавить документацию

    >>> op: AsyncWrapperCallOperation = ...
    >>>
    >>> @op.implementation
    >>> async def foo(nxt, prev, *args, **kwargs):
    >>>     thing = ...(prev)
    >>>     thing = await nxt(thing, *args, **kwargs)
    >>>     return ...(thing)

    Типичный вариант реализации операции такого типа - создание объекта если он не был создан на предыдущем шаге:

    >>> @op.implementation
    >>> async def bar_raw(nxt, thing, *args, **kwargs):
    >>>     if thing is None:
    >>>         thing = await ...make_thing(...) or None
    >>>     return await nxt(thing, *args, **kwargs)
    >>>
    >>> @op.factory_implementation
    >>> async def bar(*args, **kwargs):
    >>>     return await ...make_thing(...) or None

    >>> async def foo():
    >>>     await op(*args, **kwargs)
    """

    def ainvoke(self, *args, **kwargs):
        return call_all_as_wrappers_async(self.get_steps(), None, *args, **kwargs)

    __call__ = ainvoke

    def factory_implementation(self, fn: Callable[[*TARgs], Awaitable[TResult]]):
        if _is_method(fn):
            @wraps(fn)
            async def impl(self, nxt, prev, *args, **kwargs):
                return await nxt(prev if prev is not None else await fn(self, *args, **kwargs), *args, **kwargs)
        else:
            @wraps(fn)
            async def impl(nxt, prev, *args, **kwargs):
                return await nxt(prev if prev is not None else await fn(*args, **kwargs), *args, **kwargs)

        return self.implementation(impl)


class CallAllAsyncConcurrentOperation[*TArgs, TResult](
    MagicOperation[Union[Callable[[*TArgs], TResult], Callable[[*TArgs], Awaitable[TResult]]]]
):
    async def __call__(self, *args: TArgs, **kwargs) -> Collection[Task[TResult]]:
        return await call_all_parallel_async(self.get_steps(), *args, **kwargs)
