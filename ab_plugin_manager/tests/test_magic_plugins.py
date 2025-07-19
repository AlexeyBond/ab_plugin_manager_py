import unittest
from typing import Any

from ab_plugin_manager.abc import OperationStep
from ab_plugin_manager.magic_plugin import MagicPlugin, after, before, operation, step_name, MagicModulePlugin


class MagicPluginTest(unittest.TestCase):
    def test_add_operation_step(self):
        class TestPlugin(MagicPlugin):
            def init(self):
                ...

        plugin = TestPlugin()

        self.assertEqual(
            list(plugin.get_operation_steps('init')),
            [OperationStep(plugin.init, 'TestPlugin.init', plugin, (), ())]
        )

    def test_use_name_override(self):
        class TestPlugin(MagicPlugin):
            name = 'test_plugin'

            def init(self):
                ...

        plugin = TestPlugin()

        self.assertEqual(
            list(plugin.get_operation_steps('init')),
            [OperationStep(plugin.init, 'test_plugin.init', plugin, (), ())]
        )

    def test_step_dependency_decorators(self):
        class TestPlugin(MagicPlugin):
            @after('foo', 'bar')
            @before('buz')
            def init(self):
                ...

        plugin = TestPlugin()

        self.assertEqual(
            list(plugin.get_operation_steps('init')),
            [OperationStep(plugin.init, 'TestPlugin.init',
                           plugin, ('foo', 'bar'), ('buz',))]
        )

    def test_multiple_steps(self):
        class TestPlugin(MagicPlugin):
            @operation('init')
            @after('TestPlugin.init')
            def init2(self):
                ...

            def init(self):
                ...

        plugin = TestPlugin()

        self.assertEqual(
            list(plugin.get_operation_steps('init')),
            [
                OperationStep(plugin.init2, 'TestPlugin.init2',
                              plugin, ('TestPlugin.init',), ()),
                OperationStep(plugin.init, 'TestPlugin.init', plugin, (), ()),
            ]
        )

    def test_step_name_override(self):
        class TestPlugin(MagicPlugin):
            @step_name('init test plugin')
            def init(self):
                ...

        plugin = TestPlugin()

        self.assertEqual(
            list(plugin.get_operation_steps('init')),
            [OperationStep(plugin.init, 'init test plugin', plugin, (), ())]
        )

    def test_decorators_result(self):
        class TestPlugin(MagicPlugin):
            @step_name('renamed step')
            def renamed_step(self) -> str:
                return 'foo'

            @operation('op name override')
            def op_name_override(self) -> str:
                return 'bar'

            @after('dep')
            def step_with_dependencies(self) -> str:
                return 'baz'

            @before('r_dep')
            def step_with_reverse_dependencies(self) -> str:
                return 'buz'

        self.assertEqual(TestPlugin().renamed_step(), 'foo')
        self.assertEqual(TestPlugin().op_name_override(), 'bar')
        self.assertEqual(TestPlugin().step_with_dependencies(), 'baz')
        self.assertEqual(TestPlugin().step_with_reverse_dependencies(), 'buz')

    def test_multiple_ops(self):
        class TestPlugin(MagicPlugin):
            def init(self):
                ...

            def terminate(self):
                ...

        plugin = TestPlugin()

        self.assertEqual(
            list(plugin.get_operation_steps('init')),
            [OperationStep(plugin.init, 'TestPlugin.init', plugin, (), ())],
        )
        self.assertEqual(
            list(plugin.get_operation_steps('terminate')),
            [OperationStep(plugin.terminate,
                           'TestPlugin.terminate', plugin, (), ())],
        )

    def test_ignore_private_and_magic_members(self):
        class TestPlugin(MagicPlugin):
            def _init(self):
                ...

            def __str__(self):
                ...

        plugin = TestPlugin()
        self.assertEqual(
            list(plugin.get_operation_steps('_init')),
            []
        )
        self.assertEqual(
            list(plugin.get_operation_steps('__str__')),
            []
        )

    def test_ignore_plugin_abc_members(self):
        class TestPlugin(MagicPlugin):
            ...

        plugin = TestPlugin()

        self.assertEqual(
            list(plugin.get_operation_steps('get_operation_steps')),
            []
        )
        self.assertEqual(
            list(plugin.get_operation_steps('name')),
            []
        )
        self.assertEqual(
            list(plugin.get_operation_steps('version')),
            []
        )

    def test_module_plugin(self):
        import ab_plugin_manager.tests.magic_plugin_sample as module

        plugin = MagicModulePlugin(module)

        self.assertEqual(plugin.name, 'magic plugin module sample')
        self.assertEqual(plugin.version, '6.6.7')

        self.assertEqual(
            list(plugin.get_operation_steps('init')),
            [OperationStep(
                module.init, 'magic plugin module sample.init', plugin, ('config',), ())]
        )
        self.assertEqual(
            list(plugin.get_operation_steps('terminate')),
            [OperationStep(
                module.terminate, 'magic plugin module sample.terminate', plugin, (), ())]
        )

    def test_module_plugin_attribute_forwarding(self) -> None:
        import ab_plugin_manager.tests.magic_plugin_sample as module

        plugin = MagicModulePlugin(module)

        self.assertTrue(hasattr(plugin, 'foo'))

        self.assertIs(module.foo, plugin.foo)

        upd: dict = {}
        plugin.foo = upd
        self.assertIs(module.foo, upd)
        self.assertIs(plugin.foo, upd)

    def test_step_annotations(self) -> None:
        class TestPlugin(MagicPlugin):
            config: dict[str, Any] = {}
            foo: str = "bar"

        plugin = TestPlugin()

        self.assertEqual(
            list(plugin.get_operation_steps("config")),
            [OperationStep(TestPlugin.config, 'TestPlugin.config', plugin, (), (), dict[str, Any])],
        )
        self.assertEqual(
            list(plugin.get_operation_steps("foo")),
            [OperationStep(TestPlugin.foo, 'TestPlugin.foo', plugin, (), (), str)],
        )

    def test_step_annotations_module(self) -> None:
        import ab_plugin_manager.tests.magic_plugin_sample as module

        plugin = MagicModulePlugin(module)

        self.assertEqual(
            list(plugin.get_operation_steps("foo")),
            [OperationStep(module.foo, "magic plugin module sample.foo", plugin, (), (), dict)],
        )

    def test_module_all(self) -> None:
        import ab_plugin_manager.tests.magic_plugin_sample as module

        plugin = MagicModulePlugin(module)

        # The function is there, but not included in __all__
        self.assertEqual([], list(plugin.get_operation_steps("bar")))

    def test_list_operations(self) -> None:
        class TestPlugin(MagicPlugin):
            name = 'test'
            version = '4.2.0'

            def __init__(self):
                self._private1 = 1
                super().__init__()

            _private2 = 2

            def init(self):
                ...

        self.assertSetEqual(
            set(TestPlugin().list_implemented_operations()),
            {"init"},
        )

        import ab_plugin_manager.tests.magic_plugin_sample as module

        self.assertSetEqual(
            set(MagicModulePlugin(module).list_implemented_operations()),
            {"init", "terminate", "foo"},
        )


if __name__ == '__main__':
    unittest.main()
