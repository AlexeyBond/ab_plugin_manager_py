from ab_plugin_manager.magic_operation import MagicOperation, CallAllOperation, CallAllAsyncConcurrentOperation, \
    WrapperCallOperation, AsyncWrapperCallOperation, MagicOperationResultCheck, MagicOperationResultCheckError, \
    MagicOperationWithResultProcessing
from ab_plugin_manager.magic_operations.middleware import MiddlewareOperation

__all__ = [
    'MagicOperation',
    'CallAllOperation',
    'CallAllAsyncConcurrentOperation',
    'WrapperCallOperation',
    'AsyncWrapperCallOperation',
    'MagicOperationResultCheck',
    'MagicOperationWithResultProcessing',
    'MagicOperationResultCheckError',
    'MiddlewareOperation',
]
