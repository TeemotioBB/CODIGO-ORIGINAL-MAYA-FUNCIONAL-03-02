"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              💳 SYNCPAY INTEGRATION — Sophia Bot v8.3 APEX                  ║
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

def _sp_notified_key(uid, date_str):
    return f"sp:notified:{uid}:{date_str}"

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

def _gerar_pix(uid: int, amount: float, nome_cliente: str = "Cliente") -> dict:
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
        })
    )
    _r.setex(
        _sp_id_to_uid_key(identifier),
        timedelta(hours=2),
        str(uid)
    )

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
    }
    _r.setex(
        _sp_customer_key(uid),
        timedelta(hours=2),
        json.dumps(customer_data)
    )
    logger.info(
        f"[Meta Tracking] snapshot PIX uid={uid} | "
        f"fbc={bool(customer_data['fbc'])} fbp={bool(customer_data['fbp'])} "
        f"ip={bool(customer_data['client_ip_address'])} ua={bool(customer_data['client_user_agent'])}"
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
        save_message(
            uid,
            "system",
            f"💳 PIX ENVIADO (id={pix_data['identifier']})"
        )

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯  SUBSTITUTO DE send_teaser_and_apex
# ═══════════════════════════════════════════════════════════════════════════════

async def send_teaser_com_pix(bot, chat_id: int, uid: int):
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
            InlineKeyboardButton(cta_label, callback_data="pagar_vip")
        ]])

        await bot.send_message(
            chat_id=chat_id,
            text=pitch,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

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
    uid     = query.from_user.id
    chat_id = query.message.chat_id
    bot     = context.bot

    touch_followup5 = _callbacks.get("touch_followup5")
    if touch_followup5:
        touch_followup5(uid, "pix", query.from_user.first_name or "")

    activate_hard_wall = _callbacks.get("activate_hard_wall")
    if activate_hard_wall:
        activate_hard_wall(uid)

    try:
        pix_pendente = _get_pix_pendente(uid)
        if pix_pendente:
            logger.info(f"[SyncPay] ♻️ Reusando PIX pendente: uid={uid}")
            await bot.send_message(
                chat_id=chat_id,
                text="⏳ Você já tem um PIX gerado! Mandando o código de novo pra você:",
                parse_mode="Markdown"
            )
            await _enviar_pix_no_chat(bot, chat_id, uid, pix_pendente)
            return

        await bot.send_message(chat_id=chat_id, text="⏳ Gerando seu PIX, um segundo...")

        nome = query.from_user.full_name or "Cliente"

        preco_str = _callbacks.get("PRECO_VIP", "9,00")
        try:
            valor = float(
                preco_str.replace("R$", "").replace("R$ ", "")
                         .replace(",", ".").strip()
            )
        except Exception:
            valor = 9.00

        pix_data = _gerar_pix(uid=uid, amount=valor, nome_cliente=nome)

        # ── Salva dados do cliente no Redis para usar no webhook ──────────────
        # (no webhook o objeto tg_user não está disponível)
        customer_data = _salvar_customer(uid, query.from_user)

        await _enviar_pix_no_chat(bot, chat_id, uid, pix_data)

        # ── TRACKING ORIGEM/CAMPANHA ──────────────────────────────────────────
        try:
            track_source_event = _callbacks.get("track_source_event")
            if track_source_event:
                track_source_event(uid, "pix_created")
        except Exception as track_err:
            logger.error(f"[Tracking] Erro pix_created: {track_err}")

        # ── META CAPI — payment_created ───────────────────────────────────────
        try:
            event_data = {
                "event":     "payment_created",
                "timestamp": int(time.time()),
                "customer": dict(customer_data),
                "transaction": {
                    "internal_transaction_id": pix_data["identifier"],
                    "sale_code":      f"SALE-{uid}-{int(time.time())}",
                    "category":       "Assinatura Premium",
                    "plan_name":      "Plano Normal",
                    "plan_value":     int(valor * 100),
                    "currency":       "BRL",
                    "payment_platform": "syncpay",
                    "payment_method": "pix",
                },
            }
            _r.publish("apex:events", json.dumps(event_data))
            logger.info(f"[Meta CAPI] ✅ payment_created publicado: uid={uid}")
        except Exception as capi_err:
            logger.error(f"[Meta CAPI] Erro ao publicar payment_created: {capi_err}")
        # ─────────────────────────────────────────────────────────────────────

        try:
            set_clicked_vip = _callbacks.get("set_clicked_vip")
            track_funnel = _callbacks.get("track_funnel")
            if set_clicked_vip:
                set_clicked_vip(uid)
            if track_funnel:
                track_funnel(uid, "clicked_vip")
        except Exception as funnel_err:
            logger.error(f"[Tracking] Erro clicked_vip uid={uid}: {funnel_err}")

    except requests.exceptions.HTTPError as e:
        logger.error(f"[SyncPay] Erro HTTP ao gerar PIX: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text="😔 Tive um probleminha pra gerar o PIX...\nMe chama de novo em instantes que resolvo! 💕"
        )
    except Exception as e:
        logger.error(f"[SyncPay] Erro _pagar_vip_callback: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text="😔 Ops, tive um erro aqui. Tenta de novo em alguns segundos? 💕"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 WEBHOOK SYNCPAY — Flask route
# ═══════════════════════════════════════════════════════════════════════════════

def _register_webhook_route(flask_app):
    @flask_app.route(SYNCPAY_WEBHOOK_PATH, methods=["POST"])
    def syncpay_webhook():
        try:
            data       = flask_request.get_json(silent=True) or {}
            transacao  = data.get("data", {})
            identifier = transacao.get("id")
            status     = transacao.get("status")
            amount     = transacao.get("final_amount") or transacao.get("amount")
            logger.info(f"[SyncPay Webhook] id={identifier} status={status} valor={amount}")

            if status in ["completed", "PAID_OUT"] and identifier:
                asyncio.run_coroutine_threadsafe(
                    _processar_pagamento_confirmado(identifier, amount),
                    _loop
                )
            else:
                logger.info(f"[SyncPay] Status ignorado (ainda não pago): {status}")
            return jsonify({}), 200
        except Exception as e:
            logger.error(f"[SyncPay Webhook] Erro: {e}")
            return jsonify({}), 200


async def _processar_pagamento_confirmado(identifier: str, amount):
    try:
        uid_raw = _r.get(_sp_id_to_uid_key(identifier))
        if not uid_raw:
            logger.warning(f"[SyncPay] ⚠️ identifier={identifier} sem uid no Redis (já expirou?)")
            return
        uid = int(uid_raw)
        logger.info(f"[SyncPay] ✅ Pagamento CONFIRMADO: uid={uid} identifier={identifier} valor=R${amount}")

        notif_key = _sp_notified_key(uid, date.today().isoformat())
        if _r.exists(notif_key):
            logger.info(f"[SyncPay] ⚠️ Pagamento já processado para uid={uid} hoje")
            return

        _r.setex(notif_key, timedelta(hours=48), "1")
        _r.setex(_sp_paid_key(uid), timedelta(days=365), "1")

        cancel_followup5 = _callbacks.get("cancel_followup5")
        if cancel_followup5:
            cancel_followup5(uid, paid=True)
        clear_hard_wall = _callbacks.get("clear_hard_wall")
        if clear_hard_wall:
            clear_hard_wall(uid)

        # ── TRACKING ORIGEM/CAMPANHA ──────────────────────────────────────────
        try:
            track_source_event = _callbacks.get("track_source_event")
            if track_source_event:
                track_source_event(uid, "payment_approved", amount=float(amount or 0))
        except Exception as track_err:
            logger.error(f"[Tracking] Erro payment_approved: {track_err}")

        # ── Recupera dados do cliente salvos no momento do PIX ────────────────
        customer_data = _recuperar_customer(uid)

        # ── META CAPI — payment_approved ──────────────────────────────────────
        try:
            event_data = {
                "event":     "payment_approved",
                "timestamp": int(time.time()),
                "customer": dict(customer_data),
                "transaction": {
                    "internal_transaction_id": identifier,
                    "external_transaction_id": identifier,
                    "sale_code":        f"SALE-{uid}-{int(time.time())}",
                    "category":         "Assinatura Premium",
                    "plan_name":        "Plano Normal",
                    "plan_value":       int(float(amount) * 100),
                    "plan_duration":    "vitalicio",
                    "currency":         "BRL",
                    "payment_platform": "syncpay",
                    "payment_method":   "pix",
                },
            }
            _r.publish("apex:events", json.dumps(event_data))
            logger.info(f"[Meta CAPI] ✅ payment_approved publicado: uid={uid} full_name='{customer_data['full_name']}'")
        except Exception as capi_err:
            logger.error(f"[Meta CAPI] Erro ao publicar payment_approved: {capi_err}")
        # ─────────────────────────────────────────────────────────────────────

        set_clicked_vip = _callbacks.get("set_clicked_vip")
        add_bonus_msgs  = _callbacks.get("add_bonus_msgs")
        save_message    = _callbacks.get("save_message")
        get_router      = _callbacks.get("get_router")

        if set_clicked_vip:
            set_clicked_vip(uid)
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
        await bot.send_message(
            chat_id=uid,
            text=(
                "🎉 *PAGAMENTO CONFIRMADO!*\n\n"
                f"💰 Valor recebido: R$ {float(amount):.2f}\n\n"
                "✅ Seu acesso VIP foi liberado! Bem-vindo ao clube exclusivo 💎\n\n"
                "Clica no link abaixo pra acessar todo o conteúdo exclusivo:"
            ),
            parse_mode="Markdown"
        )
        if canal_vip:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("💎 ACESSAR VIP AGORA", url=canal_vip)
            ]])
            await bot.send_message(chat_id=uid, text="👇", reply_markup=keyboard)

        # Limpa chaves temporárias
        _r.delete(_sp_id_to_uid_key(identifier))
        _r.delete(_sp_pix_key(uid))
        _r.delete(_sp_customer_key(uid))   # ← limpa dados do cliente também
        logger.info(f"[SyncPay] 🎉 VIP liberado e usuário notificado: uid={uid}")

    except Exception as e:
        logger.error(f"[SyncPay] ❌ Erro _processar_pagamento_confirmado: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 🚀  INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

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
        CallbackQueryHandler(_pagar_vip_callback, pattern="^pagar_vip$"),
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
