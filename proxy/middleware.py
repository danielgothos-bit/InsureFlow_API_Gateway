"""Logging centralizado de cada solicitud que entra al gateway (sección 7)."""
import logging
import time
import uuid

logger = logging.getLogger("gateway.solicitudes")


class LogSolicitudesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        inicio = time.monotonic()
        response = self.get_response(request)
        duracion = round((time.monotonic() - inicio) * 1000, 1)

        usuario = getattr(request, "user", None)
        logger.info("solicitud", extra={
            "request_id": request.request_id,
            "method": request.method,
            "path": request.path,
            "user": str(getattr(usuario, "id", "")) if getattr(usuario, "is_authenticated", False) else None,
            "status": response.status_code,
            "duration_ms": duracion,
        })
        response["X-Request-Id"] = request.request_id
        return response
