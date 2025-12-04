import unittest
from abc import ABC
from pathlib import Path
from tempfile import TemporaryDirectory

from ab_plugin_manager.core_plugins.config.abc import ConfigFileKeeper, ConfigFileKeeperFactory


class BaseFileKeeperTest:
    class BaseFileKeeperTest(unittest.TestCase, ABC):
        file_suffix: str
        keeper_type: type[ConfigFileKeeper]
        factory: ConfigFileKeeperFactory

        def test_write_read(self):
            with TemporaryDirectory() as td:
                keeper = self.factory.make_default_file(Path(td), 'test', {})

                self.assertIsInstance(keeper, self.keeper_type)

                keeper.store_config({"foo": "bar", "array": [1, "2"]})

                read_config, _v = keeper.load_config()
                self.assertEqual(
                    read_config,
                    {"foo": "bar", "array": [1, "2"]},
                )

        def test_write_read_write_read(self):
            with TemporaryDirectory() as td:
                keeper = self.factory.make_default_file(Path(td), 'test', {})
                keeper.store_config({"foo": "bar", "array": [1, "2"]})

                read_config, _v = keeper.load_config()
                self.assertEqual(
                    read_config,
                    {"foo": "bar", "array": [1, "2"]},
                )

                keeper.store_config({"foo": "baz", "list": ["1", 3]})

                read_config, _v = keeper.load_config()
                self.assertEqual(
                    read_config,
                    {"foo": "baz", "list": ["1", 3]},
                )
