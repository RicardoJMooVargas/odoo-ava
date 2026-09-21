# -*- coding: utf-8 -*-
{
    "name": "AVA - Clasificación de Productos e Inventario Físico",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Clasificación por Familia, Clase, Línea, almacenes AVA01-AVA04, importadores y conteos físicos diarios",
    "description": """
Módulo personalizado para Armando Vidrios y Aluminios (AVA):
============================================================
* Clasificación inherente de productos por Familia, Clase y Línea (sin variantes).
* Proveedor principal, códigos alternos SAT y de barras, niveles de precios de catálogo (p1-p6, márgenes y costo real).
* Creación y sincronización de almacenes AVA:
    - AVA01: PRINCIPAL ARMANDO VIDRIOS Y ALUMINIOS (suministro y compras)
    - AVA02: BODEGA SECUNDARIA
    - AVA03: BODEGA MADERA
    - AVA04: BODEGA VINILOS
* Asistente de importación de Catálogo de Productos desde CSV.
* Asistente de importación de Existencias por Almacén y Ubicación recomendada (Columna M).
* Sesiones interactivas de Conteo Físico e Inventario Diario con filtros por clasificación y proveedor.
* Filtros avanzados y agrupación en Ajustes de Inventario (stock.quant).
    """,
    "author": "Ricardo Moo / AVA",
    "depends": [
        "base",
        "product",
        "stock",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/product_classification_views.xml",
        "views/product_template_views.xml",
        "views/stock_quant_views.xml",
        "views/inventory_session_views.xml",
        "views/wizard_views.xml",
        "views/menu_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
