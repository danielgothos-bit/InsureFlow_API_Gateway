"""Prueba de integración: endpoint + lógica de negocio + base de datos funcionando juntos."""
from rest_framework.test import APITestCase

from usuarios.models import Usuario


class AutenticacionIntegracionTests(APITestCase):
    def test_login_jwt_me_y_rechazo_sin_token(self):
        Usuario.objects.create_user(username="gestor1", password="ClaveSegura#2026", role="agente", email="g@insureflow.co")
        tokens = self.client.post("/api/v1/auth/login", {"username": "gestor1", "password": "ClaveSegura#2026"}, format="json").data
        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)
        self.assertEqual(self.client.get("/api/v1/polizas").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + tokens["access"])
        yo = self.client.get("/api/v1/auth/me").data
        self.assertEqual(yo["role"], "agente")


class PresentacionIntegracionTests(APITestCase):
    def test_presentacion_de_la_sustentacion_esta_publicada(self):
        resp = self.client.get("/presentacion/")
        self.assertEqual(resp.status_code, 200)
        contenido = b"".join(resp.streaming_content)  # WhiteNoise responde como archivo
        self.assertIn("Sustentación final", contenido.decode())
