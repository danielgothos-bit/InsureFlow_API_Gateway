from unittest import mock

import requests
from rest_framework.test import APITestCase

from usuarios.models import Usuario


class RespuestaFalsa:
    status_code = 201
    content = b'{"id_siniestro": "abc"}'
    headers = {"Content-Type": "application/json"}


@mock.patch.dict("os.environ", {"CLAIMS_SERVICE_URL": "http://claims:8000", "ANALYTICS_SERVICE_URL": "http://analytics:8000"})
class GatewayTests(APITestCase):
    def registrar_y_login(self, username="ana", role=None):
        datos = {"username": username, "email": f"{username}@example.com", "password": "ClaveSegura#2026"}
        if role:
            Usuario.objects.create_user(role=role, **datos)
        else:
            self.assertEqual(self.client.post("/api/v1/auth/registro", datos, format="json").status_code, 201)
        resp = self.client.post("/api/v1/auth/login", {"username": username, "password": datos["password"]}, format="json")
        self.assertEqual(resp.status_code, 200)
        return resp.data

    def test_registro_login_refresh_y_me(self):
        tokens = self.registrar_y_login()
        self.assertIn("refresh", tokens)

        resp = self.client.get("/api/v1/auth/me", HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(resp.data["role"], "asegurado")

        resp = self.client.post("/api/v1/auth/refresh", {"refresh": tokens["refresh"]}, format="json")
        self.assertIn("access", resp.data)

        usuario = Usuario.objects.get(username="ana")
        self.assertTrue(usuario.password.startswith("bcrypt_sha256$"))

    def test_no_puede_registrarse_como_admin(self):
        resp = self.client.post("/api/v1/auth/registro", {
            "username": "x", "email": "x@example.com", "password": "ClaveSegura#2026", "role": "admin",
        }, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_sin_token_responde_401(self):
        resp = self.client.get("/api/v1/siniestros")
        self.assertEqual(resp.status_code, 401)

    @mock.patch("proxy.views.requests.request", return_value=RespuestaFalsa())
    def test_reenvia_al_microservicio(self, request):
        tokens = self.registrar_y_login()
        resp = self.client.post("/api/v1/siniestros?x=1", {"descripcion": "choque"}, format="json",
                                HTTP_AUTHORIZATION=f"Bearer {tokens['access']}", HTTP_ACCEPT_ENCODING="gzip, br, zstd")

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.content, RespuestaFalsa.content)
        metodo, url = request.call_args[0]
        self.assertEqual((metodo, url), ("POST", "http://claims:8000/api/v1/siniestros"))
        cabeceras = request.call_args[1]["headers"]
        self.assertEqual(cabeceras["X-User-Role"], "asegurado")
        self.assertNotIn("Authorization", cabeceras)
        self.assertNotIn("Accept-Encoding", cabeceras)
        self.assertIn(b"choque", request.call_args[1]["data"])

    def test_rutas_bloqueadas_y_por_rol(self):
        tokens = self.registrar_y_login()
        auth = {"HTTP_AUTHORIZATION": f"Bearer {tokens['access']}"}
        self.assertEqual(self.client.post("/api/v1/eventos", {}, **auth).status_code, 404)
        self.assertEqual(self.client.get("/api/v1/analitica/fraude", **auth).status_code, 403)

    @mock.patch("proxy.views.requests.request", side_effect=requests.ConnectionError())
    def test_servicio_caido(self, request):
        tokens = self.registrar_y_login(role="agente")
        resp = self.client.get("/api/v1/analitica/fraude", HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(resp.status_code, 503)

    def test_health(self):
        self.assertEqual(self.client.get("/health").status_code, 200)

    def test_frontend_en_la_raiz(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"InsureFlow", resp.content)
