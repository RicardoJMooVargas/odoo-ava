{
    "name": "AVA - Expediente de Empleados y Metas Comerciales",
    "version": "19.0.2.1.0",
    "category": "Human Resources",
    "summary": "Expediente laboral, Esquema Mensual de Metas (AVA_API), Evaluaciones de Desempeño e Historial Legal",
    "description": (
        "Amplía los empleados de Odoo con datos administrativos, documentos del expediente, "
        "Esquema Mensual de Metas Comerciales conectado a AVA_API (/AVA/ventas y /AVA/ventas/pagos), "
        "Formato de Evaluación del Desempeño con preguntas configurables y escala 1-4, "
        "revisiones semanales e historial legal de observaciones y medidas de mejora."
    ),
    "depends": ["hr", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/hr_sales_obligation_data.xml",
        "data/hr_performance_question_data.xml",
        "views/res_config_settings_views.xml",
        "views/hr_sales_scheme_views.xml",
        "views/hr_performance_evaluation_views.xml",
        "views/hr_employee_views.xml",
        "report/hr_sales_scheme_reports.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
