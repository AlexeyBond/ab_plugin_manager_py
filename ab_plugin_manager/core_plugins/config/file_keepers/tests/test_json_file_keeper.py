import unittest

from ab_plugin_manager.core_plugins.config.file_keepers.json_file_keeper import JsonFileKeeper, JsonFileKeeperFactory
from ab_plugin_manager.core_plugins.config.file_keepers.tests.test_file_keeper_base import BaseFileKeeperTest


class JsonFileKeeperTest(BaseFileKeeperTest.BaseFileKeeperTest):
    keeper_type = JsonFileKeeper
    factory = JsonFileKeeperFactory()
    file_suffix = ".json"


if __name__ == '__main__':
    unittest.main()
