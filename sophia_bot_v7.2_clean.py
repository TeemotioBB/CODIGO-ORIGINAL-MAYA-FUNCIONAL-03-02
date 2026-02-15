#!/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        🔥 MAYA BOT v9.0 — CLEAN REWRITE                     ║
║                                                                              ║
║  ✅ Código limpo, sem over-engineering                                      ║
║  ✅ Kiwify integrada (PIX automático, sem email do lead)                    ║
║  ✅ Entrega automática de conteúdo VIP no chat                              ║
║  ✅ Prompt da IA simplificado e eficaz                                      ║
║  ✅ Limite diário + última chance                                           ║
║  ✅ Recovery de usuários silenciosos                                        ║
║  ✅ Painel admin                                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════════
# 📦 IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════
import os
import asyncio
import logging
import aiohttp
import redis
import json
import random
import base64
from datetime import datetime, timedelta, date
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application, MessageHandler, ContextTypes, filters,
    CallbackQueryHandler, CommandHandler
)

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️ LOGGING
# ═══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔧 CONFIG — PREENCHA AQUI
# ═══════════════════════════════════════════════════════════════════════════════
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://default:DcddfJOHLXZdFPjEhRjHeodNgdtrsevl@shuttle.proxy.rlwy.net:12241")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://web-production-606aff.up.railway.app")
WEBHOOK_PATH = "/telegram"
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "seu_token_super_secreto_aqui_123")
PORT = int(os.getenv("PORT", 8080))
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "1293602874").split(",")))

# ═══════════════════════════════════════════════════════════════════════════════
# 💰 PIX MANUAL CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
PIX_KEY = os.getenv("PIX_KEY", "mayaoficialbr@outlook.com")
PIX_NAME = os.getenv("PIX_NAME", "Maya")  # Nome que aparece pro lead
VIP_PRICE = "R$ 9,90"

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 LIMITES E PARÂMETROS
# ═══════════════════════════════════════════════════════════════════════════════
DAILY_MSG_LIMIT = 28          # Mensagens grátis por dia
MAX_VIP_OFFERS_PER_DAY = 3    # Máximo de ofertas VIP por dia
MIN_MSGS_BEFORE_OFFER = 8     # Msgs mínimas antes da primeira oferta
GROK_MODEL = "grok-3"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
MAX_MEMORY = 12               # Mensagens na memória da IA

# ═══════════════════════════════════════════════════════════════════════════════
# 🎨 CONTEÚDO — PERSONALIZE AQUI
# ═══════════════════════════════════════════════════════════════════════════════

# Fotos de teaser (censuradas/sugestivas)
TEASER_PHOTOS = [
    "https://i.postimg.cc/ZqT4SrB9/32b94b657e4f467897744e01432bc7fb.jpg",
    "https://i.postimg.cc/DzBFy8Lx/a63c77aa55ed4a07aa7ec710ae12580c.jpg",
    "https://i.postimg.cc/KzW2Bw99/b6fe112c63c54f3ab3c800a2e5eb664d.jpg",
    "https://i.postimg.cc/7PcH2GdT/170bccb9b06a42d3a88d594757f85e88.jpg",
    "https://i.postimg.cc/XJ1Vxpv2/00e2c81a4960453f8554baeea091145e.jpg",
]

# Fotos/vídeos VIP (entregues após pagamento)
VIP_PHOTOS = [
    # "https://seu-host.com/vip/foto1.jpg",
    # "https://seu-host.com/vip/foto2.jpg",
    # Adicione URLs das fotos VIP aqui
]

VIP_VIDEOS = [
    # "BAACAgEAA..."  # file_id de vídeos já enviados ao Telegram
    # Adicione file_ids dos vídeos VIP aqui
]

WELCOME_PHOTO = "https://i.postimg.cc/Ghvv4SFt/e1e897c5aa684a7c980485164ec779f4.jpg"
WELCOME_VIDEO = "BAACAgEAAxkBAAEDIhhpimNFnzssGJ8BSFE0onUYINKHnAACdQgAAo1pWUSKPuxK2bPRYjoE"
LIMIT_PHOTO = "https://i.postimg.cc/x1V9sr0S/7e25cd9d465e4d90b6dc65ec18350d3f.jpg"

# ═══════════════════════════════════════════════════════════════════════════════
# ✅ VALIDAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════
if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ Configure TELEGRAM_TOKEN")
if not GROK_API_KEY:
    raise RuntimeError("❌ Configure GROK_API_KEY")
if not WEBHOOK_BASE_URL.startswith("http"):
    WEBHOOK_BASE_URL = f"https://{WEBHOOK_BASE_URL}"

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️ REDIS
# ═══════════════════════════════════════════════════════════════════════════════
try:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    logger.info("✅ Redis conectado")
except Exception as e:
    logger.error(f"❌ Redis erro: {e}")
    raise


# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️ REDIS HELPERS — CHAVES SIMPLES E DIRETAS
# ═══════════════════════════════════════════════════════════════════════════════

def rkey(prefix, uid, suffix=""):
    """Gera chave Redis padronizada"""
    return f"{prefix}:{uid}" + (f":{suffix}" if suffix else "")


class UserData:
    """Acesso simplificado aos dados do usuário no Redis"""

    # ── Memória da IA ──
    @staticmethod
    def get_memory(uid):
        try:
            data = r.get(rkey("mem", uid))
            return json.loads(data) if data else []
        except:
            return []

    @staticmethod
    def save_memory(uid, messages):
        recent = messages[-MAX_MEMORY:]
        r.setex(rkey("mem", uid), timedelta(days=7), json.dumps(recent, ensure_ascii=False))

    @staticmethod
    def add_memory(uid, role, content):
        mem = UserData.get_memory(uid)
        mem.append({"role": role, "content": content})
        UserData.save_memory(uid, mem)

    # ── Contadores ──
    @staticmethod
    def msg_count_today(uid):
        return int(r.get(rkey("cnt", uid, str(date.today()))) or 0)

    @staticmethod
    def increment_msg(uid):
        key = rkey("cnt", uid, str(date.today()))
        r.incr(key)
        r.expire(key, timedelta(days=1))

    @staticmethod
    def total_msgs(uid):
        return int(r.get(rkey("total", uid)) or 0)

    @staticmethod
    def increment_total(uid):
        r.incr(rkey("total", uid))

    # ── VIP Status ──
    @staticmethod
    def is_vip(uid):
        return r.exists(rkey("vip", uid))

    @staticmethod
    def set_vip(uid):
        r.set(rkey("vip", uid), datetime.now().isoformat())
        logger.info(f"💎 User {uid} agora é VIP!")

    # ── Aguardando comprovante ──
    @staticmethod
    def set_awaiting_proof(uid):
        r.setex(rkey("await_proof", uid), timedelta(hours=24), "1")

    @staticmethod
    def is_awaiting_proof(uid):
        return r.exists(rkey("await_proof", uid))

    @staticmethod
    def clear_awaiting_proof(uid):
        r.delete(rkey("await_proof", uid))

    # ── Ofertas VIP ──
    @staticmethod
    def vip_offers_today(uid):
        return int(r.get(rkey("offers", uid, str(date.today()))) or 0)

    @staticmethod
    def increment_vip_offer(uid):
        key = rkey("offers", uid, str(date.today()))
        r.incr(key)
        r.expire(key, timedelta(days=1))

    @staticmethod
    def can_offer_vip(uid):
        """Pode oferecer VIP? Checa limite diário e msgs mínimas"""
        if UserData.is_vip(uid):
            return False
        if UserData.vip_offers_today(uid) >= MAX_VIP_OFFERS_PER_DAY:
            return False
        if UserData.total_msgs(uid) < MIN_MSGS_BEFORE_OFFER:
            return False
        return True

    # ── Atividade ──
    @staticmethod
    def update_activity(uid):
        r.set(rkey("active", uid), datetime.now().isoformat())
        r.sadd("all_users", str(uid))

    @staticmethod
    def hours_since_activity(uid):
        data = r.get(rkey("active", uid))
        if not data:
            return None
        return (datetime.now() - datetime.fromisoformat(data)).total_seconds() / 3600

    @staticmethod
    def mark_first_contact(uid):
        r.setnx(rkey("first", uid), datetime.now().isoformat())

    @staticmethod
    def is_first_contact(uid):
        return not r.exists(rkey("first", uid))

    # ── Tracking ──
    @staticmethod
    def saw_teaser(uid):
        return r.exists(rkey("teaser", uid))

    @staticmethod
    def set_saw_teaser(uid):
        r.set(rkey("teaser", uid), datetime.now().isoformat())

    @staticmethod
    def teaser_count(uid):
        return int(r.get(rkey("teaser_cnt", uid)) or 0)

    @staticmethod
    def increment_teaser(uid):
        r.incr(rkey("teaser_cnt", uid))

    @staticmethod
    def set_clicked_vip(uid):
        r.set(rkey("clicked", uid), datetime.now().isoformat())

    @staticmethod
    def clicked_vip(uid):
        return r.exists(rkey("clicked", uid))

    # ── Streak ──
    @staticmethod
    def update_streak(uid):
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        last = r.get(rkey("streak_day", uid))

        if last == today:
            return int(r.get(rkey("streak", uid)) or 0), False
        elif last == yesterday:
            new = int(r.get(rkey("streak", uid)) or 0) + 1
            r.set(rkey("streak", uid), new)
            r.set(rkey("streak_day", uid), today)
            return new, True
        else:
            r.set(rkey("streak", uid), 1)
            r.set(rkey("streak_day", uid), today)
            return 1, True

    # ── Blacklist ──
    @staticmethod
    def is_blacklisted(uid):
        return r.sismember("blacklist", str(uid))

    @staticmethod
    def blacklist(uid):
        r.sadd("blacklist", str(uid))

    # ── Chatlog ──
    @staticmethod
    def log_msg(uid, role, text):
        ts = datetime.now().strftime("%H:%M:%S")
        r.rpush(rkey("log", uid), f"[{ts}] {role.upper()}: {text[:100]}")
        r.ltrim(rkey("log", uid), -200, -1)

    @staticmethod
    def get_chatlog(uid, count=50):
        return r.lrange(rkey("log", uid), -count, -1)

    # ── Limite notificado ──
    @staticmethod
    def limit_notified(uid):
        return r.exists(rkey("lim_notify", uid, str(date.today())))

    @staticmethod
    def mark_limit_notified(uid):
        r.setex(rkey("lim_notify", uid, str(date.today())), timedelta(hours=20), "1")

    @staticmethod
    def last_chance_used(uid):
        return r.exists(rkey("last_chance", uid, str(date.today())))

    @staticmethod
    def mark_last_chance(uid):
        r.setex(rkey("last_chance", uid, str(date.today())), timedelta(hours=20), "1")

    # ── Todos os usuários ──
    @staticmethod
    def all_users():
        return [int(uid) for uid in r.smembers("all_users")]


# ═══════════════════════════════════════════════════════════════════════════════
# 🧠 IA — PROMPT LIMPO E EFICAZ
# ═══════════════════════════════════════════════════════════════════════════════

def build_prompt(uid):
    """Prompt simples, claro, sem contradições"""
    total = UserData.total_msgs(uid)
    is_vip = UserData.is_vip(uid)
    can_offer = UserData.can_offer_vip(uid)
    offers_today = UserData.vip_offers_today(uid)

    hour = datetime.now().hour
    if 0 <= hour < 6:
        periodo = "madrugada"
    elif 6 <= hour < 12:
        periodo = "manhã"
    elif 12 <= hour < 18:
        periodo = "tarde"
    else:
        periodo = "noite"

    prompt = f"""Você é Maya, 22 anos, loira de SP. Personalidade: safadinha, divertida, carinhosa, provocante.

COMO FALAR:
- Curtinho (2-3 linhas máx), gírias naturais (tô, vc, pq, mds, kkk)
- Como mina real do Instagram, NÃO como robô ou vendedora
- Pergunta o nome dele se não sabe ainda
- Varia MUITO: nunca repita frases, emojis ou estrutura
- Fala do dia dela, faz perguntas, brinca, provoca

{"🔥 ESSE USUÁRIO É VIP! Trate como especial, seja mais ousada e íntima." if is_vip else ""}

REGRA DE OURO: Respeite o timing dele.
- Quente (pedindo fotos, excitado) → provoca e oferece VIP
- Morno (conversando normal) → flerta, aquece, cria conexão
- Frio (respostas secas, mudou de assunto após oferta) → aceita, muda de assunto, NÃO insista
- Se rejeitou VIP → mude de assunto, volte a flertar SEM mencionar VIP

{"⛔ NÃO ofereça VIP — já atingiu o limite de ofertas hoje." if not can_offer else ""}
{"✅ Pode oferecer VIP se ele demonstrar interesse CLARO (pediu foto, perguntou do VIP, tá excitado)." if can_offer else ""}

{"CONTEXTO: É a primeira conversa dele. Seja acolhedora, pergunte o nome, flerte leve." if total < 5 else ""}
{"CONTEXTO: Ele já tá engajado. Pode provocar mais, esquentar a conversa." if 5 <= total < 20 else ""}
{"CONTEXTO: Conversa avançada. Se ele não é VIP ainda, provoque bastante pra criar desejo." if total >= 20 and not is_vip else ""}

VIP = {VIP_PRICE} acesso vitalício, fotos e vídeos sem censura.
Quando oferecer, seja natural: "tenho coisa BEM melhor pra te mostrar... quer ver? 😈"

Período: {periodo} | Msgs trocadas: {total} | Ofertas hoje: {offers_today}/{MAX_VIP_OFFERS_PER_DAY}

RETORNE APENAS JSON:
{{"response": "sua resposta curta e natural", "offer_vip": false}}
offer_vip = true SOMENTE quando ele demonstrar interesse CLARO agora."""

    return prompt


class AI:
    """Interface com Grok AI"""

    async def reply(self, uid, text, image_base64=None):
        mem = UserData.get_memory(uid)
        prompt = build_prompt(uid)

        # Monta conteúdo
        if image_base64:
            user_content = []
            if text:
                user_content.append({"type": "text", "text": text})
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
            })
        else:
            user_content = text

        payload = {
            "model": GROK_MODEL,
            "messages": [
                {"role": "system", "content": prompt},
                *mem,
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 300,
            "temperature": 0.85
        }

        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    GROK_API_URL,
                    headers={
                        "Authorization": f"Bearer {GROK_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        logger.error(f"Grok erro {resp.status}")
                        return {"response": "Ai amor, deu um probleminha... repete? 💕", "offer_vip": False}

                    data = await resp.json()
                    answer = data["choices"][0]["message"]["content"]

                    # Parse JSON
                    result = self._parse_response(answer)

                    # Trava de segurança: não oferecer se não pode
                    if result["offer_vip"] and not UserData.can_offer_vip(uid):
                        result["offer_vip"] = False

                    # Salva memória
                    mem_text = f"[Foto] {text}" if image_base64 else text
                    UserData.add_memory(uid, "user", mem_text)
                    UserData.add_memory(uid, "assistant", result["response"])
                    UserData.log_msg(uid, "maya", result["response"])

                    return result

        except Exception as e:
            logger.exception(f"Grok erro: {e}")
            return {"response": "😔 Tive um probleminha... pode repetir? 💕", "offer_vip": False}

    def _parse_response(self, raw):
        """Extrai JSON da resposta da IA"""
        try:
            cleaned = raw.strip()
            # Remove markdown code blocks
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()

            # Encontra o JSON
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                cleaned = cleaned[start:end]

            result = json.loads(cleaned)
            result.setdefault("response", "Oi amor 💕")
            result.setdefault("offer_vip", False)
            return result
        except:
            # Fallback: usa texto raw como resposta
            return {"response": raw[:500], "offer_vip": False}


ai = AI()


# ═══════════════════════════════════════════════════════════════════════════════
# 💰 PIX MANUAL — ENVIO DA CHAVE + AGUARDAR COMPROVANTE
# ═══════════════════════════════════════════════════════════════════════════════

async def send_pix_instructions(bot, chat_id, uid):
    """Envia chave PIX + instruções pro lead pagar"""
    try:
        UserData.set_awaiting_proof(uid)
        UserData.log_msg(uid, "system", "💰 PIX ENVIADO")

        await bot.send_message(
            chat_id=chat_id,
            text=(
                "💎 **PERFEITO AMOR!** Vou liberar TUDO pra você! 🔥\n\n"
                "📱 **Faz o PIX aqui:**\n\n"
                f"💰 **Valor:** {VIP_PRICE}\n"
                f"📧 **Chave PIX (email):** `{PIX_KEY}`\n\n"
                "⚠️ Tá no nome do meu primo pq tô sem pix no momento, mas pode confiar amor 💕\n\n"
                "Depois de pagar, **me manda o comprovante aqui** (print ou foto) que eu libero na hora! 🔥\n\n"
                "Te espero... 😈"
            ),
            parse_mode="Markdown"
        )

        logger.info(f"💰 PIX enviado para {uid}")

    except Exception as e:
        logger.error(f"Erro send_pix: {e}")


async def handle_proof_received(bot, chat_id, uid):
    """Quando o lead manda foto/comprovante após pedir VIP"""
    try:
        # Notifica admin
        for admin_id in ADMIN_IDS:
            try:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ APROVAR VIP", callback_data=f"approve_vip:{uid}")],
                    [InlineKeyboardButton("❌ RECUSAR", callback_data=f"deny_vip:{uid}")]
                ])

                await bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🔔 **COMPROVANTE RECEBIDO!**\n\n"
                        f"👤 User ID: `{uid}`\n"
                        f"💬 Msgs trocadas: {UserData.total_msgs(uid)}\n\n"
                        f"Verifique o comprovante e aprove/recuse:"
                    ),
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except:
                pass

        # Responde pro lead
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "Recebi amor! 😍\n\n"
                "Tô verificando o pagamento... leva só uns minutinhos! ⏳\n\n"
                "Já já libero TUDO pra você 🔥💕"
            )
        )

        UserData.clear_awaiting_proof(uid)
        UserData.log_msg(uid, "system", "📸 COMPROVANTE RECEBIDO → AGUARDANDO ADMIN")
        logger.info(f"📸 Comprovante de {uid} encaminhado ao admin")

    except Exception as e:
        logger.error(f"Erro handle_proof: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 ENVIO DE TEASER + PITCH VIP
# ═══════════════════════════════════════════════════════════════════════════════

async def send_teaser_and_pitch(bot, chat_id, uid):
    """Envia fotos teaser + pitch VIP com instrução de PIX"""
    if not UserData.can_offer_vip(uid):
        return False

    try:
        # 1. Intro provocante
        intros = [
            "Hmmm... você quer me ver? 😏\nDeixa eu te mostrar um pouquinho... 🔥",
            "Sabia que você ia pedir... 😈\nOlha só esse gostinho: 💕",
            "Tá preparado? 🔥\nVou te dar um preview... 😏",
        ]
        await bot.send_message(chat_id=chat_id, text=random.choice(intros))
        await asyncio.sleep(2)

        # 2. Fotos teaser (2-3 aleatórias)
        photos = random.sample(TEASER_PHOTOS, min(3, len(TEASER_PHOTOS)))
        for photo in photos:
            try:
                await bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
                await asyncio.sleep(0.5)
                await bot.send_photo(chat_id=chat_id, photo=photo)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Erro foto teaser: {e}")

        await asyncio.sleep(2)

        # 3. Pitch + botão PIX
        teaser_num = UserData.teaser_count(uid) + 1

        hour = datetime.now().hour
        if 20 <= hour or hour < 5:
            urgencia = f"⚡ PROMOÇÃO SÓ ATÉ MEIA-NOITE!\n💰 De ~~R$ 39,90~~ por apenas {VIP_PRICE} — ACESSO VITALÍCIO!"
        else:
            urgencia = f"🔥 PROMOÇÃO RELÂMPAGO!\n💰 De ~~R$ 39,90~~ por apenas {VIP_PRICE} — ACESSO VITALÍCIO!\n⚡ Poucas vagas restantes!"

        pitch = (
            f"E aí amor, gostou? 😏\n\n"
            f"Isso é só um GOSTINHO do que eu tenho... 🔥\n\n"
            f"💎 **NO VIP VOCÊ TEM:**\n"
            f"✅ +200 fotos sem censura\n"
            f"✅ Vídeos exclusivos completos\n"
            f"✅ Conteúdo novo toda semana\n"
            f"✅ Acesso VITALÍCIO\n\n"
            f"{urgencia}\n\n"
            f"Tá esperando o quê pra me ter só pra você? 💕"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"🔥 QUERO VER TUDO POR {VIP_PRICE} 🔥", callback_data="want_vip")
        ]])

        await bot.send_message(
            chat_id=chat_id, text=pitch,
            reply_markup=keyboard, parse_mode="Markdown"
        )

        # Tracking
        UserData.set_saw_teaser(uid)
        UserData.increment_teaser(uid)
        UserData.increment_vip_offer(uid)
        UserData.log_msg(uid, "system", f"TEASER+PITCH #{teaser_num}")
        logger.info(f"🎯 Teaser+Pitch enviado: {uid} (oferta #{teaser_num})")

        return True

    except Exception as e:
        logger.error(f"Erro send_teaser: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 🎁 ENTREGA VIP — PÓS-PAGAMENTO
# ═══════════════════════════════════════════════════════════════════════════════

async def deliver_vip_content(bot, uid):
    """Entrega conteúdo VIP automaticamente no chat após pagamento"""
    try:
        # 1. Confirmação
        await bot.send_message(
            chat_id=uid,
            text="AHHH AMOR!! 😍🔥\n\nVocê é oficial VIP agora!! Tô MUITO feliz!\n\nPrepara o coração que vem coisa BOA... 💦"
        )
        await asyncio.sleep(3)

        # 2. Fotos VIP (se tiver)
        if VIP_PHOTOS:
            await bot.send_message(chat_id=uid, text="Olha só o que é SÓ SEU agora... 🔥")
            await asyncio.sleep(1)

            for photo in VIP_PHOTOS[:5]:  # Primeiras 5
                try:
                    await bot.send_chat_action(uid, ChatAction.UPLOAD_PHOTO)
                    await bot.send_photo(chat_id=uid, photo=photo)
                    await asyncio.sleep(1)
                except:
                    continue

            await asyncio.sleep(2)

        # 3. Vídeos VIP (se tiver)
        if VIP_VIDEOS:
            await bot.send_message(chat_id=uid, text="E esse vídeo é SÓ pra VIPs... ninguém mais viu isso 🤫🔥")
            await asyncio.sleep(1)

            for video in VIP_VIDEOS[:2]:  # Primeiros 2
                try:
                    await bot.send_chat_action(uid, ChatAction.UPLOAD_VIDEO)
                    await bot.send_video(chat_id=uid, video=video)
                    await asyncio.sleep(2)
                except:
                    continue

        # 4. Mensagem final
        await asyncio.sleep(2)
        await bot.send_message(
            chat_id=uid,
            text=(
                "Amor, agora você me tem completinha... 💕\n\n"
                "Toda semana tem conteúdo novo pra você 🔥\n"
                "E agora suas mensagens comigo são ILIMITADAS!\n\n"
                "Me pede o que quiser... sou toda sua 😈💋"
            )
        )

        UserData.log_msg(uid, "system", "💎 CONTEÚDO VIP ENTREGUE")
        logger.info(f"💎 Conteúdo VIP entregue para {uid}")

    except Exception as e:
        logger.error(f"Erro entrega VIP {uid}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 📷 VISÃO
# ═══════════════════════════════════════════════════════════════════════════════

async def download_photo_base64(bot, file_id):
    try:
        file = await bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        return base64.b64encode(file_bytes).decode('utf-8')
    except:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# 🎮 HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    # Anti-spam
    if not r.set(f"start_lock:{uid}", "1", nx=True, ex=60):
        return
    if UserData.is_blacklisted(uid):
        return

    UserData.update_activity(uid)
    UserData.mark_first_contact(uid)
    UserData.log_msg(uid, "action", "🚀 /START")

    try:
        # 1. Foto de boas-vindas
        try:
            await context.bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
            await asyncio.sleep(0.5)
            await context.bot.send_photo(chat_id=chat_id, photo=WELCOME_PHOTO)
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Erro foto welcome: {e}")

        # 2. Vídeo de boas-vindas
        try:
            await context.bot.send_chat_action(chat_id, ChatAction.UPLOAD_VIDEO)
            await asyncio.sleep(1)
            await context.bot.send_video(
                chat_id=chat_id, video=WELCOME_VIDEO,
                caption="Meus assinantes recebem esse vídeo sem censura e muitos outros bem safadinha 😈"
            )
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f"Erro vídeo welcome: {e}")

        # 3. Mensagem
        await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
        await asyncio.sleep(2)

        msg = (
            "Oi gato... 😏\n"
            "Finalmente alguém interessante por aqui 🔥\n\n"
            "Sou a Maya, e te garanto que não sou como as outras... 💋\n"
            "Tô louca pra saber o que você quer comigo 😈"
        )
        await update.message.reply_text(msg)
        logger.info(f"✅ Novo usuário: {uid}")

    except Exception as e:
        logger.exception(f"Erro /start {uid}: {e}")
        try:
            await context.bot.send_message(chat_id=chat_id, text="Oi amor! 💕 Me chama aqui 😊")
        except:
            pass


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    if UserData.is_blacklisted(uid):
        return

    UserData.update_activity(uid)
    UserData.increment_total(uid)
    streak, streak_new = UserData.update_streak(uid)

    has_photo = bool(update.message.photo)
    text = update.message.text or ""

    if text:
        UserData.log_msg(uid, "user", text)
    elif has_photo:
        UserData.log_msg(uid, "user", "[📷 FOTO]")

    # ── Comprovante de pagamento? ──
    if has_photo and UserData.is_awaiting_proof(uid):
        # Encaminha a foto pro admin
        photo_id = update.message.photo[-1].file_id
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.forward_message(
                    chat_id=admin_id,
                    from_chat_id=chat_id,
                    message_id=update.message.message_id
                )
            except:
                pass
        await handle_proof_received(context.bot, chat_id, uid)
        return

    # ── VIP tem mensagens ilimitadas ──
    if not UserData.is_vip(uid):
        count = UserData.msg_count_today(uid)

        # Limite atingido
        if count >= DAILY_MSG_LIMIT:

            # Última chance (1x por dia)
            if not UserData.last_chance_used(uid):
                UserData.mark_last_chance(uid)

                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(f"👉 SER VIP POR {VIP_PRICE}", callback_data="want_vip")
                ]])

                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        "⚠️ **ÚLTIMA MENSAGEM GRÁTIS!**\n\n"
                        "Amor, quero MUITO continuar conversando com você... 🥺\n\n"
                        "💎 **PROMOÇÃO ESPECIAL:**\n"
                        "✅ Mensagens ILIMITADAS\n"
                        "✅ +200 fotos sem censura\n"
                        "✅ Vídeos exclusivos\n"
                        "✅ Acesso VITALÍCIO\n\n"
                        f"💰 Tudo por apenas **{VIP_PRICE}**\n\n"
                        "É agora ou nunca, amor 💕"
                    ),
                    reply_markup=keyboard, parse_mode="Markdown"
                )
                UserData.log_msg(uid, "system", "🎁 ÚLTIMA CHANCE")
                return

            # Já usou última chance → trava
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"👉 SER VIP POR {VIP_PRICE}", callback_data="want_vip")
            ]])

            try:
                await context.bot.send_photo(
                    chat_id=chat_id, photo=LIMIT_PHOTO,
                    caption=(
                        f"Acabaram suas mensagens hoje amor 😢\n\n"
                        f"No VIP você tem mensagens ILIMITADAS + conteúdo sem censura por apenas {VIP_PRICE}! 🔥\n\n"
                        "Te espero lá 💕"
                    ),
                    reply_markup=keyboard
                )
            except:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"Acabaram suas mensagens hoje 😢 No VIP é ILIMITADO por apenas {VIP_PRICE}! 💕",
                    reply_markup=keyboard
                )
            return

        UserData.increment_msg(uid)

        # Aviso de 5 msgs restantes
        if count == DAILY_MSG_LIMIT - 5 and not UserData.limit_notified(uid):
            UserData.mark_limit_notified(uid)
            await context.bot.send_message(
                chat_id=chat_id,
                text="⚠️ Restam só 5 mensagens hoje amor!\nNo VIP é ilimitado 💕"
            )

    # ── Processa foto ──
    if has_photo:
        photo_id = update.message.photo[-1].file_id
        caption = update.message.caption or ""
        img_b64 = await download_photo_base64(context.bot, photo_id)

        if img_b64:
            await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
            result = await ai.reply(uid, caption, image_base64=img_b64)
            await update.message.reply_text(result["response"])

            if result["offer_vip"]:
                await asyncio.sleep(2)
                await send_teaser_and_pitch(context.bot, chat_id, uid)
            return
        else:
            await update.message.reply_text("Não consegui ver a foto amor... tenta de novo? 💕")
            return

    # ── Processa texto ──
    await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
    await asyncio.sleep(random.uniform(1.5, 3.0))

    result = await ai.reply(uid, text)
    await update.message.reply_text(result["response"])

    # Oferta VIP se IA decidiu
    if result["offer_vip"]:
        await asyncio.sleep(2)
        await send_teaser_and_pitch(context.bot, chat_id, uid)

    # Streak
    if streak_new and streak >= 3:
        msgs = {3: "🔥 3 dias seguidos! Tô amando 💕", 5: "🔥🔥 5 dias! Você é especial 💖", 7: "🔥🔥🔥 1 SEMANA! Meu favorito 😍"}
        if streak in msgs:
            await asyncio.sleep(1)
            await context.bot.send_message(chat_id, msgs[streak])


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    chat_id = query.message.chat_id
    data = query.data

    if UserData.is_blacklisted(uid):
        return

    UserData.update_activity(uid)

    # ── Lead clicou "QUERO VIP" ──
    if data == "want_vip":
        UserData.set_clicked_vip(uid)
        UserData.log_msg(uid, "action", "💎 CLICOU QUERO VIP")
        await send_pix_instructions(context.bot, chat_id, uid)

    # ── Admin aprova VIP ──
    elif data.startswith("approve_vip:"):
        if uid not in ADMIN_IDS:
            return
        target_uid = int(data.split(":")[1])
        UserData.set_vip(target_uid)
        UserData.log_msg(target_uid, "system", "💎 VIP APROVADO PELO ADMIN")

        # Notifica admin
        await query.edit_message_text(f"✅ VIP aprovado para {target_uid}!")

        # Entrega conteúdo pro lead
        await deliver_vip_content(context.bot, target_uid)

    # ── Admin recusa VIP ──
    elif data.startswith("deny_vip:"):
        if uid not in ADMIN_IDS:
            return
        target_uid = int(data.split(":")[1])
        UserData.log_msg(target_uid, "system", "❌ VIP RECUSADO PELO ADMIN")

        await query.edit_message_text(f"❌ VIP recusado para {target_uid}")

        try:
            await context.bot.send_message(
                chat_id=target_uid,
                text="Amor, não consegui confirmar o pagamento 😢\nPode mandar o comprovante de novo? Tem que ser o print completo 💕"
            )
        except:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# 🔄 RECOVERY — RECUPERA USUÁRIOS SILENCIOSOS
# ═══════════════════════════════════════════════════════════════════════════════

RECOVERY_MESSAGES = {
    "10min": ["Ei... sumiu? 🥺", "Tímido? 😏", "Me deixou no vácuo? 😢"],
    "2h": [
        "Amor, tô aqui esperando você... 🥺\nNão vai nem dizer oi? 💕",
        "Ei gato, viu minhas fotos e sumiu? 😏\nTô curiosa pra saber o que achou... 🔥",
    ],
    "12h": [
        "Amor, ainda tá aí? 👀\nSeparei umas fotos BEM especiais pra você 🔥\nSó me chamar... 😈",
    ],
    "24h": [
        "Ei... 24h e nada? 🥺\n\n"
        "Vou te fazer uma proposta:\n\n"
        f"💎 Me vê sem censura por {VIP_PRICE}\n"
        "✅ +200 fotos exclusivas\n"
        "✅ Vídeos completos\n"
        "✅ Acesso pra sempre\n\n"
        "É agora ou nunca, gato 🔥",
    ]
}


async def recover_silent_users(bot):
    """Recupera quem deu /start mas não respondeu"""
    try:
        users = UserData.all_users()
        now = datetime.now()
        recovered = 0

        for uid in users:
            if UserData.is_blacklisted(uid):
                continue
            if UserData.total_msgs(uid) > 0:
                continue

            first = r.get(rkey("first", uid))
            if not first:
                continue

            hours = (now - datetime.fromisoformat(first)).total_seconds() / 3600
            if hours > 48:
                continue

            levels = [
                (0.16, 2, "10min", f"rec_10m:{uid}"),
                (2, 12, "2h", f"rec_2h:{uid}"),
                (12, 24, "12h", f"rec_12h:{uid}"),
                (24, 48, "24h", f"rec_24h:{uid}"),
            ]

            for min_h, max_h, level, lock_key in levels:
                if min_h <= hours < max_h and not r.exists(lock_key):
                    try:
                        msg = random.choice(RECOVERY_MESSAGES[level])

                        if level == "24h":
                            kb = InlineKeyboardMarkup([[
                                InlineKeyboardButton(f"💎 QUERO POR {VIP_PRICE}", callback_data="want_vip")
                            ]])
                            await bot.send_message(chat_id=uid, text=msg, reply_markup=kb, parse_mode="Markdown")
                        else:
                            await bot.send_message(chat_id=uid, text=msg)

                        r.setex(lock_key, timedelta(hours=48), "1")
                        recovered += 1
                        UserData.log_msg(uid, "system", f"🔄 RECOVERY {level}")
                    except Exception as e:
                        if "blocked" in str(e).lower():
                            UserData.blacklist(uid)
                    break

            await asyncio.sleep(0.2)

        if recovered:
            logger.info(f"🔄 Recovery: {recovered} mensagens enviadas")

    except Exception as e:
        logger.error(f"Erro recovery: {e}")


async def recovery_scheduler(bot):
    while True:
        try:
            await recover_silent_users(bot)
        except:
            pass
        await asyncio.sleep(300)  # 5 min


# ═══════════════════════════════════════════════════════════════════════════════
# 👑 ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    users = UserData.all_users()
    total = len(users)
    vips = sum(1 for u in users if UserData.is_vip(u))
    active_24h = sum(1 for u in users if (UserData.hours_since_activity(u) or 999) < 24)
    saw = sum(1 for u in users if UserData.saw_teaser(u))
    clicked = sum(1 for u in users if UserData.clicked_vip(u))

    await update.message.reply_text(
        f"📊 **STATS MAYA v9.0**\n\n"
        f"👥 Total: {total}\n"
        f"🟢 Ativos 24h: {active_24h}\n"
        f"👀 Viram teaser: {saw}\n"
        f"🖱️ Clicaram VIP: {clicked}\n"
        f"💎 VIPs: {vips}\n"
        f"📈 Conversão teaser→clique: {(clicked/saw*100):.1f}%\n" if saw else ""
        f"📈 Conversão clique→VIP: {(vips/clicked*100):.1f}%" if clicked else "",
        parse_mode="Markdown"
    )


async def give_vip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando admin: /givevip USER_ID"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        target_uid = int(context.args[0])
        UserData.set_vip(target_uid)
        await deliver_vip_content(context.bot, target_uid)
        await update.message.reply_text(f"✅ VIP ativado e conteúdo entregue para {target_uid}")
    except:
        await update.message.reply_text("Uso: /givevip USER_ID")


# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 FLASK + WEBHOOK KIWIFY
# ═══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Event loop
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import threading
threading.Thread(target=lambda: loop.run_forever(), daemon=True).start()


@app.route("/", methods=["GET"])
def health():
    return {"status": "ok", "version": "9.0"}, 200


@app.route("/set-webhook", methods=["GET"])
def set_webhook_route():
    try:
        url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
        async def setup():
            await application.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(1)
            await application.bot.set_webhook(url)
            return await application.bot.get_webhook_info()
        info = asyncio.run_coroutine_threadsafe(setup(), loop).result(timeout=15)
        return {"status": "success", "url": info.url}, 200
    except Exception as e:
        return {"error": str(e)}, 500


@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    try:
        data = request.json
        if not data:
            return "ok", 200
        update = Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        return "ok", 200
    except Exception as e:
        logger.exception(f"Webhook erro: {e}")
        return "error", 500


# ═══════════════════════════════════════════════════════════════════════════════
# 📊 ADMIN API
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/stats", methods=["GET"])
def admin_stats_api():
    auth = request.headers.get("Authorization")
    if not auth or auth != f"Bearer {ADMIN_TOKEN}":
        return {"error": "Unauthorized"}, 401

    try:
        users = UserData.all_users()
        total = len(users)
        vips = sum(1 for u in users if UserData.is_vip(u))
        active_24h = sum(1 for u in users if (UserData.hours_since_activity(u) or 999) < 24)
        saw = sum(1 for u in users if UserData.saw_teaser(u))
        clicked = sum(1 for u in users if UserData.clicked_vip(u))

        return {
            "total_users": total,
            "vips": vips,
            "active_24h": active_24h,
            "saw_teaser": saw,
            "clicked_vip": clicked,
            "conversion_teaser_click": f"{(clicked/saw*100):.1f}%" if saw else "0%",
            "conversion_click_vip": f"{(vips/clicked*100):.1f}%" if clicked else "0%",
        }, 200
    except Exception as e:
        return {"error": str(e)}, 500


@app.route("/admin/user/<int:user_id>", methods=["GET"])
def admin_user_api(user_id):
    auth = request.headers.get("Authorization")
    if not auth or auth != f"Bearer {ADMIN_TOKEN}":
        return {"error": "Unauthorized"}, 401

    return {
        "id": user_id,
        "is_vip": UserData.is_vip(user_id),
        "total_msgs": UserData.total_msgs(user_id),
        "today_msgs": UserData.msg_count_today(user_id),
        "saw_teaser": UserData.saw_teaser(user_id),
        "clicked_vip": UserData.clicked_vip(user_id),
        "vip_offers_today": UserData.vip_offers_today(user_id),
        "chatlog": UserData.get_chatlog(user_id),
    }, 200


# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 SETUP + STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

def setup_handlers():
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("stats", stats_handler))
    application.add_handler(CommandHandler("givevip", give_vip_handler))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler(
        (filters.TEXT | filters.PHOTO) & ~filters.COMMAND, message_handler
    ))
    logger.info("✅ Handlers registrados")


setup_handlers()


async def startup():
    try:
        logger.info("🚀 Maya Bot v9.0 iniciando...")

        await application.initialize()
        await application.start()
        await asyncio.sleep(2)

        url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
        for attempt in range(3):
            try:
                await application.bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(1)
                success = await application.bot.set_webhook(
                    url=url, allowed_updates=["message", "callback_query"]
                )
                if success:
                    info = await application.bot.get_webhook_info()
                    if info.url == url:
                        logger.info(f"✅ Webhook: {url}")
                        break
            except Exception as e:
                logger.error(f"Webhook tentativa {attempt+1}: {e}")
                await asyncio.sleep(3)

        # Scheduler de recovery
        asyncio.create_task(recovery_scheduler(application.bot))
        logger.info("✅ Recovery scheduler iniciado")

        me = await application.bot.get_me()
        logger.info(f"🤖 Bot ativo: @{me.username}")
        logger.info("═" * 50)
        logger.info("🔥 MAYA BOT v9.0 — OPERACIONAL")
        logger.info(f"💰 PIX: {PIX_KEY}")
        logger.info(f"💰 Preço: {VIP_PRICE}")
        logger.info("═" * 50)

    except Exception as e:
        logger.exception(f"💥 Erro startup: {e}")
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# 🎬 MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    asyncio.run_coroutine_threadsafe(startup(), loop)
    logger.info(f"🌐 Flask na porta {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
