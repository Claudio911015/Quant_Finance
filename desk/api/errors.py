"""Marco de errores: toda respuesta de error es JSON `{"error": str, "field": str|null}`."""
from typing import Optional

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

_HTTP_MESSAGES = {
    400: "Solicitud inválida",
    404: "Recurso no encontrado",
    405: "Método no permitido",
}


class ApiError(Exception):
    """Error de la API con status HTTP, mensaje en español y parámetro culpable."""

    def __init__(self, status: int, error: str, field: Optional[str] = None):
        super().__init__(error)
        self.status = status
        self.error = error
        self.field = field


def _response(status: int, error: str, field: Optional[str] = None):
    resp = jsonify({"error": error, "field": field})
    resp.status_code = status
    return resp


def register_error_handlers(app: Flask) -> None:
    """Registra los handlers JSON en `app`."""

    @app.errorhandler(ApiError)
    def _api_error(e: ApiError):
        return _response(e.status, e.error, e.field)

    @app.errorhandler(HTTPException)
    def _http_error(e: HTTPException):
        code = e.code or 500
        return _response(code, _HTTP_MESSAGES.get(code, e.name))

    # Módulo todavía sin implementar (más específico que RuntimeError).
    @app.errorhandler(NotImplementedError)
    def _not_implemented(e: NotImplementedError):
        return _response(501, "No implementado")

    # qfpy lanza ValueError/RuntimeError al valuar una entrada ya validada.
    @app.errorhandler(ValueError)
    @app.errorhandler(RuntimeError)
    def _pricing_error(e: Exception):
        return _response(400, "No se pudo valuar: %s" % e)
