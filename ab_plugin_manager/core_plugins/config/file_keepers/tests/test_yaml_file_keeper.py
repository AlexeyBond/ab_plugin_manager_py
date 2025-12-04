import unittest

from ab_plugin_manager.core_plugins.config.file_keepers.tests.test_file_keeper_base import BaseFileKeeperTest
from ab_plugin_manager.core_plugins.config.file_keepers.yaml_file_keeper import YamlFileKeeper, \
    YamlConfigFileKeeperFactory


class YamlFileKeeperTest(BaseFileKeeperTest.BaseFileKeeperTest):
    keeper_type = YamlFileKeeper
    factory = YamlConfigFileKeeperFactory()
    file_suffix = ".yaml"


if __name__ == '__main__':
    unittest.main()
