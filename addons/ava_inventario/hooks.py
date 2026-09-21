# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def sync_ava_warehouses(env):
    """
    Crea o sincroniza los almacenes AVA requeridos:
      - AVA01: PRINCIPAL ARMANDO VIDRIOS Y ALUMINIOS (suministro/recepción primario)
      - AVA02: BODEGA SECUNDARIA
      - AVA03: BODEGA MADERA
      - AVA04: BODEGA VINILOS
    """
    Warehouse = env['stock.warehouse']
    company = env.company

    ava_configs = [
        {
            'code': 'AVA01',
            'name': 'PRINCIPAL ARMANDO VIDRIOS Y ALUMINIOS',
            'is_primary': True,
        },
        {
            'code': 'AVA02',
            'name': 'BODEGA SECUNDARIA',
            'is_primary': False,
        },
        {
            'code': 'AVA03',
            'name': 'BODEGA MADERA',
            'is_primary': False,
        },
        {
            'code': 'AVA04',
            'name': 'BODEGA VINILOS',
            'is_primary': False,
        },
    ]

    wh_map = {}
    has_buy_resupply = 'buy_to_resupply' in Warehouse._fields
    has_resupply_wh = 'resupply_wh_ids' in Warehouse._fields

    # 1. Buscar si ya existe AVA01 o un almacén por defecto (WH)
    ava01_wh = Warehouse.search([('code', '=', 'AVA01'), ('company_id', '=', company.id)], limit=1)
    if not ava01_wh:
        # Revisar si hay un almacén default 'WH'
        default_wh = Warehouse.search([('code', '=', 'WH'), ('company_id', '=', company.id)], limit=1)
        if default_wh:
            _logger.info("Renombrando almacén por defecto 'WH' a 'AVA01' - 'PRINCIPAL ARMANDO VIDRIOS Y ALUMINIOS'")
            vals = {
                'code': 'AVA01',
                'name': 'PRINCIPAL ARMANDO VIDRIOS Y ALUMINIOS',
            }
            if 'reception_steps' in Warehouse._fields:
                vals['reception_steps'] = 'one_step'
            if 'delivery_steps' in Warehouse._fields:
                vals['delivery_steps'] = 'ship_only'
            if has_buy_resupply:
                vals['buy_to_resupply'] = True
            default_wh.write(vals)
            ava01_wh = default_wh
        else:
            _logger.info("Creando almacén AVA01 - PRINCIPAL ARMANDO VIDRIOS Y ALUMINIOS")
            vals = {
                'code': 'AVA01',
                'name': 'PRINCIPAL ARMANDO VIDRIOS Y ALUMINIOS',
                'company_id': company.id,
            }
            if 'reception_steps' in Warehouse._fields:
                vals['reception_steps'] = 'one_step'
            if 'delivery_steps' in Warehouse._fields:
                vals['delivery_steps'] = 'ship_only'
            if has_buy_resupply:
                vals['buy_to_resupply'] = True
            ava01_wh = Warehouse.create(vals)
    else:
        vals = {
            'name': 'PRINCIPAL ARMANDO VIDRIOS Y ALUMINIOS',
        }
        if has_buy_resupply:
            vals['buy_to_resupply'] = True
        ava01_wh.write(vals)

    wh_map['AVA01'] = ava01_wh

    # 2. Configurar los demás almacenes
    for config in ava_configs[1:]:
        code = config['code']
        name = config['name']
        wh = Warehouse.search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
        if wh:
            wh.write({'name': name})
            _logger.info("Almacén %s actualizado con nombre '%s'", code, name)
        else:
            _logger.info("Creando almacén %s - '%s'", code, name)
            vals = {
                'code': code,
                'name': name,
                'company_id': company.id,
            }
            if 'reception_steps' in Warehouse._fields:
                vals['reception_steps'] = 'one_step'
            if 'delivery_steps' in Warehouse._fields:
                vals['delivery_steps'] = 'ship_only'
            if has_resupply_wh and ava01_wh:
                vals['resupply_wh_ids'] = [(4, ava01_wh.id)]
            wh = Warehouse.create(vals)
        wh_map[code] = wh

    _logger.info("Sincronización de almacenes AVA completada exitosamente.")
    return wh_map


def post_init_hook(env):
    """Hook ejecutado al instalar el módulo."""
    _logger.info("Ejecutando post_init_hook de ava_inventario...")
    sync_ava_warehouses(env)
