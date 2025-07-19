import asyncio
import unittest
from logging import Logger
from unittest.async_case import IsolatedAsyncioTestCase
from unittest.mock import Mock

from ab_plugin_manager.abc import OperationStep, DependencyCycleException, PluginManager, \
    CurrentPluginManagerNotSetException
from ab_plugin_manager.magic_plugin import MagicPlugin, after, step_name, before
from ab_plugin_manager.plugin_manager import PluginManagerImpl


class _TestPlugin1(MagicPlugin):
    def init(self):
        ...


class _TestPlugin2(MagicPlugin):
    @after('_TestPlugin1.init')
    def init(self):
        ...


class _TestPlugin3(MagicPlugin):
    @before('_TestPlugin1.init')
    def init(self):
        ...


class _ChickenPlugin(MagicPlugin):
    @after('egg')
    @step_name('chicken')
    def create(self):
        ...


class _EggPlugin(MagicPlugin):
    @after('chicken')
    @step_name('egg')
    def create(self):
        ...


class PluginManagerTest(unittest.TestCase):
    def test_get_single_step(self):
        logger = Mock(spec=Logger)
        plugins = [_TestPlugin1()]
        pm = PluginManagerImpl(plugins, logger=logger)

        self.assertEqual(
            list(pm.get_operation_sequence('init')),
            [OperationStep(plugins[0].init, '_TestPlugin1.init',
                           plugins[0], (), ())]
        )

        logger.warning.assert_not_called()

    def test_ignore_duplicates(self):
        logger = Mock(spec=Logger)
        plugins = [_TestPlugin1(), _TestPlugin1()]
        pm = PluginManagerImpl(plugins, logger=logger)

        self.assertEqual(
            list(pm.get_operation_sequence('init')),
            [OperationStep(plugins[0].init, '_TestPlugin1.init',
                           plugins[0], (), ())]
        )

        logger.warning.assert_called_once()

    def test_detect_loop(self):
        pm = PluginManagerImpl([_ChickenPlugin(), _EggPlugin()])

        with self.assertRaises(DependencyCycleException) as e:
            pm.get_operation_sequence('create')

        self.assertRegex(str(e.exception), r'_ChickenPlugin')
        self.assertRegex(str(e.exception), r'_EggPlugin')
        self.assertRegex(str(e.exception), r'chicken')
        self.assertRegex(str(e.exception), r'egg')

    def test_steps_order(self):
        plugins = [_TestPlugin1(), _TestPlugin2(), _TestPlugin3()]
        pm = PluginManagerImpl(plugins)

        self.assertEqual(
            list(pm.get_operation_sequence('init')),
            [
                OperationStep(plugins[2].init, '_TestPlugin3.init',
                              plugins[2], (), ('_TestPlugin1.init',)),
                OperationStep(plugins[0].init,
                              '_TestPlugin1.init', plugins[0], (), ()),
                OperationStep(plugins[1].init, '_TestPlugin2.init',
                              plugins[1], ('_TestPlugin1.init',), ()),
            ]
        )

    def test_current(self):
        pm, pm2 = PluginManagerImpl([]), PluginManagerImpl([])
        self.assertIs(PluginManager.current_maybe(), None)
        with self.assertRaises(CurrentPluginManagerNotSetException):
            PluginManager.current()
        with pm.as_current():
            self.assertIs(PluginManager.current_maybe(), pm)
            self.assertIs(PluginManager.current(), pm)

            with pm2.as_current():
                self.assertIs(PluginManager.current_maybe(), pm2)
                self.assertIs(PluginManager.current(), pm2)

            self.assertIs(PluginManager.current_maybe(), pm)
            self.assertIs(PluginManager.current(), pm)
        self.assertIs(PluginManager.current_maybe(), None)
        with self.assertRaises(CurrentPluginManagerNotSetException):
            PluginManager.current()

    def test_op_cache(self):
        pm = PluginManagerImpl([])

        def compute(foo):
            return {foo: "bar"}

        val1 = pm.operation_cache("test", 1, compute, foo="f00")

        self.assertIs(pm.operation_cache("test", 1, compute), val1)

        # Different key
        self.assertIsNot(pm.operation_cache("test", 2, compute, "f00"), val1)
        # Different op
        self.assertIsNot(pm.operation_cache("test1", 1, compute, foo="f00"), val1)

    def test_op_cache_drop(self):
        pm = PluginManagerImpl([])

        def compute(foo):
            return {foo: "bar"}

        val1 = pm.operation_cache("test", 1, compute, "f00")

        pm.drop_operation_cache()

        self.assertIsNot(pm.operation_cache("test", 1, compute, "f00"), val1)


class PluginManagerTestAsync(IsolatedAsyncioTestCase):
    async def test_current_async(self):
        b = asyncio.Barrier(2)
        pm, pm1, pm2 = PluginManagerImpl([]), PluginManagerImpl([]), PluginManagerImpl([])

        async def task1():
            self.assertIs(PluginManager.current(), pm)
            with pm1.as_current():
                self.assertIs(PluginManager.current(), pm1)
                await b.wait()
                self.assertIs(PluginManager.current(), pm1)
                await b.wait()
                self.assertIs(PluginManager.current(), pm1)
            self.assertIs(PluginManager.current(), pm)

        async def task2():
            self.assertIs(PluginManager.current(), pm)
            with pm2.as_current():
                self.assertIs(PluginManager.current(), pm2)
                await b.wait()
                self.assertIs(PluginManager.current(), pm2)
                await b.wait()
                self.assertIs(PluginManager.current(), pm2)
            self.assertIs(PluginManager.current(), pm)

        with pm.as_current():
            await asyncio.gather(task1(), task2())

    async def test_current_async_to_sync(self):
        pm, pm1, pm2 = PluginManagerImpl([]), PluginManagerImpl([]), PluginManagerImpl([])

        def sync_task():
            self.assertIs(PluginManager.current(), pm1)
            with pm2.as_current():
                self.assertIs(PluginManager.current(), pm2)
            self.assertIs(PluginManager.current(), pm1)

        async def async_task():
            self.assertIs(PluginManager.current(), pm)
            with pm1.as_current():
                self.assertIs(PluginManager.current(), pm1)
                await asyncio.to_thread(sync_task)
                self.assertIs(PluginManager.current(), pm1)
            self.assertIs(PluginManager.current(), pm)

        with pm.as_current():
            await async_task()
            self.assertIs(PluginManager.current(), pm)


if __name__ == '__main__':
    unittest.main()
