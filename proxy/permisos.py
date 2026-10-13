"""
Control de acceso a nivel de objeto (secciones 12 y 13 del documento).

- asegurado: solo puede ver y operar SUS propios datos (su ficha, sus pólizas, sus pagos,
  sus siniestros, sus documentos y sus notificaciones).
- perito: solo sus inspecciones y la información de los siniestros que inspecciona.
- agente y admin: acceso completo a la operación.

`autorizar` devuelve (permitido, cuerpo) donde `cuerpo` puede venir modificado
(por ejemplo, se fuerza el id del asegurado autenticado al crear una póliza o un siniestro).
"""
import json
import re

from .servicios import ServicioError, llamar

UUID = r"([0-9a-fA-F-]{36})"


def _poliza_propia(usuario, id_poliza):
    try:
        poliza = llamar("POLICY", "GET", f"/api/v1/polizas/{id_poliza}")
    except ServicioError:
        return False
    return str(poliza.get("id_asegurado")) == str(usuario.id_asegurado)


def _siniestro_propio(usuario, id_siniestro):
    try:
        siniestro = llamar("CLAIMS", "GET", f"/api/v1/siniestros/{id_siniestro}")
    except ServicioError:
        return False
    return str(siniestro.get("id_asegurado")) == str(usuario.id_asegurado)


def _documento_propio(usuario, id_documento):
    try:
        doc = llamar("DOCUMENT", "GET", f"/api/v1/documentos/{id_documento}")
    except ServicioError:
        return False
    if doc.get("id_siniestro") and _siniestro_propio(usuario, doc["id_siniestro"]):
        return True
    return bool(doc.get("id_poliza")) and _poliza_propia(usuario, doc["id_poliza"])


def _inspeccion_propia(usuario, id_inspeccion):
    try:
        propias = llamar("ADJUSTER", "GET", f"/api/v1/inspecciones/perito/{usuario.id_perito}")
    except ServicioError:
        return False
    return any(str(i.get("id_inspeccion")) == str(id_inspeccion) for i in propias)


def _siniestro_del_perito(usuario, id_siniestro):
    try:
        propias = llamar("ADJUSTER", "GET", f"/api/v1/inspecciones/perito/{usuario.id_perito}")
    except ServicioError:
        return False
    return any(str(i.get("id_siniestro")) == str(id_siniestro) for i in propias)


def _cuerpo(body):
    try:
        return json.loads(body or b"{}")
    except ValueError:
        return None


def _regla_asegurado(usuario, metodo, ruta, body):
    propio = str(usuario.id_asegurado)

    m = re.fullmatch(rf"asegurados/{UUID}(/kyc|/kyc/documentos)?", ruta)
    if m:
        permitido = (metodo, m.group(2)) in {("GET", None), ("PUT", None), ("GET", "/kyc"), ("POST", "/kyc/documentos")}
        return permitido and m.group(1) == propio, body

    for patron in (rf"polizas/asegurado/{UUID}", rf"siniestros/asegurado/{UUID}", rf"notificaciones/asegurado/{UUID}"):
        m = re.fullmatch(patron, ruta)
        if m:
            return metodo == "GET" and m.group(1) == propio, body

    for patron in (rf"polizas/{UUID}", rf"polizas/{UUID}/cobertura", rf"pagos/primas/poliza/{UUID}", rf"documentos/poliza/{UUID}"):
        m = re.fullmatch(patron, ruta)
        if m:
            return metodo == "GET" and _poliza_propia(usuario, m.group(1)), body

    for patron in (rf"siniestros/{UUID}", rf"siniestros/{UUID}/historial", rf"pagos/indemnizaciones/siniestro/{UUID}",
                   rf"documentos/siniestro/{UUID}", rf"inspecciones/siniestro/{UUID}"):
        m = re.fullmatch(patron, ruta)
        if m:
            return metodo == "GET" and _siniestro_propio(usuario, m.group(1)), body

    m = re.fullmatch(rf"documentos/{UUID}(/archivo)?", ruta)
    if m:
        return metodo == "GET" and _documento_propio(usuario, m.group(1)), body

    datos = _cuerpo(body) if metodo == "POST" else None

    if metodo == "POST" and ruta == "polizas" and isinstance(datos, dict):
        # El cliente contrata para sí mismo y con un plan del cotizador (la prima la calcula el sistema).
        datos["id_asegurado"] = propio
        datos.pop("premium", None)
        return True, json.dumps(datos).encode()

    if metodo == "POST" and ruta == "pagos/primas" and isinstance(datos, dict):
        return bool(datos.get("id_poliza")) and _poliza_propia(usuario, datos["id_poliza"]), body

    if metodo == "POST" and ruta == "siniestros" and isinstance(datos, dict):
        if not datos.get("id_poliza") or not _poliza_propia(usuario, datos["id_poliza"]):
            return False, body
        datos["id_asegurado"] = propio
        return True, json.dumps(datos).encode()

    return False, body


def _regla_perito(usuario, metodo, ruta, body):
    if not usuario.id_perito:
        return False, body
    if metodo == "GET" and ruta in ("peritos", "peritos/disponibilidad"):
        return True, body
    m = re.fullmatch(rf"inspecciones/perito/{UUID}", ruta)
    if m:
        return metodo == "GET" and m.group(1) == str(usuario.id_perito), body
    m = re.fullmatch(rf"inspecciones/{UUID}/informe", ruta)
    if m:
        return metodo == "PUT" and _inspeccion_propia(usuario, m.group(1)), body
    for patron in (rf"siniestros/{UUID}", rf"siniestros/{UUID}/historial", rf"documentos/siniestro/{UUID}",
                   rf"inspecciones/siniestro/{UUID}"):
        m = re.fullmatch(patron, ruta)
        if m:
            return metodo == "GET" and _siniestro_del_perito(usuario, m.group(1)), body
    return False, body


def autorizar(usuario, metodo, ruta, body):
    ruta = ruta.rstrip("/")
    if usuario.role in ("agente", "admin"):
        return True, body
    if usuario.role == "perito":
        return _regla_perito(usuario, metodo, ruta, body)
    if usuario.role == "asegurado" and usuario.id_asegurado:
        return _regla_asegurado(usuario, metodo, ruta, body)
    return False, body
