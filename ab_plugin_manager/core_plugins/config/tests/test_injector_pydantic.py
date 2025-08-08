import unittest
from typing import Optional

from pydantic import BaseModel, ValidationError, ConfigDict

from ab_plugin_manager.core_plugins.config.abc import UnsupportedConfigTypeException
from ab_plugin_manager.core_plugins.config.injector_pydantic import PydanticConfigInjector
from ab_plugin_manager.magic_plugin import MagicPlugin


class PydanticInjectorTest(unittest.TestCase):
    def setUp(self):
        class Config1(BaseModel):
            """Config 1"""

            foo: str = "bar"
            """This is foo"""

            buz: str = "baz"

            bzz: Optional[int] = None

            model_config = ConfigDict(use_attribute_docstrings=True)
            # ^ necessary to use description from docstring (see foo)

        class TestPlugin(MagicPlugin):
            config1 = Config1()

            config2 = {}

        self._plugin = TestPlugin()

    def test_valid_config(self):
        injector = PydanticConfigInjector.try_instantiate(next(iter(self._plugin.get_operation_steps("config1"))))

        self.assertEqual(
            {"foo": "bar", "buz": "baz", "bzz": None},
            injector.get_current_content(),
        )

        hash1 = injector.get_current_hash()

        self.assertEqual(
            hash1,
            injector.get_current_hash(),
        )

        injector.inject_config({"foo": "hello", "bzz": 1})
        injector.inject_config({})

        self.assertEqual(
            {"foo": "hello", "bzz": 1, "buz": "baz"},
            injector.get_current_content(),
        )

        hash2 = injector.get_current_hash()

        self.assertNotEqual(hash1, hash2)

    def test_invalid_injection(self):
        injector = PydanticConfigInjector.try_instantiate(next(iter(self._plugin.get_operation_steps("config1"))))

        with self.assertRaises(ValidationError):
            injector.inject_config({"foo": {"bar": "yes"}})

    def test_unsupported_config_type(self):
        with self.assertRaises(UnsupportedConfigTypeException):
            PydanticConfigInjector.try_instantiate(next(iter(self._plugin.get_operation_steps("config2"))))

    def test_schema(self):
        injector = PydanticConfigInjector.try_instantiate(next(iter(self._plugin.get_operation_steps("config1"))))

        self.assertEqual(
            injector.get_schema(),
            {
                'description': 'Config 1',
                'properties': {
                    'buz': {
                        'default': 'baz',
                        'title': 'Buz',
                        'type': 'string',
                    },
                    'bzz': {
                        'anyOf': [
                            {'type': 'integer'},
                            {'type': 'null'},
                        ],
                        'default': None,
                        'title': 'Bzz',
                    },
                    'foo': {
                        'default': 'bar',
                        'type': 'string',
                        'title': 'Foo',
                        'description': "This is foo",
                    },
                },
                'title': 'Config1',
                'type': 'object',
            },
        )


if __name__ == '__main__':
    unittest.main()
