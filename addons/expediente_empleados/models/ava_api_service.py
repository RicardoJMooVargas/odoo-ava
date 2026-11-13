# -*- coding: utf-8 -*-
import logging
import unicodedata
import requests

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

EXCLUDED_PAYMENT_DESCRIPTIONS = (
    "99 NOTA DE DEVOLUCI",
    "DEVOLUCION DE PRODUCTO",
)


def _normalize_text(value):
    """Convierte a mayúsculas, elimina acentos y espacios sobrantes para comparaciones seguras."""
    if not value:
        return ""
    text = str(value).strip().upper()
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


class AvaApiService(models.AbstractModel):
    _name = "ava.api.service"
    _description = "Cliente de Integración con AVA_API (/AVA/ventas y /AVA/ventas/pagos)"

    @api.model
    def _get_api_config(self):
        params = self.env["ir.config_parameter"].sudo()
        base_url = (params.get_param("ava_api.base_url") or "https://logichounds.com").rstrip("/")
        auth_type = params.get_param("ava_api.auth_type") or "bearer"
        username = params.get_param("ava_api.username") or "ADMIN"
        password = params.get_param("ava_api.password") or ""
        api_key = params.get_param("ava_api.api_key") or ""
        api_key_name = params.get_param("ava_api.api_key_name") or "X-API-Key"
        catalogo = params.get_param("ava_api.catalogo") or "AVA01"
        try:
            timeout = int(params.get_param("ava_api.timeout") or 30)
        except ValueError:
            timeout = 30
        return {
            "base_url": base_url,
            "auth_type": auth_type,
            "username": username,
            "password": password,
            "api_key": api_key,
            "api_key_name": api_key_name,
            "catalogo": catalogo,
            "timeout": max(timeout, 5),
        }

    @api.model
    def _build_request_kwargs(self, config, extra_params=None):
        headers = {"Accept": "application/json"}
        params = {"catalogo": config["catalogo"]}
        if config["username"]:
            params.setdefault("usuario", config["username"])
        if extra_params:
            params.update(extra_params)

        auth = None
        auth_type = config["auth_type"]
        if auth_type == "bearer" and config["api_key"]:
            headers["Authorization"] = f"Bearer {config['api_key']}"
        elif auth_type == "basic" and config["username"]:
            auth = (config["username"], config["password"])
        elif auth_type == "api_key_header" and config["api_key"]:
            headers[config["api_key_name"]] = config["api_key"]
        elif auth_type == "api_key_query" and config["api_key"]:
            params[config["api_key_name"]] = config["api_key"]

        return {
            "headers": headers,
            "params": params,
            "auth": auth,
            "timeout": config["timeout"],
        }

    @api.model
    def _extract_list(self, payload, candidate_keys):
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            for key in candidate_keys:
                if isinstance(payload.get(key), list):
                    return payload[key]
            # Fallback: busca el primer valor tipo lista dentro del dict
            for val in payload.values():
                if isinstance(val, list):
                    return val
        return []

    @api.model
    def _is_excluded_return_payment(self, description):
        norm_desc = _normalize_text(description)
        if not norm_desc:
            return False
        return any(pattern in norm_desc for pattern in EXCLUDED_PAYMENT_DESCRIPTIONS)

    @api.model
    def _extract_amount(self, record):
        for key in ("importe", "monto", "total", "montoPago", "importePago", "cantidad", "valor"):
            if key in record and record[key] not in (None, ""):
                try:
                    val = str(record[key]).replace(",", "").replace("$", "").strip()
                    return float(val)
                except (ValueError, TypeError):
                    continue
        return 0.0

    @api.model
    def _extract_sale_id(self, record):
        for key in ("idVenta", "id_venta", "ventaId", "id", "folio", "documento", "numeroVenta"):
            if record.get(key) not in (None, ""):
                return str(record[key]).strip()
        return None

    @api.model
    def _extract_vendor_name(self, record):
        for key in ("nombreVendedor", "nombre_vendedor", "vendedor", "agente", "nombreAgente"):
            if record.get(key):
                return _normalize_text(record[key])
        return ""

    @api.model
    def _extract_payment_description(self, record):
        for key in ("descripcion", "concepto", "tipoPago", "formaPago", "observaciones", "detalle"):
            if record.get(key):
                return str(record[key]).strip()
        return ""

    @api.model
    def test_connection(self):
        config = self._get_api_config()
        url = f"{config['base_url']}/AVA/ventas"
        req_kwargs = self._build_request_kwargs(config)
        try:
            response = requests.get(url, **req_kwargs)
            response.raise_for_status()
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Conexión exitosa con AVA_API"),
                    "message": _("El endpoint %s respondió correctamente (HTTP %s).")
                    % (url, response.status_code),
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as exc:
            raise UserError(
                _("No se pudo conectar con AVA_API (%s):\n%s") % (url, exc)
            ) from exc

    @api.model
    def fetch_agent_sales_and_payments(self, nombre_alias, date_start, date_end):
        """
        Consulta /AVA/ventas filtrando por nombreVendedor == nombre_alias
        y calcula el total de ventas computables desde /AVA/ventas/pagos,
        excluyendo los pagos cuya descripción contenga '99 NOTA DE DEVOLUCI'
        o 'DEVOLUCION DE PRODUCTO'.
        """
        target_alias = _normalize_text(nombre_alias)
        if not target_alias:
            raise UserError(
                _("La trabajadora no tiene configurado un 'Nombre Alias' para empatar con 'nombreVendedor' en AVA_API.")
            )

        config = self._get_api_config()
        start_str = str(date_start) if date_start else ""
        end_str = str(date_end) if date_end else ""

        query_dates = {
            "fechaInicio": start_str,
            "fechaFin": end_str,
            "fecha_inicio": start_str,
            "fecha_fin": end_str,
            "nombreVendedor": nombre_alias.strip(),
        }

        # 1. Consultar /AVA/ventas
        ventas_url = f"{config['base_url']}/AVA/ventas"
        ventas_kwargs = self._build_request_kwargs(config, extra_params=query_dates)
        try:
            ventas_resp = requests.get(ventas_url, **ventas_kwargs)
            ventas_resp.raise_for_status()
            ventas_payload = ventas_resp.json()
        except Exception as exc:
            _logger.error("Error consultando %s: %s", ventas_url, exc)
            raise UserError(
                _("Error al consultar el endpoint de ventas (%s):\n%s") % (ventas_url, exc)
            ) from exc

        all_sales = self._extract_list(ventas_payload, ("ventas", "registros", "data", "items"))
        matched_sales = []
        matched_sale_ids = set()

        for sale in all_sales:
            if not isinstance(sale, dict):
                continue
            vendor = self._extract_vendor_name(sale)
            if vendor == target_alias:
                matched_sales.append(sale)
                sale_id = self._extract_sale_id(sale)
                if sale_id:
                    matched_sale_ids.add(sale_id)

        # 2. Consultar /AVA/ventas/pagos
        pagos_url = f"{config['base_url']}/AVA/ventas/pagos"
        pagos_kwargs = self._build_request_kwargs(config, extra_params=query_dates)
        try:
            pagos_resp = requests.get(pagos_url, **pagos_kwargs)
            pagos_resp.raise_for_status()
            pagos_payload = pagos_resp.json()
        except Exception as exc:
            _logger.error("Error consultando %s: %s", pagos_url, exc)
            raise UserError(
                _("Error al consultar el endpoint de pagos (%s):\n%s") % (pagos_url, exc)
            ) from exc

        all_payments = self._extract_list(pagos_payload, ("pagos", "registros", "data", "items"))

        valid_sales_amount = 0.0
        excluded_returns_amount = 0.0
        valid_payments_count = 0
        excluded_payments_count = 0

        for payment in all_payments:
            if not isinstance(payment, dict):
                continue

            # Verificar si el pago pertenece al vendedor por nombreVendedor o por idVenta empatado en /AVA/ventas
            payment_vendor = self._extract_vendor_name(payment)
            payment_sale_id = self._extract_sale_id(payment)

            belongs_to_agent = False
            if payment_vendor:
                belongs_to_agent = (payment_vendor == target_alias)
            elif payment_sale_id and matched_sale_ids:
                belongs_to_agent = (payment_sale_id in matched_sale_ids)

            if not belongs_to_agent:
                continue

            amount = self._extract_amount(payment)
            description = self._extract_payment_description(payment)

            if self._is_excluded_return_payment(description):
                excluded_returns_amount += amount
                excluded_payments_count += 1
            else:
                valid_sales_amount += amount
                valid_payments_count += 1

        return {
            "matched_sales_count": len(matched_sales),
            "valid_payments_count": valid_payments_count,
            "excluded_payments_count": excluded_payments_count,
            "valid_sales_amount": round(valid_sales_amount, 2),
            "excluded_returns_amount": round(excluded_returns_amount, 2),
        }

