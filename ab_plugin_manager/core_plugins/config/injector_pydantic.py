from typing import Any, Optional

from pydantic import BaseModel

from ab_plugin_manager.abc import OperationStep
from ab_plugin_manager.core_plugins.config.abc import ConfigInjector, RawConfig, UnsupportedConfigTypeException
from ab_plugin_manager.utils.snapshot_hash import snapshot_hash


class PydanticConfigInjector(ConfigInjector):
    def __init__(self, config: BaseModel):
        self._config = config
        self._model: type[BaseModel] = config.__class__
        self._schema: Optional[dict[str, Any]] = None

    def get_current_hash(self) -> int:
        return snapshot_hash(self._config, hash)

    def get_current_content(self) -> RawConfig:
        return self._config.model_dump(mode="json")

    def inject_config(self, config: RawConfig):
        update = self._config.model_validate(config)
        for f in self._model.model_fields:
            if f in config:
                setattr(self._config, f, getattr(update, f))

    def get_schema(self) -> dict[str, Any]:
        if self._schema is None:
            self._schema = self._config.model_json_schema()

        return self._schema

    @classmethod
    def try_instantiate(cls, step: OperationStep) -> ConfigInjector:
        if not isinstance(step.step, BaseModel):
            raise UnsupportedConfigTypeException()

        return cls(step.step)
