#!/usr/bin/env python

"""
Пример сервера/бэкэнда веб-приложения на основе менеджера плагинов.

Пример включает сам сервер веб-приложения и пример пакетной задачи, которая может запускаться, например через cron.
Обработчики запросов веб-сервера добавляются за счёт добавления плагинов (см. `plugin_api_endpoint.py`).
Аналогично добавляются и новые пакетные задачи - см. `plugin_job_calculate_revenue.py`.

Запуск веб сервера:

```shell
./main.py
```

Запуск примера пакетной задачи:

```shell
./main.py --job calculate-daily-revenue
```
"""

import os

from ab_plugin_manager.core_plugins import PluginDiscoveryPlugin, ConfigPluginWithAPI, LoggingPlugin
from ab_plugin_manager.extensions.jobs import JobsPlugin
from ab_plugin_manager.extensions.web_server import WebServerPlugin
from ab_plugin_manager.file_patterns import register_variable
from ab_plugin_manager.launcher import launch_application

register_variable(
    "package_root",
    os.path.dirname(__file__),
)

if __name__ == '__main__':
    launch_application([
        PluginDiscoveryPlugin(config={
            **PluginDiscoveryPlugin.config,
            "pluginPaths": [
                "{package_root}/**/plugin_*.py",
            ],
        }),
        # Плагин, управляющий настройками плагинов
        ConfigPluginWithAPI(
            watch_run_mode='default_job',
        ),
        # Плагин, настраивающий логгеры
        LoggingPlugin(),
        # Плагин, позволяющий запускать различные задачи через одну точку входа
        JobsPlugin(),
        # Плагин веб-сервера.
        # Настраивает FastAPI-приложение (разные плагины могут регистрировать свои endpoint'ы),
        # запускает приложение через uvicorn.
        WebServerPlugin(
            app_name="Пример web-сервера",
            # Сервер запускается как задача через JobsPlugin
            run_mode='default_job',
        ),
    ])
