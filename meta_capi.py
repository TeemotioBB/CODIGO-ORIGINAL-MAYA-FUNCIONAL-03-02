# meta_capi.py
# Meta Conversions API - Integração com ApexVips

import os
import json
import asyncio
import aiohttp
import hashlib
import logging
import time
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# ==================== CONFIGURAÇÕES ====================
META_PIXEL_ID     = os.getenv("META_PIXEL_ID", "988265177099445")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")  # ⚠️ defina no ambiente, nunca no código
REDIS_URL         = os.getenv("REDIS_URL", "redis://default:DcddfJOHLXZdFPjEhRjHeodNgdtrsevl@shuttle.proxy.rlwy.net:12241")
TEST_EVENT_CODE   = os.getenv("META_TEST_EVENT_CODE")  # deixe vazio em produção

redis_client = None

async def get_redis():
    global redis_client
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
    """Ex: 'pt-br' → 'br', 'en-us' → 'us'"""
    if not language_code:
        return ""
    parts = language_code.strip().lower().split("-")
    return parts[-1] if len(parts) > 1 else parts[0]

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

        # Localização explícita (se o bot coleta)
        if customer.get("city"):
            user_data["ct"] = [hash_value(customer.get("city"))]
        if customer.get("state"):
            user_data["st"] = [hash_value(customer.get("state"))]
        if customer.get("zip"):
            user_data["zp"] = [hash_value(customer.get("zip"))]

        # País: tenta explícito primeiro, depois infere pelo language_code do Telegram
        country = customer.get("country") or extract_country_from_language(
            customer.get("language_code", "")
        )
        if country:
            user_data["country"] = [hash_value(country)]

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

        # ── payload ───────────────────────────────────────────────────────────
        ts = normalize_timestamp(apex_event.get("timestamp"))

        payload = {
            "data": [{
                "event_name":    event_name,
                "event_time":    ts,
                "action_source": "other",
                "event_id":      f"{event_name}_{customer.get('chat_id')}_{ts}",
                "user_data":     user_data,
                "custom_data":   custom_data,
            }],
            "access_token": META_ACCESS_TOKEN,
        }

        if TEST_EVENT_CODE:
            payload["test_event_code"] = TEST_EVENT_CODE

        # ── envio ─────────────────────────────────────────────────────────────
        async with aiohttp.ClientSession() as session:
            url = f"https://graph.facebook.com/v21.0/{META_PIXEL_ID}/events"
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if resp.status == 200:
                    logger.info(
                        f"✅ META CAPI → {event_name} enviado | "
                        f"User {customer.get('chat_id')} | "
                        f"Campos: {list(user_data.keys())}"
                    )
                else:
                    logger.error(f"❌ META CAPI erro {resp.status}: {result}")

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
                    await send_to_meta("InitiateCheckout", apex_event)
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
