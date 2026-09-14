{
    "name": "Expediente de Empleados",
    "version": "19.0.1.0.0",
    "category": "Human Resources",
    "summary": "Datos y documentos del expediente laboral",
    "description": "Amplia los empleados de Odoo con datos administrativos y documentos del expediente.",
    "depends": ["hr"],
    "data": [
        "security/ir.model.access.csv",
        "views/hr_employee_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
