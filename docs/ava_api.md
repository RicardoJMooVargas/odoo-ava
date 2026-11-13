# Documentación de Integración con `AVA_API` (Ventas y Metas Comerciales)

Esta guía documenta el uso de los endpoints `/AVA/ventas` y `/AVA/ventas/pagos` dentro de Odoo 19 (`expediente_empleados`) para el seguimiento automático del **Esquema Mensual de Metas Comerciales, Evaluación de Desempeño e Incentivos**.

---

## 1. Configuración de Credenciales en Odoo

Las credenciales de conexión se configuran dentro de Odoo en **Empleados -> Configuración -> Ajustes** (o en **Ajustes Generales -> Metas Comerciales y AVA_API**) y se almacenan de forma segura en `ir.config_parameter`:

| Parámetro del Sistema (`ir.config_parameter`) | Descripción | Valor por defecto |
| :--- | :--- | :--- |
| `ava_api.base_url` | URL base del servidor de `AVA_API` (sin barra final) | `https://logichounds.com` |
| `ava_api.auth_type` | Método de autenticación (`none`, `bearer`, `basic`, `api_key_header`, `api_key_query`) | `bearer` |
| `ava_api.username` | Usuario para Basic Auth o parámetro de usuario | `ADMIN` |
| `ava_api.password` | Contraseña o secreto para Basic Auth | *(vacío)* |
| `ava_api.api_key` | Token Bearer o API Key | *(vacío)* |
| `ava_api.api_key_name` | Nombre del Header o Query Param cuando se usa API Key | `X-API-Key` |
| `ava_api.catalogo` | Catálogo consultado en el servicio | `AVA01` |
| `ava_api.timeout` | Tiempo máximo de espera por petición HTTP (segundos) | `30` |

---

## 2. Empate de Empleados (`Nombre Alias` ↔ `nombreVendedor`)

En la ficha del empleado (`hr.employee`), pestaña **Expediente laboral** / **Metas Comerciales**:
- Se dispone del campo **`Nombre Alias`** (`nombre_alias`) y el indicador **`Es agente de ventas`** (`es_agente_ventas`).
- Al consultar `/AVA/ventas`, el sistema filtra las operaciones donde el campo **`nombreVendedor`** (normalizado en mayúsculas y sin espacios adicionales) coincida con el **`Nombre Alias`** del empleado en Odoo.

---

## 3. Endpoints Utilizados

### 3.1. Consultar Ventas (`/AVA/ventas`)

Obtiene las ventas registradas en un periodo para identificar aquellas atribuibles al agente de ventas mediante `nombreVendedor`.

**Endpoint**

```text
GET {base_url}/AVA/ventas
```

**Parámetros de Consulta Soportados**

- `fechaInicio` / `fecha_inicio`: Fecha inicial del periodo (`YYYY-MM-DD`).
- `fechaFin` / `fecha_fin`: Fecha final del periodo (`YYYY-MM-DD`).
- `catalogo`: Catálogo configurado (ej. `AVA01`).
- `nombreVendedor` *(opcional en query, filtrado también en Odoo)*: `Nombre Alias` del empleado.

**Estructura de Respuesta Esperada (JSON)**

El cliente de Odoo soporta tanto una lista directa `[...]` como un objeto contenedor `{"ventas": [...]}` o `{"registros": [...]}` o `{"data": [...]}`:

```json
{
    "ventas": [
        {
            "idVenta": "V-10025",
            "folio": "F-10025",
            "fecha": "2026-11-05",
            "nombreVendedor": "ALMENDRA",
            "total": 25000.00
        }
    ]
}
```

---

### 3.2. Consultar Pagos de Ventas (`/AVA/ventas/pagos`)

Obtiene los pagos asociados a las ventas del periodo para calcular el **Total de Ventas Computables** (meta mensual o avance semanal).

**Endpoint**

```text
GET {base_url}/AVA/ventas/pagos
```

**Parámetros de Consulta Soportados**

- `fechaInicio` / `fecha_inicio`: Fecha inicial del periodo (`YYYY-MM-DD`).
- `fechaFin` / `fecha_fin`: Fecha final del periodo (`YYYY-MM-DD`).
- `catalogo`: Catálogo configurado (ej. `AVA01`).
- `idVenta` / `folio` *(en caso de consulta individual o por lote de ventas del vendedor)*.

**Estructura de Respuesta Esperada (JSON)**

```json
{
    "pagos": [
        {
            "idPago": "P-501",
            "idVenta": "V-10025",
            "nombreVendedor": "ALMENDRA",
            "fecha": "2026-11-06",
            "descripcion": "PAGO EN EFECTIVO / TRANSFERENCIA",
            "importe": 25000.00
        },
        {
            "idPago": "P-502",
            "idVenta": "V-10025",
            "nombreVendedor": "ALMENDRA",
            "fecha": "2026-11-08",
            "descripcion": "99 NOTA DE DEVOLUCI PARCIAL",
            "importe": 3500.00
        }
    ]
}
```

---

## 4. Reglas de Negocio para el Cálculo de la Meta

1. **Filtrado por Agente**: Solo se consideran las ventas/pagos cuyo vendedor (`nombreVendedor`) corresponda al **`Nombre Alias`** (`nombre_alias`) de la trabajadora evaluada.
2. **Exclusión de Devoluciones (Sección III del Esquema Legal)**:
   - Se inspecciona el campo de descripción del pago (`descripcion` / `concepto` / `tipoPago`).
   - Si la descripción contiene cualquiera de los textos:
     - **`"99 NOTA DE DEVOLUCI"`**
     - **`"DEVOLUCION DE PRODUCTO"`** *(o con tilde `"DEVOLUCIÓN DE PRODUCTO"`)*
   - Dicho registro **se excluye de la suma de la meta** y se acumula por separado en el campo informativo **`Monto Excluido (Devoluciones)`** (`excluded_returns_amount`) para dejar evidencia auditable en el esquema mensual.
3. **Total de Ventas Computables (`actual_sales`)**:
   - Es la suma de los importes (`importe` / `monto` / `total`) de todos los pagos válidos del periodo que no fueron excluidos por las reglas anteriores.

