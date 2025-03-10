import sys
from importlib.util import spec_from_file_location, module_from_spec
from inspect import isclass
from logging import getLogger
from os.path import isfile, basename, splitext
from types import ModuleType
from typing import Optional, TypedDict, Iterable

from ab_plugin_manager.abc import PluginManager, Plugin, OperationStep
from ab_plugin_manager.errors import PluginExcludedException
from ab_plugin_manager.file_patterns import match_files, substitute_patterns
from ab_plugin_manager.magic_plugin import MagicPlugin, after, step_name, operation, MagicModulePlugin
from ab_plugin_manager.run_operation import call_until_first_result, call_all


class PluginDiscoveryPlugin(MagicPlugin):
    name = 'discover_plugins'
    version = '1.0.2'

    _logger = getLogger(name)

    class _Config(TypedDict):
        pluginPaths: list[str]
        appendPythonPath: list[str]
        excludePlugins: list[str]

    config: _Config = {
        'pluginPaths': [],
        'appendPythonPath': [],
        "excludePlugins": []
    }

    config_comment = """
    Настройки поиска и загрузки пользовательских плагинов.

    Доступные параметры:
    - `pluginPaths`       - шаблоны путей файлов плагинов
    - `appendPythonPath`  - шаблоны путей папок, которые будут добавлены в PYTHONPATH.
                            Если зависимости плагинов ставятся в папку, не находящуюся в PYTHONPATH, то путь к этой
                            папке нужно указать здесь.
    - `excludePlugins`    - список плагинов, которые загружать не нужно. См. далее.
    
    ## Отключение плагинов

    Для отключения плагина, в excludePlugins можно указать:

    - имя файла плагина, с расширением (например, plugin_tts_cache.py) или без (например, plugin_tts_cache).
      При возможности, стоит использовать этот способ т.к. в этом случае файл плагина не будет импортирован, что ускорит
      загрузку всего приложения.
    - имя плагина, как указано в его переменной name (например, tts_cache)
    - имя плагина с версией (например, tts_cache@0.2.0).
      Такой вариант можно использовать чтобы отключить стандартную версию плагина, положив свою версию в одну из папок,
      указанных в pluginPaths.
    """

    def __init__(self) -> None:
        super().__init__()
        self._plugins: list[Plugin] = []
        self._excluded: set[str] = set()

    def receive_config(self, config, *_args, **_kwargs):
        self._excluded = set(config['excludePlugins'])

    def get_operation_steps(self, op_name: str) -> Iterable[OperationStep]:
        for plugin in self._plugins:
            yield from plugin.get_operation_steps(op_name)

        yield from super().get_operation_steps(op_name)

    @after('config')
    def bootstrap(self, pm: PluginManager, *_args, **_kwargs):
        sys.path.extend(substitute_patterns(self.config['appendPythonPath']))

        plugin_discover_op = list(
            pm.get_operation_sequence('discover_plugins_at_path'))
        plugin_discovered_op = list(
            pm.get_operation_sequence('plugin_discovered'))

        for plugin_path in match_files(self.config['pluginPaths']):
            try:
                plugins: Optional[Iterable[Plugin]] = call_until_first_result(
                    plugin_discover_op, pm, plugin_path)
            except PluginExcludedException:
                self._logger.info(
                    "Плагин из файла %s отключён",
                    plugin_path,
                )
                continue

            if plugins is None:
                self._logger.warning(
                    "Не удалось загрузить плагин из %s",
                    plugin_path
                )
                continue

            for plugin in plugins:
                if plugin.name in self._excluded or str(plugin) in self._excluded:
                    continue

                self._logger.debug(
                    "Найден плагин %s в файле %s",
                    plugin, plugin_path
                )

                self._plugins.append(plugin)
                call_all(plugin_discovered_op, pm, plugin)

    @step_name('discover_python_module')
    def discover_plugins_at_path(self, pm: PluginManager, path: str, *_args, **_kwargs):
        if not isfile(path):
            return

        if not path.endswith('.py'):
            return

        file_basename = basename(path)

        if file_basename in self._excluded:
            raise PluginExcludedException()

        module_name = splitext(file_basename)[0]

        if module_name in self._excluded:
            raise PluginExcludedException()

        spec = spec_from_file_location(
            module_name,
            path,
        )

        if spec is None or spec.loader is None:
            self._logger.warning(
                "Не удалось загрузить модуль плагина %s - не удалось создать спецификацию модуля",
                path
            )
            return

        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        return call_until_first_result(pm.get_operation_sequence('discover_plugins_in_module'), pm, module)

    @step_name('discover_explicit_plugins')
    def discover_plugins_in_module(self, pm: PluginManager, module: ModuleType, *_args, **_kwargs):
        found = []
        excluded = 0
        attrs = getattr(module, '__all__', dir(module))

        for attr in attrs:
            value = getattr(module, attr, None)

            if isinstance(value, Plugin):
                found.append(value)
            elif isclass(value) and \
                    issubclass(value, Plugin) and \
                    getattr(value, '__module__', module.__name__) == module.__name__:
                if getattr(value, 'name', None) in self._excluded:
                    excluded = excluded + 1
                    continue

                found.append(value())

        if len(found) > 0:
            return found

        if excluded > 0:
            raise PluginExcludedException()

    @operation('discover_plugins_in_module')
    @step_name('discover_magic_plugin_module')
    @after('discover_explicit_plugins')
    def discover_magic_plugin_module(self, _pm: PluginManager, module: ModuleType, *_args, **_kwargs):
        name = getattr(module, 'name', None)

        if not isinstance(name, str):
            return None

        version = getattr(module, 'version', None)

        if not isinstance(version, str):
            return None

        return MagicModulePlugin(module),

    def register_fastapi_endpoints(self, router, *_args, **_kwargs) -> None:
        from fastapi import APIRouter
        from pydantic import BaseModel, Field

        r: APIRouter = router

        class PluginModel(BaseModel):
            name: str = Field(
                title="Имя плагина",
            )
            version: str = Field(
                title="Версия плагина",
            )
            docs: Optional[str] = Field(
                title="Документация плагина",
                description="Извлекается из docstring'а класса или модуля плагина",
            )

        @r.get(
            '/plugins',
            response_model=list[PluginModel],
            name="Получение списка всех пользовательских плагинов",
        )
        def list_all_user_plugins():
            """
            Возвращает список всех плагинов с их краткими описаниями.
            """
            return [
                PluginModel(
                    name=plugin.name,
                    version=plugin.version,
                    docs=getattr(plugin, '__doc__', None)
                ) for plugin in self._plugins
            ]
