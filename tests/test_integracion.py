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


class DesactivarPeritoIntegracionTests(APITestCase):
    def test_desactivar_perito_lo_marca_no_disponible_en_peritaje(self):
        from unittest import mock
        Usuario.objects.create_user(username="admin1", password="ClaveSegura#2026", role="admin", email="a@insureflow.co")
        perito = Usuario.objects.create_user(username="perito1", password="ClaveSegura#2026", role="perito", email="p@insureflow.co",
                                             id_perito="22222222-2222-4222-8222-222222222222")
        token = self.client.post("/api/v1/auth/login", {"username": "admin1", "password": "ClaveSegura#2026"}, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
        with mock.patch("usuarios.views.llamar") as llamar:
            resp = self.client.patch(f"/api/v1/auth/usuarios/{perito.id}", {"is_active": False}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Usuario.objects.get(pk=perito.pk).is_active)
        llamar.assert_called_once_with("ADJUSTER", "PATCH", f"/api/v1/peritos/{perito.id_perito}", json={"disponible": False})


class BloqueoPorKycIntegracionTests(APITestCase):
    def test_rechazar_identidad_bloquea_la_cuenta_y_verificarla_la_desbloquea(self):
        import json as _json
        from unittest import mock
        aseg = "33333333-3333-4333-8333-333333333333"
        Usuario.objects.create_user(username="gestor2", password="ClaveSegura#2026", role="agente", email="g2@insureflow.co")
        cliente = Usuario.objects.create_user(username="ana@example.com", password="ClaveSegura#2026", role="asegurado",
                                              email="ana@example.com", id_asegurado=aseg)
        datos = {"username": "gestor2", "password": "ClaveSegura#2026"}
        token = self.client.post("/api/v1/auth/login", datos, format="json").data["access"]
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)

        class Resp:
            def __init__(self, estado):
                self.status_code, self.headers = 200, {"Content-Type": "application/json"}
                self.content = _json.dumps({"id_asegurado": aseg, "kyc_status": estado}).encode()

        with mock.patch.dict("os.environ", {"POLICYHOLDER_SERVICE_URL": "http://policyholder:8000"}), \
                mock.patch("proxy.views.requests.request", return_value=Resp("rechazado")):
            self.assertEqual(self.client.put(f"/api/v1/asegurados/{aseg}/kyc", {"kyc_status": "rechazado"}, format="json").status_code, 200)
        self.assertFalse(Usuario.objects.get(pk=cliente.pk).is_active)

        self.client.credentials()
        resp = self.client.post("/api/v1/auth/login", {"username": "ana@example.com", "password": "ClaveSegura#2026"}, format="json")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("identidad", str(resp.data))

        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
        with mock.patch.dict("os.environ", {"POLICYHOLDER_SERVICE_URL": "http://policyholder:8000"}), \
                mock.patch("proxy.views.requests.request", return_value=Resp("verificado")):
            self.client.put(f"/api/v1/asegurados/{aseg}/kyc", {"kyc_status": "verificado"}, format="json")
        self.assertTrue(Usuario.objects.get(pk=cliente.pk).is_active)
