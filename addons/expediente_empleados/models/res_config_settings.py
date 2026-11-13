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
        help="URL base del servidor de la API (ej. https://sistemainforweb.com o https://logichounds.com).",
    )
    ava_api_key = fields.Char(
        string="1. API Key (Cabecera X-Api-Key)",
        config_parameter="ava_api.api_key",
        help="Se envía en la cabecera X-Api-Key en todas las peticiones (/AVA/Token y consultas GET).",
    )
    ava_api_client_id = fields.Char(
        string="2. ClientId",
        config_parameter="ava_api.client_id",
        help="Identificador de cliente entregado a AVA. Se envía en el cuerpo JSON de POST /AVA/Token.",
    )
    ava_api_client_secret = fields.Char(
        string="3. ClientSecret",
        config_parameter="ava_api.client_secret",
        help="Secreto de cliente entregado a AVA. Se envía en el cuerpo JSON de POST /AVA/Token.",
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
        if not res.get("ava_api_base_url"):
            res["ava_api_base_url"] = "https://sistemainforweb.com"
        return res

    def _save_ava_params_sudo(self):
        self.ensure_one()
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("ava_api.base_url", (self.ava_api_base_url or "https://sistemainforweb.com").strip().rstrip("/"))
        params.set_param("ava_api.api_key", (self.ava_api_key or "").strip())
        params.set_param("ava_api.client_id", (self.ava_api_client_id or "").strip())
        params.set_param("ava_api.client_secret", (self.ava_api_client_secret or "").strip())
        params.set_param("ava_api.timeout", str(self.ava_api_timeout or 30))
        params.set_param("ava_metas.default_objective", self.ava_default_scheme_objective or DEFAULT_SCHEME_OBJECTIVE)
        # Limpiar token en caché cuando se actualizan las credenciales
        params.set_param("ava_api.cached_token", "")
        params.set_param("ava_api.token_expires_at", "0")

    def action_save_ava_config(self):
        self.ensure_one()
        self._save_ava_params_sudo()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Configuración Guardada"),
                "message": _("Los 3 parámetros de acceso (API Key, ClientId y ClientSecret) se han guardado correctamente."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_test_ava_api_connection(self):
        self.ensure_one()
        self._save_ava_params_sudo()
        return self.env["ava.api.service"].test_connection()
