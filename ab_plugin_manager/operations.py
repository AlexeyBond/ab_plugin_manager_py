"""
Операции, запускаемые лаунчером и плагинами ядра, включёнными в этот пакет.
"""
from argparse import ArgumentParser, Namespace

from ab_plugin_manager.magic_operation import CallAllOperation, CallAllAsyncConcurrentOperation

bootstrap = CallAllOperation[()]("bootstrap")
"""
Операция, которая выполняется при запуске приложения.
Доступна только в плагинах ядра.
"""

setup_cli_arguments = CallAllOperation[(ArgumentParser,)]("setup_cli_arguments")
"""
Операция, настройки парсера аргументов командной строки.
Выполняется при запуске приложения. Для плагинов ядра выполняется два раза - до и после загрузки плагинов приложения.
"""

receive_cli_arguments = CallAllOperation[(Namespace,)]("receive_cli_arguments")
"""
Операция, выполняющаяся после парсинга аргументов командной строки.
Выполняется при запуске приложения. Для плагинов ядра выполняется два раза - до и после загрузки плагинов приложения.
"""

init = CallAllAsyncConcurrentOperation[()]("init")
"""
Операция, выполняющаяся при запуске приложения.
Доступна во всех плагинах.
"""

run = CallAllAsyncConcurrentOperation[()]("run")
"""
Операция, выполняющая основную работу приложения.
"""

terminate = CallAllAsyncConcurrentOperation[()]("terminate")
"""
Операция, выполняемая перед остановкой приложения.
"""
