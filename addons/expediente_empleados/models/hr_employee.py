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
    puesto_expediente = fields.Char(string="Puesto del expediente")

    comp_domic = fields.Binary(string="Comprobante de domicilio", attachment=True)
    comp_domic_filename = fields.Char(string="Nombre del comprobante de domicilio")
    const_sit_fiscal = fields.Binary(string="Constancia de situación fiscal", attachment=True)
    const_sit_fiscal_filename = fields.Char(string="Nombre de la constancia fiscal")
    descript_puesto = fields.Binary(string="Descripción de puesto", attachment=True)
    descript_puesto_filename = fields.Char(string="Nombre de la descripción de puesto")
    licencia_chof = fields.Binary(string="Licencia de conducir", attachment=True)
    licencia_chof_filename = fields.Char(string="Nombre de la licencia")
    curriculum = fields.Binary(string="Currículum", attachment=True)
    curriculum_filename = fields.Char(string="Nombre del currículum")
    solicitud_empl = fields.Binary(string="Solicitud de empleo", attachment=True)
    solicitud_empl_filename = fields.Char(string="Nombre de la solicitud")
    act_naci = fields.Binary(string="Acta de nacimiento", attachment=True)
    act_naci_filename = fields.Char(string="Nombre del acta de nacimiento")
    ine = fields.Binary(string="INE", attachment=True)
    ine_filename = fields.Char(string="Nombre de la INE")
    curp = fields.Binary(string="CURP", attachment=True)
    curp_filename = fields.Char(string="Nombre de la CURP")
    rfc = fields.Binary(string="RFC", attachment=True)
    rfc_filename = fields.Char(string="Nombre del RFC")
    contrato = fields.Binary(string="Contrato", attachment=True)
    contrato_filename = fields.Char(string="Nombre del contrato")
    acta_hechos = fields.Binary(string="Acta de hechos", attachment=True)
    acta_hechos_filename = fields.Char(string="Nombre del acta de hechos")
