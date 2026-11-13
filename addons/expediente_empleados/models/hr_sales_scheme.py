# -*- coding: utf-8 -*-
import calendar
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .res_config_settings import DEFAULT_SCHEME_OBJECTIVE

SPANISH_MONTHS = {
    1: "ENERO",
    2: "FEBRERO",
    3: "MARZO",
    4: "ABRIL",
    5: "MAYO",
    6: "JUNIO",
    7: "JULIO",
    8: "AGOSTO",
    9: "SEPTIEMBRE",
    10: "OCTUBRE",
    11: "NOVIEMBRE",
    12: "DICIEMBRE",
}


def _int_to_spanish(n):
    unidades = [
        "", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE",
        "DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", "DIECISEIS", "DIECISIETE",
        "DIECIOCHO", "DIECINUEVE", "VEINTE", "VEINTIUN", "VEINTIDOS", "VEINTITRES",
        "VEINTICUATRO", "VEINTICINCO", "VEINTISEIS", "VEINTISIETE", "VEINTIOCHO", "VEINTINUEVE",
    ]
    decenas = [
        "", "DIEZ", "VEINTE", "TREINTA", "CUARENTA", "CINCUENTA",
        "SESENTA", "SETENTA", "OCHENTA", "NOVENTA",
    ]
    centenas = [
        "", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS",
        "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS",
    ]
    if n == 0:
        return "CERO"
    if n == 100:
        return "CIEN"
    if n < 30:
        return unidades[n]
    if n < 100:
        d, u = divmod(n, 10)
        return decenas[d] if u == 0 else f"{decenas[d]} Y {unidades[u]}"
    if n < 1000:
        c, r = divmod(n, 100)
        return centenas[c] if r == 0 else f"{centenas[c]} {_int_to_spanish(r)}"
    if n < 1000000:
        miles, r = divmod(n, 1000)
        pref = "MIL" if miles == 1 else f"{_int_to_spanish(miles)} MIL"
        return pref if r == 0 else f"{pref} {_int_to_spanish(r)}"
    millones, r = divmod(n, 1000000)
    pref = "UN MILLON" if millones == 1 else f"{_int_to_spanish(millones)} MILLONES"
    return pref if r == 0 else f"{pref} {_int_to_spanish(r)}"


def amount_to_spanish_words(amount):
    if not amount or amount <= 0:
        return "CERO PESOS 00/100 M.N."
    entero = int(round(amount, 2))
    centavos = int(round((round(amount, 2) - entero) * 100))
    moneda = "PESO" if entero == 1 else "PESOS"
    return f"{_int_to_spanish(entero)} {moneda} {centavos:02d}/100 M.N."


class HrSalesObligation(models.Model):
    _name = "hr.sales.obligation"
    _description = "Obligación Comercial (Sección VII del Esquema)"
    _order = "code, id"

    code = fields.Char(string="Inciso", required=True)
    name = fields.Char(string="Obligación Comercial", required=True)
    active = fields.Boolean(default=True)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code}) {rec.name}" if rec.code else rec.name


class HrSalesIncentiveLine(models.Model):
    _name = "hr.sales.incentive.line"
    _description = "Línea de Esquema de Incentivos Económicos (Sección V)"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    scheme_id = fields.Many2one(
        "hr.sales.scheme",
        string="Esquema Mensual",
        required=True,
        ondelete="cascade",
    )
    compliance_level = fields.Selection(
        [
            ("meta_alcanzada", "Meta alcanzada"),
            ("meta_superada", "Meta superada"),
        ],
        string="Nivel de cumplimiento",
        required=True,
        default="meta_alcanzada",
    )
    period_sales_text = fields.Char(
        string="Ventas del periodo",
        required=True,
        placeholder="Ej. De $150,000.00 a $199,999.99",
    )
    commission_text = fields.Char(
        string="Comisión",
        required=True,
        placeholder="Ej. 2.0% sobre ventas cobradas / $3,000.00",
    )


class HrSalesScheme(models.Model):
    _name = "hr.sales.scheme"
    _description = "Esquema Mensual de Metas Comerciales, Evaluación e Incentivos"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "period_start desc, id desc"

    name = fields.Char(
        string="Referencia del Esquema",
        compute="_compute_name",
        store=True,
        readonly=False,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Empresa",
        default=lambda self: self.env.company,
        required=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
    )

    # ── I. DATOS GENERALES DE LA TRABAJADORA ──────────────────────────────────
    employee_id = fields.Many2one(
        "hr.employee",
        string="Nombre de la persona trabajadora",
        required=True,
        tracking=True,
    )
    nombre_alias = fields.Char(
        related="employee_id.nombre_alias",
        string="Nombre Alias (AVA_API)",
        readonly=False,
    )
    job_title = fields.Char(
        string="Puesto",
        default="Agente de ventas",
        required=True,
    )
    area_name = fields.Char(
        string="Área",
        default="Ventas",
        required=True,
    )
    manager_id = fields.Many2one(
        "hr.employee",
        string="Responsable del área",
        tracking=True,
    )
    communication_date = fields.Date(
        string="Fecha de comunicación del esquema",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help="La meta y condiciones económicas deben comunicarse antes del inicio del periodo.",
    )
    period_start = fields.Date(
        string="Inicio del periodo de evaluación",
        required=True,
        default=lambda self: self._default_period_start(),
        tracking=True,
    )
    period_end = fields.Date(
        string="Fin del periodo de evaluación",
        required=True,
        default=lambda self: self._default_period_end(),
        tracking=True,
    )
    period_display = fields.Char(
        string="Periodo de evaluación",
        compute="_compute_period_display",
        store=True,
    )

    # ── II. OBJETO ────────────────────────────────────────────────────────────
    objective_text = fields.Text(
        string="II. Objeto",
        default=lambda self: self._default_objective_text(),
        required=True,
    )

    # ── III. META COMERCIAL INDIVIDUAL ────────────────────────────────────────
    target_amount = fields.Monetary(
        string="Meta mensual de ventas ($)",
        currency_field="currency_id",
        required=True,
        tracking=True,
    )
    target_amount_text = fields.Char(
        string="Importe en letra",
        compute="_compute_target_amount_text",
        store=True,
        readonly=False,
    )
    attribution_criteria = fields.Selection(
        [
            ("ventas_cobradas", "Ventas cobradas (Pagos registrados en AVA_API sin devoluciones)"),
            ("ventas_facturadas", "Ventas facturadas"),
            ("pedidos_aceptados", "Pedidos aceptados"),
            ("otro", "Otro criterio expresamente definido"),
        ],
        string="Base de contabilización de ventas",
        default="ventas_cobradas",
        required=True,
        tracking=True,
    )
    attribution_criteria_other = fields.Char(
        string="Especificar otro criterio",
    )

    # ── IV. NIVELES DE PRODUCCIÓN Y EVALUACIÓN ───────────────────────────────
    threshold_critical = fields.Monetary(
        string="1. Producción críticamente baja (inferior a $)",
        currency_field="currency_id",
        required=True,
        tracking=True,
        help="Cuando las ventas mensuales sean inferiores a este monto, se activará una revisión específica y medidas de mejora.",
    )
    threshold_below_min = fields.Monetary(
        string="2. Producción inferior a la meta (igual o superior a $)",
        currency_field="currency_id",
        compute="_compute_thresholds_from_target",
        store=True,
        readonly=False,
    )
    threshold_below_max = fields.Monetary(
        string="Pero inferior a la meta mensual de ($)",
        currency_field="currency_id",
        compute="_compute_thresholds_from_target",
        store=True,
        readonly=False,
    )
    threshold_reached = fields.Monetary(
        string="3. Meta alcanzada (ventas iguales a $)",
        currency_field="currency_id",
        compute="_compute_thresholds_from_target",
        store=True,
        readonly=False,
    )
    threshold_exceeded = fields.Monetary(
        string="4. Meta superada (ventas excedan de $)",
        currency_field="currency_id",
        compute="_compute_thresholds_from_target",
        store=True,
        readonly=False,
    )

    # ── V. ESQUEMA DE INCENTIVOS ECONÓMICOS ───────────────────────────────────
    incentive_line_ids = fields.One2many(
        "hr.sales.incentive.line",
        "scheme_id",
        string="Tabla de Incentivos Aplicables",
        default=lambda self: self._default_incentive_lines(),
    )

    # ── RENDIMIENTO REAL DESDE AVA_API (/AVA/ventas y /AVA/ventas/pagos) ──────
    actual_sales = fields.Monetary(
        string="Ventas computables del mes (AVA_API)",
        currency_field="currency_id",
        tracking=True,
        help="Suma de pagos válidos desde /AVA/ventas/pagos excluyendo '99 NOTA DE DEVOLUCI' y 'DEVOLUCION DE PRODUCTO'.",
    )
    excluded_returns_amount = fields.Monetary(
        string="Monto excluido por devoluciones",
        currency_field="currency_id",
        readonly=True,
        help="Pagos excluidos cuya descripción contiene '99 NOTA DE DEVOLUCI' o 'DEVOLUCION DE PRODUCTO'.",
    )
    matched_sales_count = fields.Integer(
        string="Ventas en /AVA/ventas",
        readonly=True,
    )
    valid_payments_count = fields.Integer(
        string="Pagos válidos sumados",
        readonly=True,
    )
    excluded_payments_count = fields.Integer(
        string="Pagos por devolución excluidos",
        readonly=True,
    )
    last_api_sync = fields.Datetime(
        string="Última sincronización AVA_API",
        readonly=True,
    )
    compliance_percentage = fields.Float(
        string="% de Cumplimiento",
        compute="_compute_evaluation_metrics",
        store=True,
    )
    evaluation_level = fields.Selection(
        [
            ("sin_evaluar", "Sin evaluar"),
            ("criticamente_baja", "1. Producción críticamente baja"),
            ("inferior_meta", "2. Producción inferior a la meta"),
            ("meta_alcanzada", "3. Meta alcanzada"),
            ("meta_superada", "4. Meta superada"),
        ],
        string="Nivel de Producción Alcanzado",
        compute="_compute_evaluation_metrics",
        store=True,
        tracking=True,
    )

    # ── VI. SEGUIMIENTO SEMANAL Y VIII. OBSERVACIONES LEGALES ─────────────────
    weekly_review_ids = fields.One2many(
        "hr.sales.weekly.review",
        "scheme_id",
        string="VI. Revisiones Semanales",
    )
    legal_observation_ids = fields.One2many(
        "hr.sales.legal.observation",
        "scheme_id",
        string="VIII. Resultados, Desviaciones y Medidas de Mejora",
    )
    weekly_review_count = fields.Integer(
        compute="_compute_child_counts",
        string="Revisiones Semanales",
    )
    observation_count = fields.Integer(
        compute="_compute_child_counts",
        string="Observaciones Legales",
    )

    # ── X. ALCANCE, ACEPTACIÓN Y DOCUMENTO PDF FIRMADO ────────────────────────
    witness_1 = fields.Char(string="Testigo 1")
    witness_2 = fields.Char(string="Testigo 2")
    signed_date = fields.Date(
        string="Fecha de firma del esquema",
        default=fields.Date.context_today,
    )
    signed_scheme_pdf_ids = fields.Many2many(
        "ir.attachment",
        "hr_sales_scheme_signed_pdf_rel",
        "scheme_id",
        "attachment_id",
        string="Esquema Mensual Firmado (PDF)",
        help="Sube aquí el documento PDF escaneado ya firmado por la trabajadora, la empresa y los testigos.",
    )
    state = fields.Selection(
        [
            ("borrador", "Borrador"),
            ("comunicado", "Comunicado y Firmado"),
            ("en_evaluacion", "En Evaluación"),
            ("cerrado", "Cerrado"),
            ("cancelado", "Cancelado"),
        ],
        string="Estado",
        default="borrador",
        tracking=True,
    )

    # ── Defaults ──────────────────────────────────────────────────────────────
    @api.model
    def _default_period_start(self):
        today = fields.Date.context_today(self)
        return date(today.year, today.month, 1)

    @api.model
    def _default_period_end(self):
        today = fields.Date.context_today(self)
        last_day = calendar.monthrange(today.year, today.month)[1]
        return date(today.year, today.month, last_day)

    @api.model
    def _default_objective_text(self):
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("ava_metas.default_objective")
            or DEFAULT_SCHEME_OBJECTIVE
        )

    @api.model
    def _default_incentive_lines(self):
        return [
            (0, 0, {
                "sequence": 10,
                "compliance_level": "meta_alcanzada",
                "period_sales_text": "Al alcanzar el 100% de la meta mensual",
                "commission_text": "Según tabulador vigente del periodo",
            }),
            (0, 0, {
                "sequence": 20,
                "compliance_level": "meta_superada",
                "period_sales_text": "Ventas superiores a la meta mensual",
                "commission_text": "Según tabulador vigente del periodo",
            }),
        ]

    # ── Onchanges y Computados ────────────────────────────────────────────────
    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        for rec in self:
            if rec.employee_id:
                rec.job_title = (
                    rec.employee_id.puesto_expediente
                    or rec.employee_id.job_title
                    or "Agente de ventas"
                )
                rec.area_name = (
                    rec.employee_id.department_id.name
                    or rec.employee_id.division
                    or "Ventas"
                )
                if rec.employee_id.parent_id:
                    rec.manager_id = rec.employee_id.parent_id

    @api.depends("employee_id.name", "period_start")
    def _compute_name(self):
        for rec in self:
            if rec.employee_id and rec.period_start:
                month_name = SPANISH_MONTHS.get(rec.period_start.month, "")
                rec.name = f"ESQ-{rec.period_start.year}-{rec.period_start.month:02d} ({month_name}) - {rec.employee_id.name}"
            elif rec.employee_id:
                rec.name = f"ESQ - {rec.employee_id.name}"
            else:
                rec.name = _("Nuevo Esquema Mensual")

    @api.depends("period_start", "period_end")
    def _compute_period_display(self):
        for rec in self:
            if rec.period_start and rec.period_end:
                m_start = SPANISH_MONTHS.get(rec.period_start.month, "")
                m_end = SPANISH_MONTHS.get(rec.period_end.month, "")
                if rec.period_start.month == rec.period_end.month and rec.period_start.year == rec.period_end.year:
                    rec.period_display = (
                        f"DEL {rec.period_start.day:02d} DE {m_start} "
                        f"AL {rec.period_end.day:02d} DE {m_end} DE {rec.period_end.year}."
                    )
                else:
                    rec.period_display = (
                        f"DEL {rec.period_start.day:02d} DE {m_start} DE {rec.period_start.year} "
                        f"AL {rec.period_end.day:02d} DE {m_end} DE {rec.period_end.year}."
                    )
            else:
                rec.period_display = ""

    @api.depends("target_amount")
    def _compute_target_amount_text(self):
        for rec in self:
            rec.target_amount_text = amount_to_spanish_words(rec.target_amount)

    @api.depends("target_amount", "threshold_critical")
    def _compute_thresholds_from_target(self):
        for rec in self:
            if rec.target_amount and not rec.threshold_critical:
                rec.threshold_critical = round(rec.target_amount * 0.60, 2)
            rec.threshold_below_min = rec.threshold_critical or 0.0
            rec.threshold_below_max = rec.target_amount or 0.0
            rec.threshold_reached = rec.target_amount or 0.0
            rec.threshold_exceeded = rec.target_amount or 0.0

    @api.depends("actual_sales", "target_amount", "threshold_critical", "threshold_reached", "threshold_exceeded")
    def _compute_evaluation_metrics(self):
        for rec in self:
            if rec.target_amount > 0:
                rec.compliance_percentage = round((rec.actual_sales / rec.target_amount) * 100.0, 2)
            else:
                rec.compliance_percentage = 0.0

            if not rec.last_api_sync and rec.actual_sales <= 0:
                rec.evaluation_level = "sin_evaluar"
            elif rec.actual_sales < rec.threshold_critical:
                rec.evaluation_level = "criticamente_baja"
            elif rec.actual_sales < (rec.threshold_reached or rec.target_amount):
                rec.evaluation_level = "inferior_meta"
            elif rec.actual_sales == (rec.threshold_reached or rec.target_amount):
                rec.evaluation_level = "meta_alcanzada"
            else:
                rec.evaluation_level = "meta_superada"

    @api.depends("weekly_review_ids", "legal_observation_ids")
    def _compute_child_counts(self):
        for rec in self:
            rec.weekly_review_count = len(rec.weekly_review_ids)
            rec.observation_count = len(rec.legal_observation_ids)

    @api.constrains("period_start", "period_end")
    def _check_period_dates(self):
        for rec in self:
            if rec.period_start and rec.period_end and rec.period_end < rec.period_start:
                raise ValidationError(
                    _("La fecha de fin del periodo no puede ser anterior a la fecha de inicio.")
                )

    def _format_signed_date_legal(self):
        self.ensure_one()
        d = self.signed_date or self.communication_date or fields.Date.context_today(self)
        month_name = SPANISH_MONTHS.get(d.month, "")
        return f"A los {d.day:02d} días del mes de {month_name} del {d.year}."

    # ── Acciones de Flujo y Sincronización AVA_API ────────────────────────────
    def action_print_scheme_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "expediente_empleados.action_report_hr_sales_scheme"
        ).report_action(self)

    def action_confirm_communicated(self):
        for rec in self:
            if rec.target_amount <= 0:
                raise UserError(_("Debes definir una Meta mensual de ventas mayor a $0.00 antes de comunicar el esquema."))
            if not rec.signed_scheme_pdf_ids:
                raise UserError(
                    _(
                        "Para marcar el esquema como Comunicado y Firmado, primero debes imprimir el formato en PDF, "
                        "recabar las firmas físicas y subir el documento escaneado en el campo 'Esquema Mensual Firmado (PDF)'."
                    )
                )
            rec.state = "comunicado"
            rec.message_post(
                body=_(
                    "Esquema mensual comunicado y respaldado con PDF firmado adjunto. "
                    "Meta establecida: $%s (%s)."
                )
                % (f"{rec.target_amount:,.2f}", rec.target_amount_text)
            )

    def action_start_evaluation(self):
        for rec in self:
            if not rec.signed_scheme_pdf_ids:
                raise UserError(_("El esquema debe contar con el PDF firmado adjunto antes de iniciar la evaluación."))
            rec.state = "en_evaluacion"

    def action_close_scheme(self):
        for rec in self:
            rec.state = "cerrado"

    def action_reset_draft(self):
        for rec in self:
            rec.state = "borrador"

    def action_sync_ava_sales(self):
        self.ensure_one()
        alias = self.employee_id.nombre_alias
        if not alias:
            raise UserError(
                _(
                    "La empleada '%s' no tiene configurado su 'Nombre Alias' en su ficha de empleado. "
                    "Configúralo para poder empatar con 'nombreVendedor' en /AVA/ventas."
                )
                % self.employee_id.name
            )

        result = self.env["ava.api.service"].fetch_agent_sales_and_payments(
            nombre_alias=alias,
            date_start=self.period_start,
            date_end=self.period_end,
        )

        self.write({
            "actual_sales": result["valid_sales_amount"],
            "excluded_returns_amount": result["excluded_returns_amount"],
            "matched_sales_count": result["matched_sales_count"],
            "valid_payments_count": result["valid_payments_count"],
            "excluded_payments_count": result["excluded_payments_count"],
            "last_api_sync": fields.Datetime.now(),
        })

        self.message_post(
            body=_(
                "Sincronización con AVA_API completada para el alias '%s' (%s a %s): "
                "Ventas computables = $%s (%s pagos válidos). "
                "Devoluciones excluidas = $%s (%s pagos con '99 NOTA DE DEVOLUCI' / 'DEVOLUCION DE PRODUCTO')."
            )
            % (
                alias,
                self.period_start,
                self.period_end,
                f"{result['valid_sales_amount']:,.2f}",
                result["valid_payments_count"],
                f"{result['excluded_returns_amount']:,.2f}",
                result["excluded_payments_count"],
            )
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Ventas actualizadas desde AVA_API"),
                "message": _(
                    "Ventas computables: $%s | Devoluciones excluidas: $%s"
                )
                % (
                    f"{result['valid_sales_amount']:,.2f}",
                    f"{result['excluded_returns_amount']:,.2f}",
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def action_create_legal_observation(self):
        self.ensure_one()
        default_results = (
            f"Periodo evaluado: {self.period_display}\n"
            f"Meta mensual establecida: ${self.target_amount:,.2f} ({self.target_amount_text})\n"
            f"Ventas computables registradas en AVA_API: ${self.actual_sales:,.2f} "
            f"({self.compliance_percentage:.2f}% de cumplimiento)\n"
            f"Devoluciones excluidas ('99 NOTA DE DEVOLUCI' / 'DEVOLUCION DE PRODUCTO'): "
            f"${self.excluded_returns_amount:,.2f}\n"
            f"Nivel de producción ubicado: {dict(self._fields['evaluation_level'].selection).get(self.evaluation_level, '')}"
        )
        default_type = (
            "produccion_critica"
            if self.evaluation_level == "criticamente_baja"
            else "desviacion_relevante"
        )
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva Observación / Medida de Mejora (Sección VIII)"),
            "res_model": "hr.sales.legal.observation",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_scheme_id": self.id,
                "default_employee_id": self.employee_id.id,
                "default_manager_id": self.manager_id.id,
                "default_incident_type": default_type,
                "default_results_and_period": default_results,
            },
        }

