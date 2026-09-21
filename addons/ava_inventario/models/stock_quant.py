# -*- coding: utf-8 -*-
from odoo import fields, models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    family_id = fields.Many2one(
        related="product_id.family_id",
        string="Familia",
        store=True,
        readonly=True,
        index=True,
    )
    class_id = fields.Many2one(
        related="product_id.class_id",
        string="Clase",
        store=True,
        readonly=True,
        index=True,
    )
    line_id = fields.Many2one(
        related="product_id.line_id",
        string="Línea",
        store=True,
        readonly=True,
        index=True,
    )
    supplier_id = fields.Many2one(
        related="product_id.primary_supplier_id",
        string="Proveedor",
        store=True,
        readonly=True,
        index=True,
    )
    ubicacion_recomendada = fields.Char(
        related="product_id.ubicacion_recomendada",
        string="Ubicación Recomendada",
        store=True,
        readonly=True,
        index=True,
    )
