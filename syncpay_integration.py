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

# Validade do PIX gerado (em minutos). Após isso, gera um novo se o usuário
# clicar de novo.
PIX_VALIDADE_MINUTOS = 30

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️  ESTADO INTERNO (referências injetadas via init())
# ═══════════════════════════════════════════════════════════════════════════════

_r          = None   # redis
_loop       = None   # event loop do bot
_bot_app    = None   # telegram Application
_callbacks  = {}     # funções do bot principal

_token_cache = {"token": None, "expires_at": None}

# ═══════════════════════════════════════════════════════════════════════════════
# 🔑  REDIS KEYS (isoladas com prefixo "sp:" pra não colidir com o bot)
# ═══════════════════════════════════════════════════════════════════════════════

def _sp_pix_key(uid):
    """Dados do PIX pendente do usuário."""
    return f"sp:pix:{uid}"

def _sp_id_to_uid_key(identifier):
    """Mapeia identifier SyncPay → uid do Telegram."""
    return f"sp:id2uid:{identifier}"

def _sp_paid_key(uid):
    """Marca que o usuário já pagou."""
    return f"sp:paid:{uid}"

def _sp_notified_key(uid, date_str):
    """Evita notificação duplicada de confirmação."""
    return f"sp:notified:{uid}:{date_str}"

# ═══════════════════════════════════════════════════════════════════════════════
# 🔐  AUTENTICAÇÃO SYNCPAY
# ═══════════════════════════════════════════════════════════════════════════════

def _get_token() -> str:
    """
    Retorna o Bearer Token da SyncPay.
    Gera um novo token apenas quando o anterior expirar (token válido 1 hora).
    """
    agora = datetime.utcnow()

    if _token_cache["token"] and _token_cache["expires_at"]:
        # Renova 5 minutos antes de expirar para evitar rejeição
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

    # expires_at vem como ISO 8601 UTC, ex: "2025-06-22T02:49:47.440458Z"
    expires_str = data["expires_at"].replace("Z", "+00:00")
    _token_cache["expires_at"] = datetime.fromisoformat(expires_str).replace(tzinfo=None)

    logger.info(f"[SyncPay] ✅ Token OK — expira: {_token_cache['expires_at']}")
    return _token_cache["token"]


# ═══════════════════════════════════════════════════════════════════════════════
# 💸  GERAÇÃO DE PIX
# ═══════════════════════════════════════════════════════════════════════════════

def _gerar_pix(uid: int, amount: float, nome_cliente: str = "Cliente") -> dict:
    """
    Cria uma cobrança PIX na SyncPay para o uid informado.

    Retorna: { "pix_code": str, "identifier": str }

    A webhook_url que é passada aponta para /webhook/syncpay deste módulo.
    O identifier é salvo no Redis para identificar o pagamento no webhook.
    """
    token = _get_token()
    webhook_url = f"{WEBHOOK_BASE_URL}{SYNCPAY_WEBHOOK_PATH}"

    payload = {
        "amount": round(amount, 2),
        "description": f"VIP Sophia Bot — uid {uid}",
        "webhook_url": webhook_url,
        "client": {
            "name": nome_cliente or "Cliente",
            # CPF placeholder — a SyncPay aceita 00000000000 para testes
            # Em produção, colete o CPF do usuário antes de gerar o PIX
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
    resultado = resp.json()  # { message, pix_code, identifier }

    identifier = resultado["identifier"]
    pix_code   = resultado["pix_code"]

    # ── Persiste no Redis ─────────────────────────────────────────────────────
    # 1. Dados do PIX vinculados ao uid (para reenvio se usuário clicar de novo)
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
    # 2. Mapeamento identifier → uid (para o webhook encontrar o usuário)
    _r.setex(
        _sp_id_to_uid_key(identifier),
        timedelta(hours=2),
        str(uid)
    )

    logger.info(f"[SyncPay] 💸 PIX gerado: uid={uid} identifier={identifier} valor=R${amount}")
    return {"pix_code": pix_code, "identifier": identifier}


def _get_pix_pendente(uid: int) -> dict | None:
    """
    Retorna os dados do PIX pendente se ainda não expirou.
    Retorna None se não houver PIX ou se já expirou.
    """
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
    """
    Manda o código PIX formatado para o usuário no chat do Telegram.
    """
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

    # Código em bloco separado para facilitar copiar no celular
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
#     Idêntico ao original, mas o botão usa callback_data="pagar_vip"
#     em vez de url=canal_vip — isso permite gerar o PIX na hora do clique
# ═══════════════════════════════════════════════════════════════════════════════

async def send_teaser_com_pix(bot, chat_id: int, uid: int):
    """
    Drop-in replacement para send_teaser_and_apex.

    Diferença única: o botão usa callback_data="pagar_vip" em vez de
    abrir o link do canal. Assim, quando o usuário clicar, o bot gera
    o PIX dinamicamente e manda o código no chat.

    Importe este módulo e reatribua:
        send_teaser_and_apex  = syncpay_integration.send_teaser_com_pix
        send_teaser_and_pitch = syncpay_integration.send_teaser_com_pix
    """
    # ── Imports tardios para evitar circular import ───────────────────────────
    # Usamos o módulo principal apenas para funções auxiliares de controle
    # (can_offer_vip, get_ab_group etc.) que não dependem deste módulo.
    try:
        import IA_SEM_CAPI as bot_main
    except ImportError:
        logger.error("[SyncPay] Não consegui importar IA_SEM_CAPI")
        return False

    try:
        get_router      = _callbacks.get("get_router")
        ia_config       = get_router().get_ia_config(uid=uid) if get_router else {}
        fotos_teaser    = ia_config.get("fotos_teaser", bot_main.FOTOS_TEASER)
        preco           = ia_config.get("preco", _callbacks.get("PRECO_VIP", "R$ 12,90"))

        # Verificação antes de enviar (respeita cooldowns e limites)
        can_offer, reason = bot_main.can_offer_vip(uid)
        if not can_offer:
            logger.info(f"[SyncPay] 🚫 Teaser bloqueado para {uid}: {reason}")
            return False

        ab_group = bot_main.get_ab_group(uid)

        bot_main.set_saw_teaser(uid)
        bot_main.track_funnel(uid, "saw_teaser")
        bot_main.increment_vip_offers(uid)
        bot_main.reset_msgs_since_offer(uid)

        # 1. Intro
        intro = random.choice(bot_main.TEASER_INTRO_MESSAGES[ab_group])
        await bot.send_message(chat_id=chat_id, text=intro)
        await asyncio.sleep(2)

        # 2. Fotos teaser (3–4 aleatórias)
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

        # 3. Pitch com urgência dinâmica
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

        # ── DIFERENÇA CHAVE: callback_data em vez de url ──────────────────────
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
    """
    Chamado quando o usuário clica no botão callback_data="pagar_vip".
    Gera (ou reusa) o PIX e manda o código no chat.
    """
    query = update.callback_query
    await query.answer()  # fecha o "loading" do botão

    uid     = query.from_user.id
    chat_id = query.message.chat_id
    bot     = context.bot

    try:
        # Verifica se já tem PIX pendente não expirado (evita gerar duplicado)
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

        # Gera novo PIX
        await bot.send_message(chat_id=chat_id, text="⏳ Gerando seu PIX, um segundo...")

        try:
            import IA_SEM_CAPI as bot_main
            nome = query.from_user.full_name or "Cliente"
            preco_str = _callbacks.get("PRECO_VIP", "12.90")
            # Remove "R$", espaços e troca vírgula por ponto
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

        # Registra no funil
        try:
            import IA_SEM_CAPI as bot_main
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
    """
    Registra a rota /webhook/syncpay no Flask.
    A SyncPay chamará esta rota quando o status da transação mudar.
    """

    @flask_app.route(SYNCPAY_WEBHOOK_PATH, methods=["POST"])
    def syncpay_webhook():
        """
        Recebe eventos da SyncPay.
        Quando status == 'completed', libera o VIP do usuário e notifica no Telegram.

        ⚠️ A SyncPay tem timeout de 5 segundos — respondemos imediatamente
           e processamos em background.
        """
        try:
            data      = flask_request.get_json(silent=True) or {}
            transacao = data.get("data", {})

            identifier = transacao.get("id")
            status     = transacao.get("status")
            amount     = transacao.get("final_amount") or transacao.get("amount")

            logger.info(f"[SyncPay Webhook] id={identifier} status={status} valor={amount}")

            if status == "completed" and identifier:
                # Roda o processamento sem bloquear a resposta
                asyncio.run_coroutine_threadsafe(
                    _processar_pagamento_confirmado(identifier, amount),
                    _loop
                )

            # Responde imediatamente (< 5s)
            return jsonify({}), 200

        except Exception as e:
            logger.error(f"[SyncPay Webhook] Erro: {e}")
            return jsonify({}), 200  # sempre 200 pra SyncPay não retentar em loop


async def _processar_pagamento_confirmado(identifier: str, amount):
    """
    Chamado quando a SyncPay confirma o pagamento (status=completed).

    1. Descobre qual uid fez o pagamento via Redis
    2. Marca VIP como pago
    3. Libera mensagens bônus
    4. Notifica o usuário no Telegram
    """
    try:
        # Busca uid pelo identifier
        uid_raw = _r.get(_sp_id_to_uid_key(identifier))
        if not uid_raw:
            logger.warning(f"[SyncPay] ⚠️  identifier={identifier} sem uid no Redis (já expirou?)")
            return

        uid = int(uid_raw)
        logger.info(f"[SyncPay] ✅ Pagamento CONFIRMADO: uid={uid} identifier={identifier} valor=R${amount}")

        # Evita processar o mesmo pagamento duas vezes
        notif_key = _sp_notified_key(uid, date.today().isoformat())
        if _r.exists(notif_key):
            logger.info(f"[SyncPay] ⚠️  Pagamento já processado para uid={uid} hoje")
            return

        _r.setex(notif_key, timedelta(hours=48), "1")
        _r.setex(_sp_paid_key(uid), timedelta(days=365), "1")

        # ── Atualiza estado do usuário no bot ─────────────────────────────────
        set_clicked_vip = _callbacks.get("set_clicked_vip")
        add_bonus_msgs  = _callbacks.get("add_bonus_msgs")
        save_message    = _callbacks.get("save_message")
        get_router      = _callbacks.get("get_router")

        if set_clicked_vip:
            set_clicked_vip(uid)

        if add_bonus_msgs:
            add_bonus_msgs(uid, 9999)  # mensagens ilimitadas para VIP

        if save_message:
            save_message(uid, "system", f"💎 PAGAMENTO CONFIRMADO via SyncPay (id={identifier})")

        # ── Notifica o usuário ────────────────────────────────────────────────
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

        # Remove o PIX pendente (já pago)
        _r.delete(_sp_id_to_uid_key(identifier))
        _r.delete(_sp_pix_key(uid))

        logger.info(f"[SyncPay] 🎉 VIP liberado e usuário notificado: uid={uid}")

    except Exception as e:
        logger.error(f"[SyncPay] ❌ Erro _processar_pagamento_confirmado: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 🚀  INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def init(flask_app, bot_app, event_loop, redis_conn, callbacks: dict):
    """
    Inicializa a integração SyncPay.

    Parâmetros:
        flask_app   : objeto Flask (app)  do IA_SEM_CAPI.py
        bot_app     : objeto Application (application) do IA_SEM_CAPI.py
        event_loop  : loop asyncio (loop) do IA_SEM_CAPI.py
        redis_conn  : conexão Redis (r) do IA_SEM_CAPI.py
        callbacks   : dict com as funções e variáveis do bot principal:
            {
                "set_clicked_vip" : set_clicked_vip,
                "add_bonus_msgs"  : add_bonus_msgs,
                "save_message"    : save_message,
                "get_router"      : get_router,
                "CANAL_VIP_LINK"  : CANAL_VIP_LINK,
                "PRECO_VIP"       : PRECO_VIP,
            }
    """
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

    # 1. Registra a rota webhook no Flask
    _register_webhook_route(flask_app)

    # 2. Registra o callback handler "pagar_vip" no bot do Telegram
    #    (antes dos outros handlers genéricos — por isso group=-1)
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
    """Verifica se o uid já fez pagamento confirmado via SyncPay."""
    return bool(_r and _r.exists(_sp_paid_key(uid)))


def pix_pendente(uid: int) -> dict | None:
    """Retorna dados do PIX pendente do usuário, ou None se não houver."""
    return _get_pix_pendente(uid)
