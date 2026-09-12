# meta_capi.py
# Meta Conversions API - Integração com ApexVips

import os
import json
import asyncio
import aiohttp
import hashlib
import logging
import time
import re
import unicodedata
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# ==================== CONFIGURAÇÕES ====================
META_PIXEL_ID     = os.getenv("META_PIXEL_ID", "988265177099445")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")  # ⚠️ defina no ambiente, nunca no código
REDIS_URL         = os.getenv("REDIS_URL", "").strip()
TEST_EVENT_CODE   = os.getenv("META_TEST_EVENT_CODE")  # deixe vazio em produção
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v26.0").strip() or "v26.0"
if not META_GRAPH_VERSION.startswith("v"):
    META_GRAPH_VERSION = f"v{META_GRAPH_VERSION}"

redis_client = None

async def get_redis():
    global redis_client
    if not REDIS_URL:
        raise RuntimeError("REDIS_URL não definido")
    if redis_client is None:
        redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

def hash_value(value) -> str:
    """Hash SHA256 obrigatório para PII no CAPI"""
    if not value:
        return ""
    return hashlib.sha256(str(value).strip().lower().encode("utf-8")).hexdigest()

def normalize_timestamp(ts) -> int:
    """Garante que o timestamp está em segundos (não ms)"""
    ts = int(ts or time.time())
    if ts > 1_000_000_000_000:  # veio em milissegundos
        ts = ts // 1000
    return ts

def extract_country_from_language(language_code: str) -> str:
    """Só infere país quando o locale realmente o contém: pt-br -> br, en-us -> us."""
    if not language_code:
        return ""
    parts = language_code.strip().lower().replace("_", "-").split("-")
    if len(parts) > 1 and len(parts[-1]) == 2 and parts[-1].isalpha():
        return parts[-1]
    return ""



def normalize_meta_location(value, field="generic") -> str:
    """
    Normaliza localização antes do SHA-256.
    - cidade: minúscula, sem acentos/espaços/pontuação
    - estado: idem; preferencialmente código de 2 letras vindo do GeoIP
    - CEP: somente letras/números
    - país: código ISO de 2 letras em minúsculo
    """
    if value is None:
        return ""

    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "undefined"}:
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()

    if field in {"city", "state", "zip"}:
        text = re.sub(r"[^a-z0-9]", "", text)
    elif field == "country":
        text = re.sub(r"[^a-z]", "", text)[:2]
    else:
        text = re.sub(r"\s+", " ", text).strip()

    return text


def clean_unhashed(value) -> str:
    """FBC, FBP, IP e User-Agent devem ser enviados sem SHA-256."""
    if value is None:
        return ""
    value = str(value).strip()
    if not value or value.lower() in {"null", "none", "undefined"}:
        return ""
    return value

# ==================== ENVIO PARA META ====================
async def send_to_meta(event_name: str, apex_event: dict):
    if not META_ACCESS_TOKEN:
        logger.error("❌ META_ACCESS_TOKEN não definido nas variáveis de ambiente")
        return

    try:
        customer    = apex_event.get("customer", {})
        transaction = apex_event.get("transaction", {})

        # ── user_data ─────────────────────────────────────────────────────────
        user_data = {
            "external_id": [hash_value(str(customer.get("chat_id")))],
        }

        # Telefone (maior impacto no match rate no Brasil)
        if customer.get("phone"):
            user_data["ph"] = [hash_value(customer.get("phone"))]

        # Email
        if customer.get("email"):
            user_data["em"] = [hash_value(customer.get("email"))]

        # Nome completo — campo correto: full_name
        if customer.get("full_name"):
            names = customer["full_name"].split()
            user_data["fn"] = [hash_value(names[0])]
            if len(names) > 1:
                user_data["ln"] = [hash_value(" ".join(names[1:]))]

        # Localização: city/state/zip podem vir do GeoIP capturado na landing.
        city = normalize_meta_location(customer.get("city"), "city")
        state = normalize_meta_location(customer.get("state"), "state")
        zip_code = normalize_meta_location(customer.get("zip"), "zip")

        # País: tenta GeoIP explícito primeiro, depois infere pelo language_code do Telegram.
        country = normalize_meta_location(
            customer.get("country") or extract_country_from_language(
                customer.get("language_code", "")
            ),
            "country",
        )

        if city:
            user_data["ct"] = [hash_value(city)]
        if state:
            user_data["st"] = [hash_value(state)]

        # Para Brasil, só envia CEP quando tiver exatamente 8 dígitos.
        # Ex.: "30111000" -> envia | "30111" -> ignora.
        if zip_code:
            if country == "br":
                if zip_code.isdigit() and len(zip_code) == 8:
                    user_data["zp"] = [hash_value(zip_code)]
                else:
                    logger.info(
                        f"[META CAPI] CEP BR ignorado por estar incompleto/inválido: '{zip_code}'"
                    )
            else:
                user_data["zp"] = [hash_value(zip_code)]

        if country:
            user_data["country"] = [hash_value(country)]

        # Identificadores/headers de matching Meta: NÃO aplicar hash.
        fbc = clean_unhashed(customer.get("fbc"))
        fbp = clean_unhashed(customer.get("fbp"))
        client_ip = clean_unhashed(customer.get("client_ip_address"))
        client_ua = clean_unhashed(customer.get("client_user_agent"))

        if fbc:
            user_data["fbc"] = fbc
        if fbp:
            user_data["fbp"] = fbp
        if client_ip:
            user_data["client_ip_address"] = client_ip
        if client_ua:
            user_data["client_user_agent"] = client_ua

        # ── custom_data ───────────────────────────────────────────────────────
        custom_data = {
            "currency":     transaction.get("currency", "BRL"),
            "value":        float(transaction.get("plan_value") or 0) / 100,
            "content_name": transaction.get("plan_name", ""),
            "content_type": "product",
            "num_items":    1,
            "order_id":     transaction.get("internal_transaction_id", ""),
        }
        if transaction.get("plan_id"):
            custom_data["content_ids"] = [str(transaction.get("plan_id"))]
        if transaction.get("pix_origin"):
            custom_data["pix_origin"] = str(transaction.get("pix_origin"))

        # ── payload ───────────────────────────────────────────────────────────
        ts = normalize_timestamp(apex_event.get("timestamp"))

        transaction_id = (
            transaction.get("internal_transaction_id")
            or transaction.get("external_transaction_id")
            or f"{customer.get('chat_id')}_{ts}"
        )

        payload = {
            "data": [{
                "event_name":    event_name,
                "event_time":    ts,
                # Telegram é um app de mensagens; 'chat' é o action_source apropriado.
                "action_source": "chat",
                "event_id":      f"{event_name}_{transaction_id}",
                "user_data":     user_data,
                "custom_data":   custom_data,
            }],
            "access_token": META_ACCESS_TOKEN,
        }

        if TEST_EVENT_CODE:
            payload["test_event_code"] = TEST_EVENT_CODE

        # ── envio ─────────────────────────────────────────────────────────────
        async with aiohttp.ClientSession() as session:
            url = f"https://graph.facebook.com/{META_GRAPH_VERSION}/{META_PIXEL_ID}/events"
            async with session.post(url, json=payload) as resp:
                result = await resp.json()

                if resp.status == 200:
                    logger.info(
                        f"✅ META CAPI → {event_name} enviado | "
                        f"User {customer.get('chat_id')} | "
                        f"Campos: {list(user_data.keys())} | "
                        f"Resposta Meta: {result}"
                    )
                else:
                    logger.error(
                        f"❌ META CAPI erro {resp.status}: {result}"
                    )

    except Exception:
        logger.exception(f"Erro ao enviar {event_name} para Meta")

# ==================== LISTENER PRINCIPAL ====================
async def capi_listener():
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("apex:events")

    logger.info("📡 Meta CAPI Listener iniciado (escutando apex:events)")

    async for message in pubsub.listen():
        if message["type"] == "message":
            try:
                apex_event = json.loads(message["data"])
                event_type = apex_event.get("event")

                if event_type == "payment_approved":
                    await send_to_meta("Purchase", apex_event)
                elif event_type == "payment_created":
                    tracking = apex_event.get("tracking", {}) or {}
                    qualified = tracking.get("checkout_qualified", True)
                    if qualified:
                        await send_to_meta("InitiateCheckout", apex_event)
                    else:
                        logger.info(
                            "META CAPI: InitiateCheckout ignorado por baixa qualificação "
                            f"origin={tracking.get('pix_origin', 'unknown')}"
                        )
                elif event_type == "user_joined":
                    await send_to_meta("Lead", apex_event)

            except Exception as e:
                logger.error(f"Erro processando evento Apex → Meta: {e}")

async def start_capi_tracker():
    """Chame esta função no startup do bot"""
    while True:
        try:
            await capi_listener()
        except Exception as e:
            logger.error(f"⚠️ CAPI listener caiu, reiniciando em 5s: {e}")
            await asyncio.sleep(5)
