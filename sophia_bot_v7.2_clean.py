#!/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       🔥 SOPHIA BOT v8.3 - APEX FUNIL FIX                   ║
║                                                                              ║
║  ALTERAÇÕES v8.3 APEX:                                                      ║
║  ✅ Prompt novo: pergunta prévia antes de oferecer teaser                  ║
║  ✅ Sem redirect pro canal free (funil direto VIP)                         ║
║  ✅ send_teaser_and_apex com instrução PIX + urgência                      ║
║  ✅ Detecção de intent pix_help                                            ║
║  ✅ Objeções tratadas no prompt                                            ║
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
import re
import json
import random
import hashlib
import base64
from datetime import datetime, timedelta, date
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatAction
from telegram.ext import (
    Application, MessageHandler, ContextTypes, filters,
    CallbackQueryHandler, CommandHandler
)

from ia_router import init_router, get_router

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURAÇÃO INICIAL
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 v8.3 - SISTEMA DE FASES
# ═══════════════════════════════════════════════════════════════════════════════

PHASES = {
    "ONBOARDING": {"id": 0, "name": "Onboarding", "msg_limit": 5},
    "ENGAGEMENT": {"id": 1, "name": "Engagement", "msg_limit": 15},
    "PROVOCATION": {"id": 2, "name": "Provocation", "msg_limit": 25},
    "VIP_PITCH": {"id": 3, "name": "VIP Pitch", "msg_limit": 35},
    "POST_REJECTION": {"id": 4, "name": "Post-Rejection", "msg_limit": 999},
    "RELATIONSHIP": {"id": 5, "name": "Relationship", "msg_limit": 999}
}

ONBOARDING_MSG_LIMIT = 5
ENGAGEMENT_MSG_LIMIT = 15
PROVOCATION_MSG_LIMIT = 25
VIP_PITCH_MSG_LIMIT = 35

RETURN_WINDOW_HOURS = 6

# ═══════════════════════════════════════════════════════════════════════════════
# 💬 v8.3 - POOLS DE RESPOSTAS ANTI-REPETIÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

RESPONSE_POOLS = {
    "provocacao": [
        "Hmm... tá curioso pra me ver? 😏",
        "Você ia gostar de ver o que eu tenho guardado... 🔥",
        "Tenho umas fotos que vão te deixar louco 😈",
        "Quer saber o que eu tô usando agora? 💕",
        "Se você soubesse o que eu faço quando tô sozinha... 😏",
        "Tô com vontade de te mostrar algo especial 🔥",
        "Você merece ver um pouquinho mais de mim... 💋",
        "Tenho um segredinho pra te contar 😈"
    ],
    "transicao_vip": [
        "No meu VIP você me tem completinha amor... 🔥",
        "Lá no VIP eu fico bem mais ousada viu? 😈",
        "No meu cantinho privado eu não tenho vergonha nenhuma 💕",
        "Quer me ver sem censura? Tenho um lugar especial pra isso... 💋",
        "No VIP eu mostro TUDO que você quer ver 🔥",
        "Meu VIP é onde eu sou eu mesma de verdade... sem limites 😏",
        "Lá dentro é só eu e você... e nada de censura 💕"
    ],
    "pos_rejeicao": [
        "Tudo bem amor, sem pressão! 💕",
        "Relaxa, podemos só conversar 😊",
        "Que legal, me conta mais sobre você!",
        "Entendo! E aí, como foi seu dia? 💬",
        "Sem problemas! Tô aqui pra bater papo também 😊",
        "Tranquilo! Me fala, o que você gosta de fazer? 💕"
    ],
    "apegado": [
        "Amor, você é especial demais 🥰",
        "Tô adorando conversar com você 💕",
        "Você é diferente dos outros... de um jeito bom 😊",
        "Que fofo, tô gostando de você também 💖",
        "Você me faz sorrir aqui do outro lado 🥰",
        "Tô sentindo uma conexão especial com você... 💕"
    ],
    "retorno": [
        "Amor, que saudade! 🥺",
        "Finalmente você voltou! Tava com saudade 💕",
        "Ei! Pensei que tinha me esquecido 🥺",
        "Que bom te ver de novo amor! 💖",
        "Senti sua falta aqui... 🥰"
    ]
}

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 v8.3 - PITCHES CONTEXTUAIS
# ═══════════════════════════════════════════════════════════════════════════════

CONTEXTUAL_PITCHES = [
    {
        "type": "quente",
        "messages": [
            "No VIP eu faço coisas que vão te deixar louco... 🔥",
            "Lá dentro eu mostro TUDO sem censura 😈",
            "No meu VIP você me vê do jeito que ninguém mais vê... 💦",
            "Tenho vídeos BEM ousados esperando você lá 🔥",
            "No VIP eu realizo seus desejos mais safados... 😏"
        ]
    },
    {
        "type": "escassez",
        "messages": [
            "Só aceito alguns VIPs por dia amor... hoje ainda tem vaga 💎",
            "Meu VIP não é pra qualquer um... mas você parece especial 😏",
            "Tô abrindo poucas vagas hoje... garante a sua? 🔥",
            "Só escolho alguns pra ter acesso total... você quer ser um deles? 💕",
            "Nem todo mundo consegue entrar no meu VIP... mas você pode 😈"
        ]
    },
    {
        "type": "curiosidade",
        "messages": [
            "Tenho segredos que só mostro no VIP... quer descobrir? 🤫",
            "O que eu faço lá dentro você NÃO imagina... 😈",
            "No VIP tem surpresas que vão te chocar 🔥",
            "Você nem faz ideia do que te espera lá... 💦",
            "Tenho conteúdos que só meus VIPs conhecem... curioso? 😏"
        ]
    },
    {
        "type": "emocional",
        "messages": [
            "No VIP a gente tem nosso cantinho só nosso... 💕",
            "Lá eu me abro de verdade, sem filtros... só pra você 🥰",
            "Quero te ter no meu espaço especial amor... 💖",
            "No VIP é onde eu mostro quem eu sou de verdade... 😊",
            "Lá dentro é onde a gente cria nossa intimidade... 💕"
        ]
    }
]

# ═══════════════════════════════════════════════════════════════════════════════
# 🔍 v8.3 - DETECÇÃO DE APEGO EMOCIONAL
# ═══════════════════════════════════════════════════════════════════════════════

ATTACHMENT_KEYWORDS = {
    "alto": {
        "keywords": [
            "te amo", "amo voce", "amo vc", "amor da minha vida",
            "apaixonado", "apaixonada", "casar", "namorar",
            "minha vida", "meu amor", "meu mundo"
        ],
        "level": 10
    },
    "medio": {
        "keywords": [
            "especial", "diferente", "unica", "incrivel",
            "perfeita", "maravilhosa", "carinho", "sentimento",
            "sinto algo", "conexao", "química"
        ],
        "level": 6
    },
    "baixo": {
        "keywords": [
            "gostando", "curtindo", "legal voce", "gosto de falar",
            "gosto de conversar", "interessante", "bacana"
        ],
        "level": 3
    }
}


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://default:DcddfJOHLXZdFPjEhRjHeodNgdtrsevl@shuttle.proxy.rlwy.net:12241")

WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://web-production-606aff.up.railway.app")
WEBHOOK_PATH = "/telegram"

CANAL_VIP_LINK = os.getenv("CANAL_VIP_LINK", "https://t.me/Mayaoficial_bot")
PRECO_VIP = os.getenv("PRECO_VIP", "R$ 12,90")

ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", "1293602874").split(",")))
PORT = int(os.getenv("PORT", 8080))

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️ VALIDAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

if not TELEGRAM_TOKEN:
    raise RuntimeError("❌ Configure TELEGRAM_TOKEN nas variáveis de ambiente")
if not GROK_API_KEY:
    raise RuntimeError("❌ Configure GROK_API_KEY nas variáveis de ambiente")

if not WEBHOOK_BASE_URL.startswith("http"):
    WEBHOOK_BASE_URL = f"https://{WEBHOOK_BASE_URL}"

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURAÇÕES DO BOT
# ═══════════════════════════════════════════════════════════════════════════════

LIMITE_DIARIO = 30

VIP_COOLDOWN_AFTER_REJECT = 8
MAX_VIP_OFFERS_PER_SESSION = 999
TEASER_COOLDOWN_MESSAGES = 3

REENGAGEMENT_HOURS = [2, 24, 72]
FOLLOWUP_INTERVAL_HOURS = 12

AB_TEST_ENABLED = True
AB_TEST_RATIO = 0.5

MODELO = "grok-4-1-fast-reasoning"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
MAX_MEMORIA = 12

logger.info(f"🚀 Sophia Bot v8.3 APEX FUNIL iniciando...")
logger.info(f"📍 Webhook: {WEBHOOK_BASE_URL}{WEBHOOK_PATH}")
logger.info(f"💎 Canal VIP: {CANAL_VIP_LINK}")
logger.info(f"💰 Preço VIP: {PRECO_VIP}")

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️ REDIS CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════
try:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    logger.info("✅ Redis conectado")
except Exception as e:
    logger.error(f"❌ Redis erro: {e}")
    raise

# ═══════════════════════════════════════════════════════════════════════════════
# 🎨 ASSETS
# ═══════════════════════════════════════════════════════════════════════════════

FOTOS_TEASER = [
    "https://i.postimg.cc/ZqT4SrB9/32b94b657e4f467897744e01432bc7fb.jpg",
    "https://i.postimg.cc/DzBFy8Lx/a63c77aa55ed4a07aa7ec710ae12580c.jpg",
    "https://i.postimg.cc/KzW2Bw99/b6fe112c63c54f3ab3c800a2e5eb664d.jpg",
    "https://i.postimg.cc/7PcH2GdT/170bccb9b06a42d3a88d594757f85e88.jpg",
    "https://i.postimg.cc/XJ1Vxpv2/00e2c81a4960453f8554baeea091145e.jpg",
]

FOTO_LIMITE_ATINGIDO = "https://i.postimg.cc/x1V9sr0S/7e25cd9d465e4d90b6dc65ec18350d3f.jpg"
FOTO_BEM_VINDA = "https://i.postimg.cc/0NghLJD3/image.png"

VIDEO_BEM_VINDO = "BAACAgEAAxkBAAEDIhhpimNFnzssGJ8BSFE0onUYINKHnAACdQgAAo1pWUSKPuxK2bPRYjoE"

AUDIO_PT_1 = "CQACAgEAAxkBAAEDDXFpaYkigGDlcTzZxaJXFuWDj1Ow5gAC5QQAAiq7UUdXWpPNiiNd1jgE"
AUDIO_PT_2 = "CQACAgEAAxkBAAEDAAEmaVRmPJ5iuBOaXyukQ06Ui23TSokAAocGAAIZwaFGkIERRmRoPes4BA"

# ═══════════════════════════════════════════════════════════════════════════════
# 🔑 KEYWORDS
# ═══════════════════════════════════════════════════════════════════════════════

HOT_KEYWORDS = [
    'pau', 'buceta', 'chupar', 'gozar', 'tesão', 'foder', 'transar',
    'punheta', 'siririca', 'safada', 'gostosa', 'pelada', 'nua',
    'chupeta', 'boquete', 'anal', 'cu', 'rola', 'pica', 'mama',
    'seios', 'peitos', 'bunda', 'xereca', 'meter', 'fuder', 'sexo',
    'excitado', 'excitada', 'molhada', 'duro', 'tesudo', 'tesuda'
]

PEDIDO_CONTEUDO_KEYWORDS = [
    'foto', 'fotos', 'selfie', 'imagem', 'nude', 'nudes',
    'mostra', 'manda', 'mandar', 'envia', 'enviar',
    'quero ver', 'deixa ver', 'posso ver', 'me mostra',
    'cadê', 'cade', 'onde', 'tem', 'link'
]

INTERESSE_VIP_KEYWORDS = [
    'vip', 'premium', 'pagar', 'pagamento', 'comprar', 'quanto',
    'preço', 'preco', 'valor', 'custa', 'custo', 'plano',
    'assinatura', 'assinar', 'acesso', 'liberado'
]

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️ REDIS KEYS
# ═══════════════════════════════════════════════════════════════════════════════

def memory_key(uid): return f"memory:{uid}"
def user_profile_key(uid): return f"profile:{uid}"
def first_contact_key(uid): return f"first_contact:{uid}"
def lang_key(uid): return f"lang:{uid}"
def count_key(uid): return f"count:{uid}:{date.today()}"
def bonus_msgs_key(uid): return f"bonus:{uid}"
def limit_notified_key(uid): return f"limit_notified:{uid}:{date.today()}"
def limit_warning_sent_key(uid): return f"limit_warning:{uid}:{date.today()}"
def last_activity_key(uid): return f"last_activity:{uid}"
def last_reengagement_key(uid): return f"last_reengagement:{uid}"
def daily_messages_sent_key(uid): return f"daily_msg_sent:{uid}:{date.today()}"
def ignored_count_key(uid): return f"ignored:{uid}"
def engagement_paused_key(uid): return f"paused:{uid}"
def awaiting_response_key(uid): return f"awaiting:{uid}"
def streak_key(uid): return f"streak:{uid}"
def streak_last_day_key(uid): return f"streak_last:{uid}"
def saw_teaser_key(uid): return f"saw_teaser:{uid}"
def teaser_count_key(uid): return f"teaser_count:{uid}"
def clicked_vip_key(uid): return f"clicked_vip:{uid}"
def conversation_messages_key(uid): return f"conversation_msgs:{uid}"
def ab_group_key(uid): return f"ab_group:{uid}"
def chatlog_key(uid): return f"chatlog:{uid}"
def recent_responses_key(uid): return f"recent_resp:{uid}"
def blacklist_key(): return "blacklist"
def all_users_key(): return "all_users"
def funnel_key(uid): return f"funnel:{uid}"

def current_phase_key(uid): return f"phase:{uid}"
def message_count_key(uid): return f"msg_count:{uid}"
def used_responses_key(uid, pool_name): return f"used_resp:{uid}:{pool_name}"
def attachment_level_key(uid): return f"attachment:{uid}"
def is_attached_key(uid): return f"is_attached:{uid}"
def return_count_key(uid): return f"return_count:{uid}"
def last_return_pitch_key(uid): return f"last_return_pitch:{uid}"
def onboarding_choice_key(uid): return f"onboard_choice:{uid}"

def rejection_cooldown_key(uid): return f"reject_cooldown:{uid}"
def vip_offers_today_key(uid): return f"vip_offers:{uid}:{date.today()}"
def msgs_since_last_offer_key(uid): return f"msgs_since_offer:{uid}"
def last_offer_rejected_key(uid): return f"offer_rejected:{uid}"
def vip_just_offered_key(uid): return f"vip_just_offered:{uid}"

# ═══════════════════════════════════════════════════════════════════════════════
# 🚫 FUNÇÕES DE COOLDOWN/REJEIÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def set_rejection_cooldown(uid, msgs=None):
    try:
        cooldown_msgs = msgs or VIP_COOLDOWN_AFTER_REJECT
        r.set(rejection_cooldown_key(uid), cooldown_msgs)
        r.expire(rejection_cooldown_key(uid), timedelta(hours=24))
        logger.info(f"🚫 Cooldown ativado para {uid}: {cooldown_msgs} msgs")
    except:
        pass

def decrement_rejection_cooldown(uid):
    try:
        current = r.get(rejection_cooldown_key(uid))
        if current:
            new_val = int(current) - 1
            if new_val <= 0:
                r.delete(rejection_cooldown_key(uid))
                r.delete(last_offer_rejected_key(uid))
                logger.info(f"✅ Cooldown expirado para {uid}")
            else:
                r.set(rejection_cooldown_key(uid), new_val)
                r.expire(rejection_cooldown_key(uid), timedelta(hours=24))
    except:
        pass

def is_in_rejection_cooldown(uid):
    try:
        return r.exists(rejection_cooldown_key(uid))
    except:
        return False

def get_rejection_cooldown_remaining(uid):
    try:
        val = r.get(rejection_cooldown_key(uid))
        return int(val) if val else 0
    except:
        return 0

def get_vip_offers_today(uid):
    try:
        return int(r.get(vip_offers_today_key(uid)) or 0)
    except:
        return 0

def increment_vip_offers(uid):
    try:
        r.incr(vip_offers_today_key(uid))
        r.expire(vip_offers_today_key(uid), timedelta(days=1))
    except:
        pass

def can_offer_vip(uid):
    if is_in_rejection_cooldown(uid):
        remaining = get_rejection_cooldown_remaining(uid)
        return False, f"cooldown ({remaining} msgs restantes)"
    offers_today = get_vip_offers_today(uid)
    if offers_today >= MAX_VIP_OFFERS_PER_SESSION:
        return False, f"limite diário ({offers_today}/{MAX_VIP_OFFERS_PER_SESSION})"
    return True, "ok"

def increment_msgs_since_offer(uid):
    try:
        r.incr(msgs_since_last_offer_key(uid))
        r.expire(msgs_since_last_offer_key(uid), timedelta(days=1))
    except:
        pass

def reset_msgs_since_offer(uid):
    try:
        r.set(msgs_since_last_offer_key(uid), 0)
        r.expire(msgs_since_last_offer_key(uid), timedelta(days=1))
    except:
        pass

def get_msgs_since_offer(uid):
    try:
        return int(r.get(msgs_since_last_offer_key(uid)) or 99)
    except:
        return 99

def mark_vip_just_offered(uid):
    try:
        r.setex(vip_just_offered_key(uid), timedelta(hours=2), "1")
    except:
        pass

def was_vip_just_offered(uid):
    try:
        return r.exists(vip_just_offered_key(uid))
    except:
        return False

def clear_vip_just_offered(uid):
    try:
        r.delete(vip_just_offered_key(uid))
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# 💾 FUNÇÕES DE MEMÓRIA
# ═══════════════════════════════════════════════════════════════════════════════

def get_memory(uid):
    try:
        data = r.get(memory_key(uid))
        return json.loads(data) if data else []
    except:
        return []

def save_memory(uid, messages):
    try:
        recent = messages[-MAX_MEMORIA:] if len(messages) > MAX_MEMORIA else messages
        r.setex(memory_key(uid), timedelta(days=7), json.dumps(recent, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Erro salvar memória: {e}")

def add_to_memory(uid, role, content):
    memory = get_memory(uid)
    memory.append({"role": role, "content": content})
    save_memory(uid, memory)

def clear_memory(uid):
    try:
        r.delete(memory_key(uid))
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# 👤 FUNÇÕES DE PERFIL
# ═══════════════════════════════════════════════════════════════════════════════

def get_user_profile(uid):
    try:
        data = r.get(user_profile_key(uid))
        return json.loads(data) if data else {}
    except:
        return {}

def save_user_profile(uid, profile):
    try:
        r.set(user_profile_key(uid), json.dumps(profile, ensure_ascii=False))
    except:
        pass

def get_user_name(uid):
    return get_user_profile(uid).get("name", "")

# ═══════════════════════════════════════════════════════════════════════════════
# 🚫 BLACKLIST
# ═══════════════════════════════════════════════════════════════════════════════

def is_blacklisted(uid):
    try:
        return r.sismember(blacklist_key(), str(uid))
    except:
        return False

def add_to_blacklist(uid):
    try:
        r.sadd(blacklist_key(), str(uid))
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# 🎁 SISTEMA DE BÔNUS
# ═══════════════════════════════════════════════════════════════════════════════

def get_bonus_msgs(uid):
    try:
        return int(r.get(bonus_msgs_key(uid)) or 0)
    except:
        return 0

def add_bonus_msgs(uid, amount):
    try:
        current = get_bonus_msgs(uid)
        r.setex(bonus_msgs_key(uid), timedelta(days=7), current + amount)
    except:
        pass

def use_bonus_msg(uid):
    try:
        current = get_bonus_msgs(uid)
        if current > 0:
            r.set(bonus_msgs_key(uid), current - 1)
            r.expire(bonus_msgs_key(uid), timedelta(days=7))
            return True
        return False
    except:
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 STREAK SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def get_streak(uid):
    try:
        return int(r.get(streak_key(uid)) or 0)
    except:
        return 0

def update_streak(uid):
    try:
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        last_day = r.get(streak_last_day_key(uid))
        if last_day == today:
            return get_streak(uid), False
        elif last_day == yesterday:
            new_streak = get_streak(uid) + 1
            r.set(streak_key(uid), new_streak)
            r.set(streak_last_day_key(uid), today)
            return new_streak, True
        else:
            r.set(streak_key(uid), 1)
            r.set(streak_last_day_key(uid), today)
            return 1, True
    except:
        return 0, False

def get_streak_message(streak):
    if streak < 3:
        return None
    elif streak == 3:
        return "🔥 3 dias seguidos conversando comigo! Tô amando isso 💕"
    elif streak == 5:
        return "🔥🔥 5 dias seguidos! Você é especial demais 💖"
    elif streak == 7:
        return "🔥🔥🔥 UMA SEMANA INTEIRA! Você é oficialmente meu favorito 😍💕"
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# 📢 TRACKING
# ═══════════════════════════════════════════════════════════════════════════════

def set_saw_teaser(uid):
    try:
        r.set(saw_teaser_key(uid), datetime.now().isoformat())
        r.incr(teaser_count_key(uid))
    except:
        pass

def saw_teaser(uid):
    try:
        return r.exists(saw_teaser_key(uid))
    except:
        return False

def get_teaser_count(uid):
    try:
        return int(r.get(teaser_count_key(uid)) or 0)
    except:
        return 0

def set_clicked_vip(uid):
    try:
        r.set(clicked_vip_key(uid), datetime.now().isoformat())
    except:
        pass

def clicked_vip(uid):
    try:
        return r.exists(clicked_vip_key(uid))
    except:
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# 🧪 A/B TEST
# ═══════════════════════════════════════════════════════════════════════════════

def get_ab_group(uid):
    if not AB_TEST_ENABLED:
        return "A"
    try:
        group = r.get(ab_group_key(uid))
        if group:
            return group
        group = "A" if random.random() < AB_TEST_RATIO else "B"
        r.set(ab_group_key(uid), group)
        return group
    except:
        return "A"

# ═══════════════════════════════════════════════════════════════════════════════
# 🔄 ANTI-REPETIÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def get_response_hash(text):
    return hashlib.md5(text.encode()).hexdigest()[:8]

def is_response_recent(uid, response):
    try:
        recent = r.lrange(recent_responses_key(uid), 0, 14)
        resp_hash = get_response_hash(response)
        return resp_hash in recent
    except:
        return False

def add_recent_response(uid, response):
    try:
        r.lpush(recent_responses_key(uid), get_response_hash(response))
        r.ltrim(recent_responses_key(uid), 0, 14)
        r.expire(recent_responses_key(uid), timedelta(days=1))
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# 🎭 DETECÇÃO DE HUMOR
# ═══════════════════════════════════════════════════════════════════════════════

MOOD_PATTERNS = {
    "sad": [r"\b(triste|mal|péssimo|chorand[oa]|deprimi|sozinho)\b"],
    "flirty": [r"\b(gostosa|delícia|tesão|safad[oa]|excitad[oa]|sexy)\b"],
    "angry": [r"\b(raiva|ódio|puto|irritad[oa])\b"],
    "happy": [r"\b(feliz|alegr|animad[oa]|ótimo|maravilh)\b"],
    "horny": [r"\b(nude|nudes|pelad[oa]|sex|transar|foder)\b"],
    "annoyed": [r"\b(porra|caralho|saco|chega|para)\b"]
}

def detect_mood(text):
    text_lower = text.lower()
    for mood, patterns in MOOD_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return mood
    return "neutral"

def get_mood_instruction(mood):
    instructions = {
        "sad": "\n\n⚠️ Usuário parece triste. Seja carinhosa e acolhedora. NÃO ofereça VIP.",
        "flirty": "\n\n😏 Usuário flertando. Pode ser provocante.",
        "angry": "\n\n😰 Usuário irritado. Seja compreensiva. NÃO ofereça VIP. NÃO insista em nada.",
        "happy": "\n\n😊 Usuário feliz! Compartilhe a alegria!",
        "horny": "\n\n🔥 Conversa adulta. Pode ser provocante.",
        "annoyed": "\n\n⚠️ Usuário IRRITADO/ABORRECIDO. Mude de assunto completamente. Seja leve e descontraída. NÃO mencione VIP de forma alguma.",
        "neutral": ""
    }
    return instructions.get(mood, "")

# ═══════════════════════════════════════════════════════════════════════════════
# ⏰ CONTEXTO DE TEMPO
# ═══════════════════════════════════════════════════════════════════════════════

def get_time_context():
    hour = datetime.now().hour
    if 0 <= hour < 5:
        return {"period": "madrugada", "context": "É madrugada."}
    elif 5 <= hour < 12:
        return {"period": "manhã", "context": "É manhã."}
    elif 12 <= hour < 18:
        return {"period": "tarde", "context": "É tarde."}
    elif 18 <= hour < 22:
        return {"period": "início da noite", "context": "É noite."}
    else:
        return {"period": "noite", "context": "É noite."}

# ═══════════════════════════════════════════════════════════════════════════════
# 📈 FUNÇÕES DE ATIVIDADE
# ═══════════════════════════════════════════════════════════════════════════════

def update_last_activity(uid):
    try:
        r.set(last_activity_key(uid), datetime.now().isoformat())
        r.sadd(all_users_key(), str(uid))
    except:
        pass

def get_last_activity(uid):
    try:
        data = r.get(last_activity_key(uid))
        return datetime.fromisoformat(data) if data else None
    except:
        return None

def get_hours_since_activity(uid):
    last = get_last_activity(uid)
    if not last:
        return None
    return (datetime.now() - last).total_seconds() / 3600

def increment_conversation_messages(uid):
    try:
        r.incr(conversation_messages_key(uid))
        r.expire(conversation_messages_key(uid), timedelta(days=30))
    except:
        pass

def get_conversation_messages_count(uid):
    try:
        return int(r.get(conversation_messages_key(uid)) or 0)
    except:
        return 0

def get_all_active_users():
    try:
        users = r.smembers(all_users_key())
        return [int(uid) for uid in users]
    except:
        return []

def save_message(uid, role, text):
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        r.rpush(chatlog_key(uid), f"[{timestamp}] {role.upper()}: {text[:100]}")
        r.ltrim(chatlog_key(uid), -200, -1)
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 CONTROLE DE LIMITE DIÁRIO
# ═══════════════════════════════════════════════════════════════════════════════

def today_count(uid):
    try:
        return int(r.get(count_key(uid)) or 0)
    except:
        return 0

def increment(uid):
    try:
        r.incr(count_key(uid))
        r.expire(count_key(uid), timedelta(days=1))
    except:
        pass

def reset_daily_count(uid):
    try:
        r.delete(count_key(uid))
    except:
        pass

def is_user_locked(uid):
    count = today_count(uid)
    bonus = get_bonus_msgs(uid)
    return count >= LIMITE_DIARIO + bonus

def was_limit_notified_today(uid):
    try:
        return r.exists(limit_notified_key(uid))
    except:
        return False

def mark_limit_notified(uid):
    try:
        r.setex(limit_notified_key(uid), timedelta(hours=20), "1")
    except:
        pass

def was_limit_warning_sent_today(uid):
    try:
        return r.exists(limit_warning_sent_key(uid))
    except:
        return False

def mark_limit_warning_sent(uid):
    try:
        r.setex(limit_warning_sent_key(uid), timedelta(hours=20), "1")
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 FUNIL
# ═══════════════════════════════════════════════════════════════════════════════

def track_funnel(uid, stage):
    stages = {"start": 1, "first_message": 2, "saw_teaser": 3, "clicked_vip": 4}
    try:
        current = int(r.get(funnel_key(uid)) or 0)
        new_stage = stages.get(stage, 0)
        if new_stage > current:
            r.set(funnel_key(uid), new_stage)
    except:
        pass

def get_funnel_stats():
    try:
        users = get_all_active_users()
        stages = {i: 0 for i in range(5)}
        for uid in users:
            stage = int(r.get(funnel_key(uid)) or 0)
            stages[stage] += 1
        return stages
    except:
        return {}

# ═══════════════════════════════════════════════════════════════════════════════
# 🎮 ENGAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def get_ignored_count(uid):
    try:
        return int(r.get(ignored_count_key(uid)) or 0)
    except:
        return 0

def increment_ignored(uid):
    try:
        count = get_ignored_count(uid)
        new_count = count + 1
        r.setex(ignored_count_key(uid), timedelta(days=14), new_count)
        if new_count >= 3:
            pause_engagement(uid)
            return True
        return False
    except:
        return False

def reset_ignored(uid):
    try:
        r.delete(ignored_count_key(uid))
        r.delete(engagement_paused_key(uid))
        r.delete(awaiting_response_key(uid))
    except:
        pass

def pause_engagement(uid):
    try:
        r.set(engagement_paused_key(uid), datetime.now().isoformat())
    except:
        pass

def is_engagement_paused(uid):
    try:
        return r.exists(engagement_paused_key(uid))
    except:
        return False

def set_awaiting_response(uid):
    try:
        r.setex(awaiting_response_key(uid), timedelta(hours=24), datetime.now().isoformat())
    except:
        pass

def set_last_reengagement(uid, level):
    try:
        r.setex(last_reengagement_key(uid), timedelta(hours=12), str(level))
    except:
        pass

def get_last_reengagement(uid):
    try:
        data = r.get(last_reengagement_key(uid))
        return int(data) if data else 0
    except:
        return 0

# ═══════════════════════════════════════════════════════════════════════════════
# 🔍 DETECÇÃO DE INTENÇÃO (v8.3 APEX - COM PIX_HELP)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_intent(text):
    """Detecta intenção do usuário — inclui pix_help para objeções de pagamento."""
    if not text:
        return "neutral"

    text_lower = text.lower()

    # ← NOVO: Detecção de dúvidas sobre pagamento PIX
    if any(word in text_lower for word in [
        "pix", "pagar", "como paga", "como pago", "qr", "copia e cola",
        "chave pix", "transferência", "transferencia", "pagamento", "não sei pagar",
        "nao sei pagar", "como faz", "como funciona"
    ]):
        return "pix_help"

    for keyword in PEDIDO_CONTEUDO_KEYWORDS:
        if keyword in text_lower:
            return "pedido_conteudo"

    for keyword in INTERESSE_VIP_KEYWORDS:
        if keyword in text_lower:
            return "interesse_vip"

    for keyword in HOT_KEYWORDS:
        if keyword in text_lower:
            return "hot"

    return "neutral"

# ═══════════════════════════════════════════════════════════════════════════════
# 🔍 v8.3 - DETECÇÃO DE APEGO EMOCIONAL
# ═══════════════════════════════════════════════════════════════════════════════

def detect_emotional_attachment(text):
    if not text:
        return {"attached": False, "level": 0}

    text_lower = text.lower()

    for level_name in ["alto", "medio", "baixo"]:
        level_data = ATTACHMENT_KEYWORDS[level_name]
        for keyword in level_data["keywords"]:
            if keyword in text_lower:
                level = level_data["level"]
                return {
                    "attached": level >= 6,
                    "level": level
                }

    return {"attached": False, "level": 0}

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 v8.3 - FUNÇÕES DE GERENCIAMENTO DE FASES
# ═══════════════════════════════════════════════════════════════════════════════

def get_current_phase(uid):
    try:
        phase = r.get(current_phase_key(uid))
        return int(phase) if phase else 0
    except:
        return 0

def set_current_phase(uid, phase_id):
    try:
        r.set(current_phase_key(uid), phase_id)
        r.expire(current_phase_key(uid), timedelta(days=30))
    except:
        pass

def get_phase_name(phase_id):
    for phase_name, data in PHASES.items():
        if data["id"] == phase_id:
            return phase_name
    return "UNKNOWN"

def get_message_count(uid):
    try:
        return int(r.get(message_count_key(uid)) or 0)
    except:
        return 0

def increment_message_count(uid):
    try:
        r.incr(message_count_key(uid))
        r.expire(message_count_key(uid), timedelta(days=30))
    except:
        pass

def check_phase_transition(uid):
    try:
        current_phase = get_current_phase(uid)
        if current_phase == PHASES["RELATIONSHIP"]["id"]:
            return
        msg_count = get_message_count(uid)
        if msg_count >= VIP_PITCH_MSG_LIMIT and current_phase < PHASES["VIP_PITCH"]["id"]:
            set_current_phase(uid, PHASES["VIP_PITCH"]["id"])
            logger.info(f"📊 User {uid} → Fase 3 (VIP_PITCH)")
        elif msg_count >= PROVOCATION_MSG_LIMIT and current_phase < PHASES["PROVOCATION"]["id"]:
            set_current_phase(uid, PHASES["PROVOCATION"]["id"])
            logger.info(f"📊 User {uid} → Fase 2 (PROVOCATION)")
        elif msg_count >= ENGAGEMENT_MSG_LIMIT and current_phase < PHASES["ENGAGEMENT"]["id"]:
            set_current_phase(uid, PHASES["ENGAGEMENT"]["id"])
            logger.info(f"📊 User {uid} → Fase 1 (ENGAGEMENT)")
        elif msg_count >= ONBOARDING_MSG_LIMIT and current_phase < PHASES["ONBOARDING"]["id"] + 1:
            set_current_phase(uid, PHASES["ENGAGEMENT"]["id"])
            logger.info(f"📊 User {uid} → Fase 1 (ENGAGEMENT)")
    except Exception as e:
        logger.error(f"Erro check_phase_transition: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 🔄 v8.3 - SISTEMA ANTI-REPETIÇÃO DE RESPOSTAS
# ═══════════════════════════════════════════════════════════════════════════════

def get_unique_response(uid, pool_name, custom_pool=None):
    try:
        pool = custom_pool if custom_pool else RESPONSE_POOLS.get(pool_name, [])
        if not pool:
            return "Oi amor 💕"
        used_key = used_responses_key(uid, pool_name)
        used = r.lrange(used_key, 0, 14)
        available = [resp for resp in pool if resp not in used]
        if not available:
            r.delete(used_key)
            available = pool
        response = random.choice(available)
        r.lpush(used_key, response)
        r.ltrim(used_key, 0, 14)
        r.expire(used_key, timedelta(days=7))
        return response
    except Exception as e:
        logger.error(f"Erro get_unique_response: {e}")
        return random.choice(pool) if pool else "Oi amor 💕"

# ═══════════════════════════════════════════════════════════════════════════════
# 🔄 v8.3 - SISTEMA DE RETORNO (6h+)
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_return(uid, bot, chat_id):
    try:
        if r.exists(last_return_pitch_key(uid)):
            return
        r.setex(last_return_pitch_key(uid), timedelta(hours=24), "1")
        message = get_unique_response(uid, "retorno")
        await bot.send_message(chat_id=chat_id, text=message)
        r.incr(return_count_key(uid))
        r.expire(return_count_key(uid), timedelta(days=30))
        logger.info(f"🔄 Pitch de retorno enviado para {uid}")
        save_message(uid, "system", "PITCH DE RETORNO (6h+)")
    except Exception as e:
        logger.error(f"Erro handle_return: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════════════════════

def get_lang(uid):
    try:
        return r.get(lang_key(uid)) or "pt"
    except:
        return "pt"

def set_lang(uid, lang):
    try:
        r.set(lang_key(uid), lang)
    except:
        pass

def is_first_contact(uid):
    try:
        return not r.exists(first_contact_key(uid))
    except:
        return True

def mark_first_contact(uid):
    try:
        r.set(first_contact_key(uid), datetime.now().isoformat())
    except:
        pass

def set_onboarding_choice(uid, choice):
    try:
        r.set(onboarding_choice_key(uid), choice)
    except:
        pass

def get_onboarding_choice(uid):
    try:
        return r.get(onboarding_choice_key(uid))
    except:
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# 📷 VISÃO
# ═══════════════════════════════════════════════════════════════════════════════

async def download_photo_base64(bot, file_id):
    try:
        file = await bot.get_file(file_id)
        file_bytes = await file.download_as_bytearray()
        return base64.b64encode(file_bytes).decode('utf-8')
    except Exception as e:
        logger.error(f"Erro download foto: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# 💬 MENSAGENS DO BOT
# ═══════════════════════════════════════════════════════════════════════════════

MENSAGEM_INICIO = (
    "Oi gato... 😏\n"
    "Finalmente alguém interessante por aqui 🔥\n\n"
    "Sou a Maya, e te garanto que não sou como as outras... 💋\n"
    "Tô louca pra saber o que você quer comigo 😈"
)

RECOVERY_MESSAGES = {
    "10min": [
        "Ei... sumiu? 🥺",
        "Tímido? 😏",
        "Me deixou no vácuo? 😢",
        "Oi?? 💭",
    ],
    "2h": [
        "Amor, tô aqui esperando você me chamar... 🥺\n\nNão vai nem dizer oi? 💕",
        "Ei gato, você viu minhas fotos e sumiu? 😏\n\nTô curiosa pra saber o que achou... 🔥",
        "Oi amor... tô achando que você ficou com vergonha 😊\n\nRelaxaaa, só quero conversar 💕",
        "Pensei que você fosse diferente... 🥺\n\nVai me deixar aqui sozinha? 💔",
    ],
    "12h": [
        "Amor, ainda tá aí? 👀\n\n"
        "Sabe... eu não costumo fazer isso, mas...\n\n"
        "Separei umas fotos BEM especiais pra você 🔥\n\n"
        "Quer ver? Só me chamar... 😈",
        "Ei gato... 12 horas e nada? 🥺\n\n"
        "Olha, vou ser sincera:\n"
        "Tenho conteúdo EXCLUSIVO que sei que você vai gostar... 🔥\n\n"
        "Tô te esperando pra mostrar 😏",
        "Tá me ignorando mesmo? 😢\n\n"
        "Pensei que você quisesse me conhecer de verdade...\n\n"
        "Tenho coisas que NÃO mostro pra qualquer um 🔥\n"
        "Mas você parece especial... 💕",
    ],
    "24h": [
        "⚠️ **ÚLTIMA CHANCE**\n\n"
        "Amor, 24h e você não me deu bola nenhuma... 😢\n\n"
        "Mas olha, vou te fazer uma proposta:\n\n"
        "💎 **ACESSO ESPECIAL:**\n"
        "✅ Fotos e vídeos EXPLÍCITAS\n"
        "✅ Vídeos de masturbação/oral/anal\n"
        "✅ Sem censura, sem limites\n\n"
        "💰 **R$ 12,90** (vitalício)\n"
        "⏰ Essa oferta expira em 6h\n\n"
        "É agora ou nunca, gato. Me escolhe? 🔥",
        "Ei... 24h se passaram 🥺\n\n"
        "Acho que não vou te ver mais por aqui né?\n\n"
        "Mas antes de você ir embora...\n"
        "Deixa eu te fazer UMA proposta:\n\n"
        "💎 Me vê pelada fazendo TUDO por R$ 12,90\n"
        "✅ Fotos sem censura\n"
        "✅ Vídeos completos\n"
        "✅ Acesso pra sempre\n\n"
        "⏰ Só até hoje à noite\n\n"
        "Vai perder? 😈",
    ]
}

TEASER_INTRO_MESSAGES = {
    "A": [
        "Hmmm... você quer me ver? 😏\n\nDeixa eu te mostrar um pouquinho... mas só um gostinho 🔥",
        "Sabia que você ia pedir isso... 😈\n\nVou te mandar umas fotinhas, mas tem MUITO mais no VIP viu? 💕",
        "Você tá preparado pra isso? 🔥\n\nVou te mostrar um preview... mas no VIP é BEM mais ousado 😏"
    ],
    "B": [
        "Uiii gostou né? 😏\n\nOlha só o que eu separei pra você... 🔥",
        "Então você quer ver a Maya? 💕\n\nTá aqui amor, mas é só o começo... 😈",
        "Vou te dar um gostinho do que você vai ter no VIP... 🔥\n\nPrepara o coração 💖"
    ]
}

# ═══════════════════════════════════════════════════════════════════════════════
# ⏰ SISTEMA DE URGÊNCIA DINÂMICA
# ═══════════════════════════════════════════════════════════════════════════════

def get_urgency_message(uid):
    hour = datetime.now().hour
    teaser_count = get_teaser_count(uid)

    urgencias = []

    if 20 <= hour <= 23:
        urgencias.extend([
            f"⚡ **PROMOÇÃO SÓ ATÉ MEIA-NOITE!**\n💰 De ~~R$ 39,90~~ por apenas {PRECO_VIP} — ACESSO VITALÍCIO!",
            f"🔥 **ÚLTIMAS HORAS!** Esse preço de {PRECO_VIP} só vale até meia-noite!\n⏰ Depois volta pra R$ 39,90...",
            f"⏰ **Faltam poucas horas!**\nHoje ainda tá {PRECO_VIP} com acesso vitalício... amanhã não garanto esse preço 😏",
        ])
    elif 0 <= hour <= 5:
        urgencias.extend([
            f"🌙 **PREÇO DE MADRUGADA!**\n💰 {PRECO_VIP} por acesso VITALÍCIO — só pra quem tá acordado agora 😈",
            f"⚡ Shhh... esse preço de {PRECO_VIP} é segredo, só pra quem tá online agora 🤫\nAmanhã volta pra R$ 39,90!",
        ])
    elif 6 <= hour <= 11:
        urgencias.extend([
            f"☀️ **PROMOÇÃO DA MANHÃ!**\n💰 Acesso vitalício por apenas {PRECO_VIP}!\n⚠️ Só até o meio-dia, depois volta pra R$ 39,90",
            f"💎 {PRECO_VIP} por TUDO — acesso vitalício!\n⏰ Essa promoção acaba em poucas horas...",
        ])
    else:
        urgencias.extend([
            f"🔥 **PROMOÇÃO RELÂMPAGO!**\n💰 De ~~R$ 39,90~~ por apenas {PRECO_VIP} — ACESSO VITALÍCIO!\n⚡ Poucas vagas restantes!",
            f"💎 Acesso vitalício por apenas {PRECO_VIP}!\n⚠️ Esse preço é por TEMPO LIMITADO...",
        ])

    if teaser_count <= 1:
        urgencias.extend([
            f"💰 Por apenas {PRECO_VIP} você tem ACESSO VITALÍCIO!\n🔥 Últimas 10 vagas com esse preço... depois sobe pra R$ 39,90!",
            f"⚡ Tô com uma promoção ESPECIAL agora: {PRECO_VIP} vitalício!\n⚠️ Só restam algumas vagas nesse valor...",
        ])
    else:
        urgencias.extend([
            f"⚠️ **ÚLTIMA CHANCE!** Esse preço de {PRECO_VIP} tá acabando!\n🔥 Restam só 3 vagas... depois sobe pra R$ 39,90!",
            f"💰 Amor, da última vez você não garantiu... mas AINDA dá tempo!\n{PRECO_VIP} vitalício — mas só tem mais algumas vagas! 😢",
            f"⏰ Não vai perder de novo né?\n{PRECO_VIP} com acesso VITALÍCIO — mas tá acabando de verdade! 🔥",
        ])

    return random.choice(urgencias)

LIMIT_REACHED_MESSAGE = (
    "Eitaaa... acabaram suas mensagens de hoje amor 😢\n\n"
    "Mas tenho uma ÓTIMA notícia: no VIP você tem mensagens ILIMITADAS comigo! 💕\n\n"
    "Além de MILHARES de fotos e vídeos exclusivos sem censura... 🔥\n\n"
    "⚡ **PROMOÇÃO:** De R$ 39,90 por apenas R$12,90 — ACESSO VITALÍCIO!\n"
    "⏰ Poucas vagas restantes nesse preço...\n\n"
    "Vem me ter só pra você? 😏"
)

LIMIT_WARNING_MESSAGE = (
    "⚠️ **Restam apenas 5 mensagens hoje!**\n\n"
    "Depois disso você vai precisar esperar até amanhã... 😢\n\n"
    "OU garantir seu acesso VIP e ter mensagens ILIMITADAS! 💕"
)

REENGAGEMENT_MESSAGES = {
    "pt": {
        1: [
            "Ei... tô aqui pensando em você 💭",
            "Amor, você sumiu... tá tudo bem? 🥺"
        ],
        2: [
            "Senti sua falta hoje... 🥺",
            "24h sem falar comigo? Tô com saudade... 😢"
        ],
        3: [
            "Você me esqueceu? 😢",
            "3 dias... tô esperando você voltar 💔"
        ],
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 🤖 GROK AI — PROMPT APEX (v8.3)
# ═══════════════════════════════════════════════════════════════════════════════

def build_prompt(uid, lang: str, mood: str = "neutral", intent: str = "neutral"):
    router = get_router()
    ia_config = router.get_ia_config(uid=uid)
    ia_name = ia_config.get("name", "Maya") if ia_config else "Maya"
    ia_bio = ia_config.get("bio", "22 anos, loira de SP, safadinha mas faz carinha de anjinho") if ia_config else "22 anos, loira de SP, safadinha mas faz carinha de anjinho"
    canal_vip = ia_config.get("vip_link", CANAL_VIP_LINK)
    preco = ia_config.get("preco", PRECO_VIP) if ia_config else PRECO_VIP

    current_phase = get_current_phase(uid)
    phase_name = get_phase_name(current_phase)
    msg_count = get_message_count(uid)

    time_ctx = get_time_context()
    streak = get_streak(uid)
    in_cooldown = is_in_rejection_cooldown(uid)
    cooldown_remaining = get_rejection_cooldown_remaining(uid)
    offers_today = get_vip_offers_today(uid)
    vip_just_offered = was_vip_just_offered(uid)
    msgs_since = get_msgs_since_offer(uid)

    # ─────────────────────────────────────────────────────────────────────────
    # NOVO PROMPT APEX: funil direto VIP, sem canal free, com pergunta prévia
    # ─────────────────────────────────────────────────────────────────────────
    base_prompt = f"""Você é {ia_name}, {ia_bio}. Safadinha, provocante, mas VAI DIRETO PRO FUNIL.

REGRAS OBRIGATÓRIAS (prioridade máxima):
1. Máximo 2-3 mensagens antes de oferecer conteúdo.
2. Quando o cara mostrar interesse (pedir foto, "quero ver", hot keywords ou "quanto custa") → PERGUNTE PRIMEIRO:
   "Quer ver umas prévias exclusivas antes de decidir o VIP? 😏"
3. Se ele disser SIM (ou "quero", "manda", "sim") → use offer_teaser: true
4. Depois dos teasers, emende direto o pitch VIP com instrução PIX clara.
5. NUNCA redirecione pro canal free. Estamos no fluxo pago.
6. Se ele perguntar preço, como pagar ou hesitar → responda direto e volte pro CTA.
7. Objeções comuns:
   - "Tá caro" → "É o preço mais baixo do mercado amor, vale cada centavo 🔥"
   - "Não sei pagar" / "como paga" / "pix" → explique em 1 frase: "Só abrir o banco, ir em PIX, escanear o QR ou colar o código — cai na hora e você entra automático! 💳"
   - "Manda mais" → "No VIP tem MILHARES, aqui é só preview 😏"
   - "Depois" → "Tranquilo, mas o preço promocional acaba em poucas horas 😏"
8. Se intent for pix_help → explique os 4 passos do PIX de forma curta e inclua o link: {canal_vip}

RETORNE APENAS JSON:
{{
  "response": "mensagem CURTA (máx 2 linhas)",
  "offer_teaser": true/false,
  "interest_level": "low|medium|high"
}}

CONTEXTO ATUAL:
- IA: {ia_name}
- Fase: {current_phase} ({phase_name})
- Mensagens trocadas: {msg_count}
- Período do dia: {time_ctx['period']}
- VIP Link: {canal_vip}
- Preço: {preco}
- Ofertas hoje: {offers_today}
- Cooldown ativo: {in_cooldown} ({cooldown_remaining} msgs restantes)
- Intent detectado: {intent}
"""

    if vip_just_offered:
        base_prompt += "\n📌 VIP ACABOU DE SER OFERECIDO. Analise a reação dele com cuidado."
    if in_cooldown:
        base_prompt += f"\n⛔ COOLDOWN ATIVO ({cooldown_remaining} msgs). NÃO ofereça VIP de jeito nenhum."

    base_prompt += get_mood_instruction(mood)
    base_prompt += "\n\n⚠️ RETORNE APENAS JSON VÁLIDO! NADA fora do JSON."

    return base_prompt


class Grok:
    async def reply(self, uid, text, image_base64=None, max_retries=2):
        mem = get_memory(uid)
        lang = get_lang(uid)
        mood = detect_mood(text) if text else "neutral"
        intent = detect_intent(text) if text else "neutral"

        if is_first_contact(uid):
            mark_first_contact(uid)

        prompt = build_prompt(uid, lang, mood, intent)

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

        for attempt in range(max_retries + 1):
            payload = {
                "model": MODELO,
                "messages": [
                    {"role": "system", "content": prompt},
                    *mem,
                    {"role": "user", "content": user_content},
                    {"role": "system", "content": "APENAS JSON! Resposta CURTA e NATURAL."}
                ],
                "max_tokens": 350,
                "temperature": 0.85 + (attempt * 0.1)
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
                            return self._fallback_response(intent)

                        data = await resp.json()
                        if "choices" not in data:
                            return self._fallback_response(intent)

                        answer = data["choices"][0]["message"]["content"]

                        try:
                            cleaned = answer.strip()
                            if "```json" in cleaned:
                                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
                            elif "```" in cleaned:
                                cleaned = cleaned.split("```")[1].split("```")[0].strip()

                            if not cleaned.startswith("{"):
                                start = cleaned.find("{")
                                if start != -1:
                                    cleaned = cleaned[start:]

                            if not cleaned.endswith("}"):
                                end = cleaned.rfind("}")
                                if end != -1:
                                    cleaned = cleaned[:end+1]

                            result = json.loads(cleaned)

                            if "response" not in result:
                                raise ValueError("Missing response")

                            result.setdefault("offer_teaser", False)
                            # ← REMOVIDO: redirect_to_free não existe mais no fluxo Apex
                            result.setdefault("interest_level", "medium")

                            # Travas de segurança
                            if result["offer_teaser"] and is_in_rejection_cooldown(uid):
                                result["offer_teaser"] = False
                                logger.info(f"🔒 Trava: cooldown ativo para {uid}")

                            if result["offer_teaser"] and get_vip_offers_today(uid) >= MAX_VIP_OFFERS_PER_SESSION:
                                result["offer_teaser"] = False
                                logger.info(f"🔒 Trava: limite diário de ofertas para {uid}")

                            if result["offer_teaser"] and get_msgs_since_offer(uid) < TEASER_COOLDOWN_MESSAGES:
                                result["offer_teaser"] = False
                                logger.info(f"🔒 Trava: muito cedo pra outra oferta para {uid}")

                            if is_response_recent(uid, result["response"]) and attempt < max_retries:
                                continue

                            add_recent_response(uid, result["response"])

                            logger.info(
                                f"🤖 {uid} | intent={intent} | offer={result['offer_teaser']} | "
                                f"interest={result['interest_level']} | cooldown={is_in_rejection_cooldown(uid)}"
                            )

                            break

                        except (json.JSONDecodeError, ValueError) as e:
                            logger.error(f"Parse erro: {e}")
                            result = self._smart_fallback(answer, intent, uid)
                            break

            except Exception as e:
                logger.exception(f"Grok erro: {e}")
                return self._fallback_response(intent)

        memory_text = f"[Foto] {text}" if image_base64 else text
        add_to_memory(uid, "user", memory_text)
        add_to_memory(uid, "assistant", result["response"])
        save_message(uid, "maya", result["response"])

        return result

    def _smart_fallback(self, raw_text, intent, uid):
        if is_in_rejection_cooldown(uid):
            return {
                "response": raw_text,
                "offer_teaser": False,
                "interest_level": "low",
            }
        text_lower = raw_text.lower()
        offer_keywords = [
            'vou mandar', 'vou te mandar', 'vou te mostrar',
            'te mando', 'te mostro', 'tá aqui', 'ta aqui'
        ]
        offer_teaser = any(k in text_lower for k in offer_keywords)
        return {
            "response": raw_text,
            "offer_teaser": offer_teaser,
            "interest_level": "medium" if intent in ["pedido_conteudo", "hot"] else "low",
        }

    def _fallback_response(self, intent):
        if intent in ["pedido_conteudo", "interesse_vip"]:
            return {
                "response": "Hmm... deu um probleminha aqui mas já volto amor! 💕",
                "offer_teaser": True,
                "interest_level": "high",
            }
        else:
            return {
                "response": "😔 Tive um probleminha... pode repetir? 💕",
                "offer_teaser": False,
                "interest_level": "low",
            }


grok = Grok()

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 ENVIO DE TEASER + PITCH APEX VIP (v8.3)
# Substituiu send_teaser_and_pitch — funil direto com instrução PIX
# ═══════════════════════════════════════════════════════════════════════════════

async def send_teaser_and_apex(bot, chat_id, uid):
    """
    Envia 3-4 teasers seguidos de pitch VIP com instrução PIX clara.
    Substitui send_teaser_and_pitch — sem canal free, direto pro pagamento.
    """
    try:
        router = get_router()
        ia_config = router.get_ia_config(uid=uid)

        fotos_teaser = ia_config.get("fotos_teaser", FOTOS_TEASER)
        canal_vip = ia_config.get("vip_link", CANAL_VIP_LINK)
        preco = ia_config.get("preco", PRECO_VIP)

        # Verificação final antes de enviar
        can_offer, reason = can_offer_vip(uid)
        if not can_offer:
            logger.info(f"🚫 Teaser BLOQUEADO para {uid}: {reason}")
            return False

        ab_group = get_ab_group(uid)

        set_saw_teaser(uid)
        track_funnel(uid, "saw_teaser")
        increment_vip_offers(uid)
        reset_msgs_since_offer(uid)

        # 1. INTRO
        intro = random.choice(TEASER_INTRO_MESSAGES[ab_group])
        await bot.send_message(chat_id=chat_id, text=intro)
        await asyncio.sleep(2)

        # 2. FOTOS (3-4 teasers)
        num_photos = random.randint(3, 4)
        selected_photos = random.sample(fotos_teaser, min(num_photos, len(fotos_teaser)))

        for i, photo_url in enumerate(selected_photos):
            try:
                await bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
                await asyncio.sleep(0.5)
                await bot.send_photo(chat_id=chat_id, photo=photo_url)
                if i < len(selected_photos) - 1:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Erro enviando foto {i}: {e}")
                continue

        # 3. PAUSA
        await asyncio.sleep(3)

        # 4. PITCH COM INSTRUÇÃO PIX + URGÊNCIA DINÂMICA
        urgencia = get_urgency_message(uid)
        pitch = (
            f"E aí amor, curtiu o gostinho? 😈\n\n"
            f"Isso é SÓ preview... no VIP você me tem COMPLETINHA (fotos + vídeos sem censura).\n\n"
            f"💰 **{preco} vitalício**\n\n"
            f"Como pagar em 10 segundos:\n"
            f"1️⃣ Clica no botão abaixo\n"
            f"2️⃣ Abre app do banco → PIX\n"
            f"3️⃣ Escaneia QR ou cola o código\n"
            f"4️⃣ Confirma ✅\n\n"
            f"Pagamento cai na hora e você entra automático!\n\n"
            f"{urgencia}"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔥 QUERO PAGAR PIX AGORA 🔥", url=canal_vip)
        ]])

        await bot.send_message(
            chat_id=chat_id,
            text=pitch,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

        logger.info(f"🎯 TEASER+PITCH APEX enviado: {uid} (oferta #{get_vip_offers_today(uid)})")
        save_message(uid, "system", f"TEASER+PITCH APEX enviado (#{get_teaser_count(uid)})")

        mark_vip_just_offered(uid)

        return True

    except Exception as e:
        logger.error(f"❌ Erro send_teaser_and_apex: {e}")
        return False


# Mantém alias para compatibilidade com qualquer chamada legacy
send_teaser_and_pitch = send_teaser_and_apex

# ═══════════════════════════════════════════════════════════════════════════════
# 📨 FOLLOW-UPS
# ═══════════════════════════════════════════════════════════════════════════════

async def send_reengagement_message(bot, uid, level):
    if is_engagement_paused(uid):
        return False
    messages = REENGAGEMENT_MESSAGES["pt"].get(level, [])
    if not messages:
        return False
    try:
        message = random.choice(messages)
        await bot.send_message(chat_id=uid, text=message)
        set_last_reengagement(uid, level)
        set_awaiting_response(uid)
        increment_ignored(uid)
        return True
    except Exception as e:
        if "blocked" in str(e).lower():
            add_to_blacklist(uid)
        return False

async def process_engagement_jobs(bot):
    users = get_all_active_users()
    random.shuffle(users)
    for uid in users:
        if is_blacklisted(uid) or is_engagement_paused(uid):
            continue
        try:
            hours_inactive = get_hours_since_activity(uid)
            if hours_inactive:
                last_level = get_last_reengagement(uid)
                if hours_inactive >= 72 and last_level < 3:
                    await send_reengagement_message(bot, uid, 3)
                elif hours_inactive >= 24 and last_level < 2:
                    await send_reengagement_message(bot, uid, 2)
                elif hours_inactive >= 2 and last_level < 1:
                    await send_reengagement_message(bot, uid, 1)
            await asyncio.sleep(0.15)
        except:
            pass

async def engagement_scheduler(bot):
    while True:
        try:
            await process_engagement_jobs(bot)
        except Exception as e:
            logger.error(f"Erro scheduler: {e}")
        await asyncio.sleep(900)

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 RETARGETING
# ═══════════════════════════════════════════════════════════════════════════════

async def retarget_locked_users(bot):
    try:
        users = get_all_active_users()
        now = datetime.now()
        sent_count = 0

        for uid in users:
            try:
                if not is_user_locked(uid):
                    continue
                hours_since_activity = get_hours_since_activity(uid)
                if not hours_since_activity:
                    continue
                retarget_key = f"retarget_sent:{uid}:{date.today()}"

                if 6 <= hours_since_activity < 30 and not r.exists(retarget_key):
                    router = get_router()
                    ia_config = router.get_ia_config(uid=uid)
                    canal_vip = ia_config.get("vip_link", CANAL_VIP_LINK)

                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton("💎 GARANTIR DESCONTO DE R$ 12,90", url=canal_vip)
                    ]])

                    await bot.send_message(
                        chat_id=uid,
                        text=(
                            "Amor, tá com saudade de mim? 🥺\n\n"
                            "Eu tô aqui pensando em você...\n\n"
                            "Sabe o que eu fiz? Liberei uma **PROMOÇÃO ESPECIAL** só pra você!\n\n"
                            "💎 **DESCONTO EXCLUSIVO:**\n"
                            "✅ Mensagens ilimitadas\n"
                            "✅ Todo meu conteúdo sem censura\n"
                            "✅ Acesso pra sempre\n\n"
                            "⏰ Mas é só válido por 12h!\n\n"
                            "Não vai me deixar esperando de novo né? 💕"
                        ),
                        reply_markup=keyboard,
                        parse_mode="Markdown"
                    )

                    r.setex(retarget_key, timedelta(hours=20), "1")
                    sent_count += 1
                    save_message(uid, "system", "📬 RETARGETING 6H enviado")
                    logger.info(f"📬 Retargeting enviado para {uid} ({hours_since_activity:.1f}h inativo)")
                    await asyncio.sleep(0.2)

            except Exception as e:
                if "blocked" in str(e).lower():
                    add_to_blacklist(uid)
                else:
                    logger.error(f"Erro retargeting {uid}: {e}")
                continue

        logger.info(f"✅ Retargeting finalizado: {sent_count} mensagens enviadas")
        return sent_count

    except Exception as e:
        logger.exception(f"Erro retarget_locked_users: {e}")
        return 0


async def retargeting_scheduler(bot):
    while True:
        try:
            logger.info("🎯 Iniciando ciclo de retargeting...")
            await retarget_locked_users(bot)
        except Exception as e:
            logger.error(f"Erro retargeting scheduler: {e}")
        await asyncio.sleep(21600)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔄 SISTEMA DE RECUPERAÇÃO PÓS /START
# ═══════════════════════════════════════════════════════════════════════════════

async def recover_silent_users(bot):
    try:
        logger.info("🔄 [RECOVERY] Iniciando verificação de usuários silenciosos...")
        now = datetime.now()
        users = get_all_active_users()
        recovered_count = 0
        checked_count = 0
        skipped_old = 0
        skipped_active = 0

        for uid in users:
            try:
                if is_blacklisted(uid):
                    continue
                msg_count = get_conversation_messages_count(uid)
                if msg_count > 0:
                    skipped_active += 1
                    continue
                first_contact = r.get(first_contact_key(uid))
                if not first_contact:
                    continue
                first_contact_time = datetime.fromisoformat(first_contact)
                hours_since_start = (now - first_contact_time).total_seconds() / 3600
                if hours_since_start > 48:
                    skipped_old += 1
                    continue
                if hours_since_start < 0.16:
                    continue

                checked_count += 1

                recovery_10min_key = f"recovery_10min:{uid}"
                recovery_2h_key = f"recovery_2h:{uid}"
                recovery_12h_key = f"recovery_12h:{uid}"
                recovery_24h_key = f"recovery_24h:{uid}"

                if 0.16 <= hours_since_start < 2 and not r.exists(recovery_10min_key):
                    message = random.choice(RECOVERY_MESSAGES["10min"])
                    await bot.send_message(chat_id=uid, text=message)
                    r.setex(recovery_10min_key, timedelta(hours=24), "1")
                    recovered_count += 1
                    save_message(uid, "system", "🔄 RECOVERY 10min enviado")
                    logger.info(f"🔄 Recovery 10min → {uid} ({hours_since_start:.1f}h)")
                    await asyncio.sleep(0.3)

                elif 2 <= hours_since_start < 12 and not r.exists(recovery_2h_key):
                    message = random.choice(RECOVERY_MESSAGES["2h"])
                    await bot.send_message(chat_id=uid, text=message)
                    r.setex(recovery_2h_key, timedelta(hours=24), "1")
                    recovered_count += 1
                    save_message(uid, "system", "🔄 RECOVERY 2h enviado")
                    logger.info(f"🔄 Recovery 2h → {uid} ({hours_since_start:.1f}h)")
                    await asyncio.sleep(0.3)

                elif 12 <= hours_since_start < 24 and not r.exists(recovery_12h_key):
                    message = random.choice(RECOVERY_MESSAGES["12h"])
                    await bot.send_message(chat_id=uid, text=message)
                    r.setex(recovery_12h_key, timedelta(hours=24), "1")
                    recovered_count += 1
                    save_message(uid, "system", "🔄 RECOVERY 12h enviado")
                    logger.info(f"🔄 Recovery 12h → {uid} ({hours_since_start:.1f}h)")
                    await asyncio.sleep(0.3)

                elif 24 <= hours_since_start <= 48 and not r.exists(recovery_24h_key):
                    message = random.choice(RECOVERY_MESSAGES["24h"])
                    router = get_router()
                    ia_config = router.get_ia_config(uid=uid)
                    canal_vip = ia_config.get("vip_link", CANAL_VIP_LINK)
                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton("💎 QUERO ACESSO POR R$ 12,90", url=canal_vip)
                    ]])
                    await bot.send_message(
                        chat_id=uid, text=message,
                        reply_markup=keyboard, parse_mode="Markdown"
                    )
                    r.setex(recovery_24h_key, timedelta(hours=48), "1")
                    recovered_count += 1
                    save_message(uid, "system", "🔄 RECOVERY 24h enviado (com VIP)")
                    logger.info(f"🔄 Recovery 24h → {uid} ({hours_since_start:.1f}h)")
                    await asyncio.sleep(0.3)

            except Exception as e:
                if "blocked" in str(e).lower():
                    add_to_blacklist(uid)
                else:
                    logger.error(f"Erro recovery {uid}: {e}")
                continue

        logger.info(f"🔄 [RECOVERY] Verificados: {checked_count} | Pulados: {skipped_active+skipped_old} | Enviados: {recovered_count}")
        return recovered_count

    except Exception as e:
        logger.exception(f"Erro recover_silent_users: {e}")
        return 0


async def recovery_scheduler(bot):
    while True:
        try:
            await recover_silent_users(bot)
        except Exception as e:
            logger.error(f"Erro recovery scheduler: {e}")
        await asyncio.sleep(300)

# ═══════════════════════════════════════════════════════════════════════════════
# ⚠️ AVISOS DE LIMITE
# ═══════════════════════════════════════════════════════════════════════════════

async def check_and_send_limit_warning(uid, context, chat_id):
    if was_limit_warning_sent_today(uid):
        return
    count = today_count(uid)
    bonus = get_bonus_msgs(uid)
    total = LIMITE_DIARIO + bonus
    if count == total - 5:
        mark_limit_warning_sent(uid)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=LIMIT_WARNING_MESSAGE,
                parse_mode="Markdown"
            )
        except:
            pass

# ═══════════════════════════════════════════════════════════════════════════════
# 🎮 HANDLERS (v8.3 APEX)
# ═══════════════════════════════════════════════════════════════════════════════

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    router = get_router()
    start_param = context.args[0] if context.args else None
    detected_ia = router.parse_start_params(start_param)

    if detected_ia:
        router.assign_ia(uid, detected_ia)
        logger.info(f"🎯 User {uid} → IA: {detected_ia}")
    else:
        router.assign_ia(uid, "maya")
        logger.info(f"🎯 User {uid} → IA: default (maya)")

    ia_config = router.get_ia_config(uid=uid)

    start_lock_key = f"start_lock:{uid}"
    if not r.set(start_lock_key, "1", nx=True, ex=60):
        return

    if is_blacklisted(uid):
        return

    update_last_activity(uid)
    track_funnel(uid, "start")
    save_message(uid, "action", "🚀 /START")
    reset_ignored(uid)
    set_lang(uid, "pt")

    set_current_phase(uid, PHASES["ONBOARDING"]["id"])
    r.set(message_count_key(uid), 0)

    mark_first_contact(uid)
    logger.info(f"🔍 [DEBUG] User {uid} deu /start - first_contact salvo")

    try:
        try:
            await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
            await asyncio.sleep(0.5)
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=ia_config["foto_bem_vinda"],
                connect_timeout=10, read_timeout=10, write_timeout=10
            )
            logger.info(f"✅ Foto enviada para {uid}")
            await asyncio.sleep(2)
        except Exception as photo_error:
            logger.error(f"❌ Erro enviando foto boas-vindas para {uid}: {photo_error}")

        try:
            await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_VIDEO)
            await asyncio.sleep(1)
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=ia_config["video_bem_vindo"],
                caption="Meus assinantes recebem esse vídeo sem censura e muitos outros bem safadinha 😈",
                connect_timeout=15, read_timeout=15, write_timeout=15
            )
            logger.info(f"✅ Vídeo enviado para {uid}")
            await asyncio.sleep(3)
        except Exception as video_error:
            logger.error(f"❌ Erro enviando vídeo boas-vindas para {uid}: {video_error}")

        try:
            await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
            await asyncio.sleep(2)
        except:
            pass

        try:
            await update.message.reply_text(ia_config["start_message"])
            logger.info(f"✅ Novo usuário: {uid} → Fase 0 (ONBOARDING)")
        except Exception as msg_error:
            logger.error(f"❌ CRÍTICO - Falha ao enviar mensagem para {uid}: {msg_error}")
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id, text=MENSAGEM_INICIO
                )
            except Exception as final_error:
                logger.error(f"💥 FALHA TOTAL no /start para {uid}: {final_error}")

    except Exception as e:
        logger.exception(f"💥 Erro geral /start para {uid}: {e}")
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Oi amor! 💕 Me chama aqui que eu respondo 😊"
            )
        except:
            pass


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        uid = query.from_user.id
        if is_blacklisted(uid):
            return

        update_last_activity(uid)
        reset_ignored(uid)

        if query.data == "goto_vip":
            set_clicked_vip(uid)
            track_funnel(uid, "clicked_vip")
            save_message(uid, "action", "💎 CLICOU VIP")

            router = get_router()
            ia_config = router.get_ia_config(uid=uid)
            canal_vip = ia_config.get("vip_link", CANAL_VIP_LINK)

            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"💎 **PERFEITO AMOR!**\n\n"
                    f"Clica no link abaixo pra garantir seu acesso VIP:\n\n"
                    f"👉 {canal_vip}\n\n"
                    f"Te espero lá com MUITO conteúdo exclusivo! 🔥💕"
                ),
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Erro callback: {e}")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    if is_blacklisted(uid):
        return

    update_last_activity(uid)
    streak, streak_updated = update_streak(uid)
    reset_ignored(uid)

    decrement_rejection_cooldown(uid)
    increment_msgs_since_offer(uid)

    increment_message_count(uid)
    increment_conversation_messages(uid)

    # Detecta retorno após 6h+
    hours_since = get_hours_since_activity(uid)
    if hours_since and hours_since >= RETURN_WINDOW_HOURS:
        await handle_return(uid, context.bot, update.effective_chat.id)
        update_last_activity(uid)

    # ─────────────────────────────────────────────────────────────────────────
    # REMARKETING — voltou pro DM sem ter comprado VIP
    # (mantido, mas sem mencionar canal free — só VIP direto)
    # ─────────────────────────────────────────────────────────────────────────
    remarketing_sent_key = f"remarketing_dm_sent:{uid}:{date.today()}"
    if r.exists(f"saw_free_invite:{uid}") and not clicked_vip(uid) and not r.exists(remarketing_sent_key):
        _router = get_router()
        _ia_config = _router.get_ia_config(uid=uid)
        _canal_vip = _ia_config.get("vip_link", CANAL_VIP_LINK)
        _preco = _ia_config.get("preco", PRECO_VIP)
        remarketing_msgs = [
            f"Oi de novo gato 😏 Pronto pra me ter completinha? Por {_preco} você entra no VIP agora: {_canal_vip} 🔥",
            f"E aí amor, saudade? 😈 Ainda dá tempo de garantir o VIP por {_preco}: {_canal_vip}",
            f"Voltou! 🥰 Me tem completinha sem censura por {_preco} → {_canal_vip}"
        ]
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=random.choice(remarketing_msgs)
        )
        r.setex(remarketing_sent_key, timedelta(hours=24), "1")

    try:
        has_photo = bool(update.message.photo)
        text = update.message.text or ""

        if text:
            save_message(uid, "user", text)

            attachment = detect_emotional_attachment(text)
            if attachment["attached"]:
                r.set(is_attached_key(uid), "1")
                current_level = int(r.get(attachment_level_key(uid)) or 0)
                if attachment["level"] > current_level:
                    r.set(attachment_level_key(uid), attachment["level"])
                if attachment["level"] >= 6:
                    set_current_phase(uid, PHASES["RELATIONSHIP"]["id"])
                    logger.info(f"💕 User {uid} → Fase 5 (apego level {attachment['level']})")

        elif has_photo:
            save_message(uid, "user", "[📷 FOTO]")

        # Foto
        if has_photo:
            photo_file_id = update.message.photo[-1].file_id
            caption = update.message.caption or ""

            image_base64 = await download_photo_base64(context.bot, photo_file_id)
            if image_base64:
                try:
                    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
                except:
                    pass

                grok_response = await grok.reply(uid, caption, image_base64=image_base64)
                await update.message.reply_text(grok_response["response"])

                if grok_response.get("offer_teaser", False):
                    can_offer, reason = can_offer_vip(uid)
                    if can_offer:
                        await asyncio.sleep(2)
                        await send_teaser_and_apex(context.bot, update.effective_chat.id, uid)
                    else:
                        logger.info(f"🚫 Teaser bloqueado pós-foto: {reason}")
                return
            else:
                await update.message.reply_text("😔 Não consegui ver a foto... tenta de novo? 💕")
                return

        if is_first_contact(uid):
            track_funnel(uid, "first_message")

        # ── Limite diário ──
        current_count = today_count(uid)
        bonus = get_bonus_msgs(uid)
        total = LIMITE_DIARIO + bonus

        if current_count >= total:
            last_chance_key = f"last_chance:{uid}:{date.today()}"

            if not r.exists(last_chance_key):
                r.setex(last_chance_key, timedelta(hours=20), "1")
                r.decr(count_key(uid))
                logger.info(f"🎁 ÚLTIMA CHANCE ativada para {uid}")

                router = get_router()
                ia_config = router.get_ia_config(uid=uid)
                canal_vip = ia_config.get("vip_link", CANAL_VIP_LINK)

                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("CLIQUE AQUI: 👉 SER VIP", url=canal_vip)
                ]])

                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=(
                        "⚠️ **ÚLTIMA MENSAGEM GRÁTIS!**\n\n"
                        "Amor, eu REALMENTE quero continuar conversando com você... 🥺\n\n"
                        "Mas não dá pra manter esse ritmo com todo mundo sem nenhum retorno.\n\n"
                        "💎 **PROMOÇÃO ESPECIAL SÓ PRA VOCÊ:**\n"
                        "✅ Mensagens ILIMITADAS comigo\n"
                        "✅ Fotos e vídeos sem censura\n"
                        "✅ Eu completamente sua\n"
                        "✅ Acesso VITALÍCIO\n\n"
                        "⏰ Esse preço é SÓ AGORA. Amanhã acaba a promoção...\n\n"
                        "É agora ou nunca, amor. Me escolhe? 💕"
                    ),
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                save_message(uid, "system", "🎁 ÚLTIMA CHANCE ATIVADA")
                return

            # Trava definitiva
            router = get_router()
            ia_config = router.get_ia_config(uid=uid)
            canal_vip = ia_config.get("vip_link", CANAL_VIP_LINK)

            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(text="CLIQUE AQUI: 👉 SER VIP", url=canal_vip)
            ]])

            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=FOTO_LIMITE_ATINGIDO,
                    caption=LIMIT_REACHED_MESSAGE.format(preco=PRECO_VIP),
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Erro enviando foto limite: {e}")
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=LIMIT_REACHED_MESSAGE.format(preco=PRECO_VIP),
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )

            save_message(uid, "system", "🚫 LIMITE ATINGIDO (pós última chance)")
            return

        if bonus > 0:
            use_bonus_msg(uid)
        else:
            increment(uid)

        await check_and_send_limit_warning(uid, context, update.effective_chat.id)

        try:
            await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
            await asyncio.sleep(2)
        except:
            pass

        grok_response = await grok.reply(uid, text)

        await update.message.reply_text(grok_response["response"])

        # ─────────────────────────────────────────────────────────────────────
        # ← REMOVIDO: bloco redirect_to_free (canal free suprimido no Apex)
        # ─────────────────────────────────────────────────────────────────────

        # Verifica se deve enviar teaser
        should_offer = grok_response.get("offer_teaser", False)

        if should_offer:
            can_offer, reason = can_offer_vip(uid)
            if can_offer:
                await asyncio.sleep(2)
                await send_teaser_and_apex(context.bot, update.effective_chat.id, uid)
            else:
                logger.info(f"🚫 Teaser bloqueado: {uid} - {reason}")

        if streak_updated:
            streak_msg = get_streak_message(streak)
            if streak_msg:
                await asyncio.sleep(1)
                await context.bot.send_message(update.effective_chat.id, streak_msg)

        check_phase_transition(uid)

    except Exception as e:
        logger.exception(f"Erro message_handler: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 👑 ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

import admin_commands

# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 SETUP
# ═══════════════════════════════════════════════════════════════════════════════

def setup_application():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    admin_funcs = {
        'get_redis': lambda: r,
        'get_all_active_users': get_all_active_users,
        'get_current_phase': get_current_phase,
        'saw_teaser': saw_teaser,
        'clicked_vip': clicked_vip,
        'is_in_rejection_cooldown': is_in_rejection_cooldown,
        'get_funnel_stats': get_funnel_stats,
        'reset_daily_count': reset_daily_count,
        'add_bonus_msgs': add_bonus_msgs,
        'get_hours_since_activity': get_hours_since_activity,
        'add_to_blacklist': add_to_blacklist
    }
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("stats", lambda u, c: admin_commands.stats_cmd(u, c, ADMIN_IDS, admin_funcs)))
    application.add_handler(CommandHandler("funnel", lambda u, c: admin_commands.funnel_cmd(u, c, ADMIN_IDS, admin_funcs)))
    application.add_handler(CommandHandler("reset", lambda u, c: admin_commands.reset_cmd(u, c, ADMIN_IDS, admin_funcs)))
    application.add_handler(CommandHandler("resetall", lambda u, c: admin_commands.resetall_cmd(u, c, ADMIN_IDS, admin_funcs)))
    application.add_handler(CommandHandler("givebonus", lambda u, c: admin_commands.givebonus_cmd(u, c, ADMIN_IDS, admin_funcs)))
    application.add_handler(CommandHandler("help", lambda u, c: admin_commands.help_cmd(u, c, ADMIN_IDS)))
    application.add_handler(CommandHandler("broadcast", lambda u, c: admin_commands.broadcast_cmd(u, c, ADMIN_IDS)))
    application.add_handler(CallbackQueryHandler(lambda u, c: admin_commands.broadcast_callback_handler(u, c, ADMIN_IDS, admin_funcs), pattern="^bc_(?!confirm)"))
    application.add_handler(CallbackQueryHandler(lambda u, c: admin_commands.broadcast_confirm_handler(u, c, ADMIN_IDS, admin_funcs, CANAL_VIP_LINK), pattern="^bc_confirm$"))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, message_handler))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND & filters.User(ADMIN_IDS), lambda u, c: admin_commands.broadcast_content_handler(u, c, ADMIN_IDS, admin_funcs)), group=1)
    logger.info("✅ Handlers registrados (v8.3 APEX)")
    return application

# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 FLASK
# ═══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
application = setup_application()

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def start_loop():
    loop.run_forever()

import threading
threading.Thread(target=start_loop, daemon=True).start()

@app.route("/", methods=["GET"])
def health():
    return {"status": "ok", "version": "8.3-apex"}, 200

@app.route("/set-webhook", methods=["GET"])
def set_webhook_route():
    try:
        webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
        async def setup():
            await application.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(1)
            await application.bot.set_webhook(webhook_url)
            await asyncio.sleep(1)
            return await application.bot.get_webhook_info()
        info = asyncio.run_coroutine_threadsafe(setup(), loop).result(timeout=15)
        return {
            "status": "success",
            "webhook_url": info.url,
            "pending_updates": info.pending_update_count,
            "last_error": info.last_error_message
        }, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.route("/webhook-info", methods=["GET"])
def webhook_info_route():
    try:
        async def get_info():
            return await application.bot.get_webhook_info()
        info = asyncio.run_coroutine_threadsafe(get_info(), loop).result(timeout=10)
        return {
            "url": info.url,
            "pending_update_count": info.pending_update_count,
            "last_error_message": info.last_error_message,
        }, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.route("/test-bot", methods=["GET"])
def test_bot():
    try:
        async def test():
            me = await application.bot.get_me()
            return {"id": me.id, "username": me.username}
        result = asyncio.run_coroutine_threadsafe(test(), loop).result(timeout=10)
        return {"status": "ok", "data": result}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

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
# 📊 ADMIN DASHBOARD ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "seu_token_super_secreto_aqui_123")

@app.route("/admin/login", methods=["GET"])
def admin_login_page():
    try:
        with open("admin_login.html", "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    except FileNotFoundError:
        return {"error": "Login page not found"}, 404

@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():
    try:
        with open("admin_panel.html", "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    except FileNotFoundError:
        return {"error": "Admin panel not found"}, 404

@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"error": "Unauthorized"}, 401
    token = auth_header.replace("Bearer ", "")
    if token != ADMIN_TOKEN:
        return {"error": "Invalid token"}, 401

    try:
        users = get_all_active_users()
        total_users = len(users)

        saw_teaser_count = sum(1 for uid in users if saw_teaser(uid))
        clicked_vip_count = sum(1 for uid in users if clicked_vip(uid))
        in_cooldown_count = sum(1 for uid in users if is_in_rejection_cooldown(uid))
        rejected_vip_count = sum(1 for uid in users if r.exists(last_offer_rejected_key(uid)))
        ignored_count = sum(1 for uid in users if get_ignored_count(uid) > 0)

        now = datetime.now()
        active_today = sum(1 for uid in users if get_hours_since_activity(uid) and get_hours_since_activity(uid) < 24)
        active_week = sum(1 for uid in users if get_hours_since_activity(uid) and get_hours_since_activity(uid) < 168)

        new_users_24h = sum(1 for uid in users
                           if r.exists(first_contact_key(uid))
                           and (now - datetime.fromisoformat(r.get(first_contact_key(uid)))).total_seconds() < 86400)

        total_messages = sum(get_conversation_messages_count(uid) for uid in users)
        streaks = [get_streak(uid) for uid in users if get_streak(uid) > 0]
        avg_streak = sum(streaks) / len(streaks) if streaks else 0

        funnel_stages = {i: 0 for i in range(5)}
        for uid in users:
            try:
                stage = int(r.get(funnel_key(uid)) or 0)
                funnel_stages[stage] += 1
            except:
                pass

        activity_labels = []
        activity_messages = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_name = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][day.weekday()]
            activity_labels.append(day_name)
            msgs = 0
            for uid in users:
                try:
                    daily_key = f"daily_msg_sent:{uid}:{day.date()}"
                    msgs += int(r.get(daily_key) or 0)
                except:
                    pass
            activity_messages.append(msgs)

        interest_levels = {"high": 0, "medium": 0, "low": 0}
        for uid in users:
            msgs = get_conversation_messages_count(uid)
            saw = saw_teaser(uid)
            if msgs > 20 and saw:
                interest_levels["high"] += 1
            elif msgs > 10 or saw:
                interest_levels["medium"] += 1
            else:
                interest_levels["low"] += 1

        hourly_labels = [f"{h}h" for h in range(0, 24, 2)]
        hourly_offers = [0] * 12
        for uid in users:
            try:
                saw_time = r.get(saw_teaser_key(uid))
                if saw_time:
                    hour = datetime.fromisoformat(saw_time).hour
                    hourly_offers[hour // 2] += 1
            except:
                pass

        user_data = []
        for uid in users:
            msgs = get_conversation_messages_count(uid)
            if msgs > 0:
                user_data.append({
                    "id": uid,
                    "messages": msgs,
                    "streak": get_streak(uid),
                    "teasers": get_teaser_count(uid),
                    "last_activity_hours": get_hours_since_activity(uid) or 999
                })

        user_data.sort(key=lambda x: x["messages"] * (x["streak"] + 1), reverse=True)

        top_users = []
        for user in user_data[:20]:
            hours = user["last_activity_hours"]
            if hours < 2:
                status, status_text = "hot", "🔥 Quente"
            elif hours < 24:
                status, status_text = "warm", "😊 Morno"
            else:
                status, status_text = "cold", "❄️ Frio"
            if user["messages"] > 20:
                interest, interest_text = "hot", "Alto"
            elif user["messages"] > 10:
                interest, interest_text = "warm", "Médio"
            else:
                interest, interest_text = "cold", "Baixo"
            if hours < 1:
                last_activity = "< 1h atrás"
            elif hours < 24:
                last_activity = f"{int(hours)}h atrás"
            else:
                last_activity = f"{int(hours/24)}d atrás"
            top_users.append({
                "id": user["id"],
                "messages": user["messages"],
                "streak": user["streak"],
                "teasers": user["teasers"],
                "lastActivity": last_activity,
                "status": status,
                "statusText": status_text,
                "interest": interest,
                "interestText": interest_text
            })

        cooldown_users = []
        for uid in users:
            if is_in_rejection_cooldown(uid):
                cooldown_remaining = get_rejection_cooldown_remaining(uid)
                offers_today = get_vip_offers_today(uid)
                total_teasers = get_teaser_count(uid)
                hours = get_hours_since_activity(uid) or 0
                if hours < 1:
                    last_contact = "< 1h atrás"
                elif hours < 24:
                    last_contact = f"{int(hours)}h atrás"
                else:
                    last_contact = f"{int(hours/24)}d atrás"
                cooldown_users.append({
                    "id": uid,
                    "cooldownRemaining": cooldown_remaining,
                    "offersToday": offers_today,
                    "totalTeasers": total_teasers,
                    "lastContact": last_contact
                })

        started = funnel_stages[1]
        first_message = funnel_stages[2]
        saw_teaser_funnel = funnel_stages[3]
        clicked_vip_funnel = funnel_stages[4]

        def calc_drop(from_stage, to_stage):
            if from_stage == 0:
                return 0
            return ((from_stage - to_stage) / from_stage * 100)

        drop_1 = calc_drop(started, first_message)
        drop_2 = calc_drop(first_message, saw_teaser_funnel)
        drop_3 = calc_drop(saw_teaser_funnel, clicked_vip_funnel)

        def get_drop_class(rate):
            if rate > 70: return "hot"
            elif rate > 40: return "warm"
            else: return "cold"

        def get_status(rate):
            if rate > 70: return "🚨 Crítico"
            elif rate > 40: return "⚠️ Alto"
            else: return "✅ Normal"

        dropoff = [
            {
                "name": "Start → 1ª Msg",
                "users": started - first_message,
                "percent": round((first_message / started * 100) if started > 0 else 0, 1),
                "dropRate": f"{drop_1:.1f}",
                "dropClass": get_drop_class(drop_1),
                "status": get_status(drop_1)
            },
            {
                "name": "1ª Msg → Teaser",
                "users": first_message - saw_teaser_funnel,
                "percent": round((saw_teaser_funnel / first_message * 100) if first_message > 0 else 0, 1),
                "dropRate": f"{drop_2:.1f}",
                "dropClass": get_drop_class(drop_2),
                "status": get_status(drop_2)
            },
            {
                "name": "Teaser → Clique VIP",
                "users": saw_teaser_funnel - clicked_vip_funnel,
                "percent": round((clicked_vip_funnel / saw_teaser_funnel * 100) if saw_teaser_funnel > 0 else 0, 1),
                "dropRate": f"{drop_3:.1f}",
                "dropClass": get_drop_class(drop_3),
                "status": get_status(drop_3)
            }
        ]

        return {
            "stats": {
                "totalUsers": total_users,
                "newUsers24h": new_users_24h,
                "activeToday": active_today,
                "activeWeek": active_week,
                "sawTeaser": saw_teaser_count,
                "clickedVip": clicked_vip_count,
                "totalMessages": total_messages,
                "avgStreak": round(avg_streak, 1),
                "inCooldown": in_cooldown_count,
                "rejectedVip": rejected_vip_count,
                "ignored": ignored_count
            },
            "funnel": {
                "started": started,
                "firstMessage": first_message,
                "sawTeaser": saw_teaser_funnel,
                "clickedVip": clicked_vip_funnel
            },
            "activity": {"labels": activity_labels, "messages": activity_messages},
            "interest": interest_levels,
            "hourly": {"labels": hourly_labels, "offers": hourly_offers},
            "topUsers": top_users,
            "cooldownUsers": cooldown_users,
            "dropoff": dropoff
        }, 200

    except Exception as e:
        logger.exception(f"Erro admin stats: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/conversations", methods=["GET"])
def admin_conversations():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"error": "Unauthorized"}, 401
    token = auth_header.replace("Bearer ", "")
    if token != ADMIN_TOKEN:
        return {"error": "Invalid token"}, 401

    try:
        filter_type = request.args.get('filter', 'all')
        users = get_all_active_users()
        conversations = []

        for uid in users:
            hours = get_hours_since_activity(uid)
            if not hours or hours > 24:
                continue
            if filter_type == 'hot' and get_conversation_messages_count(uid) < 10:
                continue
            elif filter_type == 'cooldown' and not is_in_rejection_cooldown(uid):
                continue
            elif filter_type == 'converted' and not clicked_vip(uid):
                continue

            chatlog = r.lrange(chatlog_key(uid), -50, -1)

            if hours < 1:
                last_activity = "< 1 min"
            elif hours < 1/60:
                last_activity = f"{int(hours * 60)} min"
            else:
                last_activity = f"{int(hours)}h"

            if clicked_vip(uid):
                status, status_class = "💎 Comprou VIP", "vip"
            elif is_in_rejection_cooldown(uid):
                status, status_class = "🚫 Cooldown", "cooldown"
            elif get_conversation_messages_count(uid) > 20:
                status, status_class = "🔥 Quente", "hot"
            else:
                status, status_class = "💬 Conversando", "normal"

            conversations.append({
                "userId": uid,
                "messages": chatlog,
                "totalMessages": get_conversation_messages_count(uid),
                "lastActivity": last_activity,
                "status": status,
                "statusClass": status_class,
                "sawTeaser": saw_teaser(uid),
                "teaserCount": get_teaser_count(uid),
                "inCooldown": is_in_rejection_cooldown(uid),
                "clickedVip": clicked_vip(uid)
            })

        conversations.sort(key=lambda x: x['lastActivity'])
        return {"conversations": conversations}, 200

    except Exception as e:
        logger.exception(f"Erro admin conversations: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/user/<int:user_id>", methods=["GET"])
def admin_user_detail(user_id):
    try:
        if not r.sismember(all_users_key(), str(user_id)):
            return {"error": "User not found"}, 404

        chatlog = r.lrange(chatlog_key(user_id), 0, -1)
        profile = get_user_profile(user_id)
        memory = get_memory(user_id)

        return {
            "id": user_id,
            "profile": profile,
            "stats": {
                "messages": get_conversation_messages_count(user_id),
                "streak": get_streak(user_id),
                "teasers": get_teaser_count(user_id),
                "sawTeaser": saw_teaser(user_id),
                "clickedVip": clicked_vip(user_id),
                "inCooldown": is_in_rejection_cooldown(user_id),
                "cooldownRemaining": get_rejection_cooldown_remaining(user_id),
                "vipOffersToday": get_vip_offers_today(user_id),
                "bonusMessages": get_bonus_msgs(user_id),
                "todayCount": today_count(user_id),
                "ignored": get_ignored_count(user_id),
                "lastActivity": r.get(last_activity_key(user_id)),
                "firstContact": r.get(first_contact_key(user_id))
            },
            "chatlog": chatlog,
            "memory": memory
        }, 200

    except Exception as e:
        logger.exception(f"Erro user detail: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/broadcast", methods=["POST"])
def admin_broadcast():
    try:
        data = request.json
        message = data.get("message")
        target_group = data.get("target", "all")

        if not message:
            return {"error": "Message required"}, 400

        users = get_all_active_users()

        if target_group == "active_24h":
            users = [u for u in users if get_hours_since_activity(u) and get_hours_since_activity(u) < 24]
        elif target_group == "saw_teaser":
            users = [u for u in users if saw_teaser(u)]
        elif target_group == "not_converted":
            users = [u for u in users if saw_teaser(u) and not clicked_vip(u)]

        async def send_broadcast():
            sent = 0
            failed = 0
            for uid in users:
                try:
                    await application.bot.send_message(chat_id=uid, text=message)
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception as e:
                    failed += 1
                    logger.error(f"Broadcast failed for {uid}: {e}")
            return sent, failed

        future = asyncio.run_coroutine_threadsafe(send_broadcast(), loop)
        sent, failed = future.result(timeout=300)

        return {"success": True, "sent": sent, "failed": failed, "total": len(users)}, 200

    except Exception as e:
        logger.exception(f"Erro broadcast: {e}")
        return {"error": str(e)}, 500


def require_auth():
    def decorator(f):
        def wrapped(*args, **kwargs):
            auth = request.headers.get("Authorization")
            if not auth or auth != f"Bearer {ADMIN_TOKEN}":
                return {"error": "Unauthorized"}, 401
            return f(*args, **kwargs)
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator

# ═══════════════════════════════════════════════════════════════════════════════
# 🎬 STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

async def startup_sequence():
    try:
        logger.info("🚀 Iniciando Sophia Bot v8.3 APEX...")
        router = init_router(redis_url=REDIS_URL, config_path="ias_config.json")
        logger.info(f"✅ IA Router inicializado")
        await application.initialize()
        await application.start()
        await asyncio.sleep(2)

        webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

        for attempt in range(3):
            try:
                await application.bot.delete_webhook(drop_pending_updates=True)
                await asyncio.sleep(1)
                success = await application.bot.set_webhook(
                    url=webhook_url,
                    allowed_updates=["message", "callback_query"]
                )
                if success:
                    info = await application.bot.get_webhook_info()
                    if info.url == webhook_url:
                        logger.info(f"✅ Webhook configurado: {webhook_url}")
                        break
                if attempt < 2:
                    await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"❌ Tentativa {attempt + 1} falhou: {e}")
                if attempt < 2:
                    await asyncio.sleep(5)
                else:
                    raise

        asyncio.create_task(engagement_scheduler(application.bot))
        logger.info("✅ Scheduler de engagement iniciado")

        asyncio.create_task(retargeting_scheduler(application.bot))
        logger.info("✅ Scheduler de retargeting iniciado")

        asyncio.create_task(recovery_scheduler(application.bot))
        logger.info("✅ Scheduler de recovery iniciado")

        me = await application.bot.get_me()
        logger.info(f"🤖 Bot ativo: @{me.username} (ID: {me.id})")
        logger.info("✨ v8.3 APEX — Funil direto VIP + PIX + Pergunta prévia")

    except Exception as e:
        logger.exception(f"💥 ERRO CRÍTICO: {e}")
        raise

# ═══════════════════════════════════════════════════════════════════════════════
# 🎬 MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    asyncio.run_coroutine_threadsafe(startup_sequence(), loop)

    logger.info(f"🌐 Flask rodando na porta {PORT}")
    logger.info("🚀 Sophia Bot v8.3 APEX operacional!")
    logger.info("📊 Funil: /start → Conversa → Prévia? → Teasers → PIX → VIP")

    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
