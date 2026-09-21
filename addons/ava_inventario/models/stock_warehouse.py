# -*- coding: utf-8 -*-
from odoo import api, models
from ..hooks import sync_ava_warehouses


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    @api.model
    def action_sync_ava_warehouses(self):
        """Método invocable para sincronizar los almacenes AVA requeridos."""
        sync_ava_warehouses(self.env)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Sincronización de Almacenes AVA",
                "message": "Los almacenes AVA01, AVA02, AVA03 y AVA04 han sido verificados y actualizados correctamente.",
                "type": "success",
                "sticky": False,
            },
        }
