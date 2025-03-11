from abc import ABC
from asyncio import Task
from functools import wraps
from typing import Callable, Iterable, Union, Awaitable, Collection

from ab_plugin_manager.abc import PluginManager, OperationStep
from ab_plugin_manager.magic_plugin import operation as operation_decorator
from ab_plugin_manager.run_operation import call_all_as_wrappers, call_all, call_all_parallel_async


class MagicOperation[TImpl: Callable]:
    """


    >>> op: MagicOperation = ...
    >>>
    >>> @op.implementation
    >>> def foo(...):
    >>>     ...
    """
    __slots__ = ("operation")

    operation: str

    def __init__(self, operation: str):
        self.operation = operation

    def get_steps(self) -> Iterable[OperationStep]:
        return PluginManager.current().get_operation_sequence(self.operation)

    def implementation(self, fn: TImpl):
        return operation_decorator(self.operation)(fn)


class CallAllOperation[TARgs](MagicOperation[Callable[[*TARgs], None]]):
    def __call__(self, *args: TARgs, **kwargs) -> None:
        call_all(self.get_steps(), *args, **kwargs)


class WrapperCallOperation[TARgs, TResult](
    MagicOperation[Callable[[Callable[[TResult, *TARgs], TResult], *TARgs], TResult]]
):
    """

    >>> op: WrapperCallOperation = ...
    >>>
    >>> @op.implementation
    >>> def foo(nxt, prev, *args, **kwargs):
    >>>     thing = ...(prev)
    >>>     thing = nxt(thing, *args, **kwargs)
    >>>     return ...(thing)
    >>>
    >>> @op.implementation
    >>> def bar_raw(nxt, thing, *args, **kwargs):
    >>>     if thing is None:
    >>>         thing = ...make_thing(...) or None
    >>>     return nxt(thing, *args, **kwargs)
    >>>
    >>> @op.factory_implementation
    >>> def bar(*args, **kwargs):
    >>>     return ...make_thing(...) or None

    >>> op(*args, **kwargs)
    """

    def __call__(self, *args: TARgs, **kwargs) -> TResult:
        return call_all_as_wrappers(self.get_steps(), None, *args, **kwargs)

    def factory_implementation(self, fn: Callable[[*TARgs], TResult]):
        @wraps(fn)
        def impl(nxt, prev, *args, **kwargs):
            return nxt(prev if prev is not None else fn(*args, **kwargs), *args, **kwargs)

        return self.implementation(impl)


class CallAllAsyncConcurrentOperation[TArgs, TResult](
    MagicOperation[Union[Callable[[*TArgs], TResult], Callable[[*TArgs], Awaitable[TResult]]]]
):
    async def __call__(self, *args: TArgs, **kwargs) -> Collection[Task[TResult]]:
        return await call_all_parallel_async(self.get_steps(), *args, **kwargs)
