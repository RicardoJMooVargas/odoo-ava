# -*- coding: utf-8 -*-
import logging
import time
import unicodedata
from datetime import datetime, timedelta
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
    _description = "Cliente de Integración con AVA_API (/AVA/Token, /AVA/ventas y /AVA/ventas/pagos)"

    @api.model
    def _get_api_config(self):
        params = self.env["ir.config_parameter"].sudo()
        base_url = (params.get_param("ava_api.base_url") or "https://sistemainforweb.com").strip().rstrip("/")
        api_key = (params.get_param("ava_api.api_key") or "").strip()
        client_id = (params.get_param("ava_api.client_id") or "").strip()
        client_secret = (params.get_param("ava_api.client_secret") or "").strip()
        try:
            timeout = int(params.get_param("ava_api.timeout") or 30)
        except ValueError:
            timeout = 30
        return {
            "base_url": base_url,
            "api_key": api_key,
            "client_id": client_id,
            "client_secret": client_secret,
            "timeout": max(timeout, 5),
        }

    @api.model
    def _validate_credentials_present(self, config):
        missing = []
        if not config["api_key"]:
            missing.append("1. API Key (X-Api-Key)")
        if not config["client_id"]:
            missing.append("2. ClientId")
        if not config["client_secret"]:
            missing.append("3. ClientSecret")
        if missing:
            raise UserError(
                _(
                    "Faltan credenciales de AVA_API por configurar:\n- %s\n\n"
                    "Ve a 'Metas y Observaciones -> Configuración AVA_API' para ingresar los 3 parámetros."
                )
                % "\n- ".join(missing)
            )

    @api.model
    def _get_access_token(self, config=None, force_refresh=False):
        """
        Obtiene o reutiliza el token JWT de 15 minutos desde POST /AVA/Token
        enviando X-Api-Key en cabecera y {"ClientId", "ClientSecret"} en el cuerpo JSON.
        """
        if config is None:
            config = self._get_api_config()
        self._validate_credentials_present(config)

        params = self.env["ir.config_parameter"].sudo()
        now = time.time()

        if not force_refresh:
            cached_token = params.get_param("ava_api.cached_token") or ""
            try:
                expires_at = float(params.get_param("ava_api.token_expires_at") or 0)
            except ValueError:
                expires_at = 0.0
            if cached_token and now < expires_at:
                return cached_token

        token_url = f"{config['base_url']}/AVA/Token"
        headers = {
            "X-Api-Key": config["api_key"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "ClientId": config["client_id"],
            "ClientSecret": config["client_secret"],
        }

        try:
            response = requests.post(
                token_url,
                headers=headers,
                json=payload,
                timeout=config["timeout"],
            )
        except Exception as exc:
            raise UserError(
                _("No se pudo conectar con %s:\n%s") % (token_url, exc)
            ) from exc

        if response.status_code == 401:
            raise UserError(
                _(
                    "Acceso denegado (401) en POST %s.\n"
                    "Verifica que API Key (X-Api-Key), ClientId y ClientSecret sean correctos."
                )
                % token_url
            )
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "900")
            raise UserError(
                _(
                    "Límite de intentos excedido (429) en POST %s. "
                    "Espera %s segundos antes de volver a intentar."
                )
                % (token_url, retry_after)
            )

        try:
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise UserError(
                _("Respuesta inválida al solicitar token en %s (HTTP %s):\n%s")
                % (token_url, response.status_code, response.text[:500])
            ) from exc

        access_token = data.get("access_token")
        if not access_token:
            raise UserError(
                _("El servidor no devolvió 'access_token' en %s:\n%s")
                % (token_url, data)
            )

        expires_in = int(data.get("expires_in") or 900)
        # Guardar token en caché con margen de seguridad de 60 segundos antes de vencer
        params.set_param("ava_api.cached_token", access_token)
        params.set_param("ava_api.token_expires_at", str(now + max(expires_in - 60, 60)))
        return access_token

    @api.model
    def _api_get(self, path, query_params=None, config=None):
        """
        Realiza una petición GET a AVA_API enviando tanto:
        - Authorization: Bearer <access_token>
        - X-Api-Key: <API_KEY>
        Maneja renovación automática de token si vence (401) y espera si recibe 429.
        """
        if config is None:
            config = self._get_api_config()

        token = self._get_access_token(config=config, force_refresh=False)
        url = f"{config['base_url']}{path}"

        for attempt in range(2):
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Api-Key": config["api_key"],
                "Accept": "application/json",
            }
            try:
                resp = requests.get(
                    url,
                    headers=headers,
                    params=query_params or {},
                    timeout=config["timeout"],
                )
            except Exception as exc:
                raise UserError(
                    _("Error de conexión al consultar %s:\n%s") % (url, exc)
                ) from exc

            if resp.status_code == 401 and attempt == 0:
                # El token pudo haber expirado; renovamos 1 sola vez
                token = self._get_access_token(config=config, force_refresh=True)
                continue

            if resp.status_code == 429 and attempt == 0:
                retry_sec = min(int(resp.headers.get("Retry-After", 5) or 5), 15)
                _logger.warning("HTTP 429 en %s, esperando %s segundos...", url, retry_sec)
                time.sleep(retry_sec)
                continue

            if resp.status_code >= 400:
                msg = resp.text[:400]
                try:
                    err_json = resp.json()
                    msg = err_json.get("result_message") or msg
                except Exception:
                    pass
                raise UserError(
                    _("Error HTTP %s en %s:\n%s") % (resp.status_code, url, msg)
                )

            return resp.json()

        raise UserError(_("No fue posible completar la consulta a %s.") % url)

    @api.model
    def _split_date_ranges_max_31_days(self, date_start, date_end):
        """
        Según la sección 4.1 de AVA_API, /AVA/ventas permite un rango máximo de 31 días
        por consulta (desde / hasta inclusivo). Divide rangos mayores en bloques <= 30 días.
        """
        if isinstance(date_start, str):
            start_dt = datetime.strptime(date_start[:10], "%Y-%m-%d").date()
        else:
            start_dt = date_start
        if isinstance(date_end, str):
            end_dt = datetime.strptime(date_end[:10], "%Y-%m-%d").date()
        else:
            end_dt = date_end

        ranges = []
        cursor = start_dt
        while cursor <= end_dt:
            chunk_end = min(cursor + timedelta(days=30), end_dt)
            ranges.append((cursor.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
            cursor = chunk_end + timedelta(days=1)
        return ranges

    @api.model
    def _is_excluded_return_payment(self, description):
        norm_desc = _normalize_text(description)
        if not norm_desc:
            return False
        return any(pattern in norm_desc for pattern in EXCLUDED_PAYMENT_DESCRIPTIONS)

    @api.model
    def test_connection(self):
        config = self._get_api_config()
        token = self._get_access_token(config=config, force_refresh=True)
        catalogs_resp = self._api_get("/AVA/Catalogos", config=config)
        catalogs = catalogs_resp.get("data", []) if isinstance(catalogs_resp, dict) else []
        cat_codes = ", ".join(c.get("codigo", "") for c in catalogs if isinstance(c, dict)) or "OK"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("¡Conexión y Token Exitosos!"),
                "message": _(
                    "Token JWT emitido correctamente en POST /AVA/Token (%s...). "
                    "Catálogos activos en /AVA/Catalogos: %s"
                )
                % (token[:15], cat_codes),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def fetch_agent_sales_and_payments(self, nombre_alias, date_start, date_end):
        """
        1. Obtiene token JWT con POST /AVA/Token (X-Api-Key + ClientId + ClientSecret).
        2. Consulta GET /AVA/ventas?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&estatus=A
           y filtra por nombreVendedor == nombre_alias.
        3. Por cada venta del vendedor, consulta GET /AVA/ventas/pagos?tipo=...&caja=...&serie=...&folio=...
           y suma 'importe' excluyendo los pagos cuya 'descripcion' contenga:
           - '99 NOTA DE DEVOLUCI'
           - 'DEVOLUCION DE PRODUCTO'
        """
        target_alias = _normalize_text(nombre_alias)
        if not target_alias:
            raise UserError(
                _("La trabajadora no tiene configurado un 'Nombre Alias' para empatar con 'nombreVendedor' en /AVA/ventas.")
            )

        config = self._get_api_config()
        date_chunks = self._split_date_ranges_max_31_days(date_start, date_end)

        matched_sales = []
        for desde_str, hasta_str in date_chunks:
            ventas_payload = self._api_get(
                "/AVA/ventas",
                query_params={
                    "desde": desde_str,
                    "hasta": hasta_str,
                    "estatus": "A",
                },
                config=config,
            )
            sales_list = ventas_payload if isinstance(ventas_payload, list) else ventas_payload.get("ventas", [])
            for sale in sales_list:
                if not isinstance(sale, dict):
                    continue
                vendor_name = _normalize_text(sale.get("nombreVendedor"))
                if vendor_name == target_alias:
                    matched_sales.append(sale)

        valid_sales_amount = 0.0
        excluded_returns_amount = 0.0
        valid_payments_count = 0
        excluded_payments_count = 0

        # Consultar /AVA/ventas/pagos por cada venta del vendedor
        for idx, sale in enumerate(matched_sales, start=1):
            # Control preventivo de rate-limit (máximo 60 GET por minuto según sección 1.3)
            if idx % 50 == 0:
                time.sleep(1.2)

            tipo = str(sale.get("tipo") or "").strip()
            caja = str(sale.get("caja") or "").strip()
            serie = str(sale.get("serie") or "").strip()
            folio = str(sale.get("folio") or "").strip()
            if folio.isdigit() and len(folio) < 6:
                folio = folio.zfill(6)

            if not (tipo and caja and folio):
                continue

            pago_params = {
                "tipo": tipo,
                "caja": caja,
                "folio": folio,
            }
            if serie:
                pago_params["serie"] = serie

            pagos_payload = self._api_get(
                "/AVA/ventas/pagos",
                query_params=pago_params,
                config=config,
            )
            pagos_list = (
                pagos_payload.get("pagos", [])
                if isinstance(pagos_payload, dict)
                else (pagos_payload if isinstance(pagos_payload, list) else [])
            )

            for payment in pagos_list:
                if not isinstance(payment, dict):
                    continue
                try:
                    importe = float(payment.get("importe") or 0.0)
                except (ValueError, TypeError):
                    importe = 0.0
                descripcion = str(payment.get("descripcion") or "").strip()

                if self._is_excluded_return_payment(descripcion):
                    excluded_returns_amount += importe
                    excluded_payments_count += 1
                else:
                    valid_sales_amount += importe
                    valid_payments_count += 1

        return {
            "matched_sales_count": len(matched_sales),
            "valid_payments_count": valid_payments_count,
            "excluded_payments_count": excluded_payments_count,
            "valid_sales_amount": round(valid_sales_amount, 2),
            "excluded_returns_amount": round(excluded_returns_amount, 2),
        }
