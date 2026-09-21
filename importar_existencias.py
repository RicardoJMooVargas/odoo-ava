#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de importación masiva de Existencias por Almacén AVA para Odoo 19.
Módulo: ava_inventario

Uso:
  python importar_existencias.py --user tu_usuario@email.com
  python importar_existencias.py --user tu_usuario@email.com --dry-run
  python importar_existencias.py --csv "LISTA DE EXISTENCIAS.xlsx - LISTA DE EXISTENCIAS.csv"
"""

import os
import csv
import sys
import getpass
import argparse
import unicodedata
import xmlrpc.client


def parse_float(val):
    if not val:
        return 0.0
    try:
        val_str = str(val).strip().replace(",", "")
        return float(val_str)
    except (ValueError, TypeError):
        return 0.0


def normalize_key(text):
    if not text:
        return ""
    text = str(text).strip()
    nfkd = unicodedata.normalize("NFKD", text).encode("ASCII", "ignore").decode("utf-8")
    return nfkd.lower()


def conectar_odoo(url, db, user, password):
    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})
    if not uid:
        raise PermissionError(f"No se pudo autenticar el usuario '{user}' en la base de datos '{db}'.")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return uid, models


def main():
    parser = argparse.ArgumentParser(description="Importar Existencias por Almacén AVA a Odoo 19")
    parser.add_argument("--url", default="http://localhost:8069", help="URL de Odoo (default: http://localhost:8069)")
    parser.add_argument("--db", default=os.getenv("DB_NAME", "odoo"), help="Nombre de la BD (default: odoo)")
    parser.add_argument("--user", default=os.getenv("ODOO_USER", "admin"), help="Usuario de Odoo")
    parser.add_argument("--password", default=os.getenv("ODOO_PASSWORD"), help="Contraseña (si se omite, se solicita)")
    parser.add_argument("--csv", default="LISTA DE EXISTENCIAS.xlsx - LISTA DE EXISTENCIAS.csv", help="Ruta al archivo CSV de existencias")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin escribir en Odoo")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: No se encontró el archivo CSV: {args.csv}")
        sys.exit(1)

    print(f"Leyendo archivo de existencias: {args.csv}")
    with open(args.csv, mode="r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Total de filas leídas: {len(rows)}")

    norm_headers = {normalize_key(h): h for h in (reader.fieldnames or [])}
    col_codigo = norm_headers.get("codigo")
    col_ava01 = norm_headers.get("ava01")
    col_ava02 = norm_headers.get("ava02")
    col_ava03 = norm_headers.get("ava03")
    col_ava04 = norm_headers.get("ava04")
    col_ubic = norm_headers.get("ubicacion")

    if not col_codigo:
        print("Error: Columna 'Codigo' no encontrada en el archivo.")
        sys.exit(1)

    if args.dry_run:
        print("[MODO DRY-RUN] Verificando existencias por almacén...")
        stats = {"AVA01": 0, "AVA02": 0, "AVA03": 0, "AVA04": 0}
        total_non_zero = 0
        with_ubic = 0

        for r in rows:
            code = r.get(col_codigo, "").strip()
            if not code:
                continue
            if col_ubic and r.get(col_ubic, "").strip():
                with_ubic += 1

            has_qty = False
            for wh, col in [("AVA01", col_ava01), ("AVA02", col_ava02), ("AVA03", col_ava03), ("AVA04", col_ava04)]:
                if col:
                    qty = parse_float(r.get(col))
                    if qty != 0:
                        stats[wh] += 1
                        has_qty = True
            if has_qty:
                total_non_zero += 1

        print(f"Artículos con ubicación recomendada: {with_ubic}")
        print(f"Artículos con existencia != 0 en al menos un almacén: {total_non_zero}")
        print(f"Desglose por almacén: {stats}")
        print("[DRY-RUN] Validación completada con éxito.")
        return

    password = args.password
    if not password:
        password = getpass.getpass(f"Contraseña de Odoo para '{args.user}': ")

    print(f"Conectando a Odoo en {args.url} (BD: {args.db})...")
    uid, models = conectar_odoo(args.url, args.db, args.user, password)
    print(f"Autenticado exitosamente con UID: {uid}")

    # Verificar almacenes
    print("Verificando almacenes AVA...")
    wh_data = models.execute_kw(args.db, uid, password, "stock.warehouse", "search_read", [[("code", "in", ["AVA01", "AVA02", "AVA03", "AVA04"])]], {"fields": ["id", "code", "lot_stock_id"]})
    wh_locations = {w["code"]: w["lot_stock_id"][0] for w in wh_data}

    missing_wh = [c for c in ["AVA01", "AVA02", "AVA03", "AVA04"] if c not in wh_locations]
    if missing_wh:
        print(f"Advertencia: Faltan los almacenes {missing_wh}. Sincronizando con ava_inventario...")
        models.execute_kw(args.db, uid, password, "stock.warehouse", "action_sync_ava_warehouses", [])
        wh_data = models.execute_kw(args.db, uid, password, "stock.warehouse", "search_read", [[("code", "in", ["AVA01", "AVA02", "AVA03", "AVA04"])]], {"fields": ["id", "code", "lot_stock_id"]})
        wh_locations = {w["code"]: w["lot_stock_id"][0] for w in wh_data}

    # Cargar mapa de productos
    print("Cargando productos existentes en Odoo...")
    prods = models.execute_kw(args.db, uid, password, "product.product", "search_read", [[("default_code", "!=", False)]], {"fields": ["id", "default_code", "ubicacion_recomendada"]})
    prod_cache = {p["default_code"].strip(): p for p in prods}

    adjusted_counts = {"AVA01": 0, "AVA02": 0, "AVA03": 0, "AVA04": 0}
    updated_ubic = 0

    print("Aplicando ajustes de existencias...")
    for i, r in enumerate(rows, start=1):
        code = r.get(col_codigo, "").strip()
        if not code or code not in prod_cache:
            continue

        prod_info = prod_cache[code]
        prod_id = prod_info["id"]

        # Ubicación recomendada
        if col_ubic:
            ubic_val = r.get(col_ubic, "").strip()
            if ubic_val and prod_info.get("ubicacion_recomendada") != ubic_val:
                models.execute_kw(args.db, uid, password, "product.product", "write", [[prod_id], {"ubicacion_recomendada": ubic_val}])
                updated_ubic += 1

        # Ajustes de existencias
        for wh_code, col in [("AVA01", col_ava01), ("AVA02", col_ava02), ("AVA03", col_ava03), ("AVA04", col_ava04)]:
            if not col or wh_code not in wh_locations:
                continue
            raw_qty = parse_float(r.get(col))
            if raw_qty <= 0:
                continue

            loc_id = wh_locations[wh_code]
            # Buscar quant existente
            quants = models.execute_kw(args.db, uid, password, "stock.quant", "search_read", [[("product_id", "=", prod_id), ("location_id", "=", loc_id)]], {"fields": ["id"]})
            if quants:
                quant_id = quants[0]["id"]
                models.execute_kw(args.db, uid, password, "stock.quant", "write", [[quant_id], {"inventory_quantity": raw_qty}], {"context": {"inventory_mode": True}})
            else:
                quant_id = models.execute_kw(args.db, uid, password, "stock.quant", "create", [{"product_id": prod_id, "location_id": loc_id, "inventory_quantity": raw_qty}], {"context": {"inventory_mode": True}})

            models.execute_kw(args.db, uid, password, "stock.quant", "action_apply_inventory", [[quant_id]])
            adjusted_counts[wh_code] += 1

        if i % 200 == 0 or i == len(rows):
            print(f"Progreso: {i}/{len(rows)} productos procesados...")

    print("\n¡Ajuste de existencias completado exitosamente!")
    print(f"- Ubicaciones recomendadas actualizadas: {updated_ubic}")
    print(f"- Movimientos aplicados por almacén: {adjusted_counts}")


if __name__ == "__main__":
    main()
