# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .hr_sales_scheme import SPANISH_MONTHS

DEFAULT_EVALUATION_OBJECTIVE = (
    "Hacer seguimiento de las competencias del empleado, con respecto al cargo, "
    "teniendo en cuenta las responsabilidades y metas del periodo evaluado."
)


class HrPerformanceQuestion(models.Model):
    _name = "hr.performance.question"
    _description = "Pregunta Configurable de Evaluación de Desempeño"
    _order = "sequence, id"

    sequence = fields.Integer(string="Orden", default=10)
    section_name = fields.Char(
        string="Área / Categoría del Desempeño",
        required=True,
        placeholder="Ej. ORIENTACIÓN DE RESULTADOS, CALIDAD, INICIATIVA...",
        help="Encabezado de agrupación en el formato de evaluación.",
    )
    name = fields.Char(
        string="Pregunta / Competencia a Evaluar",
        required=True,
        placeholder="Ej. Termina su trabajo oportunamente",
    )
    active = fields.Boolean(string="Activa", default=True)


class HrPerformanceEvaluation(models.Model):
    _name = "hr.performance.evaluation"
    _description = "Formato de Evaluación del Desempeño del Empleado"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "evaluation_date desc, id desc"

    name = fields.Char(
        string="Folio de Evaluación",
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

    # ── DATOS DEL EMPLEADO Y VÍNCULO OPCIONAL CON ESQUEMA MENSUAL ─────────────
    employee_id = fields.Many2one(
        "hr.employee",
        string="Nombre del empleado",
        required=True,
        tracking=True,
    )
    job_title = fields.Char(
        string="Cargo / Puesto",
        required=True,
        default="Agente de ventas",
    )
    area_name = fields.Char(
        string="Área",
        default="Ventas",
    )
    manager_id = fields.Many2one(
        "hr.employee",
        string="Evaluador / Gerente de Ventas",
        default=lambda self: self.env.user.employee_id,
        tracking=True,
    )
    evaluation_date = fields.Date(
        string="Fecha de elaboración",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    scheme_id = fields.Many2one(
        "hr.sales.scheme",
        string="Esquema Mensual Vinculado (Opcional)",
        tracking=True,
        help="Si se selecciona un Esquema Mensual de Metas, se rellena automáticamente el periodo que se está calificando.",
    )
    period_start = fields.Date(
        string="Inicio del periodo calificado",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    period_end = fields.Date(
        string="Fin del periodo calificado",
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    period_display = fields.Char(
        string="Periodo calificado",
        compute="_compute_period_display",
        store=True,
    )
    objective_text = fields.Char(
        string="Objetivo",
        default=DEFAULT_EVALUATION_OBJECTIVE,
        required=True,
    )

    # ── LÍNEAS DE PREGUNTAS Y CÁLCULO DE PUNTAJE (ESCALA 1 A 4) ──────────────
    line_ids = fields.One2many(
        "hr.performance.evaluation.line",
        "evaluation_id",
        string="Preguntas de Desempeño",
        default=lambda self: self._default_evaluation_lines(),
        copy=True,
    )

    count_col_1 = fields.Integer(
        string="Respuestas en 1 (Muy Bajo)",
        compute="_compute_totals",
        store=True,
    )
    count_col_2 = fields.Integer(
        string="Respuestas en 2 (Bajo)",
        compute="_compute_totals",
        store=True,
    )
    count_col_3 = fields.Integer(
        string="Respuestas en 3 (Moderado)",
        compute="_compute_totals",
        store=True,
    )
    count_col_4 = fields.Integer(
        string="Respuestas en 4 (Alto)",
        compute="_compute_totals",
        store=True,
    )

    subtotal_col_1 = fields.Integer(
        string="Subtotal Columna 1 (Muy Bajo)",
        compute="_compute_totals",
        store=True,
    )
    subtotal_col_2 = fields.Integer(
        string="Subtotal Columna 2 (Bajo)",
        compute="_compute_totals",
        store=True,
    )
    subtotal_col_3 = fields.Integer(
        string="Subtotal Columna 3 (Moderado)",
        compute="_compute_totals",
        store=True,
    )
    subtotal_col_4 = fields.Integer(
        string="Subtotal Columna 4 (Alto)",
        compute="_compute_totals",
        store=True,
    )

    total_score = fields.Integer(
        string="PUNTAJE TOTAL",
        compute="_compute_totals",
        store=True,
        tracking=True,
    )
    max_possible_score = fields.Integer(
        string="Puntaje Máximo Posible",
        compute="_compute_totals",
        store=True,
    )
    score_percentage = fields.Float(
        string="% de Desempeño",
        compute="_compute_totals",
        store=True,
    )
    overall_level = fields.Selection(
        [
            ("muy_bajo", "MUY BAJO"),
            ("bajo", "BAJO"),
            ("moderado", "MODERADO"),
            ("alto", "ALTO"),
        ],
        string="Nivel de Desempeño General",
        compute="_compute_totals",
        store=True,
        tracking=True,
    )

    general_comments = fields.Text(
        string="Observaciones / Comentarios del Evaluador",
    )
    employee_comments = fields.Text(
        string="Comentarios del Empleado",
    )
    signed_evaluation_pdf_ids = fields.Many2many(
        "ir.attachment",
        "hr_perf_eval_signed_pdf_rel",
        "evaluation_id",
        "attachment_id",
        string="Formato de Evaluación Firmado (PDF)",
        help="Imprime el formato en PDF, recaba la firma física del empleado y sube aquí el documento escaneado.",
    )
    state = fields.Selection(
        [
            ("borrador", "Borrador"),
            ("confirmado", "Evaluado / Firmado"),
            ("cerrado", "Cerrado"),
        ],
        string="Estado",
        default="borrador",
        tracking=True,
    )

    @api.model
    def _default_evaluation_lines(self):
        questions = self.env["hr.performance.question"].search([("active", "=", True)], order="sequence, id")
        lines = []
        for q in questions:
            lines.append((0, 0, {
                "sequence": q.sequence,
                "question_id": q.id,
                "section_name": q.section_name,
                "question_name": q.name,
                "score": "3",
            }))
        return lines

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
                # Si el esquema seleccionado no pertenece al nuevo empleado, limpiarlo
                if rec.scheme_id and rec.scheme_id.employee_id != rec.employee_id:
                    rec.scheme_id = False

    @api.onchange("scheme_id")
    def _onchange_scheme_id(self):
        for rec in self:
            if rec.scheme_id:
                rec.employee_id = rec.scheme_id.employee_id
                rec.job_title = rec.scheme_id.job_title
                rec.area_name = rec.scheme_id.area_name
                if rec.scheme_id.manager_id:
                    rec.manager_id = rec.scheme_id.manager_id
                rec.period_start = rec.scheme_id.period_start
                rec.period_end = rec.scheme_id.period_end

    @api.depends("employee_id.name", "evaluation_date", "period_start")
    def _compute_name(self):
        for rec in self:
            d = rec.period_start or rec.evaluation_date or fields.Date.context_today(rec)
            emp_name = rec.employee_id.name or _("Empleado")
            rec.name = f"EVAL-{d.year}-{d.month:02d} - {emp_name}"

    @api.depends("period_start", "period_end")
    def _compute_period_display(self):
        for rec in self:
            if rec.period_start and rec.period_end:
                m_start = SPANISH_MONTHS.get(rec.period_start.month, "")
                m_end = SPANISH_MONTHS.get(rec.period_end.month, "")
                if rec.period_start.month == rec.period_end.month and rec.period_start.year == rec.period_end.year:
                    rec.period_display = (
                        f"DEL {rec.period_start.day:02d} DE {m_start} "
                        f"AL {rec.period_end.day:02d} DE {m_end} DE {rec.period_end.year}"
                    )
                else:
                    rec.period_display = (
                        f"DEL {rec.period_start.day:02d} DE {m_start} DE {rec.period_start.year} "
                        f"AL {rec.period_end.day:02d} DE {m_end} DE {rec.period_end.year}"
                    )
            else:
                rec.period_display = ""

    @api.depends("line_ids.score")
    def _compute_totals(self):
        for rec in self:
            c1 = sum(1 for l in rec.line_ids if l.score == "1")
            c2 = sum(1 for l in rec.line_ids if l.score == "2")
            c3 = sum(1 for l in rec.line_ids if l.score == "3")
            c4 = sum(1 for l in rec.line_ids if l.score == "4")

            s1 = c1 * 1
            s2 = c2 * 2
            s3 = c3 * 3
            s4 = c4 * 4
            total = s1 + s2 + s3 + s4
            num_questions = len(rec.line_ids)
            max_score = num_questions * 4

            rec.count_col_1 = c1
            rec.count_col_2 = c2
            rec.count_col_3 = c3
            rec.count_col_4 = c4

            rec.subtotal_col_1 = s1
            rec.subtotal_col_2 = s2
            rec.subtotal_col_3 = s3
            rec.subtotal_col_4 = s4
            rec.total_score = total
            rec.max_possible_score = max_score
            rec.score_percentage = round((total / max_score) * 100.0, 2) if max_score > 0 else 0.0

            if num_questions == 0:
                rec.overall_level = False
            else:
                avg = total / num_questions
                if avg < 1.75:
                    rec.overall_level = "muy_bajo"
                elif avg < 2.5:
                    rec.overall_level = "bajo"
                elif avg < 3.5:
                    rec.overall_level = "moderado"
                else:
                    rec.overall_level = "alto"

    def _get_grouped_lines_for_report(self):
        """Agrupa las líneas por 'section_name' manteniendo el orden para el formato PDF."""
        self.ensure_one()
        groups = []
        current_section = None
        current_group = None
        for line in self.line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            sec = (line.section_name or "GENERAL").strip().upper()
            if sec != current_section:
                current_section = sec
                current_group = {"section": sec, "lines": []}
                groups.append(current_group)
            current_group["lines"].append(line)
        return groups

    def action_reload_default_questions(self):
        self.ensure_one()
        if self.state != "borrador":
            raise UserError(_("Solo puedes recargar la plantilla de preguntas en estado Borrador."))
        self.line_ids.unlink()
        self.line_ids = self._default_evaluation_lines()

    def action_print_evaluation_pdf(self):
        self.ensure_one()
        return self.env.ref(
            "expediente_empleados.action_report_hr_performance_evaluation"
        ).report_action(self)

    def action_confirm_evaluation(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Debes incluir al menos una pregunta en la evaluación."))
            rec.state = "confirmado"

    def action_close_evaluation(self):
        for rec in self:
            rec.state = "cerrado"

    def action_reset_draft(self):
        for rec in self:
            rec.state = "borrador"


class HrPerformanceEvaluationLine(models.Model):
    _name = "hr.performance.evaluation.line"
    _description = "Renglón de Pregunta en Evaluación de Desempeño"
    _order = "sequence, id"

    sequence = fields.Integer(string="Orden", default=10)
    evaluation_id = fields.Many2one(
        "hr.performance.evaluation",
        string="Evaluación",
        required=True,
        ondelete="cascade",
    )
    question_id = fields.Many2one(
        "hr.performance.question",
        string="Pregunta del Catálogo",
    )
    section_name = fields.Char(
        string="Área del Desempeño",
        required=True,
        default="COMPETENCIAS GENERALES",
    )
    question_name = fields.Char(
        string="Criterio / Pregunta",
        required=True,
    )
    score = fields.Selection(
        [
            ("1", "1 - MUY BAJO"),
            ("2", "2 - BAJO"),
            ("3", "3 - MODERADO"),
            ("4", "4 - ALTO"),
        ],
        string="Calificación (1 a 4)",
        required=True,
        default="3",
    )
    score_int = fields.Integer(
        string="Puntos",
        compute="_compute_score_columns",
        store=True,
    )
    col_1_mark = fields.Char(compute="_compute_score_columns", string="Muy Bajo (1)")
    col_2_mark = fields.Char(compute="_compute_score_columns", string="Bajo (2)")
    col_3_mark = fields.Char(compute="_compute_score_columns", string="Moderado (3)")
    col_4_mark = fields.Char(compute="_compute_score_columns", string="Alto (4)")
    notes = fields.Char(string="Comentario")

    @api.onchange("question_id")
    def _onchange_question_id(self):
        for rec in self:
            if rec.question_id:
                rec.section_name = rec.question_id.section_name
                rec.question_name = rec.question_id.name
                rec.sequence = rec.question_id.sequence

    @api.depends("score")
    def _compute_score_columns(self):
        for rec in self:
            rec.score_int = int(rec.score) if rec.score in ("1", "2", "3", "4") else 0
            rec.col_1_mark = "1" if rec.score == "1" else ""
            rec.col_2_mark = "2" if rec.score == "2" else ""
            rec.col_3_mark = "3" if rec.score == "3" else ""
            rec.col_4_mark = "4" if rec.score == "4" else ""
