# Documentación de Integración con `AVA_API` (Ventas y Metas Comerciales)

Esta guía documenta el consumo de `POST /AVA/Token`, `GET /AVA/ventas` y `GET /AVA/ventas/pagos` dentro de Odoo 19 (`expediente_empleados`) conforme al documento oficial **[AVA_API_Documentacion.pdf](file:///c:/Users/MiniPCTab/Repos/odoo-ava/AVA_API_Documentacion.pdf)**.

---

## 1. Los 3 Parámetros de Autenticación en Odoo

Las credenciales se configuran en **Metas y Observaciones -> Configuración AVA_API** (o en **Empleados -> Metas y Observaciones Legales -> Configuración AVA_API**) y se guardan en `ir.config_parameter`:

| Parámetro en Odoo (`ir.config_parameter`) | Dato entregado | Uso en las Peticiones |
| :--- | :--- | :--- |
| `ava_api.api_key` | **1. API key** | Se envía en la cabecera `X-Api-Key` en **todas** las peticiones (`POST /AVA/Token` y métodos `GET`). |
| `ava_api.client_id` | **2. ClientId** | Se envía en el cuerpo JSON de `POST /AVA/Token`. |
| `ava_api.client_secret` | **3. ClientSecret** | Se envía en el cuerpo JSON de `POST /AVA/Token`. |
| `ava_api.base_url` | **URL Base** | `https://sistemainforweb.com` (o `https://logichounds.com`). |

---

## 2. Flujo de Obtención y Caché del Token (`POST /AVA/Token`)

1. Odoo solicita un token JWT enviando:
   - Cabeceras: `X-Api-Key: <API_KEY>` y `Content-Type: application/json`
   - Cuerpo JSON:
     ```json
     {
       "ClientId": "<ClientId>",
       "ClientSecret": "<ClientSecret>"
     }
     ```
2. La respuesta devuelve `access_token` con vigencia de 15 minutos (`expires_in: 900`).
3. Odoo almacena en caché el `access_token` durante 14 minutos (`expires_in - 60s`) para reutilizarlo en múltiples consultas sin superar el límite de 10 peticiones por minuto de `/AVA/Token`.
4. En cada método `GET`, Odoo envía **ambas cabeceras**:
   - `Authorization: Bearer <access_token>`
   - `X-Api-Key: <API_KEY>`

---

## 3. Consulta de Ventas y Pagos por Agente

### 3.1. Listar Ventas (`GET /AVA/ventas`)

- **Query params**:
  - `desde`: `yyyy-MM-dd` (inicio del periodo)
  - `hasta`: `yyyy-MM-dd` (fin del periodo; si el rango supera 31 días, Odoo lo divide automáticamente en bloques de hasta 31 días).
  - `estatus`: `A` (ventas activas).
- **Filtrado en Odoo**:
  - Se filtran las ventas cuyo campo `nombreVendedor` coincida con el campo **`Nombre Alias`** (`nombre_alias`) configurado en la ficha de `hr.employee`.

### 3.2. Pagos de cada Venta (`GET /AVA/ventas/pagos`)

Por cada venta activa del vendedor (`nombreVendedor == nombre_alias`), se consulta `/AVA/ventas/pagos` enviando los campos de identificación de la venta:
- `tipo`: Campo `tipo` de la venta (`N` nota, `F` factura).
- `caja`: Campo `caja` de la venta (ej. `09`).
- `serie`: Campo `serie` de la venta (si no está vacía).
- `folio`: Campo `folio` de 6 dígitos (ej. `011215`).

**Regla de Exclusión de Devoluciones**:
- Se inspecciona el campo `descripcion` de cada pago en el arreglo `pagos`.
- Si contiene **`"99 NOTA DE DEVOLUCI"`** o **`"DEVOLUCION DE PRODUCTO"`**, su `importe` **no se suma a la meta** y se acumula por separado en `excluded_returns_amount` (*Monto excluido por devoluciones*).
- Todos los demás pagos se suman en `actual_sales` (*Ventas computables del mes*).
