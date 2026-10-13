"""Llamadas internas del gateway a los microservicios (con espera mientras un servicio de Render despierta)."""
import os
import time

import requests


class ServicioError(Exception):
    def __init__(self, status, data):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.data = data


def llamar(servicio, metodo, path, json=None, params=None):
    base = os.getenv(f"{servicio}_SERVICE_URL")
    if not base:
        raise ServicioError(503, {"code": "SERVICE_NOT_CONFIGURED", "message": f"{servicio} no está configurado."})

    url = f"{base.rstrip('/')}{path}"
    intentos = int(os.getenv("PROXY_WAKE_RETRIES", "6"))
    for intento in range(intentos + 1):
        try:
            resp = requests.request(metodo, url, json=json, params=params, timeout=(10, 90))
        except requests.RequestException:
            raise ServicioError(503, {"code": "SERVICE_UNAVAILABLE", "message": "Servicio no disponible."})
        if resp.status_code not in (502, 503, 504) or intento == intentos:
            break
        time.sleep(float(os.getenv("PROXY_WAKE_WAIT", "10")))

    try:
        data = resp.json()
    except ValueError:
        data = {"code": "ERROR", "message": "Respuesta inválida del servicio."}
    if resp.status_code >= 400:
        raise ServicioError(resp.status_code, data)
    return data
