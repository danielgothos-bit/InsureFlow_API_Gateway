import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from django.db import connection
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .rutas import BLOQUEADAS, ROLES_PERMITIDOS, RUTAS

logger = logging.getLogger("gateway")

# Cabeceras que no se reenvían (hop-by-hop o que el gateway reemplaza).
# accept-encoding: el gateway negocia su propia compresión (gzip) con el microservicio; si reenviara
# la del navegador (br, zstd), recibiría respuestas que no sabe descomprimir.
NO_REENVIAR = {"host", "content-length", "authorization", "connection", "keep-alive", "transfer-encoding",
               "accept-encoding", "x-user-id", "x-user-role", "x-internal-token", "cookie"}
NO_DEVOLVER = {"content-encoding", "content-length", "transfer-encoding", "connection", "keep-alive"}


def error(code, message, http_status):
    return Response({"code": code, "message": message}, status=http_status)


class ProxyView(APIView):
    """Reenvía /api/v1/<recurso>/... al microservicio dueño del recurso."""

    parser_classes = []  # el cuerpo se reenvía tal cual (JSON o multipart)

    def _reenviar(self, request, ruta):
        recurso = ruta.split("/")[0]
        if recurso in BLOQUEADAS or recurso not in RUTAS:
            return error("NOT_FOUND", "Recurso no encontrado.", status.HTTP_404_NOT_FOUND)

        roles = ROLES_PERMITIDOS.get(recurso)
        if roles and request.user.role not in roles:
            return error("FORBIDDEN", "Tu rol no tiene acceso a este recurso.", status.HTTP_403_FORBIDDEN)

        servicio = RUTAS[recurso]
        base = os.getenv(f"{servicio}_SERVICE_URL")
        if not base:
            return error("SERVICE_NOT_CONFIGURED", f"{servicio}_SERVICE_URL no está configurada.",
                         status.HTTP_503_SERVICE_UNAVAILABLE)

        cabeceras = {k: v for k, v in request.headers.items() if k.lower() not in NO_REENVIAR}
        cabeceras.update({
            "X-User-Id": str(request.user.id),
            "X-User-Role": request.user.role,
            "X-Request-Id": getattr(request._request, "request_id", ""),
        })
        url = f"{base.rstrip('/')}/api/v1/{ruta}"

        # En Render gratis un servicio dormido responde 502/503 mientras despierta (~1 minuto):
        # el gateway espera y reintenta en lugar de devolverle ese error al cliente.
        intentos = int(os.getenv("PROXY_WAKE_RETRIES", "6"))
        for intento in range(intentos + 1):
            try:
                resp = requests.request(
                    request.method, url, params=request.GET, data=request.body, headers=cabeceras,
                    timeout=(10, float(os.getenv("PROXY_TIMEOUT", "90"))), allow_redirects=False,
                )
            except requests.Timeout:
                return error("GATEWAY_TIMEOUT", f"{servicio} no respondió a tiempo.", status.HTTP_504_GATEWAY_TIMEOUT)
            except requests.RequestException:
                logger.exception("error reenviando solicitud", extra={"servicio": servicio, "url": url})
                return error("SERVICE_UNAVAILABLE", f"{servicio} no está disponible.", status.HTTP_503_SERVICE_UNAVAILABLE)

            if resp.status_code not in (502, 503, 504) or intento == intentos:
                break
            logger.info("servicio despertando, reintentando", extra={"servicio": servicio, "intento": intento + 1})
            time.sleep(float(os.getenv("PROXY_WAKE_WAIT", "10")))

        if resp.status_code in (502, 503, 504) and "text/html" in resp.headers.get("Content-Type", ""):
            return error("SERVICE_WAKING", f"{servicio} se está iniciando. Intenta de nuevo en unos segundos.",
                         status.HTTP_503_SERVICE_UNAVAILABLE)

        respuesta = HttpResponse(resp.content, status=resp.status_code)
        for clave, valor in resp.headers.items():
            if clave.lower() not in NO_DEVOLVER:
                respuesta[clave] = valor
        return respuesta

    def get(self, request, ruta):
        return self._reenviar(request, ruta)

    def post(self, request, ruta):
        return self._reenviar(request, ruta)

    def put(self, request, ruta):
        return self._reenviar(request, ruta)

    def patch(self, request, ruta):
        return self._reenviar(request, ruta)

    def delete(self, request, ruta):
        return self._reenviar(request, ruta)


FRONTEND = Path(__file__).resolve().parent / "frontend" / "index.html"


def inicio(request):
    """Consola web de InsureFlow: el mismo link del gateway sirve el frontend de prueba."""
    return HttpResponse(FRONTEND.read_bytes(), content_type="text/html; charset=utf-8")


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    try:
        connection.ensure_connection()
        db = "ok"
    except Exception:
        db = "error"
    codigo = status.HTTP_200_OK if db == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response({"service": "gateway", "status": db, "database": db}, status=codigo)


@api_view(["GET"])
@permission_classes([AllowAny])
def health_servicios(request):
    """Estado de todos los microservicios (útil para monitoreo y para despertarlos en Render)."""
    servicios = sorted(set(RUTAS.values()))

    def revisar(servicio):
        base = os.getenv(f"{servicio}_SERVICE_URL")
        if not base:
            return servicio, {"status": "no_configurado"}
        try:
            resp = requests.get(f"{base.rstrip('/')}/health", timeout=float(os.getenv("HEALTH_TIMEOUT", "60")))
            return servicio, resp.json() if resp.ok else {"status": "error", "http": resp.status_code}
        except requests.RequestException as exc:
            return servicio, {"status": "sin_respuesta", "error": exc.__class__.__name__}

    with ThreadPoolExecutor(max_workers=len(servicios)) as pool:
        resultado = dict(pool.map(revisar, servicios))

    todos_ok = all(r.get("status") == "ok" for r in resultado.values())
    return Response({"gateway": "ok", "todos_ok": todos_ok, "servicios": resultado})
