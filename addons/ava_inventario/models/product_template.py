# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    # Clasificación AVA
    family_id = fields.Many2one(
        "product.family",
        string="Familia",
        ondelete="set null",
        index=True,
    )
    class_id = fields.Many2one(
        "product.class",
        string="Clase",
        ondelete="set null",
        index=True,
    )
    line_id = fields.Many2one(
        "product.line",
        string="Línea",
        ondelete="set null",
        index=True,
    )

    # Proveedor principal e información adicional
    primary_supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor Principal",
        compute="_compute_primary_supplier_id",
        store=True,
        readonly=False,
        index=True,
    )
    cve_prod_serv = fields.Char(
        string="Clave Prod/Serv (SAT)",
        index=True,
        help="Clave del catálogo de productos y servicios del SAT (alterno2)",
    )
    ubicacion_recomendada = fields.Char(
        string="Ubicación Recomendada",
        index=True,
        help="Ubicación física / anaquel recomendado (Columna M de Existencias)",
    )

    # Costo real y niveles de precios / márgenes de catálogo
    costo_real = fields.Float(
        string="Costo Real",
        digits="Product Price",
        help="Costo de compra real según catálogo",
    )
    plista = fields.Float(
        string="Precio Lista Base",
        digits="Product Price",
    )
    dcto_prov = fields.Float(
        string="Dcto. Proveedor (%)",
    )
    p1 = fields.Float(string="Precio 1", digits="Product Price")
    p2 = fields.Float(string="Precio 2", digits="Product Price")
    p3 = fields.Float(string="Precio 3", digits="Product Price")
    p4 = fields.Float(string="Precio 4", digits="Product Price")
    p5 = fields.Float(string="Precio 5", digits="Product Price")
    p6 = fields.Float(string="Precio 6", digits="Product Price")

    m1 = fields.Float(string="Margen 1 (%)")
    m2 = fields.Float(string="Margen 2 (%)")
    m3 = fields.Float(string="Margen 3 (%)")
    m4 = fields.Float(string="Margen 4 (%)")
    m5 = fields.Float(string="Margen 5 (%)")
    m6 = fields.Float(string="Margen 6 (%)")

    @api.depends("seller_ids", "seller_ids.partner_id", "seller_ids.sequence")
    def _compute_primary_supplier_id(self):
        for template in self:
            if not template.primary_supplier_id:
                first_seller = template.seller_ids[:1]
                template.primary_supplier_id = first_seller.partner_id if first_seller else False


class ProductProduct(models.Model):
    _inherit = "product.product"

    family_id = fields.Many2one(
        related="product_tmpl_id.family_id",
        string="Familia",
        store=True,
        readonly=False,
        index=True,
    )
    class_id = fields.Many2one(
        related="product_tmpl_id.class_id",
        string="Clase",
        store=True,
        readonly=False,
        index=True,
    )
    line_id = fields.Many2one(
        related="product_tmpl_id.line_id",
        string="Línea",
        store=True,
        readonly=False,
        index=True,
    )
    primary_supplier_id = fields.Many2one(
        related="product_tmpl_id.primary_supplier_id",
        string="Proveedor Principal",
        store=True,
        readonly=False,
        index=True,
    )
    cve_prod_serv = fields.Char(
        related="product_tmpl_id.cve_prod_serv",
        string="Clave Prod/Serv (SAT)",
        store=True,
        readonly=False,
        index=True,
    )
    ubicacion_recomendada = fields.Char(
        related="product_tmpl_id.ubicacion_recomendada",
        string="Ubicación Recomendada",
        store=True,
        readonly=False,
        index=True,
    )
    costo_real = fields.Float(
        related="product_tmpl_id.costo_real",
        string="Costo Real",
        store=True,
        readonly=False,
    )
    p1 = fields.Float(
        related="product_tmpl_id.p1",
        string="Precio 1",
        store=True,
        readonly=False,
    )
