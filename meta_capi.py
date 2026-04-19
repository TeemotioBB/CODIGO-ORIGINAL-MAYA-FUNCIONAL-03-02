# meta_capi.py
# Meta Conversions API - Integração limpa com ApexVips (sem mexer no SyncPay)

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
META_PIXEL_ID = "988265177099445"
META_ACCESS_TOKEN = "EAAStT1bZBd7oBRCcSkyyEB3AyxyzCrQJFUlRHLUsGHQfg5pihVEtT5kpcjFjl0wl1f4rbgHszUZCyNLjP5tmAfid1spsCfqhlMHjHZB1tBQ0jLQcpnjs1zPXOEZB1FK56v3fmUPKENcUQjRRknMrXQybeYrXi7ZCOZC56Ls6Qa5XImoJEVWwDV5dtuE9iEJcJQegZDZD"
REDIS_URL = os.getenv("REDIS_URL", "redis://default:DcddfJOHLXZdFPjEhRjHeodNgdtrsevl@shuttle.proxy.rlwy.net:12241")

# Opcional: para testes no Events Manager
TEST_EVENT_CODE = os.getenv("META_TEST_EVENT_CODE")  # deixe vazio em produção

redis_client = None

async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

def hash_value(value: str) -> str:
    """Hash SHA256 obrigatório para PII no CAPI"""
    if not value:
        return ""
    return hashlib.sha256(str(value).strip().lower().encode('utf-8')).hexdigest()

async def send_to_meta(event_name: str, apex_event: dict):
    if not META_PIXEL_ID or not META_ACCESS_TOKEN:
        logger.warning(f"⚠️ META CAPI não configurado para evento {event_name}")
        return

    try:
        customer = apex_event.get("customer", {})
        transaction = apex_event.get("transaction", {})
        tracking = apex_event.get("tracking", {})

        # Dados do usuário (Advanced Matching)
        user_data = {
            "external_id": [hash_value(customer.get("chat_id"))],
        }
        if customer.get("phone"):
            user_data["ph"] = [hash_value(customer.get("phone"))]
        if customer.get("tax_id"):           # CPF
            user_data["external_id"].append(hash_value(customer.get("tax_id")))
        if customer.get("full_name"):
            names = customer["full_name"].split()
            user_data["fn"] = [hash_value(names[0])]
            if len(names) > 1:
                user_data["ln"] = [hash_value(" ".join(names[1:]))]

        # Custom data da compra
        custom_data = {
            "currency": transaction.get("currency", "BRL"),
            "value": float(transaction.get("plan_value", 0)) / 100,  # converte centavos
        }

        payload = {
            "data": [{
                "event_name": event_name,
                "event_time": apex_event.get("timestamp", int(time.time())),
                "action_source": "other",
                "event_id": f"{event_name}_{customer.get('chat_id')}_{apex_event.get('timestamp')}",
                "user_data": user_data,
                "custom_data": custom_data,
                "tracking_data": {
                    "click_id": tracking.get("click_id"),
                    "utm_source": tracking.get("utm_source"),
                    "utm_medium": tracking.get("utm_medium"),
                    "utm_campaign": tracking.get("utm_campaign"),
                }
            }],
            "access_token": META_ACCESS_TOKEN
        }

        if TEST_EVENT_CODE:
            payload["test_event_code"] = TEST_EVENT_CODE

        async with aiohttp.ClientSession() as session:
            url = f"https://graph.facebook.com/v21.0/{META_PIXEL_ID}/events"
            async with session.post(url, json=payload) as resp:
                result = await resp.json()
                if resp.status == 200:
                    logger.info(f"✅ META CAPI → {event_name} enviado | User {customer.get('chat_id')} | R${custom_data['value']}")
                else:
                    logger.error(f"❌ META CAPI erro {resp.status}: {result}")

    except Exception as e:
        logger.exception(f"Erro ao enviar {event_name} para Meta")

# ==================== LISTENER PRINCIPAL ====================
async def capi_listener():
    r = await get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe("apex:events")   # ← canal que vamos publicar

    logger.info("📡 Meta CAPI Listener iniciado (escutando apex:events)")

    async for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                apex_event = json.loads(message['data'])
                event_type = apex_event.get("event")

                if event_type == "payment_approved":
                    await send_to_meta("Purchase", apex_event)
                elif event_type == "payment_created":
                    await send_to_meta("InitiateCheckout", apex_event)
                elif event_type == "user_joined":
                    await send_to_meta("Lead", apex_event)   # ou "CompleteRegistration"

            except Exception as e:
                logger.error(f"Erro processando evento Apex → Meta: {e}")

async def start_capi_tracker():
    """Chame esta função no startup do bot"""
    asyncio.create_task(capi_listener())
