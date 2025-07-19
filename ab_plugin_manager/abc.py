"""
Базовые классы и типы для системы загрузки плагинов.

С точки зрения системы плагинов, работа приложения рассматривается как набор *операций*.
Каждая операция состоит из выполнения последовательности *шагов*.
Шаг может представлять собой функцию, вызываемую в процессе выполнения операции или какой-либо другой объект, в
зависимости от сути конкретной операции.

Каждый плагин может добавлять произвольное количество шагов к одной или нескольким операциям.

Каждый шаг имеет уникальное в рамках операции имя.
Порядок шагов в рамках операции определяется зависимостями между ними.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterable, Collection, Any, NamedTuple, Union, Optional, Hashable, Callable

__all__ = ["OperationStep", "Plugin", "DependencyCycleException", "UnlistableOperationSetException", "PluginManager"]


class OperationStep(NamedTuple):
    """
    Объект, содержащий один шаг операции, добавленный плагином, а так же дополнительные сведения о его имени,
    зависимостях и ссылку на исходный плагин.
    """
    step: Any
    name: str
    plugin: 'Plugin'
    dependencies: Collection[str] = ()
    reverse_dependencies: Collection[str] = ()
    annotation: Optional[Any] = None

    def __str__(self):
        return f'{self.plugin}/{self.name}'


class UnlistableOperationSetException(Exception):
    """
    Исключение, которое выбрасывает плагин, не способный перечислить свои операции при вызове
    list_implemented_operations.
    """

    def __init__(self, plugin: 'Plugin', *args):
        super().__init__("Невозможно перечислить операции, реализуемые плагином", plugin, *args)


class Plugin(ABC):
    """
    Базовый класс для плагинов.

    Содержит только основные методы и аттрибуты, используемые системой плагинов.

    Реализовывать новые плагины наследуясь напрямую от этого класса в большинстве случаев неудобно.
    Более удобные средства для разработки плагинов предоставляет класс ``MagicPlugin``.
    """
    name: str
    version: str

    @abstractmethod
    def get_operation_steps(self, op_name: str) -> Iterable[OperationStep]:
        """
        Возвращает набор шагов для заданной операции, предоставляемых данным плагином.

        Args:
            op_name:
                имя операции.
                Например 'init', 'terminate'

        Returns:
            набор шагов, предоставляемый плагином
        """

    def list_implemented_operations(self) -> Iterable[str]:
        """
        Возвращает список операций, реализуемых плагином.

        Returns:
            Список названий операций, реализуемых этим плагином.
        Raises:
             UnlistableOperationSetException если перечислить операции невозможно.
                Например, если реализации операций генерируются динамически.
        """
        raise UnlistableOperationSetException(self)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.name = cls.__dict__.get('name', cls.__name__)

    def __str__(self):
        return f'{self.name}@{getattr(self, "version", "unknown")}'


class DependencyCycleException(Exception):
    """
    Исключение, сообщающее о наличии циклических зависимостей между шагами операции.
    """
    __slots__ = ('op_name', 'steps')

    def __init__(self, op_name: str, steps: Collection[Union[OperationStep, str]]):
        self.op_name = op_name
        self.steps = steps

    def __str__(self):
        return f'Набор шагов для операции "{self.op_name} содержит цикл зависимостей из следующих шагов: "' \
               f'{", ".join(map(str, self.steps))}'


class CurrentPluginManagerNotSetException(Exception):
    def __init__(self):
        super().__init__("Активный PluginManager не установлен")


class PluginManager(ABC):
    """
    Менеджер плагинов. Предоставляет доступ ко всем загруженным на данный момент плагинам.
    """

    @abstractmethod
    def get_operation_sequence(self, op_name: str) -> Iterable[OperationStep]:
        """
        Возвращает все шаги для заданной операции, упорядоченные в соответствии с их зависимостями.

        Args:
            op_name:
                имя операции

        Returns:
            последовательность шагов операции

        Raises:
            DependencyCycleException - если у шагов операции присутствуют циклические зависимости
        """

    def operation_cache(self, _op_name: str, _key: Hashable, compute: Callable, /, *args, **kwargs) -> Any:
        """
        Вычисляет и (возможно) кэширует значение, связанное с заданной операцией.

        При первом вызове с данным именем операции и ключом, будет вызвана функция compute, и будет возвращён результат
        её выполнения.
        При последующих вызовах с теми же именем операции и ключом, может быть возвращено значение, вычисленное при
        одном из предыдущих вызовов (даже если дополнительные параметры отличаются от предыдущего вызова).

        Эта функция предназначена для кэширования промежуточных результатов интерпретации операции, которые могут быть
        переиспользованы при последующих её выполнениях.

        Реализация по-умолчанию не кэширует значения.

        :param _op_name: Название операции
        :param _key: Ключ для кэширования значения
        :param compute: Функция, вычисляющая значение, если оно не доступно в кэше
        :param args: Аргументы для вызова функции `compute`
        :param kwargs: Именованные аргументы для вызова функции `compute`
        :return:
        """
        return compute(*args, **kwargs)

    def drop_operation_cache(
            self,
            *,
            operations: Optional[Iterable[str]] = None,
            keys: Optional[Iterable[Hashable]] = None,
            plugin: Optional[Plugin] = None,
            **_kwargs
    ):
        """
        Сбрасывает кэш значений, используемый функцией `operation_cache`.

        Параметры позволяют ограничить набор операций и ключей, для которых, кэш будет сброшен, но реализация может
        сбросить кэш для более широкого набора ключей/операций.

        :param operations: Операции, для которых необходимо сбросить кэш
        :param keys: Ключи, для которых необходимо сбросить кэш
        :param plugin: Плагин, для операций, реализуемых которым, необходимо сбросить кэш.
                        Может быть применено для динамической загрузки/выгрузки плагинов.
        :param _kwargs:
        """

    _current: ContextVar['PluginManager'] = ContextVar("PluginManager.current")

    @contextmanager
    def as_current(self):
        """
        Context manager, устанавливающий этот менеджер плагинов в качестве активного для текущего контекста (потока или
        асинхронной задачи).

        Используется следующим образом:

        >>> pm: PluginManager = ...
        >>>
        >>> with pm.as_current():
        >>>     ...
        """
        token = PluginManager._current.set(self)
        try:
            yield None
        finally:
            PluginManager._current.reset(token)

    @staticmethod
    def current_maybe() -> Optional['PluginManager']:
        """
        Возвращает активный менеджер плагинов или `None` если он не установлен.
        """
        try:
            return PluginManager._current.get()
        except LookupError:
            return None

    @staticmethod
    def current() -> 'PluginManager':
        """
        Возвращает активный менеджер плагинов, кидает ошибку если он не установлен.

        :raises CurrentPluginManagerNotSetException
        """
        try:
            pm = PluginManager._current.get()
        except LookupError:
            raise CurrentPluginManagerNotSetException()
        return pm
