import re
from logging import getLogger
from pathlib import Path
from typing import Self, Any, Iterable

from ruamel.yaml import YAML, CommentedMap, CommentedSeq

from ab_plugin_manager.core_plugins.config.abc import ConfigFileKeeper, ConfigSchema, StoredConfigVersion, RawConfig, \
    MissingConfigDataException, ConfigData, MissingConfigFileException, ConfigFileKeeperFactory

_YAML_FILE_RE = re.compile(r".*\.ya?ml$", re.IGNORECASE)

_logger = getLogger('YamlFileKeeper')


class YamlFileKeeper(ConfigFileKeeper):
    def __init__(self, path: Path, schema: ConfigSchema):
        self._path = path
        self._schema = schema
        self._yaml = YAML()
        self._last_read_data = None

    def _load(self) -> RawConfig:
        self._last_read_data = self._yaml.load(self._path)
        return self._last_read_data

    def load_config(self) -> (RawConfig, StoredConfigVersion):
        try:
            return self._load(), self.get_current_version()
        except FileNotFoundError:
            raise MissingConfigDataException()

    def _create_initial_map(self, config: RawConfig, schema: ConfigSchema) -> CommentedMap:
        cm = CommentedMap()

        try:
            description = schema['description']
        except KeyError:
            pass
        else:
            cm.yaml_set_start_comment(description)

        properties = schema.get('properties', {})

        for k, v in config.items():
            cm[k] = v
            try:
                prop_schema = properties[k]
                prop_description = prop_schema['description']
            except KeyError:
                pass
            else:
                cm.yaml_set_comment_before_after_key(k, before=prop_description)

        return cm

    def _update_data(self, config: RawConfig):
        raise NotImplementedError

    def _dereference_schema(self, schema: ConfigSchema) -> ConfigSchema:
        """
        Probably not a valid implementation but may work for most schemas.
        """
        _defs_prefix = '#/'

        if isinstance(ty := schema.get('$ref'), str) and ty.startswith(_defs_prefix):
            def_path = ty[len(_defs_prefix):].split('/')
            s = self._schema
            for step in def_path:
                try:
                    s = s[step]
                except KeyError:
                    return schema

            return s

        return schema

    def _init_value(self, value: ConfigData, schema: ConfigSchema, depth: int) -> Any:
        if isinstance(value, dict):
            return self._merge(CommentedMap(), value, schema, depth=depth)

        if isinstance(value, list):
            return self._merge(CommentedSeq((None for _ in value)), value, schema, depth=depth)

        return value

    def _merge(self, known_data: Any, new_data: ConfigData, schema: ConfigSchema, depth: int) -> Any:
        schema = self._dereference_schema(schema)

        if depth == 0 and \
                (isinstance(known_data, CommentedMap) or isinstance(known_data, CommentedSeq)) and \
                isinstance(desc := schema.get("description"), str):
            known_data.yaml_set_start_comment(desc + '\n\n')

        if isinstance(known_data, dict) and isinstance(new_data, dict):
            prop_schemas = {}
            additional_props_schema = prop_schemas

            if schema.get("type") == "object":
                prop_schemas = schema.get("properties", prop_schemas)
                additional_props_schema = schema.get("additionalProperties", additional_props_schema)

            for k in known_data.keys():
                try:
                    new_value = self._init_value(
                        new_data[k],
                        prop_schemas.get(k, additional_props_schema),
                        depth=depth + 1,
                    )
                except KeyError:
                    del known_data[k]
                else:
                    known_data[k] = self._merge(
                        known_data[k],
                        new_value,
                        prop_schemas.get(k, additional_props_schema),
                        depth=depth + 1,
                    )

            for k, v in new_data.items():
                if k not in known_data:
                    known_data[k] = self._init_value(v, prop_schemas.get(k, additional_props_schema), depth=depth + 1)
                    if isinstance(known_data, CommentedMap) and \
                            isinstance(
                                prop_desc := prop_schemas.get(k, additional_props_schema).get("description"),
                                str
                            ):
                        known_data.yaml_set_comment_before_after_key(k, before=prop_desc, indent=2 * depth)

            return known_data

        if isinstance(known_data, list) and isinstance(new_data, list):
            if (ln := len(known_data)) == len(new_data):
                item_schema = {}
                if schema.get("type") == "array":
                    item_schema = schema.get("items", item_schema)

                for i in range(ln):
                    known_data[i] = self._merge(known_data[i], new_data[i], item_schema, depth=depth)

                return known_data

        return self._init_value(new_data, schema, depth=depth)

    def store_config(self, config: RawConfig) -> StoredConfigVersion:
        try:
            if self._last_read_data is None:
                self._last_read_data = self._init_value(config, self._schema, depth=0)
            else:
                self._last_read_data = self._merge(self._last_read_data, config, self._schema, depth=0)
        except Exception:
            _logger.exception(
                "Ошибка при формировании/обновлении данных YAML-файла конфигурации %s",
                self._path,
            )
            # В случае ошибки пытаемся сохранить конфигурацию без комментариев
            self._last_read_data = config

        self._yaml.dump(self._last_read_data, self._path)

        return self.get_current_version()

    def get_current_version(self) -> StoredConfigVersion:
        try:
            return self._path.stat().st_mtime
        except FileNotFoundError:
            raise MissingConfigDataException()


class YamlConfigFileKeeperFactory(ConfigFileKeeperFactory):
    def make_default_file(self, directory_path: Path, scope: str, schema: ConfigSchema) -> Self:
        return YamlFileKeeper(directory_path.joinpath(f"{scope}.json"), schema)

    def find_file(self, options: Iterable[Path], scope: str, schema: ConfigSchema) -> Self:
        pattern = re.compile(f"{re.escape(scope)}\\.ya?ml", re.IGNORECASE)

        for path in options:
            if pattern.match(path.name):
                return YamlFileKeeper(path, schema)

        raise MissingConfigFileException(f"Не найден YAML-файл конфигурации для {scope} ({scope}.yaml или {scope}.yml)")
