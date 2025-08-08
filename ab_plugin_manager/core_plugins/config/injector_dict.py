from textwrap import dedent
from typing import Any, Optional

from ab_plugin_manager.abc import OperationStep
from ab_plugin_manager.core_plugins.config.abc import ConfigInjector, RawConfig, UnsupportedConfigTypeException
from ab_plugin_manager.utils.snapshot_hash import snapshot_hash


class DictConfigInjector(ConfigInjector):
    def __init__(self, config: dict[str, Any], comment: Optional[str]):
        self._config = config
        self._comment = comment

    def get_current_hash(self) -> int:
        return snapshot_hash(self._config, hash)

    def get_current_content(self) -> RawConfig:
        return self._config

    def inject_config(self, config: RawConfig):
        self._config.update(config)

    def get_schema(self) -> dict[str, Any]:
        schema = {"type": "object", "additionalProperties": True}

        if self._comment is not None:
            schema["description"] = self._comment

        return schema

    @classmethod
    def try_instantiate(cls, step: OperationStep) -> 'ConfigInjector':
        if not isinstance(step.step, dict):
            raise UnsupportedConfigTypeException()

        comments = []

        for comment_step in step.plugin.get_operation_steps("config_comment"):
            if isinstance(step_comment := comment_step.step, str):
                comments.append(dedent(step_comment).strip())

        if len(comments) == 0:
            comments.append(f"Настройки плагина {step.plugin}")

        return cls(step.step, '\n'.join(comments))
