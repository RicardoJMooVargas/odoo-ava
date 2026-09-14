# Odoo Development Project

Entorno Dockerizado para desarrollo y despliegue de módulos Odoo personalizados. Incluye el addon `expediente_empleados`, que amplía los empleados de Odoo con datos laborales y documentos del expediente.

## Estructura

```
.
├── addons/               # Módulos propios (montados en /mnt/extra-addons)
│   └── expediente_empleados/ # Addon de expedientes laborales
├── config/
│   └── odoo.conf         # Configuración de Odoo
├── Dockerfile
├── docker-compose.yml
├── docker-compose.local.yml
├── .env                  # Variables locales (NO se sube al repo)
├── .env.example          # Plantilla de variables de entorno
└── README.md
```

## Inicio rápido

### 0. Prerequisito (solo la primera vez)

El compose base requiere la red externa `dokploy-network`. El override local la crea automáticamente con nombre `odoo-dokploy-local`, por lo que **no necesitas crearla manualmente** si usas el comando del paso 2.

### 1. Configura tus variables de entorno

**Windows (PowerShell / CMD):**
```powershell
copy .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

> Edita `.env` y cambia al menos `DB_PASSWORD` antes de continuar.

### 2. Levanta el entorno de desarrollo

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build
```

Accede en: **http://localhost:8069**

---

## Modos de ejecución

### Desarrollo (.env)

```env
APP_ENV=develop
ODOO_EXTRA_ARGS=--dev=all
```

- Hot-reload de módulos al guardar cambios
- Assets sin minificar (fácil debug de JS/CSS)
- Modo debug activado automáticamente

### Producción (Dokploy / servidor)

En el panel de Dokploy configura las variables de entorno:

```env
APP_ENV=production
ODOO_EXTRA_ARGS=           # vacío: sin flags de debug
DB_USER=odoo_prod
DB_PASSWORD=TU_PASSWORD_SEGURO
```

---

## Comandos útiles

| Acción | Comando |
|---|---|
| Levantar (dev) | `docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --build` |
| Ver logs | `docker compose -f docker-compose.yml -f docker-compose.local.yml logs -f odoo` |
| Reiniciar Odoo | `docker compose -f docker-compose.yml -f docker-compose.local.yml restart odoo` |
| Actualizar módulo | `docker compose -f docker-compose.yml -f docker-compose.local.yml exec odoo odoo -u expediente_empleados -d odoo --stop-after-init` |
| Instalar módulo | `docker compose -f docker-compose.yml -f docker-compose.local.yml exec odoo odoo -i expediente_empleados -d odoo --stop-after-init` |
| Bajar todo | `docker compose -f docker-compose.yml -f docker-compose.local.yml down` |
| Limpiar volúmenes | `docker compose -f docker-compose.yml -f docker-compose.local.yml down -v` |

---

## Crear un nuevo módulo

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml exec odoo odoo scaffold mi_nuevo_modulo /mnt/extra-addons
```

Esto genera el esqueleto del módulo directamente en `./addons/mi_nuevo_modulo/`.

## Expediente de empleados

1. Entra a Odoo y activa el modo desarrollador si necesitas administrar módulos.
2. Ve a **Aplicaciones**, actualiza la lista de aplicaciones e instala **Expediente de Empleados**.
3. Abre **Empleados**, selecciona un colaborador y usa la pestaña **Expediente laboral**.

El addon guarda la fecha de ingreso, puesto, división, estatus, indicador de chofer, número de seguridad social y observaciones. Los documentos (`comp_domic`, `const_sit_fiscal`, `descript_puesto`, `licencia_chof`, `curriculum`, `solicitud_empl`, `act_naci`, `ine`, `curp`, `rfc`, `contrato` y `acta_hechos`) se cargan desde la ficha y Odoo los almacena como adjuntos en la base de datos.

El campo `id` ya existe en Odoo como identificador interno del empleado. El nombre del colaborador corresponde al campo estándar `name`; el puesto estándar también se conserva y se incluye `puesto_expediente` para capturar el valor de la plantilla proporcionada.

### Nota de protección de datos

Estos documentos contienen información personal sensible. En producción cambia `admin_passwd`, usa una contraseña fuerte para PostgreSQL, limita los usuarios del grupo de Recursos Humanos y configura copias de seguridad cifradas.

---

## Despliegue en Dokploy

1. Apunta tu repositorio en Dokploy.
2. Configura las variables de entorno en el panel (sin subir .env).
3. Dokploy ejecuta docker compose up -d automáticamente.
