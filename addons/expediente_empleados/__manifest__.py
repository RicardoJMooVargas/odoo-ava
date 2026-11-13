{
    "name": "Expediente de Empleados y Metas Comerciales",
    "version": "19.0.2.0.0",
    "category": "Human Resources",
    "summary": "Expediente laboral, Esquema Mensual de Metas Comerciales (AVA_API) e Historial de Observaciones Legales",
    "description": (
        "Amplía los empleados de Odoo con datos administrativos, documentos del expediente, "
        "Esquema Mensual de Metas Comerciales conectado a AVA_API (/AVA/ventas y /AVA/ventas/pagos), "
        "revisiones semanales e historial legal de observaciones y medidas de mejora."
    ),
    "depends": ["hr", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_sales_obligation_data.xml",
        "views/res_config_settings_views.xml",
        "views/hr_sales_scheme_views.xml",
        "views/hr_employee_views.xml",
        "report/hr_sales_scheme_reports.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
