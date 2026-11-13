# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


DEFAULT_SCHEME_OBJECTIVE = (
    "El presente documento tiene por objeto establecer las metas comerciales individuales "
    "correspondientes al periodo señalado, los parámetros para evaluar el desempeño de la persona "
    "trabajadora, las condiciones para el otorgamiento de incentivos económicos variables y los "
    "mecanismos de seguimiento de resultados.\n\n"
    "Las metas se determinan considerando los antecedentes de ventas, la cartera de clientes asignada, "
    "las oportunidades comerciales disponibles, la demanda de los productos, las condiciones del "
    "mercado y los objetivos comerciales de ARMANDO VIDRIOS Y ALUMINIOS S.A. DE C.V., en lo "
    "sucesivo, “LA EMPRESA”.\n\n"
    "La persona trabajadora reconoce que entre las funciones inherentes a su puesto se encuentran la "
    "promoción y venta de productos, la atención y seguimiento de clientes, la gestión de cotizaciones y "
    "pedidos, el desarrollo de oportunidades comerciales y las demás actividades relacionadas con sus "
    "funciones e instrucciones de trabajo lícitas."
)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    ava_api_base_url = fields.Char(
        string="URL Base de AVA_API",
        config_parameter="ava_api.base_url",
        default="https://sistemainforweb.com",
        help="URL base donde se encuentran los endpoints /AVA/ventas y /AVA/ventas/pagos.",
    )
    ava_api_auth_type = fields.Selection(
        [
            ("none", "Sin autenticación adicional"),
            ("bearer", "Bearer Token (Header Authorization)"),
            ("basic", "HTTP Basic Auth (Usuario y Contraseña)"),
            ("api_key_header", "API Key en Header"),
            ("api_key_query", "API Key en Query Param"),
        ],
        string="Tipo de Autenticación AVA_API",
        config_parameter="ava_api.auth_type",
        default="bearer",
    )
    ava_api_username = fields.Char(
        string="Usuario AVA_API",
        config_parameter="ava_api.username",
        default="ADMIN",
    )
    ava_api_password = fields.Char(
        string="Contraseña / Clave Secreta AVA_API",
        config_parameter="ava_api.password",
    )
    ava_api_key = fields.Char(
        string="Token / API Key AVA_API",
        config_parameter="ava_api.api_key",
    )
    ava_api_key_name = fields.Char(
        string="Nombre del Header / Parámetro de Clave",
        config_parameter="ava_api.api_key_name",
        default="X-API-Key",
    )
    ava_api_catalogo = fields.Char(
        string="Catálogo AVA_API",
        config_parameter="ava_api.catalogo",
        default="AVA01",
    )
    ava_api_timeout = fields.Integer(
        string="Timeout (segundos)",
        config_parameter="ava_api.timeout",
        default=30,
    )
    ava_default_scheme_objective = fields.Char(
        string="Texto por defecto del Objeto (Sección II)",
        config_parameter="ava_metas.default_objective",
        default=DEFAULT_SCHEME_OBJECTIVE,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if res.get("ava_api_base_url") in (False, "", "https://logichounds.com"):
            res["ava_api_base_url"] = "https://sistemainforweb.com"
        return res

    def _save_ava_params_sudo(self):
        self.ensure_one()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("ava_api.base_url", (self.ava_api_base_url or "https://sistemainforweb.com").strip())
        params.set_param("ava_api.auth_type", self.ava_api_auth_type or "bearer")
        params.set_param("ava_api.username", self.ava_api_username or "")
        params.set_param("ava_api.password", self.ava_api_password or "")
        params.set_param("ava_api.api_key", self.ava_api_key or "")
        params.set_param("ava_api.api_key_name", self.ava_api_key_name or "X-API-Key")
        params.set_param("ava_api.catalogo", self.ava_api_catalogo or "AVA01")
        params.set_param("ava_api.timeout", str(self.ava_api_timeout or 30))
        params.set_param("ava_metas.default_objective", self.ava_default_scheme_objective or DEFAULT_SCHEME_OBJECTIVE)

    def action_save_ava_config(self):
        self.ensure_one()
        self._save_ava_params_sudo()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Configuración Guardada"),
                "message": _("Las credenciales y parámetros de AVA_API se han guardado correctamente."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_test_ava_api_connection(self):
        self.ensure_one()
        self._save_ava_params_sudo()
        return self.env["ava.api.service"].test_connection()
