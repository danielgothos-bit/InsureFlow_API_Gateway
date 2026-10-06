import os

from django.core.management.base import BaseCommand

from usuarios.models import Usuario


class Command(BaseCommand):
    help = "Crea (o actualiza) el usuario administrador con ADMIN_USERNAME, ADMIN_EMAIL y ADMIN_PASSWORD."

    def handle(self, *args, **options):
        password = os.getenv("ADMIN_PASSWORD")
        if not password:
            self.stdout.write("ADMIN_PASSWORD no definida: no se crea administrador.")
            return

        username = os.getenv("ADMIN_USERNAME", "admin")
        usuario, creado = Usuario.objects.get_or_create(
            username=username,
            defaults={"email": os.getenv("ADMIN_EMAIL", f"{username}@insureflow.co"), "role": Usuario.ADMIN},
        )
        usuario.role = Usuario.ADMIN
        usuario.is_staff = True
        usuario.set_password(password)
        usuario.save()
        self.stdout.write(f"Administrador {username} {'creado' if creado else 'actualizado'}.")
