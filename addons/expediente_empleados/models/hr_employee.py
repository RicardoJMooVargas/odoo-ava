# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    fecha_ingreso = fields.Date(string="Fecha de ingreso")
    es_chofer = fields.Boolean(string="Es chofer")
    es_agente_ventas = fields.Boolean(
        string="Es agente de ventas",
        default=False,
        help="Activa el historial mensual de metas comerciales y observaciones legales.",
    )
    nombre_alias = fields.Char(
        string="Nombre Alias",
        help="Alias con el que se identifica al vendedor en AVA_API (campo 'nombreVendedor' en /AVA/ventas).",
    )
    observaciones_expediente = fields.Text(string="Observaciones")
    division = fields.Char(string="División")
    estatus_expediente = fields.Selection(
        [
            ("borrador", "Borrador"),
            ("vigente", "Vigente"),
            ("baja", "Baja"),
        ],
        string="Estatus",
        default="borrador",
    )
    no_seguro_social = fields.Char(string="No. de seguridad social")
    rfc = fields.Char(string="RFC")
    puesto_expediente = fields.Char(string="Puesto del expediente")

    # ── Historial de Metas Comerciales y Observaciones Legales ───────────────
    sales_scheme_ids = fields.One2many(
        "hr.sales.scheme",
        "employee_id",
        string="Esquemas Mensuales de Metas",
    )
    legal_observation_ids = fields.One2many(
        "hr.sales.legal.observation",
        "employee_id",
        string="Historial de Observaciones Legales",
    )
    sales_scheme_count = fields.Integer(
        string="Esquemas Mensuales",
        compute="_compute_sales_counts",
    )
    legal_observation_count = fields.Integer(
        string="Observaciones Legales",
        compute="_compute_sales_counts",
    )

    # ── Documentos principales ────────────────────────────────────────────────
    comp_domic_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_comp_domic_rel",
        "employee_id",
        "attachment_id",
        string="Comprobante de domicilio",
    )
    const_sit_fiscal_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_const_sit_fiscal_rel",
        "employee_id",
        "attachment_id",
        string="Constancia de situación fiscal",
    )
    ine_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_ine_rel",
        "employee_id",
        "attachment_id",
        string="INE",
    )
    curp_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_curp_rel",
        "employee_id",
        "attachment_id",
        string="CURP",
    )

    # ── Documentos laborales ─────────────────────────────────────────────────
    solicitud_empl_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_solicitud_empl_rel",
        "employee_id",
        "attachment_id",
        string="Solicitud de empleo",
    )
    contrato_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_contrato_rel",
        "employee_id",
        "attachment_id",
        string="Contrato",
    )
    descript_puesto_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_descript_puesto_rel",
        "employee_id",
        "attachment_id",
        string="Descripción de puesto",
    )
    licencia_chof_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_licencia_chof_rel",
        "employee_id",
        "attachment_id",
        string="Licencia de conducir",
    )
    act_naci_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_act_naci_rel",
        "employee_id",
        "attachment_id",
        string="Acta de nacimiento",
    )
    acta_hechos_ids = fields.Many2many(
        "ir.attachment",
        "hr_emp_acta_hechos_rel",
        "employee_id",
        "attachment_id",
        string="Acta de hechos",
    )

    @api.depends("sales_scheme_ids", "legal_observation_ids")
    def _compute_sales_counts(self):
        for emp in self:
            emp.sales_scheme_count = len(emp.sales_scheme_ids)
            emp.legal_observation_count = len(emp.legal_observation_ids)

    def action_view_sales_schemes(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Esquemas Mensuales - %s") % self.name,
            "res_model": "hr.sales.scheme",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }

    def action_view_legal_observations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Observaciones Legales - %s") % self.name,
            "res_model": "hr.sales.legal.observation",
            "view_mode": "list,form",
            "domain": [("employee_id", "=", self.id)],
            "context": {"default_employee_id": self.id},
        }
