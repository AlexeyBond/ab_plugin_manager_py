from collections import defaultdict
from collections.abc import Hashable
from graphlib import TopologicalSorter, CycleError
from logging import getLogger
from typing import Iterable, Collection, Any, Callable, Optional

from ab_plugin_manager.abc import PluginManager, OperationStep, Plugin, DependencyCycleException, \
    UnlistableOperationSetException

__all__ = ["PluginManagerImpl"]


class PluginManagerImpl(PluginManager):
    __slots__ = ('_plugins', '_logger', '_op_cache')

    def __init__(self, plugins: Collection[Plugin], *, logger=getLogger('PluginManager')):
        self._plugins = plugins
        self._logger = logger
        self._op_cache: defaultdict[str, dict[Hashable, Any]] = defaultdict(dict)

    def get_operation_sequence(self, op_name: str) -> Iterable[OperationStep]:
        ts: TopologicalSorter[str] = TopologicalSorter()
        steps: dict[str, OperationStep] = {}

        for plugin in self._plugins:
            for step in plugin.get_operation_steps(op_name):
                if step.name in steps:
                    self._logger.warning(
                        'Шаг с именем "%s" для операции "%s" добавлен одновременно плагинами %s и %s. '
                        'Шаг, добавленные плагином %s будет проигнорирован.',
                        step.name, op_name, steps[step.name].plugin, plugin, plugin
                    )
                    continue

                steps[step.name] = step

                ts.add(step.name, *step.dependencies)

                for reverse_dep in step.reverse_dependencies:
                    ts.add(reverse_dep, step.name)

        try:
            ts.prepare()
        except CycleError as e:
            raise DependencyCycleException(
                op_name,
                [steps.get(name, name) for name in e.args[1][1:]]
            )

        # Генератор вынесен в отдельную функцию чтобы исключение DependencyCycleException выкидывалось непосредственно
        # при вызове get_operation_sequence
        def iterate():
            while ts.is_active():
                node_group = ts.get_ready()

                for name in node_group:
                    if name in steps:
                        yield steps[name]

                ts.done(*node_group)

        return iterate()

    def operation_cache(self, op_name: str, key: Hashable, compute: Callable, /, *args, **kwargs) -> Any:
        operation_scope = self._op_cache[op_name]

        try:
            return operation_scope[key]
        except KeyError:
            pass

        res = compute(*args, **kwargs)
        operation_scope[key] = res

        return res

    def drop_operation_cache(
            self,
            *,
            operations: Optional[Iterable[str]] = None,
            keys: Optional[Iterable[Hashable]] = None,
            plugin: Optional[Plugin] = None,
            **_kwargs
    ):
        op_cache = self._op_cache

        def drop_operation(operation: str):
            if keys is not None:
                operation_scope = op_cache.get(operation)
                if operation_scope is None:
                    return
                for key in keys:
                    del operation_scope[key]
            else:
                try:
                    del op_cache[operation]
                except KeyError:
                    pass

        if operations is not None:
            for op in operations:
                drop_operation(op)
            return

        if plugin is not None:
            try:
                operations = plugin.list_implemented_operations()
            except UnlistableOperationSetException:
                pass
            else:
                for op in operations:
                    drop_operation(op)
                return

        self._op_cache = defaultdict(dict)
