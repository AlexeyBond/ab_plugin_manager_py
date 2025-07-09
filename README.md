# ab_plugin_manager - менеджер плагинов для приложений на Python

## Пример

Точка входа приложения, использующего этот загрузчик плагинов обычно выглядит следующим образом:

```python
# main.py
import os

from ab_plugin_manager.core_plugins import PluginDiscoveryPlugin
from ab_plugin_manager.file_patterns import register_variable
from ab_plugin_manager.launcher import launch_application

# Регистрируем переменную корня пакета.
# Она будет в дальнейшем использоваться для построения путей, в т.ч. тех, по которым будут искаться плагины.
register_variable("package_root", os.path.dirname(__file__))


# Плагин, осуществляющий динамическую загрузку плагинов.
# В данном случае, просто PluginDiscoveryPlugin с изменёнными настройками.
class MyPluginDiscoveryPlugin(PluginDiscoveryPlugin):
    name = "discover_plugins"
    config = {
        **PluginDiscoveryPlugin.config,
        "pluginPaths": [
            # Ищем плагины внутри пакета приложения
            "{package_root}/**/plugin_*.py",
            # и среди других питоновских пакетов
            "{python_path}/myapp_plugin_*/**/plugin_*.py",
        ],
    }


if __name__ == '__main__':
    # launch_application получает на вход набор предварительно загруженных плагинов ядра (как минимум - плагин для загрузки других плагинов)
    # и блокирует поток выполнения до завершения работы приложения.
    launch_application([MyPluginDiscoveryPlugin()])
```

Вся логика приложения располагается в плагинах.
В случае если нужна более жёсткая структура приложения (например, ядро приложения не меняется, а плагины могут
использоваться только для некоторых точек расширения), следует использовать [
`PluginManager`](./ab_plugin_manager/abc.py) напрямую.
Хотя даже в таком случае стоит рассмотреть возможность вынести ядро приложения в отдельный плагин, передав его в списке
плагинов ядра при запуске приложения.

Рассмотрим пример "hello world", в котором логика вывода сообщения отделена от вызывающего её кода.
Для начала нужно определить операцию вывода сообщения:

```python
# operations.py

from ab_plugin_manager.magic_operation import CallAllOperation

# Операция типа CallAll вызывает все шаги синхронно и последовательно.
# Единственный параметр конструктора - имя операции - используется для идентификации шагов, принадлежащих этой операции
# и должен быть уникален для неё, чтобы избежать коллизий с другими операциями.
greet_op = CallAllOperation[str]("greet")
```

Затем можно создать плагин, вызывающий эту операцию:

```python
# plugin_greetings_runner.py

from operations import greet_op

# Имя и версия плагина.
# Без этих полей загрузчик плагинов не сможет распознать плагин и не загрузит его.
name = 'greetings_runner'
version = '0.1.0'


# run - одна из встроенных операций, поддерживаемых функцией launch_application
# она выполняется после инициализации приложения.
# Когда все реализации этой операции завершают работу (или хотя бы одна из них завершается с ошибкой или приложение
# получает сигнал прерывания), выполняется операция terminate и работа приложения завершается.
def run(*_args, **_kwargs):
    # CallAllOperation может быть вызвана как обычная функция.
    # Внутри вызова операция запросит у менеджера плагинов все свои шаги и выполнит их последовательно.
    greet_op("world")
```

И плагин, реализующий её:

```python
# plugin_greeter.py

from operations import greet_op

name = 'greeter'
version = '0.1.0'


# Декоратор <op>.implementation не обязателен если имя функции совпадает с именем операции (в т.ч. в этом примере)
@greet_op.implementation
def greet(who: str):
    print(f"Hello {who}!")
```

## История

Изначально этот пакет разрабатывался как
часть [проекта голосового ассистента](https://github.com/AlexeyBond/Irene-Voice-Assistant).
