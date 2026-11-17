# API Gateway — InsureFlow

Punto único de entrada de InsureFlow (sección 7 del documento de arquitectura). El frontend
(portal de asegurados, panel de agentes y app de peritos) solo necesita la URL de este gateway.

## Qué hace

- **Enrutamiento:** reenvía `/api/v1/<recurso>/...` al microservicio dueño del recurso.
- **Autenticación centralizada con JWT + refresh tokens** (sección 12.1). Contraseñas con **bcrypt** (12.2).
- **Validación de tokens:** sin token válido responde `401` sin llamar al microservicio.
- **Roles:** `asegurado`, `agente`, `perito`, `admin`. Analítica solo para agente/admin; peritos e inspecciones para agente/perito/admin.
- **Rate limiting:** 600 solicitudes/min por usuario y 60/min anónimas (configurable).
- **Logging centralizado:** cada solicitud se registra en JSON (método, ruta, usuario, estado, duración, `X-Request-Id`).
- **CORS:** solo los orígenes autorizados (`CORS_ALLOWED_ORIGINS`).

## Rutas

| Ruta | Microservicio |
|---|---|
| `/api/v1/asegurados/...` | Asegurados (Policyholder) |
| `/api/v1/polizas/...` | Pólizas (Policy) |
| `/api/v1/siniestros/...` | Siniestros (Claims) |
| `/api/v1/peritos/...`, `/api/v1/inspecciones/...` | Peritaje (Adjuster) |
| `/api/v1/pagos/...` | Pagos (Payment) |
| `/api/v1/documentos/...` | Documentación (Document) |
| `/api/v1/notificaciones/...` | Notificaciones (Notification) |
| `/api/v1/analitica/...` | Analítica (Analytics) |

## Autenticación

```
POST /api/v1/auth/registro   {"username", "email", "password", "first_name", "last_name"}
POST /api/v1/auth/login      {"username", "password"}  ->  {"access", "refresh"}
POST /api/v1/auth/refresh    {"refresh"}               ->  {"access", "refresh"}
GET  /api/v1/auth/me         (Authorization: Bearer <access>)
GET  /health                 estado del gateway
GET  /health/servicios       estado de los 8 microservicios
```

Todas las demás rutas requieren el encabezado `Authorization: Bearer <access>`.
El gateway envía a cada microservicio `X-User-Id`, `X-User-Role` y `X-Request-Id`.

## Variables de entorno

- `DATABASE_URL`: base de datos de usuarios (`gateway_db`)
- `JWT_SECRET`: clave de firma de los JWT
- `<SERVICIO>_SERVICE_URL`: URL de cada microservicio (POLICYHOLDER, POLICY, CLAIMS, ADJUSTER, PAYMENT, DOCUMENT, NOTIFICATION, ANALYTICS)
- `CORS_ALLOWED_ORIGINS`: dominios del frontend separados por coma
- `ADMIN_USERNAME`, `ADMIN_PASSWORD`: administrador inicial
- `RATE_LIMIT_USER`, `RATE_LIMIT_ANON`: límites de solicitudes (por defecto `600/min` y `60/min`)

## Ejecución local

```bash
docker compose up --build
```

Queda en http://localhost:8080. Para levantar InsureFlow completo usa `InsureFlow_Local/docker-compose.yml`.

## Despliegue en Render

**New → Blueprint** → conectar este repositorio → **Deploy Blueprint**, y llenar las URLs de los microservicios.

## Enlaces

| | |
|---|---|
| Servicio desplegado | https://insureflow-gateway-kxhm.onrender.com |
| Estado (health check) | https://insureflow-gateway-kxhm.onrender.com/health |
| Documentación de la API (Swagger) | https://insureflow-gateway-kxhm.onrender.com/api/docs |
| Esquema OpenAPI | https://insureflow-gateway-kxhm.onrender.com/api/schema |
| Métricas Prometheus | https://insureflow-gateway-kxhm.onrender.com/metrics |
| Sitio y API Gateway | https://insureflow-gateway-kxhm.onrender.com |

## Pruebas y cobertura

Las pruebas exigidas están en `tests/`:

- `tests/test_unitarias.py`: **2 pruebas unitarias** que verifican una regla de negocio aislada, con *mocks* para la base de datos, otros microservicios, la pasarela o el bus de eventos.
- `tests/test_integracion.py`: **1 prueba de integración** que recorre endpoint, lógica de negocio y base de datos.
- Las pruebas adicionales de la aplicación están en `<app>/tests.py`.

Para ejecutarlas (sin PostgreSQL ni Redis):

```bash
pip install -r requirements.txt coverage
USE_SQLITE=1 CELERY_EAGER=1 coverage run manage.py test -v 2
coverage report        # porcentaje de cobertura
coverage html          # reporte navegable en htmlcov/
```

En GitHub Actions (`.github/workflows/ci.yml`) el reporte de cobertura se publica en el resumen de la ejecución y como artefacto `reporte-cobertura`.

## CI/CD

| Archivo | Función |
|---|---|
| `.github/workflows/ci.yml` | En cada push y pull request: lint (flake8), pruebas unitarias y de integración con cobertura, auditoría de dependencias (pip-audit) e imagen Docker. Si algo falla, no se despliega. |
| `.github/workflows/deploy.yml` | Solo cuando CI termina con éxito en `main`: llama al Deploy Hook de Render (secreto `RENDER_DEPLOY_HOOK_URL`) y espera a que `/health` responda. |
| `.github/workflows/codeql.yml` | Análisis estático de seguridad. |

**Estrategia de ramas (GitFlow):**

- `main`: producción.
- `develop`: integración.
- `feature/*`: funcionalidades nuevas.
- `hotfix/*`: correcciones urgentes.

Los cambios entran por *pull request* con el pipeline en verde.

## Base de datos

- **Esquema:** migraciones de Django en `<app>/migrations/`, que se aplican solas al arrancar el contenedor (`start.sh`).
- **Datos de ejemplo:** las cuentas no se publican porque incluyen contraseñas cifradas. El administrador inicial se crea con `python manage.py crear_admin`, y los demás usuarios desde el portal de gestión.
- **Respaldo:** `datos/respaldo.sql` (volcado de PostgreSQL con `pg_dump`).
- **Variables de entorno:** ver `.env.example`. No se suben credenciales al repositorio.
