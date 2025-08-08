import asyncio
from logging import getLogger
from typing import Optional, Callable, Iterable

import uvicorn  # type: ignore
from fastapi import FastAPI, APIRouter  # type: ignore

from ab_plugin_manager.abc import OperationStep
from ab_plugin_manager.magic_operation import CallAllOperation, MagicOperation
from ab_plugin_manager.magic_plugin import MagicPlugin, step_name

__all__ = [
    "WebServerPlugin",
    "register_fastapi_endpoints_op",
    "register_fastapi_routes_op",
    "fastapi_tags_op",
]

register_fastapi_routes_op = CallAllOperation[FastAPI]("register_fastapi_routes")
register_fastapi_endpoints_op = MagicOperation[Callable[[APIRouter], None]]("register_fastapi_endpoints")
fastapi_tags_op = MagicOperation("fastapi_tags")


class WebServerPlugin(MagicPlugin):
    name = 'web_server'
    version = '0.0.1'

    config = {
        'host': '0.0.0.0',
        'port': 8086,
    }

    config_comment = """
    Настройки веб-сервера uvicorn.

    Полный список опций доступен здесь: https://www.uvicorn.org/settings/

    Этот конфиг передаётся в метод uvicorn.run, соответственно следует использовать имена параметров, написанные через
    нижнее подчёркивание (ssl_certfile, ssl_keyfile и т.д. и т.п.).
    """

    _logger = getLogger(name)

    def __init__(self, app_name: str = "Web-приложение") -> None:
        super().__init__()

        self._app_name = app_name
        self._server: Optional[uvicorn.Server] = None
        self._task: Optional[asyncio.Task] = None

    def _create_app(self):
        app = FastAPI(
            title=self._app_name,
            version=self.version,
        )

        register_fastapi_routes_op(app)

        return app

    def _get_fastapi_tags_for_tags_step(self, tags_step: OperationStep) -> Iterable[str]:
        if isinstance(tags_step.step, str):
            return (tags_step.step, )
        if isinstance(tags_step.step, Iterable):
            return tags_step.step

        self._logger.warning("Шаг %s не является тэгом или списком тэгов", tags_step)

        return ()

    def _get_fastapi_tags_for_routes_op(self, routes_step: OperationStep) -> list[str]:
        result = []

        for tags_step in routes_step.plugin.get_operation_steps(fastapi_tags_op.operation):
            for tag in self._get_fastapi_tags_for_tags_step(tags_step):
                if not isinstance(tag, str):
                    self._logger.warning("Тэг, возвращённый из %s не является строкой: %s", tags_step, tag)
                    continue
                result.append(tag)

        return result

    @step_name('register_plugin_api_endpoints')
    @register_fastapi_routes_op.implementation
    def register_fastapi_routes(self, app: FastAPI, *_args, **_kwargs):
        api_root_router = APIRouter()

        for step in register_fastapi_endpoints_op.get_steps():
            tags = self._get_fastapi_tags_for_routes_op(step)
            router = APIRouter(tags=tags)

            step.step(router)

            api_root_router.include_router(
                router, prefix=f'/{step.plugin.name}')

        app.include_router(api_root_router, prefix='/api')

    async def _shielded_run(self):
        await self._server.serve()
        self._logger.debug("Сервер завершил работу.")

    async def run(self, *_args, **_kwargs):
        if 'reload' in self.config or 'workers' in self.config:
            self._logger.warning(
                f"Конфигурация содержит параметры reload и/или workers. Они будут проигнорированы."
            )

        uvicorn_config = uvicorn.Config(
            self._create_app(),
            **self.config
        )

        uvicorn_config.workers = 1
        uvicorn_config.reload = False

        self._server = uvicorn.Server(uvicorn_config)

        # Uvicorn завершается очень некорректно если отменить его корневой task.
        # Поэтому, используем shield() чтобы защитить это нежное животное.
        self._task = asyncio.create_task(self._shielded_run())
        await asyncio.shield(self._task)

    async def terminate(self, *_args, **_kwargs):
        if self._server is not None:
            self._server.should_exit = True
            if self._task:
                self._logger.debug("Ожидаю завершения работы сервера.")
                await self._task
