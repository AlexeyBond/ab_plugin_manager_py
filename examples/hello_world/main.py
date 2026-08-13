#!/usr/bin/env python

import os

from ab_plugin_manager.core_plugins import PluginDiscoveryPlugin
from ab_plugin_manager.file_patterns import register_variable
from ab_plugin_manager.launcher import launch_application

# Регистрируем переменную корня пакета.
# Она будет в дальнейшем использоваться для построения путей, в т.ч. тех, по которым будут искаться плагины.
register_variable(
    "package_root",
    os.path.dirname(__file__),
)


if __name__ == '__main__':
    # launch_application получает на вход набор предварительно загруженных плагинов ядра (как минимум - плагин для загрузки других плагинов)
    # и блокирует поток выполнения до завершения работы приложения.
    launch_application([
        # Плагин для динамической загрузки других плагинов
        PluginDiscoveryPlugin(config={
            **PluginDiscoveryPlugin.config,
            "pluginPaths": [
                # Ищем плагины внутри пакета приложения
                "{package_root}/**/plugin_*.py",
                # и среди других питоновских пакетов
                # "{python_path}/myapp_plugin_*/**/plugin_*.py",
            ],
        }),
    ])
