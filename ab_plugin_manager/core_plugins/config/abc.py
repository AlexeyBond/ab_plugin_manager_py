from abc import ABC, abstractmethod
from typing import Any, Hashable

from ab_plugin_manager.abc import OperationStep

RawConfig = dict[str, Any]

ConfigSchema = dict[str, Any]

StoredConfigVersion = Hashable
"""
Идентификатор, характеризующий конкретную версию сохранённой конфигурации.

Это может быть дата изменения файла/записи в БД или хэш содержимого конфигурации.
"""


class UnsupportedConfigTypeException(Exception):
    pass


class ConfigInjector(ABC):
    """
    Объект, отвечающий за передачу одной конфигурации одному плагину.
    """

    @abstractmethod
    def get_current_hash(self) -> int:
        """
        Получает хэш текущего состояния конфигурации плагина.
        """
        ...

    @abstractmethod
    def get_current_content(self) -> RawConfig:
        """
        Получает текущее состояние конфигурации из плагина.
        """
        ...

    @abstractmethod
    def inject_config(self, config: RawConfig):
        """
        Передаёт плагину обновление конфигурации.
        """
        ...

    @abstractmethod
    def get_schema(self) -> ConfigSchema:
        """
        Возвращает схему конфигурации, предоставленную плагином.
        """
        ...

    @classmethod
    @abstractmethod
    def try_instantiate(cls, step: OperationStep) -> 'ConfigInjector':
        """

        Raises:
            UnsupportedConfigTypeException: если тип конфигурации не соответствует ожидаемому этим Injector'ом
        """
        ...


class ConfigKeeper(ABC):
    """
    Отвечает за хранение одной конфигурации.
    """

    @abstractmethod
    async def set_schema(self, schema: ConfigSchema):
        """
        Устанавливает схему конфигурации.

        Сохраняемая или считываемая конфигурации не обязаны соответствовать этой схеме.
        """
        ...

    @abstractmethod
    async def load_config(self) -> (RawConfig, StoredConfigVersion):
        """
        Читает текущую конфигурацию из хранилища.

        Возвращает саму конфигурацию и идентификатор её версии.
        """
        ...

    @abstractmethod
    async def store_config(self, config: RawConfig) -> StoredConfigVersion:
        """
        Сохраняет конфигурацию в хранилище.

        Возвращает идентификатор новой сохранённой версии.
        """
        ...

    @abstractmethod
    async def get_current_version(self) -> StoredConfigVersion:
        """
        Возвращает версию текущей конфигурации из хранилища.
        """
        ...


class ConfigStorage(ABC):
    @abstractmethod
    async def get_keeper(self, scope: str) -> ConfigKeeper:
        """
        Возвращает объект, предоставляющий доступ к одной из конфигураций в хранилище.
        """
        ...

    @abstractmethod
    async def shutdown(self):
        """
        Завершает работу хранилища.

        После начала вызова этого метода, любые другие обращения к хранилищу, или созданным им экземплярам
        `ConfigKeeper` ведут к неопределённому поведению.
        """
        ...
