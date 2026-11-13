# API web de Infor

Documentación de los endpoints utilizados por la integración con Infor.

## Índice

- [Compras](#compras)
    - [Buscar proveedores](#buscar-proveedores)
    - [Buscar información de artículos](#buscar-información-de-artículos)
- [Pedidos](#pedidos)
    - [Obtener parámetros](#obtener-parámetros)
    - [Obtener almacenes](#obtener-almacenes)
    - [Obtener agentes](#obtener-agentes)
- [Pendientes](#pendientes)

## Convenciones

Cada endpoint incluye la URL de consulta, sus parámetros de entrada y un ejemplo de la respuesta JSON.

- `catalogo`: catálogo de Infor utilizado en la consulta. En los ejemplos es `AVA01`.
- Las respuestas se muestran con el formato recibido desde el servicio.

## Compras

### Buscar proveedores

**Endpoint**

```text
https://logichounds.com/INFORWEB/BuscarProveedores?catalogo=AVA01&texto=LA%20VIGA%20EXTRUSIONES%09
```

**Entrada**

```text
catalogo=AVA01&texto=LA%20VIGA%20EXTRUSIONES%09
```

**Salida**

```json
{
    "proveedores": [
        {
            "id": "000004",
            "nomcor": "LA VIGA",
            "nombre": "LA VIGA EXTRUSIONES",
            "diascred": 0
        }
    ]
}
```

### Buscar información de artículos

**Endpoint**

```text
https://logichounds.com/INFORWEB/BuscarArticuloInfo?catalogo=AVA01&texto=HERR66TEXT
```

**Entrada**

```text
catalogo=AVA01&texto=HERR66TEXT
```

**Salida**

```json
{
    "registros": [
        {
            "id": "330-HERR66TEXT",
            "alterno": "HERR66TEXT",
            "traduccion": "",
            "descripcion": "LAM PANEL MDF MASISA CEREZO TEXTURIZADO ARAUCO 5.5MM 1.22 X 2.44 MTS",
            "impuesto": 16.0000,
            "unidad": "PZA",
            "costoReal": 703.5600,
            "descuentoProveedor": 15.0000,
            "ieps": 0.0000,
            "costoKilo": false
        }
    ]
}
```

## Pedidos

### Obtener parámetros

**Endpoint**

```text
https://logichounds.com/INFORWEB/ObtenerParametrosSinSeriesNiPrecios?catalogo=AVA01
```

**Entrada**

```text
catalogo=AVA01
```

**Salida**

```json
{
    "result_code": 200,
    "data": {
        "mmticketValor1": "",
        "mmticketValor3": "",
        "facturaEnCajaFisica": false,
        "descuentosManualesCantidad": 1,
        "descuentosPorLinea": true,
        "existenciaGrupalVentas": true,
        "precios": [],
        "validarRFC": false,
        "timbrarGlobales": false,
        "timbrarNotas": false,
        "seriePf": "",
        "seriePr": "",
        "formRemision": "INFOR",
        "formFactura": "INFOR",
        "formEstCuenta": "INFOR",
        "formAbono": "",
        "consultaGrupalActivo": true,
        "diasARevisar": 60,
        "cantidadASugerir": 10,
        "cotizacionValorRaw": "5",
        "cotizacionActiva": false,
        "escalaActiva": false,
        "escalaRangos": false,
        "esNotiActivo": true,
        "almacenEsPrincipal": true,
        "convertirTraspaso": false,
        "mutDirecActivo": true,
        "valExistActivo": false,
        "invPriMovActivo": true,
        "verSaldosActivo": false,
        "canCapVenActivo": true,
        "valSurPedActivo": false,
        "aparPedActivo": false,
        "formaPagoFacturaGlobal": "00",
        "pedidExistActivo": false,
        "asigConImpActivo": false,
        "fechaRemp": "",
        "serieFg": "",
        "serieNg": "",
        "serieFge": "",
        "fgV2": "",
        "ngV2": "",
        "fgeV2": "",
        "formPedidosValor1": "INFOR",
        "formPedidosValor2": "OFERTAS",
        "formPedidosValor3": false,
        "pagareActivo": false,
        "descGralValor1": "FALSE",
        "descGralValor2": "0",
        "vistaGridPedidosVentas": false,
        "buscadorConImagenes": false,
        "fgMasudaV1": "",
        "ngMasudaV1": "",
        "fgeMasudaV1": "",
        "seriesProveedorEspeciales": [],
        "mostrarAnticipos": false,
        "validarDisponible": false,
        "retencionIsr": "0",
        "retencionIva": "0",
        "ordenListaVenta": "RECIENTE"
    }
}
```

### Obtener almacenes

**Endpoint**

```text
https://logichounds.com/INFORWEB/ObtenerAlmacenes?catalogo=AVA01
```

**Entrada**

```text
catalogo=AVA01
```

**Salida**

```json
{
    "almacenes": [
        {
            "id": "003",
            "descripcion": "BODEGA MADERA AVA03",
            "codigo": "AVA03",
            "almacenPrincipal": true
        },
        {
            "id": "002",
            "descripcion": "BODEGA SECUNDARIA AVA02",
            "codigo": "AVA02",
            "almacenPrincipal": true
        },
        {
            "id": "004",
            "descripcion": "BODEGA VINILOS AVA04",
            "codigo": "AVA04",
            "almacenPrincipal": true
        },
        {
            "id": "001",
            "descripcion": "PRINCIPAL ARMANDO VIDRIOS Y ALUMINIOS AVA01",
            "codigo": "AVA01",
            "almacenPrincipal": true
        }
    ]
}
```

### Obtener agentes

**Endpoint**

```text
https://logichounds.com/INFORWEB/ObtenerAgentes?catalogo=AVA01&usuario=ADMIN
```

**Entrada**

```text
catalogo=AVA01&usuario=ADMIN
```

**Salida**

```json
{
    "registros": [
        {
            "id": "001",
            "nombre": "ALEJANDRA"
        },
        {
            "id": "016",
            "nombre": "ALMENDRA"
        },
        {
            "id": "004",
            "nombre": "AMANDA"
        },
        {
            "id": "006",
            "nombre": "CAMBIA NOMBRE DE FAVOR"
        },
        {
            "id": "014",
            "nombre": "CANDY"
        },
        {
            "id": "010",
            "nombre": "CARDOZO"
        },
        {
            "id": "005",
            "nombre": "CAROLINA"
        },
        {
            "id": "007",
            "nombre": "ELIZA"
        },
        {
            "id": "012",
            "nombre": "FERNANDO"
        },
        {
            "id": "011",
            "nombre": "MARGARITA"
        },
        {
            "id": "015",
            "nombre": "NICOLE"
        },
        {
            "id": "003",
            "nombre": "OMAR"
        },
        {
            "id": "002",
            "nombre": "ROCIO"
        },
        {
            "id": "009",
            "nombre": "TENO"
        },
        {
            "id": "013",
            "nombre": "WENDY"
        },
        {
            "id": "008",
            "nombre": "XXXX"
        }
    ]
}
```

## Endpoints de Ventas y Pagos (`AVA_API`)

Consulta la documentación detallada en [ava_api.md](ava_api.md) para el consumo desde Odoo:

1. **`/AVA/ventas`**
     - Entrada: `catalogo`, `fechaInicio`, `fechaFin` (y credenciales configurables en Ajustes de Odoo).
     - Salida: Lista de ventas con `nombreVendedor` (empatado con el campo **Nombre Alias** del empleado en Odoo).
2. **`/AVA/ventas/pagos`**
     - Entrada: `catalogo`, `fechaInicio`, `fechaFin` / `idVenta`.
     - Salida: Lista de pagos de las ventas del periodo. Se suman los importes para calcular la meta mensual, **excluyendo** los pagos cuya descripción contenga `"99 NOTA DE DEVOLUCI"` o `"DEVOLUCION DE PRODUCTO"`.




