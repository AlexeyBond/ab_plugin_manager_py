import unittest

from ab_plugin_manager.core_plugins.config.abc import UnsupportedConfigTypeException
from ab_plugin_manager.core_plugins.config.injector_dict import DictConfigInjector
from ab_plugin_manager.magic_plugin import MagicPlugin


class DictInjectorTest(unittest.TestCase):
    def setUp(self):
        class TestPlugin(MagicPlugin):
            config1 = {"foo": "bar", "buz": "baz"}
            config2 = {"foo"}
            config_comment = """
            This is test plugin config
            """

        self._plugin = TestPlugin()

    def test_simple_config(self):
        injector = DictConfigInjector.try_instantiate(next(iter(self._plugin.get_operation_steps("config1"))))

        self.assertEqual(
            {"foo": "bar", "buz": "baz"},
            injector.get_current_content(),
        )

        hash1 = injector.get_current_hash()

        self.assertEqual(
            hash1,
            injector.get_current_hash(),
        )

        injector.inject_config({"foo": "hello", "bzz": 1})

        self.assertEqual(
            {"foo": "hello", "bzz": 1, "buz": "baz"},
            injector.get_current_content(),
        )

        hash2 = injector.get_current_hash()

        self.assertNotEqual(hash1, hash2)

    def test_bad_config(self):
        with self.assertRaises(UnsupportedConfigTypeException):
            DictConfigInjector.try_instantiate(next(iter(self._plugin.get_operation_steps("config2"))))

    def test_schema(self):
        injector = DictConfigInjector.try_instantiate(next(iter(self._plugin.get_operation_steps("config1"))))
        self.assertEqual(
            {"type": "object", "additionalProperties": True, "description": "This is test plugin config"},
            injector.get_schema(),
        )


if __name__ == '__main__':
    unittest.main()
