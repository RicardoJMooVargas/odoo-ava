from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    fecha_ingreso = fields.Date(string="Fecha de ingreso")
    es_chofer = fields.Boolean(string="Es chofer")
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
