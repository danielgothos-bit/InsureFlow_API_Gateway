import json
import uuid
from unittest import mock

import requests
from rest_framework.test import APITestCase

from usuarios.models import Usuario

ENV = {
    "CLAIMS_SERVICE_URL": "http://claims:8000",
    "ANALYTICS_SERVICE_URL": "http://analytics:8000",
    "POLICYHOLDER_SERVICE_URL": "http://policyholder:8000",
    "POLICY_SERVICE_URL": "http://policy:8000",
    "ADJUSTER_SERVICE_URL": "http://adjuster:8000",
    "PROXY_WAKE_WAIT": "0",
}
CLAVE = "ClaveSegura#2026"


class RespuestaFalsa:
    def __init__(self, status_code=201, data=None):
        self.status_code = status_code
        self.content = json.dumps(data if data is not None else {"ok": True}).encode()
        self.headers = {"Content-Type": "application/json"}


@mock.patch.dict("os.environ", ENV)
class GatewayTests(APITestCase):
    def login(self, usuario):
        resp = self.client.post("/api/v1/auth/login", {"username": usuario, "password": CLAVE}, format="json")
        self.assertEqual(resp.status_code, 200, resp.content)
        return {"HTTP_AUTHORIZATION": f"Bearer {resp.data['access']}"}

    def interno(self, role="agente", **extra):
        Usuario.objects.create_user(username=f"{role}1", email=f"{role}1@insureflow.co", password=CLAVE, role=role, **extra)
        return self.login(f"{role}1")

    def cliente(self):
        self.id_asegurado = str(uuid.uuid4())
        u = Usuario.objects.create_user(username="ana@example.com", email="ana@example.com", password=CLAVE,
                                        role="asegurado", id_asegurado=self.id_asegurado)
        return self.login(u.email)

    # ---------- registro y login ----------
    @mock.patch("usuarios.views.llamar")
    def test_registro_crea_asegurado_y_usuario(self, llamar):
        llamar.return_value = {"id_asegurado": str(uuid.uuid4())}
        resp = self.client.post("/api/v1/auth/registro", {
            "nombre": "Ana", "apellido": "Gómez", "national_id": "1020", "email": "Ana@Example.com", "password": CLAVE,
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data["role"], "asegurado")
        self.assertEqual(resp.data["id_asegurado"], llamar.return_value["id_asegurado"])
        self.assertTrue(Usuario.objects.get(email="ana@example.com").password.startswith("bcrypt_sha256$"))
        # Login con el correo
        self.assertEqual(self.client.post("/api/v1/auth/login", {"username": "ana@example.com", "password": CLAVE}, format="json").status_code, 200)

    @mock.patch("usuarios.views.llamar")
    def test_registro_falla_si_asegurados_rechaza(self, llamar):
        from proxy.servicios import ServicioError
        llamar.side_effect = ServicioError(400, {"code": "VALIDATION_ERROR", "message": "Datos inválidos."})
        resp = self.client.post("/api/v1/auth/registro", {
            "nombre": "A", "apellido": "B", "national_id": "1", "email": "x@example.com", "password": CLAVE}, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Usuario.objects.filter(email="x@example.com").exists())

    def test_refresh_y_me(self):
        auth = self.interno()
        tokens = self.client.post("/api/v1/auth/login", {"username": "agente1", "password": CLAVE}, format="json").data
        self.assertIn("access", self.client.post("/api/v1/auth/refresh", {"refresh": tokens["refresh"]}, format="json").data)
        self.assertEqual(self.client.get("/api/v1/auth/me", **auth).data["role"], "agente")

    # ---------- administración de usuarios ----------
    @mock.patch("usuarios.views.llamar", return_value={"id_perito": str(uuid.uuid4())})
    def test_admin_crea_perito(self, llamar):
        auth = self.interno("admin")
        resp = self.client.post("/api/v1/auth/usuarios", {"username": "perito1", "email": "p@insureflow.co", "password": CLAVE,
                                                          "role": "perito", "especialidad": "auto", "first_name": "Carlos"},
                                format="json", **auth)
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data["id_perito"], llamar.return_value["id_perito"])
        self.assertEqual(len(self.client.get("/api/v1/auth/usuarios", **auth).data), 2)

    def test_solo_admin_gestiona_usuarios(self):
        auth = self.interno("agente")
        self.assertEqual(self.client.get("/api/v1/auth/usuarios", **auth).status_code, 403)

    # ---------- proxy ----------
    def test_sin_token_responde_401(self):
        self.assertEqual(self.client.get("/api/v1/siniestros").status_code, 401)

    @mock.patch("proxy.views.requests.request", return_value=RespuestaFalsa(200, [{"plan": "basico"}]))
    def test_cotizar_es_publico(self, request):
        resp = self.client.post("/api/v1/polizas/cotizar", {"product_type": "auto", "suma_asegurada": 1}, format="json")
        self.assertEqual(resp.status_code, 200)

    @mock.patch("proxy.views.requests.request", return_value=RespuestaFalsa())
    def test_agente_reenvia_al_microservicio(self, request):
        auth = self.interno()
        resp = self.client.post("/api/v1/siniestros?x=1", {"descripcion": "choque"}, format="json",
                                HTTP_ACCEPT_ENCODING="gzip, br, zstd", **auth)
        self.assertEqual(resp.status_code, 201)
        metodo, url = request.call_args[0]
        self.assertEqual((metodo, url), ("POST", "http://claims:8000/api/v1/siniestros"))
        cabeceras = request.call_args[1]["headers"]
        self.assertEqual(cabeceras["X-User-Role"], "agente")
        self.assertNotIn("Authorization", cabeceras)
        self.assertNotIn("Accept-Encoding", cabeceras)

    def test_rutas_bloqueadas_y_por_rol(self):
        auth = self.cliente()
        self.assertEqual(self.client.post("/api/v1/eventos", {}, **auth).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/analitica/fraude", **auth).status_code, 403)

    # ---------- el cliente solo ve lo suyo ----------
    @mock.patch("proxy.views.requests.request", return_value=RespuestaFalsa(200, []))
    def test_cliente_solo_sus_datos(self, request):
        auth = self.cliente()
        self.assertEqual(self.client.get(f"/api/v1/polizas/asegurado/{self.id_asegurado}", **auth).status_code, 200)
        self.assertEqual(self.client.get(f"/api/v1/polizas/asegurado/{uuid.uuid4()}", **auth).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/asegurados", **auth).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/siniestros", **auth).status_code, 403)

    @mock.patch("proxy.permisos.llamar")
    @mock.patch("proxy.views.requests.request", return_value=RespuestaFalsa())
    def test_cliente_contrata_y_reporta_para_si_mismo(self, request, llamar):
        auth = self.cliente()
        llamar.return_value = {"id_asegurado": self.id_asegurado}

        self.client.post("/api/v1/polizas", {"id_asegurado": str(uuid.uuid4()), "premium": "1", "product_type": "auto"}, format="json", **auth)
        enviado = json.loads(request.call_args[1]["data"])
        self.assertEqual(enviado["id_asegurado"], self.id_asegurado)
        self.assertNotIn("premium", enviado)

        resp = self.client.post("/api/v1/siniestros", {"id_poliza": str(uuid.uuid4()), "descripcion": "x"}, format="json", **auth)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(json.loads(request.call_args[1]["data"])["id_asegurado"], self.id_asegurado)

        llamar.return_value = {"id_asegurado": str(uuid.uuid4())}  # póliza de otra persona
        resp = self.client.post("/api/v1/pagos/primas", {"id_poliza": str(uuid.uuid4())}, format="json", **auth)
        self.assertEqual(resp.status_code, 403)
        resp = self.client.get(f"/api/v1/siniestros/{uuid.uuid4()}", **auth)
        self.assertEqual(resp.status_code, 403)

    @mock.patch("proxy.permisos.llamar")
    @mock.patch("proxy.views.requests.request", return_value=RespuestaFalsa(200))
    def test_perito_solo_sus_inspecciones(self, request, llamar):
        id_perito = str(uuid.uuid4())
        auth = self.interno("perito", id_perito=id_perito)
        propia = str(uuid.uuid4())
        llamar.return_value = [{"id_inspeccion": propia, "id_siniestro": str(uuid.uuid4())}]
        self.assertEqual(self.client.get(f"/api/v1/inspecciones/perito/{id_perito}", **auth).status_code, 200)
        self.assertEqual(self.client.put(f"/api/v1/inspecciones/{propia}/informe", {"findings": "x"}, format="json", **auth).status_code, 200)
        self.assertEqual(self.client.put(f"/api/v1/inspecciones/{uuid.uuid4()}/informe", {}, format="json", **auth).status_code, 403)
        self.assertEqual(self.client.get("/api/v1/polizas", **auth).status_code, 403)

    @mock.patch("proxy.views.requests.request", side_effect=requests.ConnectionError())
    def test_servicio_caido(self, request):
        auth = self.interno()
        self.assertEqual(self.client.get("/api/v1/analitica/fraude", **auth).status_code, 503)

    @mock.patch("proxy.views.requests.request")
    def test_reintenta_mientras_el_servicio_despierta(self, request):
        dormido = mock.Mock(status_code=502, content=b"<html>502</html>", headers={"Content-Type": "text/html"})
        request.side_effect = [dormido, dormido, RespuestaFalsa()]
        auth = self.interno()
        self.assertEqual(self.client.get("/api/v1/siniestros", **auth).status_code, 201)
        self.assertEqual(request.call_count, 3)

    def test_health(self):
        self.assertEqual(self.client.get("/health").status_code, 200)
