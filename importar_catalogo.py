#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de importación masiva de Catálogo de Productos para Odoo 19.
Módulo: ava_inventario

Uso:
  python importar_catalogo.py --user tu_usuario@email.com
  python importar_catalogo.py --user tu_usuario@email.com --dry-run
  python importar_catalogo.py --csv "PRODUCTOS CATALOGO.xlsx - Articulos.csv"
"""

import os
import csv
import sys
import getpass
import argparse
import xmlrpc.client


def parse_float(val):
    if not val:
        return 0.0
    try:
        val_str = str(val).strip().replace(",", "").replace("$", "")
        return float(val_str)
    except (ValueError, TypeError):
        return 0.0


def conectar_odoo(url, db, user, password):
    """Autentica y devuelve los proxies xmlrpc de common y models, más el uid."""
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise PermissionError(f"No se pudo autenticar el usuario '{user}' en la base de datos '{db}'.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return uid, models


def main():
    parser = argparse.ArgumentParser(description="Importar Catálogo de Productos a Odoo 19 (AVA)")
    parser.add_argument("--url", default="http://localhost:8069", help="URL de Odoo (default: http://localhost:8069)")
    parser.add_argument("--db", default=os.getenv("DB_NAME", "odoo"), help="Nombre de la BD (default: odoo)")
    parser.add_argument("--user", default=os.getenv("ODOO_USER", "admin"), help="Usuario de Odoo")
    parser.add_argument("--password", default=os.getenv("ODOO_PASSWORD"), help="Contraseña (si se omite, se solicita)")
    parser.add_argument("--csv", default="PRODUCTOS CATALOGO.xlsx - Articulos.csv", help="Ruta al archivo CSV de catálogo")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin escribir en Odoo")
    parser.add_argument("--batch-size", type=int, default=100, help="Tamaño de lote para commits")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: No se encontró el archivo CSV: {args.csv}")
        sys.exit(1)

    print(f"Leyendo archivo de catálogo: {args.csv}")
    with open(args.csv, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        clean_fieldnames = [c.replace("\ufeff", "").strip() for c in (reader.fieldnames or [])]
        reader.fieldnames = clean_fieldnames
        rows = list(reader)

    print(f"Total de filas leídas: {len(rows)}")

    if args.dry_run:
        print("[MODO DRY-RUN] Verificando datos sin conectar a Odoo...")
        familias = set()
        clases = set()
        lineas = set()
        proveedores = set()
        valid_rows = 0

        for r in rows:
            code = r.get("id", "").strip()
            name = r.get("descripcion", "").strip()
            if code and name:
                valid_rows += 1
                if r.get("familia") or r.get("nombrefamilia"):
                    familias.add((r.get("familia", "").strip(), r.get("nombrefamilia", "").strip()))
                if r.get("clase") or r.get("nombreclase"):
                    clases.add((r.get("clase", "").strip(), r.get("nombreclase", "").strip()))
                if r.get("linea") or r.get("nombrelinea"):
                    lineas.add((r.get("linea", "").strip(), r.get("nombrelinea", "").strip()))
                if r.get("proveedor") or r.get("nombre"):
                    proveedores.add((r.get("proveedor", "").strip(), r.get("nombre", "").strip()))

        print(f"Productos válidos: {valid_rows}")
        print(f"Familias únicas: {len(familias)}")
        print(f"Clases únicas: {len(clases)}")
        print(f"Líneas únicas: {len(lineas)}")
        print(f"Proveedores únicos: {len(proveedores)}")
        print("[DRY-RUN] Validación completada con éxito.")
        return

    password = args.password
    if not password:
        password = getpass.getpass(f"Contraseña de Odoo para '{args.user}': ")

    print(f"Conectando a Odoo en {args.url} (BD: {args.db})...")
    uid, models = conectar_odoo(args.url, args.db, args.user, password)
    print(f"Autenticado exitosamente con UID: {uid}")

    # Cargar memorias caché
    print("Cargando caché de Odoo (Familias, Clases, Líneas, Proveedores, Productos)...")
    fam_ids = models.execute_kw(args.db, uid, password, "product.family", "search_read", [[]], {"fields": ["id", "code", "name"]})
    fam_cache = {}
    for f in fam_ids:
        if f["code"]:
            fam_cache[f["code"].strip()] = f["id"]
        fam_cache[f["name"].strip().upper()] = f["id"]

    class_ids = models.execute_kw(args.db, uid, password, "product.class", "search_read", [[]], {"fields": ["id", "code", "name"]})
    class_cache = {}
    for c in class_ids:
        if c["code"]:
            class_cache[c["code"].strip()] = c["id"]
        class_cache[c["name"].strip().upper()] = c["id"]

    line_ids = models.execute_kw(args.db, uid, password, "product.line", "search_read", [[]], {"fields": ["id", "code", "name"]})
    line_cache = {}
    for l in line_ids:
        if l["code"]:
            line_cache[l["code"].strip()] = l["id"]
        line_cache[l["name"].strip().upper()] = l["id"]

    partner_ids = models.execute_kw(args.db, uid, password, "res.partner", "search_read", [[]], {"fields": ["id", "ref", "name"]})
    partner_cache = {}
    for p in partner_ids:
        if p.get("ref"):
            partner_cache[p["ref"].strip()] = p["id"]
        partner_cache[p["name"].strip().upper()] = p["id"]

    uom_ids = models.execute_kw(args.db, uid, password, "uom.uom", "search_read", [[]], {"fields": ["id", "name"]})
    uom_cache = {u["name"].strip().upper(): u["id"] for u in uom_ids}
    default_uom_id = uom_cache.get("UNIDADES") or uom_cache.get("UNIDAD") or uom_cache.get("PZA") or (uom_ids[0]["id"] if uom_ids else False)

    existing_tmpls = models.execute_kw(args.db, uid, password, "product.template", "search_read", [[("default_code", "!=", False)]], {"fields": ["id", "default_code"]})
    tmpl_cache = {t["default_code"].strip(): t["id"] for t in existing_tmpls}

    print("Iniciando procesamiento de productos...")
    created = 0
    updated = 0

    for i, row in enumerate(rows, start=1):
        code = row.get("id", "").strip()
        name = row.get("descripcion", "").strip()
        if not code or not name:
            continue

        # Familia
        fam_code = row.get("familia", "").strip()
        fam_name = row.get("nombrefamilia", "").strip()
        fam_id = False
        if fam_code or fam_name:
            fam_id = fam_cache.get(fam_code) or fam_cache.get(fam_name.upper())
            if not fam_id:
                fam_id = models.execute_kw(args.db, uid, password, "product.family", "create", [{"code": fam_code, "name": fam_name or fam_code}])
                if fam_code:
                    fam_cache[fam_code] = fam_id
                if fam_name:
                    fam_cache[fam_name.upper()] = fam_id

        # Clase
        cls_code = row.get("clase", "").strip()
        cls_name = row.get("nombreclase", "").strip()
        cls_id = False
        if cls_code or cls_name:
            cls_id = class_cache.get(cls_code) or class_cache.get(cls_name.upper())
            if not cls_id:
                cls_id = models.execute_kw(args.db, uid, password, "product.class", "create", [{"code": cls_code, "name": cls_name or cls_code}])
                if cls_code:
                    class_cache[cls_code] = cls_id
                if cls_name:
                    class_cache[cls_name.upper()] = cls_id

        # Línea
        lin_code = row.get("linea", "").strip()
        lin_name = row.get("nombrelinea", "").strip()
        lin_id = False
        if lin_code or lin_name:
            lin_id = line_cache.get(lin_code) or line_cache.get(lin_name.upper())
            if not lin_id:
                lin_id = models.execute_kw(args.db, uid, password, "product.line", "create", [{"code": lin_code, "name": lin_name or lin_code}])
                if lin_code:
                    line_cache[lin_code] = lin_id
                if lin_name:
                    line_cache[lin_name.upper()] = lin_id

        # Proveedor
        prov_code = row.get("proveedor", "").strip()
        prov_name = row.get("nombre", "").strip()
        prov_id = False
        if prov_name:
            prov_id = partner_cache.get(prov_name.upper()) or partner_cache.get(prov_code)
            if not prov_id:
                prov_id = models.execute_kw(args.db, uid, password, "res.partner", "create", [{"name": prov_name, "ref": prov_code or False}])
                partner_cache[prov_name.upper()] = prov_id
                if prov_code:
                    partner_cache[prov_code] = prov_id

        cost_real = parse_float(row.get("costoreal"))
        plista = parse_float(row.get("plista"))
        p1 = parse_float(row.get("p1"))
        sale_price = p1 if p1 > 0 else plista

        vals = {
            "name": name,
            "default_code": code,
            "barcode": row.get("alterno", "").strip() or False,
            "cve_prod_serv": row.get("alterno2", "").strip() or False,
            "family_id": fam_id,
            "class_id": cls_id,
            "line_id": lin_id,
            "primary_supplier_id": prov_id,
            "standard_price": cost_real,
            "costo_real": cost_real,
            "list_price": sale_price,
            "plista": plista,
            "dcto_prov": parse_float(row.get("dctoprov")),
            "p1": p1,
            "p2": parse_float(row.get("p2")),
            "p3": parse_float(row.get("p3")),
            "p4": parse_float(row.get("p4")),
            "p5": parse_float(row.get("p5")),
            "p6": parse_float(row.get("p6")),
            "type": "consu",
            "is_storable": True,
            "uom_id": default_uom_id,
            "uom_po_id": default_uom_id,
        }

        tmpl_id = tmpl_cache.get(code)
        if tmpl_id:
            models.execute_kw(args.db, uid, password, "product.template", "write", [[tmpl_id], vals])
            updated += 1
        else:
            tmpl_id = models.execute_kw(args.db, uid, password, "product.template", "create", [vals])
            tmpl_cache[code] = tmpl_id
            created += 1

        if i % 100 == 0 or i == len(rows):
            print(f"Progreso: {i}/{len(rows)} productos procesados (Creados: {created}, Actualizados: {updated})...")

    print("\n¡Importación finalizada con éxito!")
    print(f"- Total procesados: {len(rows)}")
    print(f"- Creados: {created}")
    print(f"- Actualizados: {updated}")


if __name__ == "__main__":
    main()
