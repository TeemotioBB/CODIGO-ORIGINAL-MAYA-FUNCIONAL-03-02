"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              💳 SYNCPAY INTEGRATION — Sophia Bot v8.3 APEX                  ║
║                                                                              ║
║  Módulo separado. Não mexa em IA_SEM_CAPI.py além das 3 linhas abaixo.     ║
║                                                                              ║
║  INSTALAÇÃO — adicione em IA_SEM_CAPI.py:                                  ║
║                                                                              ║
║  1) No topo do arquivo, junto dos outros imports:                           ║
║       import syncpay_integration                                             ║
║                                                                              ║
║  2) Logo abaixo da linha  "application = setup_application()"  :           ║
║       syncpay_integration.init(                                              ║
║           flask_app   = app,                                                 ║
║           bot_app     = application,                                         ║
║           event_loop  = loop,                                                ║
║           redis_conn  = r,                                                   ║
║           callbacks   = {                                                    ║
║               "set_clicked_vip" : set_clicked_vip,                          ║
║               "add_bonus_msgs"  : add_bonus_msgs,                           ║
║               "save_message"    : save_message,                              ║
║               "get_router"      : get_router,                                ║
║               "CANAL_VIP_LINK"  : CANAL_VIP_LINK,                           ║
║               "PRECO_VIP"       : PRECO_VIP,                                 ║
║           }                                                                  ║
║       )                                                                      ║
║                                                                              ║
║  3) Substitua a função send_teaser_and_apex pelo wrapper do módulo:         ║
║     Procure a linha:                                                         ║
║         send_teaser_and_pitch = send_teaser_and_apex                        ║
║     E adicione logo abaixo:                                                  ║
║         send_teaser_and_apex = syncpay_integration.send_teaser_com_pix      ║
║         send_teaser_and_pitch = syncpay_integration.send_teaser_com_pix     ║
║                                                                              ║
║  VARIÁVEIS DE AMBIENTE necessárias:                                         ║
║       SYNCPAY_CLIENT_ID      → seu client_id do painel SyncPay              ║
║       SYNCPAY_CLIENT_SECRET  → seu client_secret do painel SyncPay          ║
║       WEBHOOK_BASE_URL       → já existe no seu .env (ex: railway.app)      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import asyncio
import logging
import random
import importlib
import requests
from datetime import datetime, timedelta, date
from flask import request as flask_request, jsonify
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import CallbackQueryHandler

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️  CONFIGURAÇÕES SYNCPAY — lidas do ambiente
# ═══════════════════════════════════════════════════════════════════════════════

SYNCPAY_CLIENT_ID     = "423ab714-71b3-4ee1-8f28-602415b2bf92"
SYNCPAY_CLIENT_SECRET = "65ea61dd-eb51-4ce1-b3e0-fc2fcd838b6b"
SYNCPAY_BASE_URL      = "https://api.syncpay.com.br"
WEBHOOK_BASE_URL      = os.getenv("WEBHOOK_BASE_URL", "")
SYNCPAY_WEBHOOK_PATH  = "/webhook/syncpay"

PIX_VALIDADE_MINUTOS = 30

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️  ESTADO INTERNO (referências injetadas via init())
# ═══════════════════════════════════════════════════════════════════════════════

_r          = None
_loop       = None
_bot_app    = None
_callbacks  = {}

_token_cache = {"token": None, "expires_at": None}

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
        f"{SYNCPAY_BASE_URL}/api/partner/v1/auth-token",
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
        f"{SYNCPAY_BASE_URL}/api/partner/v1/cash-in",
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


# ═══════════════════════════════════════════════════════════════════════════════
# 📤  ENVIO DO PIX NO CHAT
# ═══════════════════════════════════════════════════════════════════════════════

async def _enviar_pix_no_chat(bot, chat_id: int, uid: int, pix_data: dict):
    preco = _callbacks.get("PRECO_VIP", "R$ 12,90")
    pix_code = pix_data["pix_code"]

    mensagem = (
        f"✅ *PIX gerado! Pague em até {PIX_VALIDADE_MINUTOS} minutos:*\n\n"
        f"💰 Valor: *{preco}*\n\n"
        f"*Como pagar em 30 segundos:*\n"
        f"1️⃣ Abra o app do seu banco\n"
        f"2️⃣ Vá em PIX → *Copia e Cola* (ou QR Code)\n"
        f"3️⃣ Cole o código abaixo ⬇️\n"
        f"4️⃣ Confirme e pronto! ✅\n\n"
        f"*Código PIX (copia e cola):*"
    )

    await bot.send_message(chat_id=chat_id, text=mensagem, parse_mode="Markdown")
    await asyncio.sleep(0.5)

    await bot.send_message(chat_id=chat_id, text=f"`{pix_code}`", parse_mode="Markdown")

    await asyncio.sleep(0.5)
    await bot.send_message(
        chat_id=chat_id,
        text=(
            "⏰ *Confirmação automática!*\n"
            "Assim que o pagamento cair, você recebe o acesso VIP aqui mesmo automaticamente 💕\n\n"
            "Qualquer dúvida é só me chamar 😊"
        ),
        parse_mode="Markdown"
    )

    save_message = _callbacks.get("save_message")
    if save_message:
        save_message(uid, "system", f"💳 PIX ENVIADO (id={pix_data['identifier']})")


# ═══════════════════════════════════════════════════════════════════════════════
# 🎯  SUBSTITUTO DE send_teaser_and_apex
# ═══════════════════════════════════════════════════════════════════════════════

async def send_teaser_com_pix(bot, chat_id: int, uid: int):
    try:
        import importlib
        bot_main = importlib.import_module("sophia_bot_v7.2_clean")
    except ImportError:
        logger.error("[SyncPay] Não consegui importar sophia_bot_v7.2_clean")
        return False

    try:
        get_router      = _callbacks.get("get_router")
        ia_config       = get_router().get_ia_config(uid=uid) if get_router else {}
        fotos_teaser    = ia_config.get("fotos_teaser", bot_main.FOTOS_TEASER)
        preco           = ia_config.get("preco", _callbacks.get("PRECO_VIP", "R$ 12,90"))

        can_offer, reason = bot_main.can_offer_vip(uid)
        if not can_offer:
            logger.info(f"[SyncPay] 🚫 Teaser bloqueado para {uid}: {reason}")
            return False

        ab_group = bot_main.get_ab_group(uid)

        bot_main.set_saw_teaser(uid)
        bot_main.track_funnel(uid, "saw_teaser")
        bot_main.increment_vip_offers(uid)
        bot_main.reset_msgs_since_offer(uid)

        intro = random.choice(bot_main.TEASER_INTRO_MESSAGES[ab_group])
        await bot.send_message(chat_id=chat_id, text=intro)
        await asyncio.sleep(2)

        num_photos = random.randint(3, 4)
        selected   = random.sample(fotos_teaser, min(num_photos, len(fotos_teaser)))

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

        urgencia = bot_main.get_urgency_message(uid)
        pitch = (
            f"E aí amor, curtiu o gostinho? 😈\n\n"
            f"Isso é SÓ preview... no VIP você me tem COMPLETINHA (fotos + vídeos sem censura).\n\n"
            f"💰 *{preco} vitalício*\n\n"
            f"Como pagar em 10 segundos:\n"
            f"1️⃣ Clica no botão abaixo\n"
            f"2️⃣ Copia o código PIX que eu vou te mandar\n"
            f"3️⃣ Cola no app do banco → confirma ✅\n"
            f"4️⃣ Acesso liberado automático!\n\n"
            f"{urgencia}"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔥 GERAR PIX AGORA 🔥", callback_data="pagar_vip")
        ]])

        await bot.send_message(
            chat_id=chat_id,
            text=pitch,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

        bot_main.mark_vip_just_offered(uid)
        logger.info(f"[SyncPay] 🎯 Teaser+pitch PIX enviado: uid={uid}")
        save_message = _callbacks.get("save_message")
        if save_message:
            save_message(uid, "system", f"💳 TEASER+PITCH PIX enviado (#{bot_main.get_teaser_count(uid)})")

        return True

    except Exception as e:
        logger.error(f"[SyncPay] ❌ Erro send_teaser_com_pix: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 📲  CALLBACK HANDLER — usuário clicou em "GERAR PIX AGORA"
# ═══════════════════════════════════════════════════════════════════════════════

async def _pagar_vip_callback(update: Update, context):
    query = update.callback_query
    await query.answer()

    uid     = query.from_user.id
    chat_id = query.message.chat_id
    bot     = context.bot

    try:
        pix_pendente = _get_pix_pendente(uid)

        if pix_pendente:
            logger.info(f"[SyncPay] ♻️  Reusando PIX pendente: uid={uid}")
            await bot.send_message(
                chat_id=chat_id,
                text="⏳ Você já tem um PIX gerado! Mandando o código de novo pra você:",
                parse_mode="Markdown"
            )
            await _enviar_pix_no_chat(bot, chat_id, uid, pix_pendente)
            return

        await bot.send_message(chat_id=chat_id, text="⏳ Gerando seu PIX, um segundo...")

        try:
            import importlib
            bot_main = importlib.import_module("sophia_bot_v7.2_clean")
            nome = query.from_user.full_name or "Cliente"
            preco_str = _callbacks.get("PRECO_VIP", "12.90")
            valor = float(
                preco_str.replace("R$", "").replace("R$ ", "")
                         .replace(",", ".").strip()
            )
        except Exception as e:
            logger.error(f"[SyncPay] Erro extraindo valor: {e}")
            valor = 12.90
            nome  = "Cliente"

        pix_data = _gerar_pix(uid=uid, amount=valor, nome_cliente=nome)
        await _enviar_pix_no_chat(bot, chat_id, uid, pix_data)

        try:
            import importlib
            bot_main = importlib.import_module("sophia_bot_v7.2_clean")
            bot_main.set_clicked_vip(uid)
            bot_main.track_funnel(uid, "clicked_vip")
        except Exception:
            pass

    except requests.exceptions.HTTPError as e:
        logger.error(f"[SyncPay] Erro HTTP ao gerar PIX: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "😔 Tive um probleminha pra gerar o PIX...\n"
                "Me chama de novo em instantes que resolvo! 💕"
            )
        )
    except Exception as e:
        logger.error(f"[SyncPay] Erro _pagar_vip_callback: {e}")
        await bot.send_message(
            chat_id=chat_id,
            text="😔 Ops, tive um erro aqui. Tenta de novo em alguns segundos? 💕"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 🌐  WEBHOOK SYNCPAY — Flask route
# ═══════════════════════════════════════════════════════════════════════════════

def _register_webhook_route(flask_app):

    @flask_app.route(SYNCPAY_WEBHOOK_PATH, methods=["POST"])
    def syncpay_webhook():
        try:
            data      = flask_request.get_json(silent=True) or {}
            transacao = data.get("data", {})

            identifier = transacao.get("id")
            status     = transacao.get("status")
            amount     = transacao.get("final_amount") or transacao.get("amount")

            logger.info(f"[SyncPay Webhook] id={identifier} status={status} valor={amount}")

            if status == "completed" and identifier:
                asyncio.run_coroutine_threadsafe(
                    _processar_pagamento_confirmado(identifier, amount),
                    _loop
                )

            return jsonify({}), 200

        except Exception as e:
            logger.error(f"[SyncPay Webhook] Erro: {e}")
            return jsonify({}), 200


async def _processar_pagamento_confirmado(identifier: str, amount):
    try:
        uid_raw = _r.get(_sp_id_to_uid_key(identifier))
        if not uid_raw:
            logger.warning(f"[SyncPay] ⚠️  identifier={identifier} sem uid no Redis (já expirou?)")
            return

        uid = int(uid_raw)
        logger.info(f"[SyncPay] ✅ Pagamento CONFIRMADO: uid={uid} identifier={identifier} valor=R${amount}")

        notif_key = _sp_notified_key(uid, date.today().isoformat())
        if _r.exists(notif_key):
            logger.info(f"[SyncPay] ⚠️  Pagamento já processado para uid={uid} hoje")
            return

        _r.setex(notif_key, timedelta(hours=48), "1")
        _r.setex(_sp_paid_key(uid), timedelta(days=365), "1")

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
            await bot.send_message(
                chat_id=uid,
                text="👇",
                reply_markup=keyboard
            )

        _r.delete(_sp_id_to_uid_key(identifier))
        _r.delete(_sp_pix_key(uid))

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
