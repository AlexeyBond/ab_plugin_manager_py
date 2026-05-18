import unittest
from unittest import IsolatedAsyncioTestCase

from ab_plugin_manager.magic_operations.typed_factory import TypedFactoryOperation, UnknownTypeError, KeyRetrievalError, \
    UnsupportedAsyncFactory, UnexpectedResult
from ab_plugin_manager.magic_plugin import MagicPlugin
from ab_plugin_manager.plugin_manager import PluginManagerImpl

op = TypedFactoryOperation[dict, str, str]('op', str, str)


class P1(MagicPlugin):
    @op.type_factory({'t1.0', 't1.1'})
    def t1(self, src: dict, *_args, **_kwargs):
        assert isinstance(self, P1)
        assert isinstance(src, dict)
        return 'T1'

    @op.type_factory('t2')
    def t2(self, src: dict, *_args, **_kwargs):
        assert isinstance(self, P1)
        assert isinstance(src, dict)
        return 'T2'

    @op.type_factory('t3')
    async def t3(self, src: dict, *_args, **_kwargs):
        assert isinstance(self, P1)
        assert isinstance(src, dict)
        return 'T3'

    @op.type_factory('t4')
    def t4(self, src: dict, *_args, **_kwargs):
        assert isinstance(self, P1)
        assert isinstance(src, dict)
        return 42


class TypedFactoryTest(IsolatedAsyncioTestCase):
    def test_type_factory(self):
        p = P1()

        self.assertEqual(
            p.t1({'type': 't1.1'}),
            'T1',
        )
        self.assertEqual(
            p.t1['t1.0']({'type': 't1.0'}),
            'T1',
        )

    def test_sync_factory(self):
        with PluginManagerImpl([P1()]).as_current():
            self.assertEqual(
                op.invoke({'type': 't1.1'}),
                'T1',
            )
            self.assertEqual(
                op.invoke({'type': 't1.0'}),
                'T1',
            )
            self.assertEqual(
                op.invoke({'type': 't2'}),
                'T2',
            )
            with self.assertRaises(UnknownTypeError):
                op.invoke({'type': 't2.1'})
            with self.assertRaises(KeyRetrievalError):
                op.invoke({'typo': 't2'})
            with self.assertRaises(UnsupportedAsyncFactory):
                op.invoke({'type': 't3'})
            with self.assertRaises(UnexpectedResult):
                op.invoke({'type': 't4'})


if __name__ == '__main__':
    unittest.main()
