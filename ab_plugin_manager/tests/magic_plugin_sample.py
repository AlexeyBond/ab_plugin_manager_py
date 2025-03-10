from ab_plugin_manager.magic_plugin import after

name = 'magic plugin module sample'
version = '6.6.6'


@after('config')
def init():
    ...


def terminate():
    ...


foo: dict = {}
