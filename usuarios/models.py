import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    ASEGURADO, AGENTE, PERITO, ADMIN = "asegurado", "agente", "perito", "admin"
    ROLES = [
        (ASEGURADO, "Asegurado"),
        (AGENTE, "Agente de suscripción"),
        (PERITO, "Perito"),
        (ADMIN, "Administrador"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLES, default=ASEGURADO)
    # Vínculo opcional con el registro del asegurado o del perito en su microservicio.
    id_asegurado = models.UUIDField(blank=True, null=True)
    id_perito = models.UUIDField(blank=True, null=True)

    class Meta:
        db_table = "usuario"
