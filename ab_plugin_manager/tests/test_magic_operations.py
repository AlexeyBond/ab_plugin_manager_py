import unittest

from ab_plugin_manager.magic_operation import AsyncWrapperCallOperation
from ab_plugin_manager.magic_plugin import step_name, after
from build.lib.ab_plugin_manager.magic_plugin import MagicPlugin
from build.lib.ab_plugin_manager.plugin_manager import PluginManagerImpl


class MagicOperationsTest(unittest.IsolatedAsyncioTestCase):
    async def test_async_wrapper_call(self):
        op = AsyncWrapperCallOperation("op")

        class Plugin1(MagicPlugin):
            @op.implementation
            @step_name("foo-1")
            async def foo(self, nxt, prev, *args, **kwargs):
                prev = f"{prev}+foo1"
                prev = await nxt(prev, *args, **kwargs)
                prev = f"{prev}+foo1p"
                return prev

        class Plugin2(MagicPlugin):
            @after("foo-1")
            @op.implementation
            async def foo(self, nxt, prev, *args, **kwargs):
                prev = f"{prev}+foo2"
                prev = await nxt(prev, *args, **kwargs)
                prev = f"{prev}+foo2p"
                return prev

        pm = PluginManagerImpl([Plugin2(), Plugin1()])

        with pm.as_current():
            res = await op()

        self.assertEqual(res, "None+foo1+foo2+foo2p+foo1p")

    async def test_async_wrapper_call_factory(self):
        op = AsyncWrapperCallOperation[str]("op")

        class Plugin1(MagicPlugin):
            @op.factory_implementation
            @step_name("fac1")
            async def fac1(self, *args, **_kwargs):
                if args[0] != "type1":
                    return None
                return "f1"

        class Plugin2(MagicPlugin):
            @after("fac1")
            @op.factory_implementation
            async def fac2(self, *args, **_kwargs):
                if args[0] != "type2":
                    return None
                raise AssertionError("fac2 called")

        class Plugin3(MagicPlugin):
            @op.implementation
            async def decorate3(self, nxt, prev, *args, **kwargs):
                return f"{await nxt(prev, *args, **kwargs)}+decorator"

        pm = PluginManagerImpl([Plugin1(), Plugin2(), Plugin3()])

        with pm.as_current():
            self.assertEqual(await op("type1"), "f1+decorator")
            with self.assertRaises(AssertionError):
                await op("type2")
            self.assertEqual(await op("X3"), "None+decorator")


if __name__ == "__main__":
    unittest.main()
