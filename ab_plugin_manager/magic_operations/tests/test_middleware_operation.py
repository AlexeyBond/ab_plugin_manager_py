import unittest
from unittest.async_case import IsolatedAsyncioTestCase

from ab_plugin_manager.magic_operations import MiddlewareOperation
from ab_plugin_manager.magic_operations.middleware import UnexpectedMiddlewareValue
from ab_plugin_manager.magic_plugin import MagicPlugin, step_name, after, before
from ab_plugin_manager.plugin_manager import PluginManagerImpl

op = MiddlewareOperation('op', dict, str)


class P1(MagicPlugin):
    @op.implementation
    @step_name('1')
    def i1(self, dec: dict, **_kwargs):
        upd_text = '(p11)' + dec['text'] + '(s11)'
        created = yield {**dec, 'text': upd_text}
        return '(p12)' + created + '(s12)'

    @op.implementation
    @step_name('1.5')
    @after('1')
    @before('2')
    def i1_5(self, dec: dict, **_kwargs):
        try:
            return (yield dec)
        except ValueError as e:
            if e.args[0] == 'еггор':
                return 'the error'
            raise

    @op.implementation
    @step_name('2')
    @after('1')
    def i2(self, dec: dict, **_kwargs):
        if dec['text'] == '(p11)skip(s11)':
            return 'skip'
        upd_text = '(p21)' + dec['text'] + '(s21)'
        created = yield {**dec, 'text': upd_text}
        return '(p22)' + created + '(s22)'


class P2(MagicPlugin):
    @op.implementation
    @step_name('1')
    async def i1(self, dec: dict, **_kwargs):
        upd_text = '(p11)' + dec['text'] + '(s11)'
        created = yield {**dec, 'text': upd_text}
        yield '(p12)' + created + '(s12)'

    @op.implementation
    @step_name('1.5')
    @after('1')
    @before('2')
    async def i1_5(self, dec: dict, **_kwargs):
        try:
            yield (yield dec)
        except ValueError as e:
            if e.args[0] == 'еггор':
                yield 'the error'
            else:
                raise

    @op.implementation
    @step_name('2')
    @after('1')
    async def i2(self, dec: dict, **_kwargs):
        if dec['text'] == '(p11)skip(s11)':
            yield 'skip'
        else:
            upd_text = '(p21)' + dec['text'] + '(s21)'
            created = yield {**dec, 'text': upd_text}
            yield '(p22)' + created + '(s22)'


class MiddlewareOperationTest(IsolatedAsyncioTestCase):
    def test_sync_decorators(self):
        with PluginManagerImpl([P1()]).as_current():
            self.assertEqual(
                op.invoke(
                    lambda dec, **_kw: f"[{dec['text']}]",
                    {'text': 'hellorld'},
                ),
                '(p12)(p22)[(p21)(p11)hellorld(s11)(s21)](s22)(s12)',
            )

    def test_sync_decorator_early_return(self):
        with PluginManagerImpl([P1()]).as_current():
            self.assertEqual(
                op.invoke(
                    lambda dec: ...,
                    {'text': 'skip'},
                ),
                '(p12)skip(s12)',
            )

    def test_sync_decorator_error_intercept(self):
        with PluginManagerImpl([P1()]).as_current():
            def err(*_args):
                raise ValueError('еггор')

            self.assertEqual(
                op.invoke(
                    err,
                    {'text': 'foo'},
                ),
                '(p12)the error(s12)',
            )

    async def test_ainvoke_sync_decorators(self):
        with PluginManagerImpl([P1()]).as_current():
            async def f(dec: dict, **_kwargs):
                return f"[{dec['text']}]"

            self.assertEqual(
                await op.ainvoke(
                    f,
                    {'text': 'hellorld'},
                ),
                '(p12)(p22)[(p21)(p11)hellorld(s11)(s21)](s22)(s12)',
            )

    async def test_ainvoke_sync_generator_early_return(self):
        with PluginManagerImpl([P1()]).as_current():
            self.assertEqual(
                await op.ainvoke(
                    lambda dec: ...,
                    {'text': 'skip'},
                ),
                '(p12)skip(s12)',
            )

    async def test_ainvoke_sync_generator_error_intercept(self):
        with PluginManagerImpl([P1()]).as_current():
            async def err(*_args):
                raise ValueError('еггор')

            self.assertEqual(
                await op.ainvoke(
                    err,
                    {'text': 'foo'},
                ),
                '(p12)the error(s12)',
            )

    async def test_async_decorators_sync_invocation_error(self):
        with PluginManagerImpl([P2()]).as_current():
            with self.assertRaisesRegex(
                    RuntimeError,
                    "Operation can not run synchronously as it has asynchronous",
            ):
                op.invoke(
                    lambda _: ...,
                    {'text': 'hellorld'},
                ),

    async def test_async_decorators(self):
        with PluginManagerImpl([P2()]).as_current():
            async def f(dec: dict, *_a, **_kwargs):
                return f"[{dec['text']}]"

            self.assertEqual(
                await op.ainvoke(
                    f,
                    {'text': 'hellorld'},
                ),
                '(p12)(p22)[(p21)(p11)hellorld(s11)(s21)](s22)(s12)',
            )

    async def test_async_decorator_early_return(self):
        with PluginManagerImpl([P2()]).as_current():
            self.assertEqual(
                await op.ainvoke(
                    lambda dec: ...,
                    {'text': 'skip'},
                ),
                '(p12)skip(s12)',
            )

    async def test_async_decorator_error_intercept(self):
        with PluginManagerImpl([P2()]).as_current():
            async def err(*_args):
                raise ValueError('еггор')

            self.assertEqual(
                await op.ainvoke(
                    err,
                    {'text': 'foo'},
                ),
                '(p12)the error(s12)',
            )

    def test_unexpected_sync_yield_value(self):
        class P(MagicPlugin):
            @op.implementation
            def i1(self, _dec: dict, **_kwargs):
                yield 'foo'

        with PluginManagerImpl([P()]).as_current():
            with self.assertRaises(UnexpectedMiddlewareValue) as e:
                op.invoke(lambda _: ..., {})

            self.assertEqual(e.exception.value, 'foo')
            self.assertEqual(e.exception.kind, 'yield')

    def test_unexpected_sync_return_value_backward(self):
        class P(MagicPlugin):
            @op.implementation
            def i1(self, dec: dict, **_kwargs):
                yield dec
                return 42

        with PluginManagerImpl([P()]).as_current():
            with self.assertRaises(UnexpectedMiddlewareValue) as e:
                op.invoke(lambda _: 'foo', {})

            self.assertEqual(e.exception.value, 42)
            self.assertEqual(e.exception.kind, 'return')

    def test_unexpected_sync_return_value_forward(self):
        class P(MagicPlugin):
            @op.implementation
            def i1(self, _dec: dict, **_kwargs):
                if False: yield
                return 42

        with PluginManagerImpl([P()]).as_current():
            with self.assertRaises(UnexpectedMiddlewareValue) as e:
                op.invoke(lambda _, **_kw: 'foo', {})

            self.assertEqual(e.exception.value, 42)
            self.assertEqual(e.exception.kind, 'return')

    async def test_unexpected_async_value_forward(self):
        class P(MagicPlugin):
            @op.implementation
            async def i1(self, _dec: dict, **_kwargs):
                yield 42

        with PluginManagerImpl([P()]).as_current():
            with self.assertRaises(UnexpectedMiddlewareValue) as e:
                await op.ainvoke(lambda _: ..., {})

            self.assertEqual(e.exception.value, 42)
            self.assertEqual(e.exception.kind, 'yield')

if __name__ == '__main__':
    unittest.main()
