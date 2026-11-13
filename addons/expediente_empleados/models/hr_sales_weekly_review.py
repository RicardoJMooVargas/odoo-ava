# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrSalesWeeklyReview(models.Model):
    _name = "hr.sales.weekly.review"
    _description = "Seguimiento Semanal del Desempeño Comercial (Sección VI)"
    _order = "review_date desc, id desc"

    scheme_id = fields.Many2one(
        "hr.sales.scheme",
        string="Esquema Mensual",
        required=True,
        ondelete="cascade",
    )
    employee_id = fields.Many2one(
        "hr.employee",
        related="scheme_id.employee_id",
        string="Trabajadora",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="scheme_id.currency_id",
        readonly=True,
    )
    review_date = fields.Date(
        string="Fecha de revisión",
        required=True,
        default=fields.Date.context_today,
    )
    week_number = fields.Selection(
        [
            ("1", "Semana 1"),
            ("2", "Semana 2"),
            ("3", "Semana 3"),
            ("4", "Semana 4"),
            ("5", "Semana 5 / Cierre"),
        ],
        string="Semana del mes",
        required=True,
        default="1",
    )
    reviewer_id = fields.Many2one(
        "hr.employee",
        string="Persona responsable que revisa",
        default=lambda self: self.env.user.employee_id,
    )

    # ── a) La meta mensual y el importe de ventas acumuladas ──────────────────
    target_amount = fields.Monetary(
        related="scheme_id.target_amount",
        string="a) Meta mensual ($)",
        currency_field="currency_id",
        readonly=True,
    )
    accumulated_sales = fields.Monetary(
        string="a) Importe de ventas acumuladas al corte ($)",
        currency_field="currency_id",
        required=True,
        default=0.0,
    )
    excluded_returns_amount = fields.Monetary(
        string="Devoluciones excluidas al corte ($)",
        currency_field="currency_id",
        readonly=True,
        default=0.0,
    )

    # ── b) El porcentaje de cumplimiento alcanzado ────────────────────────────
    compliance_pct = fields.Float(
        string="b) % de cumplimiento alcanzado",
        compute="_compute_compliance_pct",
        store=True,
    )

    # ── c), d) y e) ───────────────────────────────────────────────────────────
    tracked_quotes_orders = fields.Text(
        string="c) Cotizaciones, oportunidades comerciales y pedidos en seguimiento",
        required=True,
    )
    activities_and_obstacles = fields.Text(
        string="d) Actividades realizadas y obstáculos identificados",
        required=True,
    )
    agreed_actions_support = fields.Text(
        string="e) Acciones de mejora acordadas y apoyos de LA EMPRESA",
        required=True,
    )

    # ── Documentación de la revisión (Reporte, Correo, WhatsApp, Minuta, PDF) ─
    documentation_medium = fields.Selection(
        [
            ("minuta", "Minuta firmada"),
            ("formato_interno", "Formato interno"),
            ("reporte_comercial", "Reporte comercial"),
            ("correo", "Correo electrónico"),
            ("whatsapp", "Mensajería de WhatsApp"),
        ],
        string="Medio de documentación",
        default="minuta",
        required=True,
    )
    signed_review_pdf_ids = fields.Many2many(
        "ir.attachment",
        "hr_sales_weekly_review_pdf_rel",
        "review_id",
        "attachment_id",
        string="Evidencia / Minuta en PDF Firmada",
        help="Adjunta el PDF escaneado firmado de la minuta semanal, capturas de WhatsApp o reporte comercial.",
    )

    @api.depends("accumulated_sales", "target_amount")
    def _compute_compliance_pct(self):
        for rec in self:
            if rec.target_amount > 0:
                rec.compliance_pct = round((rec.accumulated_sales / rec.target_amount) * 100.0, 2)
            else:
                rec.compliance_pct = 0.0

    def action_sync_weekly_ava_sales(self):
        self.ensure_one()
        alias = self.scheme_id.employee_id.nombre_alias
        if not alias:
            raise UserError(
                _("La trabajadora '%s' no tiene configurado un 'Nombre Alias' en su ficha.")
                % self.scheme_id.employee_id.name
            )
        end_date = min(self.review_date, self.scheme_id.period_end) if self.scheme_id.period_end else self.review_date
        result = self.env["ava.api.service"].fetch_agent_sales_and_payments(
            nombre_alias=alias,
            date_start=self.scheme_id.period_start,
            date_end=end_date,
        )
        self.write({
            "accumulated_sales": result["valid_sales_amount"],
            "excluded_returns_amount": result["excluded_returns_amount"],
        })
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Avance semanal sincronizado con AVA_API"),
                "message": _(
                    "Ventas acumuladas al %s: $%s (%s%% de la meta)."
                )
                % (end_date, f"{result['valid_sales_amount']:,.2f}", f"{self.compliance_pct:.2f}"),
                "type": "success",
                "sticky": False,
            },
        }

