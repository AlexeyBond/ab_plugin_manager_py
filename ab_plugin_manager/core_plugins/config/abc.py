from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Hashable, Collection

from ab_plugin_manager.abc import OperationStep

ConfigData = list['ConfigData'] | dict[str, 'ConfigData'] | float | int | str | bool

RawConfig = dict[str, ConfigData]

ConfigSchema = dict[str, Any]

StoredConfigVersion = Hashable
"""
Идентификатор, характеризующий конкретную версию сохранённой конфигурации.

Это может быть дата изменения файла/записи в БД или хэш содержимого конфигурации.
"""


class UnsupportedConfigTypeException(TypeError):
    pass


class MissingConfigDataException(Exception):
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


class ConfigInjectorFactory(ABC):
    """
    Создаёт экземпляры ConfigInjector.
    """
    @abstractmethod
    def try_instantiate(self, step: OperationStep) -> ConfigInjector:
        """
        Создаёт ConfigInjector для данного поля полагина.

        Raises:
            UnsupportedConfigTypeException: если тип конфигурации не соответствует ожидаемому этим Injector'ом
        """
        ...


class ConfigKeeper(ABC):
    """
    Отвечает за хранение одной конфигурации.
    """

    @abstractmethod
    async def load_config(self) -> (RawConfig, StoredConfigVersion):
        """
        Читает текущую конфигурацию из хранилища.

        Возвращает саму конфигурацию и идентификатор её версии.

        Raises:
            MissingConfigDataException
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

        Raises:
            MissingConfigDataException
        """
        ...


class ConfigStorage(ABC):
    """
    Хранилище конфигураций.

    Предоставляет операции для чтения и записи конфигураций, хранящихся где-либо (в ФС, БД, каком-либо сервисе).
    """

    @abstractmethod
    async def get_keeper(self, scope: str, schema: ConfigSchema) -> ConfigKeeper:
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


# region File storage abc

class MissingConfigFileException(FileNotFoundError, MissingConfigDataException):
    pass


class ConfigFileKeeper(ABC):
    """
    Отвечает за хранение одной конфигурации в одном файле.

    Интерфейс схож с ConfigKeeper за исключением того, что все методы синхронны и существует явное допущение, что они
    осуществляют работу с файловой системой.
    """

    @abstractmethod
    def load_config(self) -> (RawConfig, StoredConfigVersion):
        """
        Загружает текущее содержимое файла конфигурации.

        Raises:
            MissingConfigFileException: если файл конфигурации отсутствует в ФС
        """

    @abstractmethod
    def store_config(self, config: RawConfig) -> StoredConfigVersion:
        """
        Записывает новое содержимое в файл конфигурации.
        """

    @abstractmethod
    def get_current_version(self) -> StoredConfigVersion:
        """
        Возвращает идентификатор текущей версии конфигурации, сохранённой в файле.

        Обычно это mtime файла.

        Raises:
            MissingConfigFileException: если файл конфигурации отсутствует в ФС
        """


class ConfigFileKeeperFactory(ABC):
    """
    Создаёт экземпляры ConfigFileKeeper.
    """

    @abstractmethod
    def find_file(self, options: Collection[Path], scope: str, schema: ConfigSchema) -> 'ConfigFileKeeper':
        """
        Ищет подходящий файл конфигурации среди списка имеющихся файлов.

        Args:
            options: список имеющихся файлов
            scope: название искомой конфигурации
            schema: JSON-схема конфигурации
        Raises:
            MissingConfigFileException: если подходящего файла не найдено
        Returns:
            ConfigFileKeeper для работы с найденным файлом
        """

    @abstractmethod
    def make_default_file(self, directory_path: Path, scope: str, schema: ConfigSchema) -> 'ConfigFileKeeper':
        """
        Создаёт или открывает файл по-умолчанию для заданной конфигурации.

        Args:
            directory_path: путь к папке с файлами конфигурации
            scope: имя конфигурации
            schema: схема конфигурации
        """

# endregion File storage abc
