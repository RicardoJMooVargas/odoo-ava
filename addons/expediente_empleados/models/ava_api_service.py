# -*- coding: utf-8 -*-
import json
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

# Ventana deslizante en memoria del worker para no superar 55 GET / 60s
_REQUEST_TIMESTAMPS = []


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
    def _throttle_get_request(self):
        """
        Respeta el límite de 60 peticiones GET por minuto por IP (Sección 1.3).
        Mantiene un margen seguro de máximo 52 peticiones cada 60 segundos.
        """
        global _REQUEST_TIMESTAMPS
        now = time.time()
        _REQUEST_TIMESTAMPS = [ts for ts in _REQUEST_TIMESTAMPS if now - ts < 61.0]
        if len(_REQUEST_TIMESTAMPS) >= 52:
            oldest = _REQUEST_TIMESTAMPS[0]
            wait_seconds = max(61.5 - (now - oldest), 1.0)
            _logger.info("Control de límite AVA_API (60 req/min): esperando %.1fs...", wait_seconds)
            time.sleep(wait_seconds)
            now = time.time()
            _REQUEST_TIMESTAMPS = [ts for ts in _REQUEST_TIMESTAMPS if now - ts < 61.0]
        _REQUEST_TIMESTAMPS.append(time.time())

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
            retry_after = response.headers.get("Retry-After", "60")
            raise UserError(
                _(
                    "Límite de peticiones excedido (429) en POST %s. "
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
        params.set_param("ava_api.cached_token", access_token)
        params.set_param("ava_api.token_expires_at", str(now + max(expires_in - 60, 60)))
        return access_token

    @api.model
    def _api_get(self, path, query_params=None, config=None):
        """
        Realiza una petición GET a AVA_API enviando tanto:
        - Authorization: Bearer <access_token>
        - X-Api-Key: <API_KEY>
        Respeta la cabecera Retry-After cuando el servidor responde HTTP 429.
        """
        if config is None:
            config = self._get_api_config()

        token = self._get_access_token(config=config, force_refresh=False)
        url = f"{config['base_url']}{path}"

        for attempt in range(5):
            self._throttle_get_request()
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

            if resp.status_code == 401 and attempt < 2:
                token = self._get_access_token(config=config, force_refresh=True)
                continue

            if resp.status_code == 429:
                raw_retry = resp.headers.get("Retry-After")
                try:
                    retry_sec = int(float(raw_retry)) + 2 if raw_retry else 20
                except (ValueError, TypeError):
                    retry_sec = 20
                retry_sec = max(min(retry_sec, 65), 5)
                _logger.warning(
                    "HTTP 429 en %s (intento %s/5). Esperando %s segundos según Retry-After...",
                    url, attempt + 1, retry_sec
                )
                if attempt < 4:
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

        raise UserError(_("Se agotaron los reintentos por límite de peticiones (429) en %s.") % url)

    @api.model
    def _load_payments_cache(self):
        raw = self.env["ir.config_parameter"].sudo().get_param("ava_api.payments_cache_v1") or "{}"
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @api.model
    def _save_payments_cache(self, cache_dict):
        # Conservar máximo las últimas 15,000 ventas en caché para mantener ligero el parámetro
        if len(cache_dict) > 15000:
            keys_to_keep = list(cache_dict.keys())[-12000:]
            cache_dict = {k: cache_dict[k] for k in keys_to_keep}
        self.env["ir.config_parameter"].sudo().set_param(
            "ava_api.payments_cache_v1", json.dumps(cache_dict)
        )

    @api.model
    def _split_date_ranges_max_31_days(self, date_start, date_end):
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
           usando caché persistente de ventas saldadas y control de tasa (60 req/min) para evitar HTTP 429.
        """
        target_alias = _normalize_text(nombre_alias)
        if not target_alias:
            raise UserError(
                _("La trabajadora no tiene configurado un 'Nombre Alias' para empatar con 'nombreVendedor' en /AVA/ventas.")
            )

        start_wall_time = time.time()
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

        payments_cache = self._load_payments_cache()
        cache_modified = False

        valid_sales_amount = 0.0
        excluded_returns_amount = 0.0
        valid_payments_count = 0
        excluded_payments_count = 0
        processed_sales_count = 0
        pending_sales_count = 0
        api_calls_made = 0

        for sale in matched_sales:
            tipo = str(sale.get("tipo") or "").strip()
            caja = str(sale.get("caja") or "").strip()
            serie = str(sale.get("serie") or "").strip()
            folio = str(sale.get("folio") or "").strip()
            if folio.isdigit() and len(folio) < 6:
                folio = folio.zfill(6)

            if not (tipo and caja and folio):
                continue

            sale_key = f"{tipo}|{caja}|{serie}|{folio}"
            cached_entry = payments_cache.get(sale_key)

            if cached_entry is not None:
                valid_sales_amount += float(cached_entry.get("valid_amount", 0.0))
                excluded_returns_amount += float(cached_entry.get("excluded_amount", 0.0))
                valid_payments_count += int(cached_entry.get("valid_count", 0))
                excluded_payments_count += int(cached_entry.get("excluded_count", 0))
                processed_sales_count += 1
                continue

            # Si llevamos más de 42 segundos o 50 llamadas nuevas en esta ejecución,
            # guardamos el avance en caché para no exceder el límite de 60 GET/min ni el timeout web.
            if api_calls_made >= 50 or (time.time() - start_wall_time) > 42.0:
                pending_sales_count += 1
                continue

            pago_params = {
                "tipo": tipo,
                "caja": caja,
                "folio": folio,
            }
            if serie:
                pago_params["serie"] = serie

            try:
                pagos_payload = self._api_get(
                    "/AVA/ventas/pagos",
                    query_params=pago_params,
                    config=config,
                )
                api_calls_made += 1
            except UserError:
                # Si ocurre 429 u otro error tras varias ventas, guardar lo avanzado en caché antes de propagar o continuar
                if cache_modified:
                    self._save_payments_cache(payments_cache)
                    self.env.cr.commit()
                raise

            pagos_list = (
                pagos_payload.get("pagos", [])
                if isinstance(pagos_payload, dict)
                else (pagos_payload if isinstance(pagos_payload, list) else [])
            )

            sale_valid_amt = 0.0
            sale_excl_amt = 0.0
            sale_valid_cnt = 0
            sale_excl_cnt = 0

            for payment in pagos_list:
                if not isinstance(payment, dict):
                    continue
                try:
                    importe = float(payment.get("importe") or 0.0)
                except (ValueError, TypeError):
                    importe = 0.0
                descripcion = str(payment.get("descripcion") or "").strip()

                if self._is_excluded_return_payment(descripcion):
                    sale_excl_amt += importe
                    sale_excl_cnt += 1
                else:
                    sale_valid_amt += importe
                    sale_valid_cnt += 1

            valid_sales_amount += sale_valid_amt
            excluded_returns_amount += sale_excl_amt
            valid_payments_count += sale_valid_cnt
            excluded_payments_count += sale_excl_cnt
            processed_sales_count += 1

            # Guardar en caché si la venta ya tiene pagos registrados
            if (sale_valid_cnt + sale_excl_cnt) > 0:
                payments_cache[sale_key] = {
                    "valid_amount": round(sale_valid_amt, 2),
                    "excluded_amount": round(sale_excl_amt, 2),
                    "valid_count": sale_valid_cnt,
                    "excluded_count": sale_excl_cnt,
                }
                cache_modified = True

        if cache_modified:
            self._save_payments_cache(payments_cache)

        return {
            "matched_sales_count": len(matched_sales),
            "processed_sales_count": processed_sales_count,
            "pending_sales_count": pending_sales_count,
            "valid_payments_count": valid_payments_count,
            "excluded_payments_count": excluded_payments_count,
            "valid_sales_amount": round(valid_sales_amount, 2),
            "excluded_returns_amount": round(excluded_returns_amount, 2),
        }
