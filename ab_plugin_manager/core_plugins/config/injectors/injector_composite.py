from typing import Sequence

from ab_plugin_manager.abc import OperationStep
from ab_plugin_manager.core_plugins.config.abc import ConfigInjector, UnsupportedConfigTypeException, \
    ConfigInjectorFactory


class UnsupportedByAllConfigTypeException(ExceptionGroup, UnsupportedConfigTypeException):
    ...


class CompositeInjector(ConfigInjectorFactory):
    def __init__(self, factories: Sequence[ConfigInjectorFactory]):
        self._factories = factories

    def try_instantiate(self, step: OperationStep) -> 'ConfigInjector':
        errors = []

        for injector in self._factories:
            try:
                return injector.try_instantiate(step)
            except UnsupportedByAllConfigTypeException as e:
                errors.append(e)

        raise UnsupportedByAllConfigTypeException(
            "",
            errors,
        )
