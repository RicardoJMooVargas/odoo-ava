# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductFamily(models.Model):
    _name = "product.family"
    _description = "Familia de Productos"
    _order = "code, name"

    code = fields.Char(string="Código de Familia", index=True)
    name = fields.Char(string="Nombre de Familia", required=True, index=True)
    active = fields.Boolean(string="Activo", default=True)
    description = fields.Text(string="Descripción")

    product_count = fields.Integer(
        string="Total de Productos",
        compute="_compute_product_count",
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            if rec.code:
                rec.display_name = f"[{rec.code}] {rec.name}"
            else:
                rec.display_name = rec.name or ""

    def _compute_product_count(self):
        ProductTemplate = self.env["product.template"]
        for rec in self:
            rec.product_count = ProductTemplate.search_count([("family_id", "=", rec.id)])

    def action_view_products(self):
        self.ensure_one()
        return {
            "name": f"Productos - {self.display_name}",
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "view_mode": "list,form",
            "domain": [("family_id", "=", self.id)],
            "context": {"default_family_id": self.id},
        }


class ProductClass(models.Model):
    _name = "product.class"
    _description = "Clase de Productos"
    _order = "code, name"

    code = fields.Char(string="Código de Clase", index=True)
    name = fields.Char(string="Nombre de Clase", required=True, index=True)
    active = fields.Boolean(string="Activo", default=True)
    description = fields.Text(string="Descripción")

    product_count = fields.Integer(
        string="Total de Productos",
        compute="_compute_product_count",
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            if rec.code:
                rec.display_name = f"[{rec.code}] {rec.name}"
            else:
                rec.display_name = rec.name or ""

    def _compute_product_count(self):
        ProductTemplate = self.env["product.template"]
        for rec in self:
            rec.product_count = ProductTemplate.search_count([("class_id", "=", rec.id)])

    def action_view_products(self):
        self.ensure_one()
        return {
            "name": f"Productos - {self.display_name}",
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "view_mode": "list,form",
            "domain": [("class_id", "=", self.id)],
            "context": {"default_class_id": self.id},
        }


class ProductLine(models.Model):
    _name = "product.line"
    _description = "Línea de Productos"
    _order = "code, name"

    code = fields.Char(string="Código de Línea", index=True)
    name = fields.Char(string="Nombre de Línea", required=True, index=True)
    active = fields.Boolean(string="Activo", default=True)
    description = fields.Text(string="Descripción")

    product_count = fields.Integer(
        string="Total de Productos",
        compute="_compute_product_count",
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for rec in self:
            if rec.code:
                rec.display_name = f"[{rec.code}] {rec.name}"
            else:
                rec.display_name = rec.name or ""

    def _compute_product_count(self):
        ProductTemplate = self.env["product.template"]
        for rec in self:
            rec.product_count = ProductTemplate.search_count([("line_id", "=", rec.id)])

    def action_view_products(self):
        self.ensure_one()
        return {
            "name": f"Productos - {self.display_name}",
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "view_mode": "list,form",
            "domain": [("line_id", "=", self.id)],
            "context": {"default_line_id": self.id},
        }
