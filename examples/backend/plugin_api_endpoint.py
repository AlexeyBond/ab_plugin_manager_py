from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ab_plugin_manager.extensions.web_server import register_fastapi_endpoints_op

name = 'time_api'
version = '0.1.0'

fastapi_tags = 'Time API'


@register_fastapi_endpoints_op.implementation
def register_api_endpoints(router: APIRouter):
    # Добавляет эндпоинты в API FastAPI-приложения.
    # Префикс роутера всегда будет /api/имя_плагина
    # Добавлять обработчики других путей и осуществлять прочие настройки FastAPI-приложения можно
    # реализовав операцию register_fastapi_routes_op

    class TimeResponse(BaseModel):
        time: datetime = Field(default_factory=datetime.now)

    @router.get('/now')
    def get_current_time() -> TimeResponse:
        return TimeResponse()
