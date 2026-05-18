from collections.abc import Callable
from dataclasses import dataclass
from functools import update_wrapper
from inspect import iscoroutinefunction
from logging import getLogger
from typing import Mapping, Iterable, Awaitable, Type, Any

from ab_plugin_manager.abc import OperationStep, PluginManager
from ab_plugin_manager.magic_operation import MagicOperationWithResultProcessing

_logger = getLogger('TypedFactoryOperation')


class _FactoriesDict[TKey, TFactory: Callable](dict[TKey, TFactory]):
    def __get__(self, instance, owner) -> dict[str, TFactory]:
        res = _FactoriesDict({
            key: value.__get__(instance, owner)
            for key, value in self.items()
        })

        res.__dict__.update(self.__dict__)

        if '__call__' in self.__dict__:
            res.__dict__['__call__'] = self.__dict__['__call__'].__get__(instance, owner)

        return res

    def __call__(self, *args, **kwargs):
        return self.__dict__['__call__'](*args, **kwargs)


class TypedFactoryError(RuntimeError):
    ...


class KeyRetrievalError(TypedFactoryError):
    ...


@dataclass
class UnknownTypeError(TypedFactoryError):
    type_name: Any


@dataclass
class UnsupportedAsyncFactory(TypedFactoryError):
    type_name: Any
    step: OperationStep


@dataclass
class UnexpectedResult(TypedFactoryError):
    type_name: Any
    step: OperationStep
    value: Any


class TypedFactoryOperation[TSrc, TKey, TRes](
    MagicOperationWithResultProcessing[TRes, Mapping[TKey, Callable[[TSrc], TRes | Awaitable[TRes]]]],
):
    """
    Операция, выполняющая один из обработчиков в зависимости от содержимого первого аргумента.

    Основное предназначение - создание объектов различных подтипов по декларативному описанию, полученому из
    JSON-конфигурации или аналогичного источника.

    >>> from ab_plugin_manager.magic_plugin import MagicPlugin
    >>>
    >>> make_item = TypedFactoryOperation('make_item', str, Item)
    >>>
    >>> item = make_item.invoke({'type': 'red'})
    >>> item = await make_item.ainvoke({'type': 'blue'})
    >>>
    >>> class ItemsPlugin(MagicPlugin):
    >>>     make_item = {
    >>>         'blue': make_blue_item,
    >>>         'red': make_red_item,
    >>>     }

    Декоратор ``TypedFactoryOperation.type_factory`` позволяет добавить функцию, создающую объект одного подтипа:

    >>> @make_item.type_factory('red')
    >>> def make_red_item(decl: dict, *_args, **_kwargs):
    >>>     ...

    Реализация может быть асинхронной (работать будет только при асинхронном же вызове операции);
    можно указывать несколько названий для одного подтипа:

    >>> @make_item.type_factory(['blue', 'Blue'])
    >>> async def make_blue_item(decl: dict, *_args, **_kwargs):
    >>>     ...
    """
    __slots__ = ('key_type', 'res_type', 'key_from_src')

    def __init__(
            self,
            operation: str,
            key_type: Type[TKey],
            res_type: Type[TRes],
            key_from_src: Callable[[TSrc], TKey] = lambda src: src['type'],
    ):
        super().__init__(operation)
        self.key_type = key_type
        self.res_type = res_type
        self.key_from_src = key_from_src

    def type_factory(
            self,
            type_name: TKey | Iterable[TKey],
    ) -> Callable[
        [Callable[[TSrc], TRes | Awaitable[TRes]]],
        _FactoriesDict[TKey, Callable[[TSrc], TRes | Awaitable[TRes]]]
    ]:
        def decorator(cb: Callable[[TSrc], TRes | Awaitable[TRes]]):
            if isinstance(type_name, self.key_type):
                fd = _FactoriesDict({type_name: cb})
            else:
                fd = _FactoriesDict({key: cb for key in type_name})

            fd.__dict__['__call__'] = cb

            update_wrapper(fd, cb)

            return self.implementation(fd)

        return decorator

    def _build_factory_mapping(self) -> dict[TKey, tuple[OperationStep, Callable[[TSrc], TRes | Awaitable[TRes]]]]:
        factories: dict[TKey, tuple[OperationStep, Callable[[TSrc], TRes | Awaitable[TRes]]]] = {}

        for step in self.get_steps_no_cache():
            assert isinstance(step.step, dict)

            for key, factory in step.step.items():
                if key in factories:
                    _logger.warning(
                        "Duplicate type name '%s' in operation '%s' - both %s and %s implement it",
                        key, self.operation, factories[key][0], step,
                    )
                else:
                    factories[key] = (step, factory)

        return factories

    def get_factories_mapping(self) -> dict[TKey, tuple[OperationStep, Callable[[TSrc], TRes | Awaitable[TRes]]]]:
        return PluginManager.current().operation_cache(
            self.operation,
            _FACTORIES_MAPPING_CACHE_KEY,
            TypedFactoryOperation._build_factory_mapping,
            self,
        )

    def _get_factory(self, src: TSrc) -> tuple[TKey, OperationStep, Callable[[TSrc], TRes | Awaitable[TRes]]]:
        try:
            key = self.key_from_src(src)
        except Exception:
            raise KeyRetrievalError()

        factories = self.get_factories_mapping()

        try:
            step, factory = factories[key]
        except KeyError:
            raise UnknownTypeError(type_name=key)

        return key, step, factory

    def invoke(self, src: TSrc, *args, **kwargs) -> TRes:
        key, step, factory = self._get_factory(src)

        if iscoroutinefunction(factory):
            raise UnsupportedAsyncFactory(type_name=key, step=step)

        res = factory(src, *args, **kwargs)

        if isinstance(res, self.res_type):
            return self._process_result(res)

        if isinstance(res, Awaitable):
            raise UnsupportedAsyncFactory(type_name=key, step=step)

        raise UnexpectedResult(type_name=key, step=step, value=res)

    async def ainvoke(self, src: TSrc, *args, **kwargs) -> TRes:
        key, step, factory = self._get_factory(src)

        res = factory(src, *args, **kwargs)

        if isinstance(res, Awaitable):
            res = await res

        if isinstance(res, self.res_type):
            return await self._aprocess_result(res)

        raise UnexpectedResult(type_name=key, step=step, value=res)


_FACTORIES_MAPPING_CACHE_KEY = id(TypedFactoryOperation)
