# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AvaInventorySession(models.Model):
    _name = "ava.inventory.session"
    _description = "Sesión de Conteo Físico e Inventario Diario AVA"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Referencia de Conteo",
        required=True,
        copy=False,
        default=lambda self: self._default_name(),
        tracking=True,
    )
    date = fields.Date(
        string="Fecha de Conteo",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="Responsable",
        default=lambda self: self.env.user,
        tracking=True,
    )
    warehouse_id = fields.Many2one(
        "stock.warehouse",
        string="Almacén",
        required=True,
        tracking=True,
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Ubicación Física",
        compute="_compute_location_id",
        store=True,
        readonly=False,
    )

    # Criterios de filtrado para el conteo cíclico
    family_id = fields.Many2one(
        "product.family",
        string="Filtrar por Familia",
    )
    class_id = fields.Many2one(
        "product.class",
        string="Filtrar por Clase",
    )
    line_id = fields.Many2one(
        "product.line",
        string="Filtrar por Línea",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Filtrar por Proveedor",
        domain=[("supplier_rank", ">", 0)],
    )
    ubicacion_recomendada = fields.Char(
        string="Filtrar por Ubicación Recomendada",
    )
    only_with_stock = fields.Boolean(
        string="Solo productos con existencia > 0",
        default=False,
    )

    state = fields.Selection(
        [
            ("draft", "Borrador"),
            ("in_progress", "En Conteo"),
            ("done", "Ajuste Aplicado"),
            ("cancel", "Cancelado"),
        ],
        string="Estado",
        default="draft",
        tracking=True,
    )

    line_ids = fields.One2many(
        "ava.inventory.session.line",
        "session_id",
        string="Líneas de Conteo",
    )

    # Métricas de resumen
    line_count = fields.Integer(
        string="Total de Artículos",
        compute="_compute_metrics",
    )
    lines_with_difference = fields.Integer(
        string="Artículos con Diferencia",
        compute="_compute_metrics",
    )
    total_theoretical_qty = fields.Float(
        string="Existencia Teórica Total",
        compute="_compute_metrics",
    )
    total_counted_qty = fields.Float(
        string="Existencia Contada Total",
        compute="_compute_metrics",
    )
    total_difference_qty = fields.Float(
        string="Diferencia Total (Pzas)",
        compute="_compute_metrics",
    )
    total_difference_value = fields.Float(
        string="Impacto Monetario ($)",
        compute="_compute_metrics",
    )

    notes = fields.Text(string="Notas y Observaciones")

    def _default_name(self):
        return f"CONTEO-{fields.Date.today().strftime('%Y%m%d')}"

    @api.depends("warehouse_id")
    def _compute_location_id(self):
        for rec in self:
            if rec.warehouse_id:
                rec.location_id = rec.warehouse_id.lot_stock_id.id
            else:
                rec.location_id = False

    @api.depends(
        "line_ids",
        "line_ids.theoretical_qty",
        "line_ids.counted_qty",
        "line_ids.difference_qty",
        "line_ids.difference_value",
    )
    def _compute_metrics(self):
        for rec in self:
            lines = rec.line_ids
            rec.line_count = len(lines)
            rec.lines_with_difference = sum(1 for l in lines if abs(l.difference_qty) > 0.0001)
            rec.total_theoretical_qty = sum(lines.mapped("theoretical_qty"))
            rec.total_counted_qty = sum(lines.mapped("counted_qty"))
            rec.total_difference_qty = sum(lines.mapped("difference_qty"))
            rec.total_difference_value = sum(lines.mapped("difference_value"))

    def action_start(self):
        """Inicia el conteo y carga productos si la lista está vacía."""
        for rec in self:
            if not rec.line_ids:
                rec.action_load_products()
            rec.state = "in_progress"

    def action_load_products(self):
        """Busca los productos según los filtros seleccionados y llena las líneas de conteo."""
        self.ensure_one()
        if self.state not in ["draft", "in_progress"]:
            raise UserError(_("No puede recargar productos en una sesión finalizada o cancelada."))

        if not self.location_id:
            raise UserError(_("Debe especificar un almacén o ubicación válida."))

        # 1. Construir dominio de productos
        domain = [("active", "=", True)]
        if self.family_id:
            domain.append(("family_id", "=", self.family_id.id))
        if self.class_id:
            domain.append(("class_id", "=", self.class_id.id))
        if self.line_id:
            domain.append(("line_id", "=", self.line_id.id))
        if self.partner_id:
            domain.append(("primary_supplier_id", "=", self.partner_id.id))
        if self.ubicacion_recomendada:
            domain.append(("ubicacion_recomendada", "=", self.ubicacion_recomendada))

        products = self.env["product.product"].search(domain)
        if not products:
            raise UserError(_("No se encontraron productos que coincidan con los filtros seleccionados."))

        # 2. Obtener existencias actuales en la ubicación
        quants = self.env["stock.quant"].search([
            ("location_id", "=", self.location_id.id),
            ("product_id", "in", products.ids),
        ])
        quant_dict = {q.product_id.id: q.quantity for q in quants}

        # 3. Preparar líneas
        existing_products = self.line_ids.mapped("product_id.id")
        new_lines = []
        for p in products:
            theoretical = quant_dict.get(p.id, 0.0)
            if self.only_with_stock and theoretical <= 0:
                continue
            if p.id in existing_products:
                continue

            cost = p.standard_price or p.costo_real or 0.0
            new_lines.append((0, 0, {
                "product_id": p.id,
                "theoretical_qty": theoretical,
                "counted_qty": theoretical,  # Inicializa con la teórica
                "standard_price": cost,
                "is_counted": False,
            }))

        if new_lines:
            self.write({"line_ids": new_lines})

        return True

    def action_set_counted_equal_theoretical(self):
        """Asigna a todos los artículos la cantidad contada igual a la teórica."""
        for line in self.line_ids:
            line.write({
                "counted_qty": line.theoretical_qty,
                "is_counted": True,
            })

    def action_apply_inventory(self):
        """Aplica el ajuste de inventario en Odoo a través de stock.quant."""
        self.ensure_one()
        if self.state != "in_progress":
            raise UserError(_("Solo se pueden aplicar ajustes de sesiones en estado 'En Conteo'."))

        Quant = self.env["stock.quant"].with_context(inventory_mode=True)
        adjusted_count = 0

        for line in self.line_ids:
            # Solo ajustar si fue marcado como contado o si hay discrepancia
            if abs(line.difference_qty) > 0.0001:
                # Buscar quant existente
                quant = Quant.search([
                    ("product_id", "=", line.product_id.id),
                    ("location_id", "=", self.location_id.id),
                ], limit=1)

                if not quant:
                    quant = Quant.create({
                        "product_id": line.product_id.id,
                        "location_id": self.location_id.id,
                        "inventory_quantity": line.counted_qty,
                    })
                else:
                    quant.inventory_quantity = line.counted_qty

                quant.action_apply_inventory()
                adjusted_count += 1

        self.write({"state": "done"})
        self.message_post(body=_(
            "Ajuste de inventario aplicado exitosamente. Se actualizaron %d productos con discrepancia.",
            adjusted_count,
        ))
        return True

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_reset_draft(self):
        self.write({"state": "draft"})


class AvaInventorySessionLine(models.Model):
    _name = "ava.inventory.session.line"
    _description = "Línea de Conteo Físico AVA"
    _order = "ubicacion_recomendada, default_code, id"

    session_id = fields.Many2one(
        "ava.inventory.session",
        string="Sesión de Conteo",
        required=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "product.product",
        string="Producto",
        required=True,
        domain=[("active", "=", True)],
    )

    # Campos informativos relacionados
    default_code = fields.Char(
        related="product_id.default_code",
        string="Código / Ref",
        readonly=True,
    )
    barcode = fields.Char(
        related="product_id.barcode",
        string="Cód. Barras",
        readonly=True,
    )
    uom_id = fields.Many2one(
        related="product_id.uom_id",
        string="Unidad",
        readonly=True,
    )
    family_id = fields.Many2one(
        related="product_id.family_id",
        string="Familia",
        readonly=True,
    )
    class_id = fields.Many2one(
        related="product_id.class_id",
        string="Clase",
        readonly=True,
    )
    line_id = fields.Many2one(
        related="product_id.line_id",
        string="Línea",
        readonly=True,
    )
    supplier_id = fields.Many2one(
        related="product_id.primary_supplier_id",
        string="Proveedor",
        readonly=True,
    )
    ubicacion_recomendada = fields.Char(
        related="product_id.ubicacion_recomendada",
        string="Ubic. Recomendada",
        readonly=True,
    )

    # Existencias y conteo
    theoretical_qty = fields.Float(
        string="Teórica (Sistema)",
        digits="Product Unit of Measure",
        readonly=True,
    )
    counted_qty = fields.Float(
        string="Física (Contada)",
        digits="Product Unit of Measure",
    )
    difference_qty = fields.Float(
        string="Diferencia",
        compute="_compute_difference",
        store=True,
        digits="Product Unit of Measure",
    )
    standard_price = fields.Float(
        string="Costo Unitario",
        digits="Product Price",
        readonly=True,
    )
    difference_value = fields.Float(
        string="Valor Diferencia ($)",
        compute="_compute_difference",
        store=True,
        digits="Product Price",
    )
    is_counted = fields.Boolean(
        string="Contado",
        default=False,
    )

    @api.depends("theoretical_qty", "counted_qty", "standard_price")
    def _compute_difference(self):
        for line in self:
            diff = line.counted_qty - line.theoretical_qty
            line.difference_qty = diff
            line.difference_value = diff * (line.standard_price or 0.0)
