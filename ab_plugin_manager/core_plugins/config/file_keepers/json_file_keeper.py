import json
import re
from pathlib import Path
from typing import Self, Iterable

from ab_plugin_manager.core_plugins.config.abc import ConfigFileKeeper, StoredConfigVersion, RawConfig, \
    ConfigSchema, MissingConfigFileException, ConfigFileKeeperFactory

_JSON_EXTENSION_RE = re.compile(r".*\.json$", re.IGNORECASE)


class JsonFileKeeper(ConfigFileKeeper):
    dump_options = {}

    def __init__(self, path: Path):
        self._path = path

    def load_config(self) -> (RawConfig, StoredConfigVersion):
        try:
            with self._path.open("r") as f:
                return json.load(f), self.get_current_version()
        except FileNotFoundError:
            raise MissingConfigFileException(self._path)

    def store_config(self, config: RawConfig) -> StoredConfigVersion:
        with self._path.open("w") as f:
            json.dump(config, f, **self.dump_options)

        return self.get_current_version()

    def get_current_version(self) -> StoredConfigVersion:
        try:
            return self._path.stat().st_mtime
        except FileNotFoundError:
            raise MissingConfigFileException(self._path)


class JsonFileKeeperFactory(ConfigFileKeeperFactory):
    def make_default_file(self, directory_path: Path, scope: str, schema: ConfigSchema) -> Self:
        return JsonFileKeeper(directory_path.joinpath(f"{scope}.json"))

    def find_file(self, options: Iterable[Path], scope: str, schema: ConfigSchema) -> Self:
        pattern = re.compile(f"{re.escape(scope)}\\.json", re.IGNORECASE)

        for path in options:
            if pattern.match(path.name):
                return JsonFileKeeper(path)

        raise MissingConfigFileException(f"Не найден JSON-файл конфигурации для {scope} ({scope}.json)")
