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
from typing import Iterable, Collection, Any, NamedTuple, Union, Optional

__all__ = ["OperationStep", "Plugin", "DependencyCycleException", "PluginManager"]


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

    def __str__(self):
        return f'{self.plugin}/{self.name}'


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
