from dataclasses import dataclass
from inspect import isgeneratorfunction
from typing import Generator, TypeVar, Callable, AsyncGenerator, Optional, Sequence, Any, Type, NamedTuple, Literal, \
    Awaitable, Self, cast

from ab_plugin_manager.abc import OperationStep, PluginManager
from ab_plugin_manager.magic_operation import MagicOperation


@dataclass(frozen=True)
class MiddlewareError(RuntimeError):
    step: Optional[OperationStep] = None


@dataclass(frozen=True)
class UnexpectedMiddlewareValue(MiddlewareError):
    value: Any = None
    kind: Literal['yield', 'return'] = 'yield'


class UnexpectedMiddlewareStop(MiddlewareError):
    ...


class UnexpectedMiddlewareContinue(MiddlewareError):
    ...


class UnsupportedMiddlewareType(MiddlewareError):
    ...


TArg = TypeVar('TArg')
TRes = TypeVar('TRes')

SyncMiddlewareGenerator = Generator[TArg, TRes, TRes]
SyncMiddlewareGeneratorFn = Callable[[TArg], SyncMiddlewareGenerator]
AsyncMiddlewareGenerator = AsyncGenerator[TArg | TRes, TRes]
AsyncMiddlewareGeneratorFn = Callable[[TArg], AsyncMiddlewareGenerator]
AnyMiddlewareGeneratorFn = AsyncMiddlewareGeneratorFn | SyncMiddlewareGeneratorFn


class MiddlewareImplementation[TArg, TRes](NamedTuple):
    generator_fns: Sequence[tuple[OperationStep, AnyMiddlewareGeneratorFn]]
    arg_type: Type[TArg]
    res_type: Type[TRes]
    is_sync: bool

    @staticmethod
    def _is_sync_step(fn: AnyMiddlewareGeneratorFn) -> bool:
        return isgeneratorfunction(fn)

    @classmethod
    def from_implementations(
            cls,
            arg_type: Type[TArg],
            res_type: Type[TRes],
            fns: Sequence[tuple[OperationStep, AnyMiddlewareGeneratorFn]],
    ) -> Self:
        is_sync = all(cls._is_sync_step(fn) for _step, fn in fns)
        return cls(generator_fns=fns, arg_type=arg_type, res_type=res_type, is_sync=is_sync)

    def run_sync(
            self,
            wrapped: Callable[[TArg], TRes],
            arg: TArg,
            **kwargs,
    ) -> TRes:
        if not self.is_sync:
            async_step_sample = next(step for step, fn in self.generator_fns if not self._is_sync_step(fn))
            raise RuntimeError(
                f"Operation can not run synchronously as it has asynchronous steps, eg: {async_step_sample}"
            )

        return MiddlewareRunner.run_sync(self, wrapped, arg, **kwargs)

    async def run_async(
            self,
            wrapped: Callable[[TArg], Awaitable[TRes]],
            arg: TArg,
            **kwargs,
    ) -> TRes:
        return await MiddlewareRunner.run_async(self, wrapped, arg, **kwargs)


class MiddlewareRunner[TArg, TRes]:
    generators: list[tuple[OperationStep, AsyncMiddlewareGenerator | SyncMiddlewareGenerator]]
    result: Optional[TRes]
    error: Optional[Exception]
    arg: TArg
    kwargs: dict[str, Any]
    implementation: MiddlewareImplementation[TArg, TRes]

    __slots__ = ('implementation', 'generators', 'result', 'error', 'arg', 'kwargs')

    def __init__(
            self,
            impl: MiddlewareImplementation[TArg, TRes],
            arg: TArg,
            kwargs: dict[str, Any],
    ):
        self.implementation = impl
        self.generators = []
        self.result = None
        self.error = None
        self.arg = arg
        self.kwargs = kwargs

    def _step_forward_sync(self, step: OperationStep, generator: SyncMiddlewareGenerator) -> bool:
        try:
            res = next(generator)
        except StopIteration as e:
            if isinstance(e.value, self.implementation.res_type):
                self.result = e.value
                return True
            else:
                self.error = UnexpectedMiddlewareValue(step=step, value=e.value, kind='return')
                return True
        except Exception as e:
            self.error = e
            return True
        else:
            if isinstance(res, self.implementation.arg_type):
                self.arg = res
                self.generators.append((step, generator))
                return False
            else:
                self.error = UnexpectedMiddlewareValue(step=step, value=res)
                return True

    async def _ensure_async_generator_stop(self, step: OperationStep, generator: AsyncMiddlewareGenerator):
        try:
            await anext(generator)
        except StopAsyncIteration:
            ...
        except Exception as e:
            self.error = e
        else:
            self.error = UnexpectedMiddlewareContinue(step=step)

    async def _step_forward_async(self, step: OperationStep, generator: AsyncMiddlewareGenerator) -> bool:
        try:
            res = await anext(generator)
        except StopAsyncIteration:
            self.error = UnexpectedMiddlewareStop(step=step)
            return True
        except Exception as e:
            self.error = e
            return True
        else:
            if isinstance(res, self.implementation.arg_type):
                self.arg = res
                self.generators.append((step, generator))
                return False
            elif isinstance(res, self.implementation.res_type):
                self.result = res
                await self._ensure_async_generator_stop(step, generator)
                return True
            else:
                self.error = UnexpectedMiddlewareValue(step=step, value=res)
                return True

    def _step_backward_sync(self, step: OperationStep, generator: SyncMiddlewareGenerator):
        try:
            if self.error is not None:
                res = generator.throw(self.error)
            else:
                res = generator.send(self.result)
        except StopIteration as e:
            if isinstance(e.value, self.implementation.res_type):
                self.result = e.value
                self.error = None
            else:
                self.error = UnexpectedMiddlewareValue(step=step, value=e.value, kind='return')
        except Exception as e:
            self.error = e
        else:
            self.error = UnexpectedMiddlewareValue(step=step, value=res)

    def _return(self) -> TRes:
        if self.error is not None:
            raise self.error
        else:
            assert isinstance(self.result, self.implementation.res_type)
            return self.result

    def _run_backward_sync(self) -> TRes:
        for step, generator in self.generators[::-1]:
            self._step_backward_sync(step, generator)
        return self._return()

    async def _step_backward_async(self, step: OperationStep, generator: AsyncMiddlewareGenerator):
        try:
            if self.error is not None:
                res = await generator.athrow(self.error)
            else:
                res = await generator.asend(self.result)
        except StopAsyncIteration:
            self.error = UnexpectedMiddlewareStop(step=step)
        except Exception as e:
            self.error = e
        else:
            if isinstance(res, self.implementation.res_type):
                self.result = res
                self.error = None
                await self._ensure_async_generator_stop(step, generator)
            else:
                self.error = UnexpectedMiddlewareValue(step=step, value=res)

    async def _run_backward_async(self) -> TRes:
        for step, generator in self.generators[::-1]:
            if isinstance(generator, AsyncGenerator):
                await self._step_backward_async(step, generator)
            else:
                self._step_backward_sync(step, generator)
        return self._return()

    def _run_forward_sync(self) -> bool:
        for step, fn in self.implementation.generator_fns:
            try:
                generator = fn(self.arg, **self.kwargs)
            except Exception as e:
                self.error = e
                return True

            if isinstance(generator, Generator):
                if self._step_forward_sync(step, generator):
                    return True
            else:
                self.error = UnsupportedMiddlewareType(step=step)
                return True

        return False

    async def _run_forward_async(self) -> bool:
        for step, fn in self.implementation.generator_fns:
            try:
                generator = fn(self.arg, **self.kwargs)
            except Exception as e:
                self.error = e
                return True

            if isinstance(generator, AsyncGenerator):
                should_break = await self._step_forward_async(step, generator)
            elif isinstance(generator, Generator):
                should_break = self._step_forward_sync(step, generator)
            else:
                self.error = UnsupportedMiddlewareType(step=step)
                should_break = True

            if should_break:
                return True

        return False

    @classmethod
    def run_sync(
            cls,
            impl: MiddlewareImplementation[TArg, TRes],
            wrapped: Callable[[TArg], TRes],
            /,
            arg: TArg,
            **kwargs,
    ) -> TRes:
        self = cls(impl, arg, kwargs)

        if self._run_forward_sync():
            return self._run_backward_sync()

        try:
            self.result = wrapped(self.arg, **self.kwargs)
        except Exception as e:
            self.error = e

        return self._run_backward_sync()

    @classmethod
    async def run_async(
            cls,
            impl: MiddlewareImplementation[TArg, TRes],
            wrapped: Callable[[TArg], Awaitable[TRes]],
            /,
            arg: TArg,
            **kwargs,
    ) -> TRes:
        self = cls(impl, arg, kwargs)

        if await self._run_forward_async():
            return await self._run_backward_async()

        try:
            self.result = await wrapped(self.arg, **self.kwargs)
        except Exception as e:
            self.error = e

        return await self._run_backward_async()


class MiddlewareOperation[TArg, TRes](MagicOperation[AnyMiddlewareGeneratorFn[TArg, TRes]]):
    """
    Операция, добавляющая дополнительные действия до и после выполнения функции.

    Функция и аргументы передаются вызывающей стороной:

    >>> op = MiddlewareOperation('create_item_mw', dict, Item)
    >>>
    >>> def create_item(params: dict) -> Item:
    >>>     ...
    >>>
    >>> op.invoke(create_item, {'color': 'red'})

    Можно использовать как с синхронными, так и с асинхронными функциями:

    >>> async def create_item_async(params: dict) -> Item:
    >>>     ...
    >>>
    >>> async def foo():
    >>>     await op.ainvoke(create_item_async, {'color': 'blue'})

    Реализации так же могут быть как синхронными, так и асинхронными (но при наличии асинхронных реализаций синхронный
    вызов операции работать не будет):

    >>> @op.implementation
    >>> def add_telemetry(arg: dict, **_kwargs):
    >>>     with telemetry.span('create_item', arg):
    >>>         # первый и единственный yield должен быть выполнен с параметром операции
    >>>         # (его можно изменить/заменить перед yield)
    >>>         # И вернёт результат операции, который затем нужно вернуть с помощью return
    >>>         return (yield arg)
    >>>
    >>> @op.implementation
    >>> async def cache_items(arg: dict, **_kwargs):
    >>>     if item := await get_cached_item(arg):
    >>>         yield item
    >>>         return
    >>>     # В случае асинхронной реализации не получится использовать return, так что нужно использовать
    >>>     # два оператора yield - первый - с обновлённым параметром операции вернёт её результат.
    >>>     # Второй - с (обновлённым) результатом операции.
    >>>     new_item = yield arg
    >>>     await save_cached_item(arg, new_item)
    >>>     yield new_item
    """

    __slots__ = ('arg_type', 'res_type')

    arg_type: Type[TArg]
    res_type: Type[TRes]

    def __init__(
            self,
            operation: str,
            arg_type: Type[TArg],
            res_type: Type[TRes],
    ):
        super().__init__(operation, cache_steps=False)
        self.arg_type = arg_type
        self.res_type = res_type

    def _compute_implementation(self) -> MiddlewareImplementation[TArg, TRes]:
        return MiddlewareImplementation.from_implementations(
            self.arg_type,
            self.res_type,
            [(step, cast(AnyMiddlewareGeneratorFn, step.step)) for step in self.get_steps_no_cache()],
        )

    def get_implementation(self) -> MiddlewareImplementation[TArg, TRes]:
        return PluginManager.current().operation_cache(
            self.operation,
            id(self),
            MiddlewareOperation._compute_implementation,
            self,
        )

    def invoke(
            self,
            wrapped: Callable[[TArg], TRes],
            /,
            arg: TArg,
            **kwargs,
    ) -> TRes:
        return self.get_implementation().run_sync(wrapped, arg, **kwargs)

    async def ainvoke(
            self,
            wrapped: Callable[[TArg], Awaitable[TRes]],
            /,
            arg: TArg,
            **kwargs,
    ) -> TRes:
        return await self.get_implementation().run_async(wrapped, arg, **kwargs)
