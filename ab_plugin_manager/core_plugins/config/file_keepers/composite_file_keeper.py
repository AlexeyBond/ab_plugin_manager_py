from pathlib import Path
from typing import Sequence, Iterable, Collection

from ab_plugin_manager.core_plugins.config.abc import ConfigFileKeeper, ConfigSchema, MissingConfigFileException, \
    ConfigFileKeeperFactory


class MissingConfigFilesException(ExceptionGroup, MissingConfigFileException):
    ...


class CompositeFileKeeper(ConfigFileKeeperFactory):
    def __init__(self, factories: Sequence[ConfigFileKeeperFactory]):
        self._factories = factories

    def make_default_file(self, directory_path: Path, scope: str, schema: ConfigSchema) -> ConfigFileKeeper:
        return self._factories[0].make_default_file(directory_path, scope, schema)

    def find_file(self, options: Collection[Path], scope: str, schema: ConfigSchema) -> ConfigFileKeeper:
        errors = []

        for keeper in self._factories:
            try:
                return keeper.find_file(options, scope, schema)
            except MissingConfigFileException as e:
                errors.append(e)

        raise MissingConfigFilesException(
            f"Не найдено ни одного подходящего файла конфигурации для {scope}",
            errors,
        )
