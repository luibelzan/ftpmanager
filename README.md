# FTP Manager — Backend

Gestor de descargas FTP/SFTP multicliente con scheduler, alertas y soporte VPN.

## Stack

- **Python 3.11+** · FastAPI · SQLAlchemy 2 (async) · APScheduler
- **PostgreSQL** (base de datos principal + jobstore del scheduler)
- **ftplib** (FTP/FTPS) · **paramiko** (SFTP) · **OpenVPN** (VPN por cliente)
- **Telegram Bot** para alertas

---

## Instalación

### 1. Prerrequisitos

```bash
# Python 3.11+
python --version

# PostgreSQL corriendo (o Docker)
docker run -d --name ftpdb -e POSTGRES_USER=ftpuser \
  -e POSTGRES_PASSWORD=ftppass -e POSTGRES_DB=ftpmanager \
  -p 5432:5432 postgres:16-alpine
```

### 2. Entorno virtual y dependencias

```bash
cd ftp-manager
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuración

```bash
cp .env.example .env
# Editar .env con tus valores reales
```

Variables clave:
```env
DATABASE_URL=postgresql+asyncpg://ftpuser:ftppass@localhost:5432/ftpmanager
DATABASE_URL_SYNC=postgresql://ftpuser:ftppass@localhost:5432/ftpmanager
SECRET_KEY=genera-una-clave-de-32-chars-aqui
BASE_DOWNLOAD_PATH=C:/GD/Distribuidoras
OPENVPN_BIN=C:/Program Files/OpenVPN/bin/openvpn.exe
OPENVPN_CONFIG_DIR=C:/GD/config/vpn
TELEGRAM_BOT_TOKEN=tu-token          # opcional
TELEGRAM_CHAT_ID=tu-chat-id          # opcional
```

### 4. Crear tablas y cargar los 3 clientes iniciales

```bash
python scripts/seed_clients.py
```

Esto crea:
- **FEREZ** — FTP simple, `/upload`, patrones S04/S05, lunes-sábado 06:00
- **VARGAS** — FTP + VPN OpenVPN, 2 directorios (Penillar + Polígono), 13 tipos de fichero, 05:30
- **GARCIA** — SFTP, `/datos/salida`, patrones S04/S05/G01, 06:15

Para VARGAS, coloca el fichero `vargas.ovpn` en `OPENVPN_CONFIG_DIR`.

### 5. Arrancar el servidor

```bash
# Desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Producción (Windows Service o como proceso en background)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

> Usar `--workers 1` siempre — el scheduler debe correr en un único proceso.

---

## API — Endpoints principales

### Clientes

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/clients/` | Listar todos los clientes |
| `POST` | `/api/v1/clients/` | Crear nuevo cliente |
| `GET` | `/api/v1/clients/{id}` | Detalle de cliente |
| `PATCH` | `/api/v1/clients/{id}` | Actualizar cliente |
| `DELETE` | `/api/v1/clients/{id}` | Eliminar cliente |
| `POST` | `/api/v1/clients/{id}/toggle` | Activar/desactivar |
| `POST` | `/api/v1/clients/{id}/run` | Ejecución manual inmediata |
| `POST` | `/api/v1/clients/test-connection` | Test de conexión FTP |
| `POST` | `/api/v1/clients/{id}/rules` | Añadir regla de descarga |
| `DELETE` | `/api/v1/clients/rules/{rule_id}` | Eliminar regla |

### Dashboard y monitorización

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/dashboard/stats` | Estadísticas generales |
| `GET` | `/api/v1/dashboard/scheduler/jobs` | Jobs activos en el scheduler |
| `GET` | `/api/v1/alerts/` | Listado de alertas |
| `POST` | `/api/v1/alerts/{id}/acknowledge` | Reconocer alerta |
| `GET` | `/api/v1/jobs/` | Historial de ejecuciones |
| `GET` | `/api/v1/jobs/{id}` | Detalle de ejecución |

Documentación interactiva: `http://localhost:8000/docs`

---

## Estructura del proyecto

```
ftp-manager/
├── app/
│   ├── main.py                  # FastAPI app + lifespan
│   ├── core/
│   │   └── config.py            # Settings (pydantic-settings)
│   ├── db/
│   │   └── database.py          # Engine async + sesión
│   ├── models/
│   │   └── models.py            # SQLAlchemy ORM
│   ├── schemas/
│   │   └── schemas.py           # Pydantic I/O schemas
│   ├── services/
│   │   ├── client_service.py    # CRUD clientes
│   │   ├── ftp_engine.py        # Motor FTP/FTPS/SFTP
│   │   ├── vpn_service.py       # Gestión túneles OpenVPN
│   │   ├── alert_service.py     # Alertas + Telegram
│   │   ├── job_runner.py        # Orquestador VPN+FTP+Alertas
│   │   └── scheduler_service.py # APScheduler wrapper
│   └── api/routes/
│       ├── clients.py           # Endpoints /clients
│       └── dashboard.py         # Endpoints /dashboard /alerts /jobs
├── scripts/
│   └── seed_clients.py          # Carga los 3 clientes iniciales
├── config/vpn/                  # Ficheros .ovpn (no subir a git)
├── requirements.txt
├── .env.example
└── alembic.ini
```

---

## Equivalencia scripts .bat → base de datos

Cada script `.bat` de WinSCP se traduce a:

```
Cliente (ftp_host, ftp_user, ftp_password, local_base_path)
  └── DownloadRule (ftp_directory = cada bloque cd)
        └── FilePattern (pattern, file_type, local_subfolder, min_age_days)
```

Ejemplo Ferez:
```
open ftp://ftp_0132:iCLq.0573@82.159.192.202   → Client.ftp_*
cd upload                                        → DownloadRule.ftp_directory = "/upload"
get *_S04_*>1D>=1 C:\...\S04\                   → FilePattern(pattern="*_S04_*", min_age_days=1, local_subfolder="S04")
```

---

## Añadir un cliente nuevo via API

```bash
curl -X POST http://localhost:8000/api/v1/clients/ \
  -H "Content-Type: application/json" \
  -d '{
    "code": "NUEVO",
    "name": "Distribuidora Nueva S.L.",
    "ftp_host": "ftp.nueva.com",
    "ftp_port": 21,
    "ftp_protocol": "FTP",
    "ftp_user": "user",
    "ftp_password": "pass",
    "local_base_path": "C:/GD/Distribuidoras/Nueva/Import",
    "vpn_required": false,
    "schedule_cron": "0 7 * * 1-5",
    "download_rules": [
      {
        "ftp_directory": "/datos",
        "file_patterns": [
          {"pattern": "*_S04_*", "file_type": "S04", "local_subfolder": "S04", "min_age_days": 1, "min_size_bytes": 1}
        ]
      }
    ]
  }'
```

---

## VPN (Vargas)

1. Coloca `vargas.ovpn` en `C:/GD/config/vpn/`
2. Asegúrate de que OpenVPN está instalado y `openvpn.exe` está en la ruta configurada
3. El proceso debe ejecutarse con permisos de administrador para gestionar interfaces de red
4. El sistema levanta el túnel antes de cada ejecución y lo cierra al terminar

---

## Notas de producción

- Ejecutar el proceso como **Administrador** (necesario para OpenVPN)
- Hacer backup de la BD antes de actualizaciones
- Los passwords FTP se guardan en texto plano en la BD — considera usar cifrado a nivel de columna en producción
- El scheduler persiste sus jobs en la misma BD, por lo que sobrevive reinicios del servicio
