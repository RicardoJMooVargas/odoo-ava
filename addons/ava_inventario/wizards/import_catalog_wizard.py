# -*- coding: utf-8 -*-
import base64
import csv
import io
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AvaImportCatalogWizard(models.TransientModel):
    _name = "ava.import.catalog.wizard"
    _description = "Asistente de Importación de Catálogo de Productos AVA"

    data_file = fields.Binary(
        string="Archivo CSV de Catálogo",
        required=True,
    )
    filename = fields.Char(string="Nombre del Archivo")
    update_existing = fields.Boolean(
        string="Actualizar productos existentes",
        default=True,
        help="Si está marcado, actualizará los productos existentes cuyo código coincida con 'id'.",
    )
    create_missing = fields.Boolean(
        string="Crear productos no existentes",
        default=True,
    )
    encoding = fields.Selection(
        [
            ("utf-8-sig", "UTF-8 / UTF-8-BOM (Recomendado)"),
            ("latin1", "Latin-1 / CP1252 / ISO-8859-1"),
        ],
        string="Codificación",
        default="utf-8-sig",
        required=True,
    )

    def _parse_float(self, val):
        """Convierte cadenas con formato numérico a float seguro."""
        if not val:
            return 0.0
        try:
            val_str = str(val).strip().replace(",", "").replace("$", "")
            return float(val_str)
        except (ValueError, TypeError):
            return 0.0

    def _get_uom_map(self):
        """Construye un mapa rápido de unidades de medida existentes o crea las comunes."""
        Uom = self.env["uom.uom"]
        uoms = Uom.search([])
        uom_map = {}
        for u in uoms:
            uom_map[u.name.upper()] = u
            if hasattr(u, "symbol") and u.symbol:
                uom_map[u.symbol.upper()] = u

        # Aliases comunes
        unit_uom = self.env.ref("uom.product_uom_unit", raise_if_not_found=False) or Uom.search([], limit=1)
        meter_uom = self.env.ref("uom.product_uom_meter", raise_if_not_found=False)
        kg_uom = self.env.ref("uom.product_uom_kg", raise_if_not_found=False)
        m2_uom = self.env.ref("uom.product_uom_square_meter", raise_if_not_found=False)

        alias_map = {
            "PZA": unit_uom,
            "PIEZA": unit_uom,
            "UNIDAD": unit_uom,
            "MTS": meter_uom or unit_uom,
            "MT": meter_uom or unit_uom,
            "M": meter_uom or unit_uom,
            "M2": m2_uom or unit_uom,
            "KILO": kg_uom or unit_uom,
            "KG": kg_uom or unit_uom,
            "NA": unit_uom,
            "ACT": unit_uom,
        }
        for k, v in alias_map.items():
            if v and k not in uom_map:
                uom_map[k] = v

        return uom_map, unit_uom

    def action_import(self):
        """Ejecuta la importación del catálogo desde el archivo CSV cargado."""
        self.ensure_one()
        if not self.data_file:
            raise UserError(_("Por favor seleccione un archivo CSV."))

        try:
            raw_data = base64.b64decode(self.data_file)
            text_data = raw_data.decode(self.encoding)
        except Exception as e:
            raise UserError(_("Error al decodificar el archivo con codificación %s: %s") % (self.encoding, str(e)))

        reader = csv.DictReader(io.StringIO(text_data))
        if not reader.fieldnames:
            raise UserError(_("El archivo CSV no tiene encabezados válidos."))

        # Normalizar nombres de columnas eliminando espacios y BOM
        clean_fieldnames = [c.replace("\ufeff", "").strip() for c in reader.fieldnames]
        reader.fieldnames = clean_fieldnames

        if "id" not in clean_fieldnames or "descripcion" not in clean_fieldnames:
            raise UserError(_(
                "El archivo debe contener al menos las columnas 'id' (código principal) y 'descripcion'."
            ))

        # Cargar memorias caché de entidades relacionadas para evitar N+1 queries
        Family = self.env["product.family"]
        Class = self.env["product.class"]
        Line = self.env["product.line"]
        Partner = self.env["res.partner"]
        ProductTemplate = self.env["product.template"].with_context(active_test=False)
        SupplierInfo = self.env["product.supplierinfo"]

        fam_cache = {}
        for f in Family.search([]):
            if f.code:
                fam_cache[f.code.strip()] = f
            fam_cache[f.name.strip().upper()] = f

        class_cache = {}
        for c in Class.search([]):
            if c.code:
                class_cache[c.code.strip()] = c
            class_cache[c.name.strip().upper()] = c

        line_cache = {}
        for l in Line.search([]):
            if l.code:
                line_cache[l.code.strip()] = l
            line_cache[l.name.strip().upper()] = l

        partner_cache = {}
        partner_domain = [("supplier_rank", ">", 0)] if "supplier_rank" in Partner._fields else []
        for p in Partner.search(partner_domain):
            if p.ref:
                partner_cache[p.ref.strip()] = p
            partner_cache[p.name.strip().upper()] = p

        tmpl_cache = {}
        for t in ProductTemplate.search([("default_code", "!=", False)]):
            tmpl_cache[t.default_code.strip()] = t

        uom_map, default_uom = self._get_uom_map()

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for row in reader:
            code = row.get("id", "").strip()
            name = row.get("descripcion", "").strip()
            if not code or not name:
                skipped_count += 1
                continue

            # 1. Resolver Familia
            fam_code = row.get("familia", "").strip()
            fam_name = row.get("nombrefamilia", "").strip()
            family_record = False
            if fam_code or fam_name:
                key = fam_code or fam_name.upper()
                family_record = fam_cache.get(key) or fam_cache.get(fam_name.upper())
                if not family_record:
                    family_record = Family.create({
                        "code": fam_code,
                        "name": fam_name or fam_code,
                    })
                    if fam_code:
                        fam_cache[fam_code] = family_record
                    if fam_name:
                        fam_cache[fam_name.upper()] = family_record

            # 2. Resolver Clase
            cls_code = row.get("clase", "").strip()
            cls_name = row.get("nombreclase", "").strip()
            class_record = False
            if cls_code or cls_name:
                key = cls_code or cls_name.upper()
                class_record = class_cache.get(key) or class_cache.get(cls_name.upper())
                if not class_record:
                    class_record = Class.create({
                        "code": cls_code,
                        "name": cls_name or cls_code,
                    })
                    if cls_code:
                        class_cache[cls_code] = class_record
                    if cls_name:
                        class_cache[cls_name.upper()] = class_record

            # 3. Resolver Línea
            lin_code = row.get("linea", "").strip()
            lin_name = row.get("nombrelinea", "").strip()
            line_record = False
            if lin_code or lin_name:
                key = lin_code or lin_name.upper()
                line_record = line_cache.get(key) or line_cache.get(lin_name.upper())
                if not line_record:
                    line_record = Line.create({
                        "code": lin_code,
                        "name": lin_name or lin_code,
                    })
                    if lin_code:
                        line_cache[lin_code] = line_record
                    if lin_name:
                        line_cache[lin_name.upper()] = line_record

            # 4. Resolver Proveedor
            prov_code = row.get("proveedor", "").strip()
            prov_name = row.get("nombre", "").strip()
            supplier_record = False
            if prov_name:
                key = prov_name.upper()
                supplier_record = partner_cache.get(key) or partner_cache.get(prov_code)
                if not supplier_record:
                    p_vals = {
                        "name": prov_name,
                        "ref": prov_code or False,
                    }
                    if "supplier_rank" in Partner._fields:
                        p_vals["supplier_rank"] = 1
                    supplier_record = Partner.create(p_vals)
                    partner_cache[prov_name.upper()] = supplier_record
                    if prov_code:
                        partner_cache[prov_code] = supplier_record

            # 5. Resolver Unidad de Medida
            raw_uom = row.get("unidad", "").strip().upper()
            uom = uom_map.get(raw_uom, default_uom)

            # 6. Valores numéricos y campos adicionales
            barcode = row.get("alterno", "").strip() or False
            cve_sat = row.get("alterno2", "").strip() or False
            cost_real = self._parse_float(row.get("costoreal"))
            plista = self._parse_float(row.get("plista"))
            dctoprov = self._parse_float(row.get("dctoprov"))
            p1 = self._parse_float(row.get("p1"))
            p2 = self._parse_float(row.get("p2"))
            p3 = self._parse_float(row.get("p3"))
            p4 = self._parse_float(row.get("p4"))
            p5 = self._parse_float(row.get("p5"))
            p6 = self._parse_float(row.get("p6"))
            m1 = self._parse_float(row.get("m1"))
            m2 = self._parse_float(row.get("m2"))
            m3 = self._parse_float(row.get("m3"))
            m4 = self._parse_float(row.get("m4"))
            m5 = self._parse_float(row.get("m5"))
            m6 = self._parse_float(row.get("m6"))

            sale_price = p1 if p1 > 0 else plista

            vals = {
                "name": name,
                "default_code": code,
                "barcode": barcode,
                "cve_prod_serv": cve_sat,
                "uom_id": uom.id if uom else False,
                "uom_po_id": uom.id if uom else False,
                "family_id": family_record.id if family_record else False,
                "class_id": class_record.id if class_record else False,
                "line_id": line_record.id if line_record else False,
                "primary_supplier_id": supplier_record.id if supplier_record else False,
                "standard_price": cost_real,
                "costo_real": cost_real,
                "list_price": sale_price,
                "plista": plista,
                "dcto_prov": dctoprov,
                "p1": p1,
                "p2": p2,
                "p3": p3,
                "p4": p4,
                "p5": p5,
                "p6": p6,
                "m1": m1,
                "m2": m2,
                "m3": m3,
                "m4": m4,
                "m5": m5,
                "m6": m6,
                "type": "consu",  # En Odoo 19 con is_storable se define como consu
            }
            if hasattr(ProductTemplate, "is_storable"):
                vals["is_storable"] = True

            # 7. Crear o actualizar producto
            tmpl = tmpl_cache.get(code)
            if tmpl:
                if self.update_existing:
                    tmpl.write(vals)
                    updated_count += 1
                else:
                    skipped_count += 1
            elif self.create_missing:
                tmpl = ProductTemplate.create(vals)
                tmpl_cache[code] = tmpl
                created_count += 1
            else:
                skipped_count += 1
                continue

            # 8. Sincronizar info de proveedor (product.supplierinfo)
            if tmpl and supplier_record:
                supplier_info = SupplierInfo.search([
                    ("product_tmpl_id", "=", tmpl.id),
                    ("partner_id", "=", supplier_record.id),
                ], limit=1)
                s_vals = {
                    "partner_id": supplier_record.id,
                    "product_tmpl_id": tmpl.id,
                    "price": cost_real,
                    "discount": dctoprov,
                }
                if supplier_info:
                    supplier_info.write(s_vals)
                else:
                    SupplierInfo.create(s_vals)

        _logger.info(
            "Importación de catálogo terminada: Creados %d, Actualizados %d, Omitidos %d",
            created_count,
            updated_count,
            skipped_count,
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Importación de Catálogo Completada"),
                "message": _(
                    "Se procesó el catálogo con éxito: %d productos creados, %d actualizados, %d omitidos."
                ) % (created_count, updated_count, skipped_count),
                "type": "success",
                "sticky": True,
            },
        }
