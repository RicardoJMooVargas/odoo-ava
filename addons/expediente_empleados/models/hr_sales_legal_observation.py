# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .hr_sales_scheme import SPANISH_MONTHS


class HrSalesLegalObservation(models.Model):
    _name = "hr.sales.legal.observation"
    _description = "Observación Legal, Desviación y Medidas de Mejora (Sección VIII)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    name = fields.Char(
        string="Folio de Observación",
        compute="_compute_name",
        store=True,
        readonly=False,
    )
    scheme_id = fields.Many2one(
        "hr.sales.scheme",
        string="Esquema Mensual Evaluado",
        required=True,
        ondelete="cascade",
        tracking=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Persona trabajadora",
        required=True,
        tracking=True,
    )
    nombre_alias = fields.Char(
        related="employee_id.nombre_alias",
        string="Nombre Alias (AVA_API)",
        readonly=True,
    )
    manager_id = fields.Many2one(
        "hr.employee",
        string="Responsable del área",
        tracking=True,
    )
    date = fields.Date(
        string="Fecha de documentación",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    incident_type = fields.Selection(
        [
            ("produccion_critica", "1. Nivel de producción críticamente bajo (Sección IV.1)"),
            ("incumplimiento_actividades", "2. Incumplimiento de actividades comerciales asignadas (Sección VII)"),
            ("desviacion_relevante", "3. Desviación relevante respecto del desempeño esperado"),
        ],
        string="Causa de la documentación (Sección VIII)",
        required=True,
        default="produccion_critica",
        tracking=True,
    )
    breached_obligation_ids = fields.Many2many(
        "hr.sales.obligation",
        "hr_sales_obs_obligation_rel",
        "observation_id",
        "obligation_id",
        string="Obligaciones comerciales señaladas (Sección VII)",
    )

    # ── LOS 5 PUNTOS OBLIGATORIOS DEL ABOGADO (SECCIÓN VIII) ──────────────────
    results_and_period = fields.Text(
        string="1. Los resultados obtenidos y el periodo evaluado",
        required=True,
        tracking=True,
    )
    facts_and_data = fields.Text(
        string="2. Los hechos y datos que sustentan la evaluación",
        required=True,
        tracking=True,
        help="Describe de forma objetiva, verificable y sin juicios de valor los hechos y registros comerciales que sustentan la desviación.",
    )
    activities_to_correct = fields.Text(
        string="3. Las actividades que deberán corregirse o mejorarse",
        required=True,
        tracking=True,
    )
    goals_and_deadlines = fields.Text(
        string="4. Los objetivos y plazos para verificar los avances",
        required=True,
        tracking=True,
    )
    verification_date = fields.Date(
        string="Fecha programada de verificación de avances",
        tracking=True,
    )
    employee_statement = fields.Text(
        string="5. Las observaciones de la persona trabajadora",
        tracking=True,
        help="La persona trabajadora podrá manifestar por escrito las circunstancias que expliquen sus resultados y aportar la información que considere pertinente.",
    )

    # ── TESTIGOS E IMPRESIÓN / SUBIDA DE PDF FIRMADO ──────────────────────────
    witness_1 = fields.Char(string="Testigo 1")
    witness_2 = fields.Char(string="Testigo 2")
    signed_observation_pdf_ids = fields.Many2many(
        "ir.attachment",
        "hr_sales_obs_signed_pdf_rel",
        "observation_id",
        "attachment_id",
        string="Acta de Observación Firmada (PDF)",
        help="Imprime el formato en PDF, recaba las firmas físicas (y observaciones de puño y letra si aplica) y sube aquí el PDF escaneado ya firmado.",
    )
    state = fields.Selection(
        [
            ("borrador", "Borrador"),
            ("notificado", "Firmado y Notificado"),
            ("en_seguimiento", "En Seguimiento de Mejora"),
            ("cumplido", "Medidas Cumplidas"),
            ("incumplido", "Medidas Incumplidas"),
        ],
        string="Estado",
        default="borrador",
        tracking=True,
    )

    @api.onchange("scheme_id")
    def _onchange_scheme_id(self):
        for rec in self:
            if rec.scheme_id:
                rec.employee_id = rec.scheme_id.employee_id
                rec.manager_id = rec.scheme_id.manager_id
                if not rec.results_and_period:
                    rec.results_and_period = (
                        f"Periodo evaluado: {rec.scheme_id.period_display}\n"
                        f"Meta mensual establecida: ${rec.scheme_id.target_amount:,.2f} "
                        f"({rec.scheme_id.target_amount_text})\n"
                        f"Ventas computables registradas en AVA_API: ${rec.scheme_id.actual_sales:,.2f} "
                        f"({rec.scheme_id.compliance_percentage:.2f}% de cumplimiento)\n"
                        f"Devoluciones excluidas: ${rec.scheme_id.excluded_returns_amount:,.2f}"
                    )

    @api.depends("employee_id.name", "date", "scheme_id.period_start")
    def _compute_name(self):
        for rec in self:
            d = rec.date or fields.Date.context_today(rec)
            emp_name = rec.employee_id.name or _("Sin Empleado")
            rec.name = f"OBS-{d.year}-{d.month:02d}-{d.day:02d} - {emp_name}"

    def _format_date_legal(self):
        self.ensure_one()
        d = self.date or fields.Date.context_today(self)
        month_name = SPANISH_MONTHS.get(d.month, "")
        return f"A los {d.day:02d} días del mes de {month_name} del {d.year}."

    def action_print_observation_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "expediente_empleados.action_report_hr_sales_legal_observation"
        ).report_action(self)

    def action_mark_notified(self):
        for rec in self:
            if not rec.signed_observation_pdf_ids:
                raise UserError(
                    _(
                        "Para marcar esta observación como Firmada y Notificada, primero debes imprimir el Acta en PDF, "
                        "recabar la firma física de la trabajadora (o testigos) y subir el PDF firmado en "
                        "'Acta de Observación Firmada (PDF)'."
                    )
                )
            rec.state = "notificado"
            rec.message_post(
                body=_("Acta de Observación y Medidas de Mejora firmada y subida en PDF al expediente.")
            )

    def action_start_followup(self):
        for rec in self:
            if not rec.signed_observation_pdf_ids:
                raise UserError(_("Debes adjuntar el PDF firmado antes de pasar a seguimiento."))
            rec.state = "en_seguimiento"

    def action_mark_fulfilled(self):
        for rec in self:
            rec.state = "cumplido"

    def action_mark_unfulfilled(self):
        for rec in self:
            rec.state = "incumplido"

    def action_reset_draft(self):
        for rec in self:
            rec.state = "borrador"

