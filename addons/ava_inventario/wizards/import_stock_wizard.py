# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging
import unicodedata
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from ..hooks import sync_ava_warehouses

_logger = logging.getLogger(__name__)


def _normalize_key(text):
    """Normaliza texto removiendo acentos y convirtiendo a minúsculas."""
    if not text:
        return ""
    text = str(text).strip()
    nfkd = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    return nfkd.lower()


class AvaImportStockWizard(models.TransientModel):
    _name = "ava.import.stock.wizard"
    _description = "Asistente de Importación de Existencias por Almacén AVA"

    data_file = fields.Binary(
        string="Archivo CSV de Existencias",
        required=True,
    )
    filename = fields.Char(string="Nombre del Archivo")
    mode = fields.Selection(
        [
            ("apply_direct", "Aplicar directamente a existencias (Ajuste de Inventario)"),
            ("create_session", "Crear sesión de Conteo Físico por almacén para revisión previa"),
        ],
        string="Modo de Operación",
        default="apply_direct",
        required=True,
    )
    create_missing_products = fields.Boolean(
        string="Crear productos faltantes",
        default=True,
        help="Si un código en el archivo no existe en el catálogo, se crea con los datos disponibles.",
    )
    update_ubicacion = fields.Boolean(
        string="Actualizar Ubicación Recomendada (Columna M)",
        default=True,
        help="Asigna el valor de la columna 'Ubicación' a la ficha del producto.",
    )
    only_non_zero = fields.Boolean(
        string="Ajustar solo cantidades distintas de cero",
        default=True,
        help="Omite registros con existencia 0 para mayor velocidad.",
    )
    encoding = fields.Selection(
        [
            ("utf-8", "UTF-8 (Recomendado)"),
            ("utf-8-sig", "UTF-8 con BOM"),
            ("latin1", "Latin-1 / CP1252 / ISO-8859-1"),
        ],
        string="Codificación",
        default="utf-8",
        required=True,
    )

    def _parse_float(self, val):
        if not val:
            return 0.0
        try:
            val_str = str(val).strip().replace(",", "")
            return float(val_str)
        except (ValueError, TypeError):
            return 0.0

    def action_import(self):
        """Procesa el archivo de existencias y aplica o genera sesiones."""
        self.ensure_one()
        if not self.data_file:
            raise UserError(_("Por favor seleccione un archivo CSV."))

        # 1. Asegurar almacenes AVA01-AVA04
        wh_map = sync_ava_warehouses(self.env)
        wh_locations = {
            "ava01": wh_map["AVA01"].lot_stock_id,
            "ava02": wh_map["AVA02"].lot_stock_id,
            "ava03": wh_map["AVA03"].lot_stock_id,
            "ava04": wh_map["AVA04"].lot_stock_id,
        }

        # 2. Decodificar archivo
        try:
            raw_data = base64.b64decode(self.data_file)
            text_data = raw_data.decode(self.encoding)
        except Exception as e:
            raise UserError(_("Error al decodificar el archivo: %s") % str(e))

        reader = csv.DictReader(io.StringIO(text_data))
        if not reader.fieldnames:
            raise UserError(_("El archivo CSV no contiene encabezados válidos."))

        # Mapear nombres de columnas normalizados
        normalized_headers = {}
        for h in reader.fieldnames:
            norm = _normalize_key(h)
            normalized_headers[norm] = h

        col_codigo = normalized_headers.get("codigo")
        col_desc = normalized_headers.get("descripcion")
        col_unidad = normalized_headers.get("unidad")
        col_activo = normalized_headers.get("activo")
        col_prov = normalized_headers.get("proveedor")
        col_fam = normalized_headers.get("familia")
        col_clase = normalized_headers.get("clase")
        col_linea = normalized_headers.get("linea")
        col_ubic = normalized_headers.get("ubicacion")

        col_ava01 = normalized_headers.get("ava01")
        col_ava02 = normalized_headers.get("ava02")
        col_ava03 = normalized_headers.get("ava03")
        col_ava04 = normalized_headers.get("ava04")

        if not col_codigo:
            raise UserError(_("No se encontró la columna requerida 'Codigo' en el archivo."))

        # Cachés en memoria
        ProductProduct = self.env["product.product"].with_context(active_test=False)
        ProductTemplate = self.env["product.template"].with_context(active_test=False)
        Family = self.env["product.family"]
        Class = self.env["product.class"]
        Line = self.env["product.line"]
        Partner = self.env["res.partner"]
        Uom = self.env["uom.uom"]

        prod_cache = {}
        for p in ProductProduct.search([("default_code", "!=", False)]):
            prod_cache[p.default_code.strip()] = p

        fam_cache = {f.name.strip().upper(): f for f in Family.search([])}
        cls_cache = {c.name.strip().upper(): c for c in Class.search([])}
        lin_cache = {l.name.strip().upper(): l for l in Line.search([])}
        partner_domain = [("supplier_rank", ">", 0)] if "supplier_rank" in Partner._fields else []
        partner_cache = {p.name.strip().upper(): p for p in Partner.search(partner_domain)}

        default_uom = self.env.ref("uom.product_uom_unit", raise_if_not_found=False) or Uom.search([], limit=1)

        # Contadores de resultados
        adjusted_counts = {"AVA01": 0, "AVA02": 0, "AVA03": 0, "AVA04": 0}
        created_prods = 0
        updated_ubic_count = 0

        # Para modo creación de sesiones
        session_lines_per_wh = {
            "AVA01": [],
            "AVA02": [],
            "AVA03": [],
            "AVA04": [],
        }

        Quant = self.env["stock.quant"].with_context(inventory_mode=True)

        for row in reader:
            code = row.get(col_codigo, "").strip() if col_codigo else ""
            if not code:
                continue

            product = prod_cache.get(code)
            ubic_val = row.get(col_ubic, "").strip() if col_ubic else ""

            # Si el producto no existe y está habilitada la creación
            if not product and self.create_missing_products:
                name = row.get(col_desc, "").strip() if col_desc else code
                is_active = True
                if col_activo:
                    act_str = str(row.get(col_activo, "")).strip().lower()
                    if act_str in ["false", "0", "no"]:
                        is_active = False

                # Resolver Familia, Clase, Línea por nombre
                fam_val = row.get(col_fam, "").strip() if col_fam else ""
                fam_rec = False
                if fam_val:
                    fam_rec = fam_cache.get(fam_val.upper())
                    if not fam_rec:
                        fam_rec = Family.create({"name": fam_val})
                        fam_cache[fam_val.upper()] = fam_rec

                cls_val = row.get(col_clase, "").strip() if col_clase else ""
                cls_rec = False
                if cls_val:
                    cls_rec = cls_cache.get(cls_val.upper())
                    if not cls_rec:
                        cls_rec = Class.create({"name": cls_val})
                        cls_cache[cls_val.upper()] = cls_rec

                lin_val = row.get(col_linea, "").strip() if col_linea else ""
                lin_rec = False
                if lin_val:
                    lin_rec = lin_cache.get(lin_val.upper())
                    if not lin_rec:
                        lin_rec = Line.create({"name": lin_val})
                        lin_cache[lin_val.upper()] = lin_rec

                prov_val = row.get(col_prov, "").strip() if col_prov else ""
                prov_rec = False
                if prov_val:
                    prov_rec = partner_cache.get(prov_val.upper())
                    if not prov_rec:
                        p_vals = {"name": prov_val}
                        if "supplier_rank" in Partner._fields:
                            p_vals["supplier_rank"] = 1
                        prov_rec = Partner.create(p_vals)
                        partner_cache[prov_val.upper()] = prov_rec

                tmpl_vals = {
                    "name": name,
                    "default_code": code,
                    "active": is_active,
                    "family_id": fam_rec.id if fam_rec else False,
                    "class_id": cls_rec.id if cls_rec else False,
                    "line_id": lin_rec.id if lin_rec else False,
                    "primary_supplier_id": prov_rec.id if prov_rec else False,
                    "ubicacion_recomendada": ubic_val or False,
                    "uom_id": default_uom.id if default_uom else False,
                    "type": "consu",
                }
                if "uom_po_id" in ProductTemplate._fields and default_uom:
                    tmpl_vals["uom_po_id"] = default_uom.id
                if "is_storable" in ProductTemplate._fields:
                    tmpl_vals["is_storable"] = True

                tmpl = ProductTemplate.create(tmpl_vals)
                product = tmpl.product_variant_id
                prod_cache[code] = product
                created_prods += 1
            elif product and self.update_ubicacion and ubic_val:
                if product.ubicacion_recomendada != ubic_val:
                    product.write({"ubicacion_recomendada": ubic_val})
                    updated_ubic_count += 1

            if not product:
                continue

            # Mapeo de cantidades para cada almacén
            wh_cols = [
                ("AVA01", col_ava01, wh_locations["ava01"]),
                ("AVA02", col_ava02, wh_locations["ava02"]),
                ("AVA03", col_ava03, wh_locations["ava03"]),
                ("AVA04", col_ava04, wh_locations["ava04"]),
            ]

            for wh_code, col_name, loc in wh_cols:
                if not col_name:
                    continue
                raw_qty = self._parse_float(row.get(col_name))
                if self.only_non_zero and abs(raw_qty) < 0.0001:
                    continue

                # Evitar cantidades negativas en inventario físico nativo
                counted_qty = max(0.0, raw_qty)

                if self.mode == "apply_direct":
                    quant = Quant.search([
                        ("product_id", "=", product.id),
                        ("location_id", "=", loc.id),
                    ], limit=1)

                    if not quant:
                        quant = Quant.create({
                            "product_id": product.id,
                            "location_id": loc.id,
                            "inventory_quantity": counted_qty,
                        })
                    else:
                        quant.inventory_quantity = counted_qty

                    quant.action_apply_inventory()
                    adjusted_counts[wh_code] += 1

                elif self.mode == "create_session":
                    session_lines_per_wh[wh_code].append((0, 0, {
                        "product_id": product.id,
                        "theoretical_qty": 0.0,
                        "counted_qty": counted_qty,
                        "is_counted": True,
                        "standard_price": product.standard_price or 0.0,
                    }))

        # Si el modo fue create_session, crear una sesión por cada almacén que tenga líneas
        if self.mode == "create_session":
            Session = self.env["ava.inventory.session"]
            created_sessions = []
            for wh_code, lines in session_lines_per_wh.items():
                if lines:
                    wh = wh_map[wh_code]
                    s = Session.create({
                        "name": f"IMPORT-EXISTENCIAS-{wh_code}-{fields.Date.today().strftime('%Y%m%d')}",
                        "warehouse_id": wh.id,
                        "location_id": wh.lot_stock_id.id,
                        "line_ids": lines,
                        "state": "in_progress",
                    })
                    created_sessions.append(s.id)

            return {
                "name": _("Sesiones de Conteo Generadas"),
                "type": "ir.actions.act_window",
                "res_model": "ava.inventory.session",
                "view_mode": "list,form",
                "domain": [("id", "in", created_sessions)],
            }

        # Mensaje de resultado para modo directo
        total_adjusted = sum(adjusted_counts.values())
        msg = _(
            "Ajuste de existencias completado exitosamente.\n"
            "- Productos nuevos creados: %d\n"
            "- Ubicaciones recomendadas actualizadas: %d\n"
            "- Movimientos aplicados por almacén: AVA01: %d, AVA02: %d, AVA03: %d, AVA04: %d (Total: %d)"
        ) % (
            created_prods,
            updated_ubic_count,
            adjusted_counts["AVA01"],
            adjusted_counts["AVA02"],
            adjusted_counts["AVA03"],
            adjusted_counts["AVA04"],
            total_adjusted,
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Importación de Existencias Exitosa"),
                "message": msg,
                "type": "success",
                "sticky": True,
            },
        }
