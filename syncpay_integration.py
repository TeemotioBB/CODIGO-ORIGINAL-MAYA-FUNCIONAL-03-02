"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              💳 SYNCPAY INTEGRATION — Sophia Bot v8.5.1 APEX                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import asyncio
import logging
import random
import requests
import time

from datetime import datetime, timedelta, date
from flask import request as flask_request, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import CallbackQueryHandler


logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️  CONFIGURAÇÕES SYNCPAY
# ═══════════════════════════════════════════════════════════════════════════════

SYNCPAY_CLIENT_ID     = os.getenv("SYNCPAY_CLIENT_ID", "").strip()
SYNCPAY_CLIENT_SECRET = os.getenv("SYNCPAY_CLIENT_SECRET", "").strip()
SYNCPAY_BASE_URL      = "https://api.syncpayments.com.br/api/partner/v1"
WEBHOOK_BASE_URL      = os.getenv("WEBHOOK_BASE_URL", "")
SYNCPAY_WEBHOOK_PATH  = "/webhook/syncpay"

PIX_VALIDADE_MINUTOS = 30

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️  ESTADO INTERNO
# ═══════════════════════════════════════════════════════════════════════════════

_r          = None
_loop       = None
_bot_app    = None
_callbacks  = {}

_token_cache = {"token": None, "expires_at": None}

PIX_ALLOWED_ORIGINS = {
    "teaser", "direct_intent", "followup", "limit", "objection",
    "resend", "pix_recovery", "remarketing", "unknown",
}
PIX_QUALIFIED_ORIGINS = {"teaser", "direct_intent", "followup", "objection", "resend"}

def _normalize_pix_origin(raw_callback: str) -> str:
    raw = str(raw_callback or "pagar_vip")
    origin = raw.split("|", 1)[1].strip().lower() if "|" in raw else "unknown"
    return origin if origin in PIX_ALLOWED_ORIGINS else "unknown"

def _is_checkout_qualified(origin: str, first_message: bool, saw_teaser: bool) -> bool:
    """Sinal forte para Meta: contexto comercial + alguma interação/pitch real."""
    return bool(origin in PIX_QUALIFIED_ORIGINS and (first_message or saw_teaser))

def _parse_syncpay_webhook(payload):
    """Aceita payload oficial no corpo raiz e envelopes legados data/transaction."""
    if not isinstance(payload, dict):
        return None, "", None
    nested = payload.get("data")
    transaction = nested if isinstance(nested, dict) else payload
    if isinstance(transaction.get("transaction"), dict):
        transaction = transaction["transaction"]
    identifier = transaction.get("id") or transaction.get("identifier")
    status = str(transaction.get("status") or "").strip().lower()
    amount = transaction.get("final_amount")
    if amount is None:
        amount = transaction.get("amount")
    return (str(identifier) if identifier else None), status, amount


# ═══════════════════════════════════════════════════════════════════════════════
# 🔧  INTEGRAÇÃO COM O BOT PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════════════
# IMPORTANTE: não reimportamos sophia_bot_v7.2_clean.py aqui.
# Tudo que o SyncPay precisa do bot principal chega por callbacks no init().
# Isso evita executar novamente o startup, Redis, handlers e schedulers a cada PIX.

# ═══════════════════════════════════════════════════════════════════════════════
# 🔑  REDIS KEYS
# ═══════════════════════════════════════════════════════════════════════════════

def _sp_pix_key(uid):
    return f"sp:pix:{uid}"

def _sp_id_to_uid_key(identifier):
    return f"sp:id2uid:{identifier}"

def _sp_paid_key(uid):
    return f"sp:paid:{uid}"

def _sp_pix_created_key(uid):
    """Marca persistente de que o usuário já gerou ao menos um PIX."""
    return f"sp:pix_created:{uid}"

def _sp_processed_tx_key(identifier):
    return f"sp:processed_tx:{identifier}"

def _sp_pix_origin_key(uid):
    return f"sp:pix_origin:{uid}"

def _sp_customer_key(uid):
    """Chave para salvar dados do cliente no momento do PIX"""
    return f"sp:customer:{uid}"


def _meta_tracking_key(uid):
    return f"meta:tracking:{uid}"


def _get_meta_tracking(uid: int) -> dict:
    """Lê os identificadores Meta vinculados ao Telegram UID."""
    try:
        callback = _callbacks.get("get_meta_tracking")
        if callback:
            data = callback(uid) or {}
        else:
            data = _r.hgetall(_meta_tracking_key(uid)) or {}
        return {
            "fbc": str(data.get("fbc") or "").strip(),
            "fbp": str(data.get("fbp") or "").strip(),
            "client_ip_address": str(data.get("ip") or data.get("client_ip_address") or "").strip(),
            "client_user_agent": str(data.get("user_agent") or data.get("client_user_agent") or "").strip(),
            "page_url": str(data.get("page_url") or "").strip(),
            "referrer": str(data.get("referrer") or "").strip(),
            "city": str(data.get("city") or "").strip(),
            "state": str(data.get("state") or "").strip(),
            "zip": str(data.get("zip") or "").strip(),
            "country": str(data.get("country") or "").strip().lower(),
        }
    except Exception as e:
        logger.error(f"[Meta Tracking] Erro lendo tracking uid={uid}: {e}")
        return {}

# ═══════════════════════════════════════════════════════════════════════════════
# 🔐  AUTENTICAÇÃO SYNCPAY
# ═══════════════════════════════════════════════════════════════════════════════

def _get_token() -> str:
    agora = datetime.utcnow()

    if _token_cache["token"] and _token_cache["expires_at"]:
        if agora < _token_cache["expires_at"] - timedelta(minutes=5):
            return _token_cache["token"]

    logger.info("[SyncPay] 🔄 Gerando novo token de autenticação...")

    resp = requests.post(
        f"{SYNCPAY_BASE_URL}/auth-token",
        json={
            "client_id": SYNCPAY_CLIENT_ID,
            "client_secret": SYNCPAY_CLIENT_SECRET,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    _token_cache["token"] = data["access_token"]

    expires_str = data["expires_at"].replace("Z", "+00:00")
    _token_cache["expires_at"] = datetime.fromisoformat(expires_str).replace(tzinfo=None)

    logger.info(f"[SyncPay] ✅ Token OK — expira: {_token_cache['expires_at']}")
    return _token_cache["token"]


# ═══════════════════════════════════════════════════════════════════════════════
# 💸  GERAÇÃO DE PIX
# ═══════════════════════════════════════════════════════════════════════════════

def _gerar_pix(uid: int, amount: float, nome_cliente: str = "Cliente", origin: str = "unknown", checkout_qualified: bool = False) -> dict:
    token = _get_token()
    webhook_url = f"{WEBHOOK_BASE_URL}{SYNCPAY_WEBHOOK_PATH}"

    payload = {
        "amount": round(amount, 2),
        "description": f"VIP Sophia Bot — uid {uid}",
        "webhook_url": webhook_url,
        "client": {
            "name": nome_cliente or "Cliente",
            "cpf": "00000000000",
            "email": f"user{uid}@sophiabot.com",
            "phone": "11999999999",
        },
    }

    resp = requests.post(
        f"{SYNCPAY_BASE_URL}/cash-in",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    resultado = resp.json()

    identifier = resultado["identifier"]
    pix_code   = resultado["pix_code"]

    _r.setex(
        _sp_pix_key(uid),
        timedelta(minutes=PIX_VALIDADE_MINUTOS),
        json.dumps({
            "identifier": identifier,
            "pix_code":   pix_code,
            "amount":     amount,
            "created_at": datetime.utcnow().isoformat(),
            "origin": origin,
            "checkout_qualified": bool(checkout_qualified),
        })
    )
    _r.setex(
        _sp_id_to_uid_key(identifier),
        timedelta(days=7),
        str(uid)
    )

    # Mantém um marco cumulativo para o funil do painel. Diferente de sp:pix:<uid>,
    # esta chave não some quando o PIX expira ou quando o pagamento é concluído.
    _r.setex(
        _sp_pix_created_key(uid),
        timedelta(days=365),
        "1"
    )
    # Índice temporal do funil: primeira criação de PIX por usuário.
    try:
        _r.zadd("admin:funnel:ts:pix_created", {str(uid): float(time.time())}, nx=True)
    except Exception as idx_err:
        logger.debug(f"[Admin Funnel] Erro indexando pix_created uid={uid}: {idx_err}")

    logger.info(f"[SyncPay] 💸 PIX gerado: uid={uid} identifier={identifier} valor=R${amount}")
    return {"pix_code": pix_code, "identifier": identifier}


def _get_pix_pendente(uid: int):
    data = _r.get(_sp_pix_key(uid))
    if not data:
        return None
    try:
        return json.loads(data)
    except Exception:
        return None


def _salvar_customer(uid: int, tg_user) -> dict:
    """
    Salva os dados do usuário Telegram + identificadores Meta no momento do PIX.
    O webhook de pagamento usa esse snapshot para manter exatamente o mesmo match data.
    """
    tracking = _get_meta_tracking(uid)
    customer_data = {
        "chat_id":       uid,
        "full_name":     tg_user.full_name or "",
        "username":      tg_user.username or "",
        "language_code": tg_user.language_code or "pt-br",
        "fbc": tracking.get("fbc", ""),
        "fbp": tracking.get("fbp", ""),
        "client_ip_address": tracking.get("client_ip_address", ""),
        "client_user_agent": tracking.get("client_user_agent", ""),
        "page_url": tracking.get("page_url", ""),
        "referrer": tracking.get("referrer", ""),
        "city": tracking.get("city", ""),
        "state": tracking.get("state", ""),
        "zip": tracking.get("zip", ""),
        "country": tracking.get("country", ""),
    }
    _r.setex(
        _sp_customer_key(uid),
        timedelta(days=7),
        json.dumps(customer_data)
    )
    logger.info(
        f"[Meta Tracking] snapshot PIX uid={uid} | "
        f"fbc={bool(customer_data['fbc'])} fbp={bool(customer_data['fbp'])} "
        f"ip={bool(customer_data['client_ip_address'])} ua={bool(customer_data['client_user_agent'])} | "
        f"city='{customer_data.get('city', '')}' "
        f"state='{customer_data.get('state', '')}' "
        f"zip='{customer_data.get('zip', '')}' "
        f"country='{customer_data.get('country', '')}'"
    )
    return customer_data


def _recuperar_customer(uid: int) -> dict:
    """Recupera cliente do PIX e completa tracking caso o snapshot esteja ausente/incompleto."""
    tracking = _get_meta_tracking(uid)
    fallback = {
        "chat_id": uid,
        "full_name": "",
        "username": "",
        "language_code": "pt-br",
        "fbc": tracking.get("fbc", ""),
        "fbp": tracking.get("fbp", ""),
        "client_ip_address": tracking.get("client_ip_address", ""),
        "client_user_agent": tracking.get("client_user_agent", ""),
        "page_url": tracking.get("page_url", ""),
        "referrer": tracking.get("referrer", ""),
        "city": tracking.get("city", ""),
        "state": tracking.get("state", ""),
        "zip": tracking.get("zip", ""),
        "country": tracking.get("country", ""),
    }
    raw = _r.get(_sp_customer_key(uid))
    if not raw:
        return fallback
    try:
        data = json.loads(raw)
        for key, value in fallback.items():
            if not data.get(key) and value:
                data[key] = value
        return data
    except Exception:
        return fallback


# ═══════════════════════════════════════════════════════════════════════════════
# 📤  ENVIO DO PIX NO CHAT
# ═══════════════════════════════════════════════════════════════════════════════

import html


async def _enviar_pix_no_chat(bot, chat_id: int, uid: int, pix_data: dict):
    preco = _callbacks.get("PRECO_VIP", "R$ 9,00")
    pix_code = pix_data["pix_code"]

    preco_html = html.escape(str(preco))
    pix_code_html = html.escape(str(pix_code))

    mensagem = (
        f"✅ <b>PIX gerado! Pague em até {PIX_VALIDADE_MINUTOS} minutos:</b>\n\n"
        f"💰 Valor: <b>{preco_html}</b>\n\n"
        f"<b>Como pagar em 30 segundos:</b>\n"
        f"1️⃣ Abra o app do seu banco\n"
        f"2️⃣ Vá em PIX → <b>Copia e Cola</b> (ou QR Code)\n"
        f"3️⃣ Copie o código abaixo ⬇️\n"
        f"4️⃣ Confirme e pronto! ✅\n\n"
        f"<b>Código PIX (copia e cola):</b>\n"
        f"<pre>{pix_code_html}</pre>\n\n"
        f"⏰ <b>Confirmação automática!</b>\n"
        f"Assim que o pagamento cair, você recebe o acesso VIP aqui mesmo automaticamente 💕\n\n"
        f"Qualquer dúvida é só me chamar 😊"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📋 COPIAR CÓDIGO PIX",
                api_kwargs={
                    "copy_text": {
                        "text": pix_code
                    }
                }
            )
        ]
    ])

    await bot.send_message(
        chat_id=chat_id,
        text=mensagem,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    save_message = _callbacks.get("save_message")
    if save_message:
        save_message(uid, "maya", mensagem)
        save_message(
            uid,
            "system",
            f"💳 PIX ENVIADO (id={pix_data['identifier']})"
        )

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯  SUBSTITUTO DE send_teaser_and_apex
# ═══════════════════════════════════════════════════════════════════════════════

async def send_teaser_com_pix(bot, chat_id: int, uid: int, payment_origin: str = "direct_intent"):
    try:
        get_router = _callbacks.get("get_router")
        ia_config = get_router().get_ia_config(uid=uid) if get_router else {}

        fotos_teaser_default = _callbacks.get("FOTOS_TEASER", [])
        fotos_teaser = ia_config.get("fotos_teaser", fotos_teaser_default)
        preco = ia_config.get("preco", _callbacks.get("PRECO_VIP", "R$ 9,00"))

        can_offer_vip = _callbacks.get("can_offer_vip")
        get_ab_group = _callbacks.get("get_ab_group")
        set_saw_teaser = _callbacks.get("set_saw_teaser")
        track_funnel = _callbacks.get("track_funnel")
        increment_vip_offers = _callbacks.get("increment_vip_offers")
        reset_msgs_since_offer = _callbacks.get("reset_msgs_since_offer")
        teaser_intro_messages = _callbacks.get("TEASER_INTRO_MESSAGES", {})
        get_urgency_message = _callbacks.get("get_urgency_message")
        get_cta_label = _callbacks.get("get_cta_label")
        mark_vip_just_offered = _callbacks.get("mark_vip_just_offered")
        get_teaser_count = _callbacks.get("get_teaser_count")

        required = {
            "can_offer_vip": can_offer_vip,
            "get_ab_group": get_ab_group,
            "set_saw_teaser": set_saw_teaser,
            "track_funnel": track_funnel,
            "increment_vip_offers": increment_vip_offers,
            "reset_msgs_since_offer": reset_msgs_since_offer,
            "get_urgency_message": get_urgency_message,
            "mark_vip_just_offered": mark_vip_just_offered,
            "get_teaser_count": get_teaser_count,
        }
        missing = [name for name, fn in required.items() if not fn]
        if missing:
            logger.error(f"[SyncPay] Callbacks ausentes: {', '.join(missing)}")
            return False

        can_offer, reason = can_offer_vip(uid)
        if not can_offer:
            logger.info(f"[SyncPay] 🚫 Teaser bloqueado para {uid}: {reason}")
            return False

        ab_group = get_ab_group(uid)

        set_saw_teaser(uid)
        track_funnel(uid, "saw_teaser")
        increment_vip_offers(uid)
        reset_msgs_since_offer(uid)

        intro_pool = teaser_intro_messages.get(ab_group) or teaser_intro_messages.get("A") or []
        if intro_pool:
            intro = random.choice(intro_pool)
            await bot.send_message(chat_id=chat_id, text=intro)
            save_message = _callbacks.get("save_message")
            if save_message:
                save_message(uid, "maya", intro)
            await asyncio.sleep(2)

        num_photos = random.randint(3, 4)
        selected = random.sample(fotos_teaser, min(num_photos, len(fotos_teaser))) if fotos_teaser else []

        for i, photo_url in enumerate(selected):
            try:
                await bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
                await asyncio.sleep(0.5)
                await bot.send_photo(chat_id=chat_id, photo=photo_url)
                if i < len(selected) - 1:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"[SyncPay] Erro enviando foto {i}: {e}")

        await asyncio.sleep(3)

        send_vip_intro_audio = _callbacks.get("send_vip_intro_audio")
        if send_vip_intro_audio:
            try:
                await send_vip_intro_audio(bot, chat_id, uid)
                await asyncio.sleep(0.8)
            except Exception as audio_err:
                logger.error(f"[SyncPay] Erro no áudio de apresentação uid={uid}: {audio_err}")

        urgencia = get_urgency_message(uid)
        pitch = (
            f"E aí amor, curtiu o gostinho? 😈\n\n"
            f"Isso que você viu agora é só uma **prévia**...\n\n"
            f"No VIP você me tem **completinha**:\n"
            f"✅ Fotos e vídeos 100% sem censura\n"
            f"✅ Vídeos meus transando, chupando, gozando...\n"
            f"✅ Acesso ao meu WhatsApp pessoal (só você e eu)\n"
            f"✅ Pode me chamar a hora que quiser e pedir o que quiser 💦\n\n"
            f"Tudo isso por apenas **{preco} vitalício** 🔥\n\n"
            f"{urgencia}\n\n"
            f"Quer garantir seu acesso agora? Clica no botão abaixo 👇"
        )

        cta_label = get_cta_label(uid) if get_cta_label else "🔥 GERAR PIX AGORA 🔥"
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(cta_label, callback_data=f"pagar_vip|{payment_origin}")
        ]])

        await bot.send_message(
            chat_id=chat_id,
            text=pitch,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        save_message = _callbacks.get("save_message")
        if save_message:
            save_message(uid, "maya", pitch)

        mark_vip_just_offered(uid)
        activate_hard_wall = _callbacks.get("activate_hard_wall")
        if activate_hard_wall:
            activate_hard_wall(uid)
        activate_followup5 = _callbacks.get("activate_followup5")
        if activate_followup5:
            activate_followup5(uid, reset_stage=False)

        logger.info(f"[SyncPay] 🎯 Teaser+pitch PIX enviado: uid={uid}")
        save_message = _callbacks.get("save_message")
        if save_message:
            save_message(uid, "system", f"💳 TEASER+PITCH PIX enviado (#{get_teaser_count(uid)})")

        return True

    except Exception as e:
        logger.error(f"[SyncPay] ❌ Erro send_teaser_com_pix: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 📲 CALLBACK HANDLER — usuário clicou em "GERAR PIX AGORA"
# ═══════════════════════════════════════════════════════════════════════════════

async def _pagar_vip_callback(update: Update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    chat_id = query.message.chat_id
    bot = context.bot

    origin = _normalize_pix_origin(query.data)

    # Qualificação: InitiateCheckout só vai à Meta quando houve contexto comercial real.
    first_message = bool(_r.exists(f"first_message_seen:{uid}"))
    saw_teaser = bool(_r.exists(f"saw_teaser:{uid}"))
    checkout_qualified = _is_checkout_qualified(origin, first_message, saw_teaser)

    touch_followup5 = _callbacks.get("touch_followup5")
    if touch_followup5:
        touch_followup5(uid, "pix", query.from_user.first_name or "")
    activate_hard_wall = _callbacks.get("activate_hard_wall")
    if activate_hard_wall:
        activate_hard_wall(uid)

    try:
        set_clicked_vip = _callbacks.get("set_clicked_vip")
        track_funnel = _callbacks.get("track_funnel")
        track_source_event = _callbacks.get("track_source_event")
        if set_clicked_vip:
            set_clicked_vip(uid)
        if track_funnel:
            track_funnel(uid, "clicked_vip")
        if track_source_event:
            track_source_event(uid, f"pix_click_{origin}")
    except Exception as funnel_err:
        logger.error(f"[Tracking] Erro clicked_vip uid={uid}: {funnel_err}")

    try:
        pix_pendente = _get_pix_pendente(uid)
        if pix_pendente:
            logger.info(f"[SyncPay] ♻️ Reusando PIX pendente: uid={uid} origin={origin}")
            reused_msg = "⏳ Você já tem um PIX gerado! Mandando o código de novo pra você:"
            await bot.send_message(chat_id=chat_id, text=reused_msg)
            save_message = _callbacks.get("save_message")
            if save_message:
                save_message(uid, "maya", reused_msg)
            await _enviar_pix_no_chat(bot, chat_id, uid, pix_pendente)
            return

        generating_msg = "⏳ Gerando seu PIX, um segundo..."
        await bot.send_message(chat_id=chat_id, text=generating_msg)
        save_message = _callbacks.get("save_message")
        if save_message:
            save_message(uid, "maya", generating_msg)
        nome = query.from_user.full_name or "Cliente"
        preco_str = _callbacks.get("PRECO_VIP", "9,00")
        try:
            valor = float(preco_str.replace("R$", "").replace("R$ ", "").replace(",", ".").strip())
        except Exception:
            valor = 9.00

        pix_data = _gerar_pix(
            uid=uid, amount=valor, nome_cliente=nome,
            origin=origin, checkout_qualified=checkout_qualified,
        )
        customer_data = _salvar_customer(uid, query.from_user)

        # Guarda a PRIMEIRA origem de geração por usuário (coerente com o funil único)
        # e também a última para diagnóstico de tentativas posteriores.
        origin_key = _sp_pix_origin_key(uid)
        _r.hsetnx(origin_key, "first_origin", origin)
        _r.hsetnx(origin_key, "first_identifier", pix_data["identifier"])
        _r.hsetnx(origin_key, "first_qualified", "1" if checkout_qualified else "0")
        _r.hsetnx(origin_key, "first_at", datetime.utcnow().isoformat())
        _r.hset(origin_key, mapping={
            "last_origin": origin,
            "last_identifier": pix_data["identifier"],
            "last_qualified": "1" if checkout_qualified else "0",
            "last_at": datetime.utcnow().isoformat(),
        })
        _r.expire(origin_key, timedelta(days=365))

        await _enviar_pix_no_chat(bot, chat_id, uid, pix_data)

        try:
            track_source_event = _callbacks.get("track_source_event")
            if track_source_event:
                track_source_event(uid, f"pix_from_{origin}")
        except Exception as track_err:
            logger.error(f"[Tracking] Erro pix_created: {track_err}")

        try:
            event_data = {
                "event": "payment_created",
                "timestamp": int(time.time()),
                "customer": dict(customer_data),
                "tracking": {"checkout_qualified": checkout_qualified, "pix_origin": origin},
                "transaction": {
                    "internal_transaction_id": pix_data["identifier"],
                    "sale_code": f"SALE-{uid}-{int(time.time())}",
                    "category": "Assinatura Premium",
                    "plan_name": "Plano Normal",
                    "plan_value": int(valor * 100),
                    "currency": "BRL",
                    "payment_platform": "syncpay",
                    "payment_method": "pix",
                    "pix_origin": origin,
                },
            }
            _r.publish("apex:events", json.dumps(event_data))
            logger.info(f"[Meta CAPI] payment_created uid={uid} origin={origin} qualified={checkout_qualified}")
        except Exception as capi_err:
            logger.error(f"[Meta CAPI] Erro ao publicar payment_created: {capi_err}")

    except requests.exceptions.HTTPError as e:
        logger.error(f"[SyncPay] Erro HTTP ao gerar PIX: {e}")
        error_msg = "😔 Tive um probleminha pra gerar o PIX...\nMe chama de novo em instantes que resolvo! 💕"
        await bot.send_message(chat_id=chat_id, text=error_msg)
        save_message = _callbacks.get("save_message")
        if save_message:
            save_message(uid, "maya", error_msg)
    except Exception as e:
        logger.error(f"[SyncPay] Erro _pagar_vip_callback: {e}")
        error_msg = "😔 Ops, tive um erro aqui. Tenta de novo em alguns segundos? 💕"
        await bot.send_message(chat_id=chat_id, text=error_msg)
        save_message = _callbacks.get("save_message")
        if save_message:
            save_message(uid, "maya", error_msg)

def _register_webhook_route(flask_app):
    @flask_app.route(SYNCPAY_WEBHOOK_PATH, methods=["POST"])
    def syncpay_webhook():
        try:
            payload = flask_request.get_json(silent=True) or {}
            identifier, status, amount = _parse_syncpay_webhook(payload)
            logger.info(f"[SyncPay Webhook] id={identifier} status={status} valor={amount}")

            # 'completed' é o status de cash-in concluído na documentação atual.
            if status in {"completed", "paid_out"} and identifier:
                asyncio.run_coroutine_threadsafe(
                    _processar_pagamento_confirmado(str(identifier), amount), _loop
                )
            else:
                logger.info(f"[SyncPay] Status ignorado (ainda não pago): {status or 'ausente'}")
            return jsonify({}), 200
        except Exception as e:
            # Retorna 200 para não causar tempestade de retry, mas registra payload/erro.
            logger.exception(f"[SyncPay Webhook] Erro: {e}")
            return jsonify({}), 200

async def _processar_pagamento_confirmado(identifier: str, amount):
    processing_key = _sp_processed_tx_key(identifier)
    # Lock curto contra webhooks duplicados simultâneos.
    if not _r.set(processing_key, "processing", nx=True, ex=300):
        logger.info(f"[SyncPay] webhook duplicado/tx em processamento: {identifier}")
        return
    try:
        uid_raw = _r.get(_sp_id_to_uid_key(identifier))
        if not uid_raw:
            logger.warning(f"[SyncPay] ⚠️ identifier={identifier} sem uid no Redis")
            _r.delete(processing_key)
            return
        uid = int(uid_raw)

        pix_data = _get_pix_pendente(uid) or {}
        try:
            paid_amount = float(amount if amount is not None else pix_data.get("amount") or 0)
        except Exception:
            paid_amount = float(pix_data.get("amount") or 0)
        logger.info(f"[SyncPay] ✅ Pagamento CONFIRMADO: uid={uid} identifier={identifier} valor=R${paid_amount:.2f}")

        _r.setex(_sp_paid_key(uid), timedelta(days=365), "1")
        try:
            _r.zadd("admin:funnel:ts:paid", {str(uid): float(time.time())}, nx=True)
            _r.zadd("admin:funnel:ts:pix_created", {str(uid): float(time.time())}, nx=True)
        except Exception as idx_err:
            logger.debug(f"[Admin Funnel] Erro indexando pagamento uid={uid}: {idx_err}")

        cancel_followup5 = _callbacks.get("cancel_followup5")
        if cancel_followup5:
            cancel_followup5(uid, paid=True)
        clear_hard_wall = _callbacks.get("clear_hard_wall")
        if clear_hard_wall:
            clear_hard_wall(uid)

        try:
            track_source_event = _callbacks.get("track_source_event")
            if track_source_event:
                track_source_event(uid, "payment_approved", amount=paid_amount)
        except Exception as track_err:
            logger.error(f"[Tracking] Erro payment_approved: {track_err}")

        customer_data = _recuperar_customer(uid)
        origin_meta = _r.hgetall(_sp_pix_origin_key(uid)) or {}
        pix_origin = origin_meta.get("last_origin") or origin_meta.get("first_origin") or pix_data.get("origin") or "unknown"

        try:
            event_data = {
                "event": "payment_approved",
                "timestamp": int(time.time()),
                "customer": dict(customer_data),
                "transaction": {
                    "internal_transaction_id": identifier,
                    "external_transaction_id": identifier,
                    "sale_code": f"SALE-{uid}-{int(time.time())}",
                    "category": "Assinatura Premium",
                    "plan_name": "Plano Normal",
                    "plan_value": int(paid_amount * 100),
                    "plan_duration": "vitalicio",
                    "currency": "BRL",
                    "payment_platform": "syncpay",
                    "payment_method": "pix",
                    "pix_origin": pix_origin,
                },
            }
            _r.publish("apex:events", json.dumps(event_data))
            logger.info(f"[Meta CAPI] ✅ payment_approved publicado: uid={uid} origin={pix_origin}")
        except Exception as capi_err:
            logger.error(f"[Meta CAPI] Erro ao publicar payment_approved: {capi_err}")

        # Compra confirmada NÃO inventa clicked_vip/saw_teaser/first_message.
        # Essas etapas permanecem 100% literais no painel.
        add_bonus_msgs = _callbacks.get("add_bonus_msgs")
        save_message = _callbacks.get("save_message")
        get_router = _callbacks.get("get_router")
        if add_bonus_msgs:
            add_bonus_msgs(uid, 9999)
        if save_message:
            save_message(uid, "system", f"💎 PAGAMENTO CONFIRMADO via SyncPay (id={identifier})")

        canal_vip = _callbacks.get("CANAL_VIP_LINK", "")
        if get_router:
            try:
                ia_config = get_router().get_ia_config(uid=uid)
                canal_vip = ia_config.get("vip_link", canal_vip)
            except Exception:
                pass

        bot = _bot_app.bot
        payment_confirmed_msg = (
            "🎉 *PAGAMENTO CONFIRMADO!*\n\n"
            f"💰 Valor recebido: R$ {paid_amount:.2f}\n\n"
            "✅ Seu acesso VIP foi liberado!\n\n"
            "Clica no link abaixo pra acessar o conteúdo:"
        )
        await bot.send_message(
            chat_id=uid,
            text=payment_confirmed_msg,
            parse_mode="Markdown"
        )
        if save_message:
            save_message(uid, "maya", payment_confirmed_msg)
        if canal_vip:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("💎 ACESSAR VIP AGORA", url=canal_vip)
            ]])
            await bot.send_message(chat_id=uid, text="👇", reply_markup=keyboard)

        # Marca DONE por 30 dias: retries posteriores da mesma tx são idempotentes.
        _r.setex(processing_key, timedelta(days=30), "done")
        _r.delete(_sp_id_to_uid_key(identifier))
        _r.delete(_sp_pix_key(uid))
        _r.delete(_sp_customer_key(uid))
        logger.info(f"[SyncPay] 🎉 VIP liberado e usuário notificado: uid={uid}")
    except Exception as e:
        logger.exception(f"[SyncPay] ❌ Erro _processar_pagamento_confirmado: {e}")
        try:
            if _r.get(processing_key) == "processing":
                _r.delete(processing_key)
        except Exception:
            pass

def init(flask_app, bot_app, event_loop, redis_conn, callbacks: dict):
    global _r, _loop, _bot_app, _callbacks

    if not SYNCPAY_CLIENT_ID or not SYNCPAY_CLIENT_SECRET:
        raise RuntimeError(
            "❌ [SyncPay] Configure SYNCPAY_CLIENT_ID e SYNCPAY_CLIENT_SECRET "
            "nas variáveis de ambiente!"
        )

    _r         = redis_conn
    _loop      = event_loop
    _bot_app   = bot_app
    _callbacks = callbacks

    _register_webhook_route(flask_app)

    bot_app.add_handler(
        CallbackQueryHandler(_pagar_vip_callback, pattern=r"^pagar_vip(?:\|[a-z0-9_]+)?$"),
        group=-1
    )

    logger.info(
        f"[SyncPay] ✅ Integração iniciada!\n"
        f"  Webhook URL: {WEBHOOK_BASE_URL}{SYNCPAY_WEBHOOK_PATH}\n"
        f"  Client ID:   {SYNCPAY_CLIENT_ID[:8]}***"
    )
    logger.info("[SyncPay] 🔔 Lembre-se de registrar este webhook no painel SyncPay!")


# ═══════════════════════════════════════════════════════════════════════════════
# 🛠️  UTILITÁRIOS EXTRAS
# ═══════════════════════════════════════════════════════════════════════════════

def usuario_pagou(uid: int) -> bool:
    return bool(_r and _r.exists(_sp_paid_key(uid)))


def pix_pendente(uid: int):
    return _get_pix_pendente(uid)
