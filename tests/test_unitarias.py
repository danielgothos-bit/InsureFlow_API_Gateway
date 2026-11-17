"""Pruebas unitarias: una unidad de lógica de negocio aislada; las dependencias externas se simulan con mocks."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from proxy.permisos import autorizar

POLIZA = "11111111-1111-4111-8111-111111111111"


class PermisosUnitTests(SimpleTestCase):
    @mock.patch("proxy.permisos.llamar", return_value={"id_asegurado": "otro-cliente"})
    def test_cliente_no_puede_ver_poliza_ajena(self, llamar):
        cliente = SimpleNamespace(role="asegurado", id_asegurado="cliente-1")
        permitido, _ = autorizar(cliente, "GET", f"polizas/{POLIZA}", None)
        self.assertFalse(permitido)
        llamar.assert_called_once_with("POLICY", "GET", f"/api/v1/polizas/{POLIZA}")

    @mock.patch("proxy.permisos.llamar", return_value={"id_asegurado": "cliente-1"})
    def test_cliente_si_puede_ver_su_poliza_y_gestor_todo(self, llamar):
        cliente = SimpleNamespace(role="asegurado", id_asegurado="cliente-1")
        self.assertTrue(autorizar(cliente, "GET", f"polizas/{POLIZA}", None)[0])
        gestor = SimpleNamespace(role="agente", id_asegurado=None)
        self.assertTrue(autorizar(gestor, "DELETE", "cualquier/ruta", None)[0])
