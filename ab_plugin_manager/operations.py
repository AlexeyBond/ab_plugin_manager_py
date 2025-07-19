"""
Операции, запускаемые лаунчером и плагинами ядра, включёнными в этот пакет.
"""
from argparse import ArgumentParser, Namespace
from typing import Tuple

from ab_plugin_manager.magic_operation import CallAllOperation, CallAllAsyncConcurrentOperation

bootstrap = CallAllOperation[*Tuple[()]]("bootstrap", cache_steps=False)
"""
Операция, которая выполняется при запуске приложения.
Доступна только в плагинах ядра.
"""

setup_cli_arguments = CallAllOperation[ArgumentParser]("setup_cli_arguments", cache_steps=False)
"""
Операция, настройки парсера аргументов командной строки.
Выполняется при запуске приложения. Для плагинов ядра выполняется два раза - до и после загрузки плагинов приложения.
"""

receive_cli_arguments = CallAllOperation[Namespace]("receive_cli_arguments", cache_steps=False)
"""
Операция, выполняющаяся после парсинга аргументов командной строки.
Выполняется при запуске приложения. Для плагинов ядра выполняется два раза - до и после загрузки плагинов приложения.
"""

init = CallAllAsyncConcurrentOperation[None]("init", cache_steps=False)
"""
Операция, выполняющаяся при запуске приложения.
Доступна во всех плагинах.
"""

run = CallAllAsyncConcurrentOperation[None]("run", cache_steps=False)
"""
Операция, выполняющая основную работу приложения.
"""

terminate = CallAllAsyncConcurrentOperation[None]("terminate", cache_steps=False)
"""
Операция, выполняемая перед остановкой приложения.
"""
