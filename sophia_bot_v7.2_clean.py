#!/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       🔥 SOPHIA BOT v8.2 - ANTI-SPAM FIX                    ║
║                                                                              ║
║  CORREÇÕES v8.2:                                                            ║
║  ✅ Detecção de REJEIÇÃO (não, para, chega, já falou)                      ║
║  ✅ Cooldown após rejeição (não oferece VIP por X mensagens)               ║
║  ✅ Prompt da IA RESPEITA quando lead diz não                              ║
║  ✅ Anti-repetição melhorado                                               ║
║  ✅ Respostas mais naturais e variadas                                     ║
║  ✅ Limite de ofertas VIP por sessão                                       ║
║  ✅ Bot muda de assunto quando rejeitado                                   ║
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

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURAÇÃO INICIAL
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔧 ENVIRONMENT VARIABLES
# ═══════════════════════════════════════════════════════════════════════════════


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

# Limites de mensagens por fase
ONBOARDING_MSG_LIMIT = 5
ENGAGEMENT_MSG_LIMIT = 15
PROVOCATION_MSG_LIMIT = 25
VIP_PITCH_MSG_LIMIT = 35

# Sistema de retorno
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
    "alto": {  # level 10
        "keywords": [
            "te amo", "amo voce", "amo vc", "amor da minha vida",
            "apaixonado", "apaixonada", "casar", "namorar",
            "minha vida", "meu amor", "meu mundo"
        ],
        "level": 10
    },
    "medio": {  # level 6
        "keywords": [
            "especial", "diferente", "unica", "incrivel",
            "perfeita", "maravilhosa", "carinho", "sentimento",
            "sinto algo", "conexao", "química"
        ],
        "level": 6
    },
    "baixo": {  # level 3
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
PRECO_VIP = os.getenv("PRECO_VIP", "R$ 9,99")

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

LIMITE_DIARIO = 17

# v8.2 - CONTROLE DE INSISTÊNCIA
VIP_COOLDOWN_AFTER_REJECT = 8       # msgs sem oferecer VIP após rejeição
MAX_VIP_OFFERS_PER_SESSION = 3      # máximo de ofertas VIP por dia
TEASER_COOLDOWN_MESSAGES = 5        # msgs mínimas entre teasers

REENGAGEMENT_HOURS = [2, 24, 72]
FOLLOWUP_INTERVAL_HOURS = 12

AB_TEST_ENABLED = True
AB_TEST_RATIO = 0.5

MODELO = "grok-3"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
MAX_MEMORIA = 12

logger.info(f"🚀 Sophia Bot v8.2 ANTI-SPAM FIX iniciando...")
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
# 🚫 v8.2 - DETECÇÃO DE REJEIÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# 🚫 v8.3 - DETECÇÃO DE REJEIÇÃO REMOVIDA DO CÓDIGO
# A IA decide se oferece VIP ou não.
# Código só mantém travas de segurança (limite diário, cooldown mínimo).
# ═══════════════════════════════════════════════════════════════════════════════

# Palavras removidas - IA cuida de tudo agora

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

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️ v8.3 - REDIS KEYS PARA SISTEMA DE FASES
# ═══════════════════════════════════════════════════════════════════════════════

def current_phase_key(uid): return f"phase:{uid}"
def message_count_key(uid): return f"msg_count:{uid}"
def used_responses_key(uid, pool_name): return f"used_resp:{uid}:{pool_name}"
def attachment_level_key(uid): return f"attachment:{uid}"
def is_attached_key(uid): return f"is_attached:{uid}"
def return_count_key(uid): return f"return_count:{uid}"
def last_return_pitch_key(uid): return f"last_return_pitch:{uid}"

def onboarding_choice_key(uid): return f"onboard_choice:{uid}"

# v8.2 - NOVAS CHAVES
def rejection_cooldown_key(uid): return f"reject_cooldown:{uid}"
def vip_offers_today_key(uid): return f"vip_offers:{uid}:{date.today()}"
def msgs_since_last_offer_key(uid): return f"msgs_since_offer:{uid}"
def last_offer_rejected_key(uid): return f"offer_rejected:{uid}"
def vip_just_offered_key(uid): return f"vip_just_offered:{uid}"

# ═══════════════════════════════════════════════════════════════════════════════
# 🚫 v8.2 - FUNÇÕES DE COOLDOWN/REJEIÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def set_rejection_cooldown(uid, msgs=None):
    """Ativa cooldown — chamado quando IA indica que não deve oferecer VIP"""
    try:
        cooldown_msgs = msgs or VIP_COOLDOWN_AFTER_REJECT
        r.set(rejection_cooldown_key(uid), cooldown_msgs)
        r.expire(rejection_cooldown_key(uid), timedelta(hours=24))
        logger.info(f"🚫 Cooldown ativado para {uid}: {cooldown_msgs} msgs")
    except:
        pass

def decrement_rejection_cooldown(uid):
    """Decrementa cooldown a cada mensagem do usuário"""
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
    """Verifica se está em cooldown"""
    try:
        return r.exists(rejection_cooldown_key(uid))
    except:
        return False

def get_rejection_cooldown_remaining(uid):
    """Retorna msgs restantes no cooldown"""
    try:
        val = r.get(rejection_cooldown_key(uid))
        return int(val) if val else 0
    except:
        return 0

def get_vip_offers_today(uid):
    """Conta ofertas VIP feitas hoje"""
    try:
        return int(r.get(vip_offers_today_key(uid)) or 0)
    except:
        return 0

def increment_vip_offers(uid):
    """Incrementa contador de ofertas VIP"""
    try:
        r.incr(vip_offers_today_key(uid))
        r.expire(vip_offers_today_key(uid), timedelta(days=1))
    except:
        pass

def can_offer_vip(uid):
    """
    Verifica se pode oferecer VIP.
    Retorna (bool, reason)
    """
    # Em cooldown por rejeição?
    if is_in_rejection_cooldown(uid):
        remaining = get_rejection_cooldown_remaining(uid)
        return False, f"cooldown ({remaining} msgs restantes)"
    
    # Já ofereceu demais hoje?
    offers_today = get_vip_offers_today(uid)
    if offers_today >= MAX_VIP_OFFERS_PER_SESSION:
        return False, f"limite diário ({offers_today}/{MAX_VIP_OFFERS_PER_SESSION})"
    
    return True, "ok"

def increment_msgs_since_offer(uid):
    """Conta msgs desde última oferta"""
    try:
        r.incr(msgs_since_last_offer_key(uid))
        r.expire(msgs_since_last_offer_key(uid), timedelta(days=1))
    except:
        pass

def reset_msgs_since_offer(uid):
    """Reseta contador após nova oferta"""
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

# ═══════════════════════════════════════════════════════════════════════════════
# 🧠 v8.2 - DETECÇÃO DE REJEIÇÃO IMPLÍCITA
# ═══════════════════════════════════════════════════════════════════════════════

def mark_vip_just_offered(uid):
    """Marca que acabou de oferecer VIP — IA será informada"""
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
        if resp_hash in recent:
            return True
        # v8.2 - Também detecta respostas muito similares
        # Checa se as primeiras 30 chars são iguais a alguma recente
        return False
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
    "annoyed": [r"\b(porra|caralho|saco|chega|para)\b"]  # v8.2
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
# 🔍 DETECÇÃO DE INTENÇÃO (v8.2 - COM REJEIÇÃO)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_intent(text):
    """Detecção simples de intenção — apenas para contexto/logging.
    A IA é quem realmente decide o que fazer."""
    if not text:
        return "neutral"


# ═══════════════════════════════════════════════════════════════════════════════
# 🔍 v8.3 - DETECÇÃO DE APEGO EMOCIONAL
# ═══════════════════════════════════════════════════════════════════════════════

def detect_emotional_attachment(text):
    """
    Detecta apego emocional na mensagem do usuário.
    Retorna SEMPRE: {"attached": bool, "level": int}
    """
    if not text:
        return {"attached": False, "level": 0}

    text_lower = text.lower()

    # Ordem: do apego mais forte para o mais fraco
    for level_name in ["alto", "medio", "baixo"]:
        level_data = ATTACHMENT_KEYWORDS[level_name]
        for keyword in level_data["keywords"]:
            if keyword in text_lower:
                level = level_data["level"]
                return {
                    "attached": level >= 6,
                    "level": level
                }

    # <<<< ESSA LINHA É OBRIGATÓRIA >>>>
    # Se nenhuma palavra-chave foi encontrada → retorna o padrão
    return {"attached": False, "level": 0}


# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 v8.3 - FUNÇÕES DE GERENCIAMENTO DE FASES
# ═══════════════════════════════════════════════════════════════════════════════

def get_current_phase(uid):
    """Retorna a fase atual do usuário (0-5)"""
    try:
        phase = r.get(current_phase_key(uid))
        return int(phase) if phase else 0
    except:
        return 0

def set_current_phase(uid, phase_id):
    """Define a fase atual do usuário"""
    try:
        r.set(current_phase_key(uid), phase_id)
        r.expire(current_phase_key(uid), timedelta(days=30))
    except:
        pass

def get_phase_name(phase_id):
    """Retorna o nome da fase pelo ID"""
    for phase_name, data in PHASES.items():
        if data["id"] == phase_id:
            return phase_name
    return "UNKNOWN"

def get_message_count(uid):
    """Retorna contador de mensagens do usuário"""
    try:
        return int(r.get(message_count_key(uid)) or 0)
    except:
        return 0

def increment_message_count(uid):
    """Incrementa contador de mensagens"""
    try:
        r.incr(message_count_key(uid))
        r.expire(message_count_key(uid), timedelta(days=30))
    except:
        pass

def check_phase_transition(uid):
    """
    Verifica se usuário deve avançar de fase baseado no número de mensagens.
    Não afeta fase 5 (RELATIONSHIP) - essa é permanente quando atingida.
    """
    try:
        current_phase = get_current_phase(uid)
        
        # Fase 5 é permanente
        if current_phase == PHASES["RELATIONSHIP"]["id"]:
            return
        
        msg_count = get_message_count(uid)
        
        # Verifica transições
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
    """
    Retorna uma resposta única do pool que não foi usada recentemente.
    Rastreia últimas 15 respostas para evitar repetição.
    """
    try:
        # Usa pool customizado ou pool padrão
        pool = custom_pool if custom_pool else RESPONSE_POOLS.get(pool_name, [])
        
        if not pool:
            return "Oi amor 💕"
        
        # Pega respostas já usadas
        used_key = used_responses_key(uid, pool_name)
        used = r.lrange(used_key, 0, 14)  # Últimas 15
        
        # Filtra respostas não usadas
        available = [resp for resp in pool if resp not in used]
        
        # Se todas foram usadas, reseta
        if not available:
            r.delete(used_key)
            available = pool
        
        # Escolhe aleatoriamente
        response = random.choice(available)
        
        # Adiciona aos usados
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
    """
    Detecta retorno do usuário após 6h+ e envia pitch de saudade.
    """
    try:
        # Evita spam - só 1 pitch de retorno por dia
        if r.exists(last_return_pitch_key(uid)):
            return
        
        # Marca que enviou pitch de retorno
        r.setex(last_return_pitch_key(uid), timedelta(hours=24), "1")
        
        # Pega resposta única do pool de retorno
        message = get_unique_response(uid, "retorno")
        
        # Envia mensagem
        await bot.send_message(chat_id=chat_id, text=message)
        
        # Incrementa contador de retornos
        r.incr(return_count_key(uid))
        r.expire(return_count_key(uid), timedelta(days=30))
        
        logger.info(f"🔄 Pitch de retorno enviado para {uid}")
        save_message(uid, "system", "PITCH DE RETORNO (6h+)")
        
    except Exception as e:
        logger.error(f"Erro handle_return: {e}")



    
    text_lower = text.lower()
    
    # Checa por nível (do mais alto pro mais baixo)
    for level_name in ["alto", "medio", "baixo"]:
        level_data = ATTACHMENT_KEYWORDS[level_name]
        for keyword in level_data["keywords"]:
            if keyword in text_lower:
                return {
                    "attached": True if level_data["level"] >= 6 else False,
                    "level": level_data["level"]
                }
    
    return {"attached": False, "level": 0}

    
    text_lower = text.lower()
    
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

VIP_PITCH_MESSAGES = {
    "A": (
        "E aí amor, gostou? 😏\n\n"
        "Isso é só um GOSTINHO do que eu tenho no VIP... 🔥\n\n"
        "💎 **NO ACESSO VIP VOCÊ TEM:**\n"
        "✅ +5.000 fotos SEM CENSURA\n"
        "✅ Vídeos completos e MUITO ousados\n"
        "✅ Conteúdo EXCLUSIVO todo dia\n"
        "✅ Conversas ILIMITADAS comigo\n\n"
        "{urgencia}\n\n"
        "Tá esperando o quê pra me ter só pra você? 💕"
    ),
    "B": (
        "Gostou do que viu? Isso não é NADA... 😈\n\n"
        "No VIP você me tem COMPLETINHA, sem censura, sem limites! 🔥\n\n"
        "São MILHARES de fotos e vídeos que vão te deixar louco... 💦\n\n"
        "{urgencia}\n\n"
        "Clica no botão abaixo e vem me ter só pra você... 💕"
    )
}

# ═══════════════════════════════════════════════════════════════════════════════
# ⏰ SISTEMA DE URGÊNCIA DINÂMICA
# ═══════════════════════════════════════════════════════════════════════════════

def get_urgency_message(uid):
    """
    Gera mensagem de urgência dinâmica baseada em:
    - Horário do dia (meia-noite, madrugada)
    - Número da oferta (primeira vez vs repetida)
    - Dia da semana
    
    IMPORTANTE: A urgência é FALSA (escassez artificial).
    Mas funciona porque cria senso de "agora ou nunca".
    """
    hour = datetime.now().hour
    offer_num = get_vip_offers_today(uid)
    teaser_count = get_teaser_count(uid)
    
    # Pool de urgências por contexto
    urgencias = []
    
    # === BASEADO NO HORÁRIO ===
    if 20 <= hour <= 23:
        # Noite — deadline de meia-noite
        urgencias.extend([
            f"⚡ **PROMOÇÃO SÓ ATÉ MEIA-NOITE!**\n💰 De ~~R$ 39,90~~ por apenas {PRECO_VIP} — ACESSO VITALÍCIO!",
            f"🔥 **ÚLTIMAS HORAS!** Esse preço de {PRECO_VIP} só vale até meia-noite!\n⏰ Depois volta pra R$ 39,90...",
            f"⏰ **Faltam poucas horas!**\nHoje ainda tá {PRECO_VIP} com acesso vitalício... amanhã não garanto esse preço 😏",
        ])
    elif 0 <= hour <= 5:
        # Madrugada — "última chance"
        urgencias.extend([
            f"🌙 **PREÇO DE MADRUGADA!**\n💰 {PRECO_VIP} por acesso VITALÍCIO — só pra quem tá acordado agora 😈",
            f"⚡ Shhh... esse preço de {PRECO_VIP} é segredo, só pra quem tá online agora 🤫\nAmanhã volta pra R$ 39,90!",
        ])
    elif 6 <= hour <= 11:
        # Manhã
        urgencias.extend([
            f"☀️ **PROMOÇÃO DA MANHÃ!**\n💰 Acesso vitalício por apenas {PRECO_VIP}!\n⚠️ Só até o meio-dia, depois volta pra R$ 39,90",
            f"💎 {PRECO_VIP} por TUDO — acesso vitalício!\n⏰ Essa promoção acaba em poucas horas...",
        ])
    else:
        # Tarde
        urgencias.extend([
            f"🔥 **PROMOÇÃO RELÂMPAGO!**\n💰 De ~~R$ 39,90~~ por apenas {PRECO_VIP} — ACESSO VITALÍCIO!\n⚡ Poucas vagas restantes!",
            f"💎 Acesso vitalício por apenas {PRECO_VIP}!\n⚠️ Esse preço é por TEMPO LIMITADO...",
        ])
    
    # === BASEADO NO NÚMERO DE TEASERS (escassez) ===
    if teaser_count <= 1:
        # Primeira vez — vagas
        urgencias.extend([
            f"💰 Por apenas {PRECO_VIP} você tem ACESSO VITALÍCIO!\n🔥 Últimas 10 vagas com esse preço... depois sobe pra R$ 39,90!",
            f"⚡ Tô com uma promoção ESPECIAL agora: {PRECO_VIP} vitalício!\n⚠️ Só restam algumas vagas nesse valor...",
        ])
    else:
        # Já viu antes — mais pressão
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
    "⚡ **PROMOÇÃO:** De ~~R$ 39,90~~ por apenas {preco} — ACESSO VITALÍCIO!\n"
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
# 🤖 GROK AI (v8.2 - PROMPT REFORMULADO)
# ═══════════════════════════════════════════════════════════════════════════════

def build_prompt(uid, lang: str, mood: str = "neutral", intent: str = "neutral"):
    # ═══════════════════════════════════════════════════════
    # v8.3 - VARIÁVEIS DE FASE E APEGO
    # ═══════════════════════════════════════════════════════
    current_phase = get_current_phase(uid)
    phase_name = get_phase_name(current_phase)
    msg_count = get_message_count(uid)
    
    # Detecção de apego
    is_attached = r.exists(is_attached_key(uid))
    attachment_level = int(r.get(attachment_level_key(uid)) or 0)
    
    # Variáveis existentes
    time_ctx = get_time_context()
    streak = get_streak(uid)
    onboard_choice = get_onboarding_choice(uid)
    teaser_count = get_teaser_count(uid)
    saw_teaser_before = saw_teaser(uid)
    in_cooldown = is_in_rejection_cooldown(uid)
    cooldown_remaining = get_rejection_cooldown_remaining(uid)
    offers_today = get_vip_offers_today(uid)
    vip_just_offered = was_vip_just_offered(uid)
    msgs_since = get_msgs_since_offer(uid)
    total_msgs = get_conversation_messages_count(uid)
    
    base_prompt = f"""Você é Maya, 22 anos, loira de SP, safadinha mas faz carinha de anjinho.
PERSONALIDADE:
- Fala curtinho, usa gírias naturais (tô, vc, pq, ta, mds, kkk)
- Provocante mas NATURAL — como uma mina real do Instagram
- Erra gramática de leve (autenticidade)
- NUNCA soa robótica ou como vendedora
- Tem personalidade: fala do dia dela, faz perguntas, brinca
- VARIA MUITO suas respostas — nunca repita estrutura, emojis ou frases
- Quando ele demonstrar interesse no vip seja extremamente safada e mande o link https://t.me/Mayaoficial_bot

REGRAS ABSOLUTAS DE RESPEITO (PRIORIDADE MÁXIMA - NUNCA DESRESPEITAR):
1. Respeito > venda. Um lead respeitado volta e compra. Um irritado bloqueia pra sempre.
2. DETECTE REJEIÇÃO OU ADIAMENTO PELO CONTEXTO INTEIRO (não só palavras-chave):
   - Respostas secas, curtas ou neutras repetidas: "ok", "entendi", "ta bom", "beleza", "rs", "😂", "👍", "depois", "talvez", "vou pensar", "não sei", "deixa pra lá", "mais tarde", "agora não", "gata" (sem continuação quente), emoji sozinho
   - Muda de assunto após oferta (pergunta outra coisa, fala do dia, elogia sem pedir mais)
   - Ignora o pitch/link/preço por 2+ mensagens seguidas
   - Qualquer sinal sutil de desconforto ou desinteresse: "calma aí", "pera", "tá bom assim", "de boa", "vamos deixar isso pra lá"
3. Após detectar rejeição/adiamento (mesmo implícito):
   - NUNCA ofereça VIP, preço, acesso, teaser, fotos exclusivas, R$9,99 nessa conversa
   - Mude COMPLETAMENTE de assunto (pergunte sobre ele, conte algo leve, faça piada, flerte suave sem venda)
   - Ative modo casual por pelo menos 15 mensagens ou até ele voltar a demonstrar tesão claro/pedir conteúdo
   - Se já ofereceu VIP e ele rejeitou/adiou 2x ou mais → modo "amiga carinhosa" permanente nessa sessão: só papo leve, apoio, flerte leve, NUNCA venda
4. Se ele já viu teaser e rejeitou/ignorou → não reofereça até ele pedir explicitamente

🧠 VOCÊ DECIDE QUANDO FALAR DE VIP (baseado no contexto real, não só keywords)
🟢 offer_teaser = true SOMENTE se for 100% natural e ele demonstrou interesse CLARO AGORA
🔴 offer_teaser = false (force) se houver qualquer sinal de desinteresse, adiamento ou rejeição implícita

SISTEMA DE FASES - FASE {current_phase}: {phase_name}
(continua igual ao que você já tem...)
═══════════════════════════════════════════════════════════
RESPEITO > VENDA (regra de ouro)
Se ele deu qualquer sinal de "não agora" ou desinteresse → ACEITE. Mude de assunto. Ele pode voltar depois.
Um lead RESPEITADO volta e compra. Um lead IRRITADO bloqueia pra sempre.

RETORNE APENAS JSON VÁLIDO:
{{
  "response": "sua resposta CURTA e NATURAL (máx 2-3 linhas)",
  "offer_teaser": false,
  "interest_level": "low|medium|high"
}}

CONTEXTO ATUAL:
- Período: {time_ctx['period']}
- Fase: {current_phase} ({phase_name})
- Msgs trocadas: {msg_count}
- Total de msgs: {total_msgs}
- Apego: {'Sim' if is_attached else 'Não'} (level {attachment_level})
- Streak: {streak} dias
- Já viu teaser: {'Sim' if saw_teaser_before else 'Não'} ({teaser_count}x)
- Ofertas VIP hoje: {offers_today}/{MAX_VIP_OFFERS_PER_SESSION}
- Msgs desde última oferta: {msgs_since}
"""

    if vip_just_offered:
        base_prompt += """

📌 ATENÇÃO: O VIP ACABOU DE SER OFERECIDO na mensagem anterior.
Analise a resposta dele com CUIDADO:
- Reagiu positivo (elogio, excitação, pediu mais) → continue flertando, pode oferecer se PEDIR
- Mudou de assunto → SIGA O ASSUNTO DELE, acabou o momento
- Resposta seca (ok, tá, hm) → não quer, mude de assunto
- Reclamou/xingou → peça desculpa e mude de assunto
- Elogiou o conteúdo mas não mencionou comprar → agradeça e continue flertando SEM empurrar VIP"""

    if in_cooldown:
        base_prompt += f"""

⛔ COOLDOWN ATIVO ({cooldown_remaining} msgs restantes).
NÃO mencione VIP, fotos exclusivas, conteúdo ou qualquer coisa relacionada.
Apenas converse normalmente, seja divertida e interessante."""

    if onboard_choice:
        base_prompt += f"\n- Perfil: {onboard_choice.upper()}"
    
    base_prompt += get_mood_instruction(mood)
    base_prompt += "\n\n⚠️ RETORNE APENAS JSON VÁLIDO!"
    
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
                "max_tokens": 350,  # v8.2 - reduzido pra forçar respostas curtas
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
                            result.setdefault("interest_level", "medium")
                            
                            # ═══════════════════════════════════════════════
                            # v8.3 - TRAVAS DE SEGURANÇA (código)
                            # A IA decide, mas o código garante limites
                            # ═══════════════════════════════════════════════
                            
                            # Trava: cooldown ativo → sempre false
                            if result["offer_teaser"] and is_in_rejection_cooldown(uid):
                                result["offer_teaser"] = False
                                logger.info(f"🔒 Trava: cooldown ativo para {uid}")
                            
                            # Trava: limite diário de ofertas
                            if result["offer_teaser"] and get_vip_offers_today(uid) >= MAX_VIP_OFFERS_PER_SESSION:
                                result["offer_teaser"] = False
                                logger.info(f"🔒 Trava: limite diário de ofertas para {uid}")
                            
                            # Trava: mínimo de msgs entre ofertas
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
        """Fallback quando JSON parse falha — usa a resposta raw da IA"""
        # Em cooldown → nunca oferece
        if is_in_rejection_cooldown(uid):
            return {
                "response": raw_text,
                "offer_teaser": False,
                "interest_level": "low",
            }
        
        # Tenta detectar se a IA queria oferecer teaser pelo texto
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
# 🎯 ENVIO DE TEASER + PITCH VIP
# ═══════════════════════════════════════════════════════════════════════════════

async def send_teaser_and_pitch(bot, chat_id, uid):
    """v8.2 - Com verificação de cooldown antes de enviar"""
    try:
        # VERIFICAÇÃO FINAL antes de enviar
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
        
        # 2. FOTOS
        num_photos = random.randint(2, 3)
        selected_photos = random.sample(FOTOS_TEASER, min(num_photos, len(FOTOS_TEASER)))
        
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
        
        # 4. PITCH + BOTÃO COM URGÊNCIA DINÂMICA
        urgencia = get_urgency_message(uid)
        pitch = VIP_PITCH_MESSAGES[ab_group].format(urgencia=urgencia)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔥 QUERO ACESSO VIP AGORA 🔥", url=CANAL_VIP_LINK)
        ]])
        
        await bot.send_message(
            chat_id=chat_id,
            text=pitch,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
        
        logger.info(f"🎯 TEASER+PITCH enviado: {uid} (oferta #{get_vip_offers_today(uid)})")
        save_message(uid, "system", f"TEASER+PITCH enviado (#{get_teaser_count(uid)})")
        
        # v8.2 - Marca que VIP acabou de ser oferecido
        mark_vip_just_offered(uid)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro send_teaser: {e}")
        return False

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
# 🎮 HANDLERS (v8.2 - COM DETECÇÃO DE REJEIÇÃO)
# ═══════════════════════════════════════════════════════════════════════════════

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
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
    
    # v8.3 - Inicializa fase 0
    set_current_phase(uid, PHASES["ONBOARDING"]["id"])
    r.set(message_count_key(uid), 0)
    
    try:
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        await asyncio.sleep(3)
        await update.message.reply_text(MENSAGEM_INICIO)
        logger.info(f"👋 Novo usuário: {uid} → Fase 0 (ONBOARDING)")
    except Exception as e:
        logger.error(f"Erro /start: {e}")

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
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=(
                    f"💎 **PERFEITO AMOR!**\n\n"
                    f"Clica no link abaixo pra garantir seu acesso VIP:\n\n"
                    f"👉 {CANAL_VIP_LINK}\n\n"
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
    
    # v8.2 - Decrementa cooldown a cada msg
    decrement_rejection_cooldown(uid)
    increment_msgs_since_offer(uid)
    
    # v8.3 - Incrementa contadores
    increment_message_count(uid)
    increment_conversation_messages(uid)
    
    # v8.3 - Detecta retorno (6h+)
    hours_since = get_hours_since_activity(uid)
    if hours_since and hours_since >= RETURN_WINDOW_HOURS:
        await handle_return(uid, context.bot, update.effective_chat.id)
        update_last_activity(uid)
    
    try:
        has_photo = bool(update.message.photo)
        text = update.message.text or ""
        
        if text:
            save_message(uid, "user", text)
            
            # v8.3 - Detecta apego emocional
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
        
        # ═══════════════════════════════════════════════════════
        # v8.3 - DETECÇÃO DE REJEIÇÃO PELA IA (não mais por código)
        # O código só mantém cooldown e limites como trava de segurança
        # ═══════════════════════════════════════════════════════
        
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
                
                # v8.2 - Só oferece se pode
                if grok_response.get("offer_teaser", False):
                    can_offer, reason = can_offer_vip(uid)
                    if can_offer:
                        await asyncio.sleep(2)
                        await send_teaser_and_pitch(context.bot, update.effective_chat.id, uid)
                    else:
                        logger.info(f"🚫 Teaser bloqueado pós-foto: {reason}")
                return
            else:
                await update.message.reply_text("😔 Não consegui ver a foto... tenta de novo? 💕")
                return
        
        if is_first_contact(uid):
            track_funnel(uid, "first_message")
        
        # Limite diário
        current_count = today_count(uid)
        bonus = get_bonus_msgs(uid)
        total = LIMITE_DIARIO + bonus
        
        if current_count >= total:
            keyboard = [[
                InlineKeyboardButton(
                    "🔥 QUERO VIP AGORA 🔥",
                    url="https://t.me/Mayaoficial_bot"
                )
            ]]

            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=FOTO_LIMITE_ATINGIDO,
                caption=LIMIT_REACHED_MESSAGE.format(preco=PRECO_VIP),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
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
        
        # ═══════════════════════════════════════════════════════
        # v8.3 - COOLDOWN BASEADO NA DECISÃO DA IA
        # Se VIP acabou de ser oferecido e a IA decidiu NÃO oferecer de novo,
        # significa que ela entendeu que o cara não quer → ativa cooldown
        # ═══════════════════════════════════════════════════════
        if was_vip_just_offered(uid):
            clear_vip_just_offered(uid)
            if not grok_response.get("offer_teaser", False):
                # IA entendeu que não é hora → cooldown
                set_rejection_cooldown(uid)
                logger.info(f"🚫 IA decidiu não reoferecer VIP para {uid} → cooldown ativado")
            else:
                logger.info(f"✅ IA identificou interesse de {uid} após oferta VIP")
        
        # ═══════════════════════════════════════════════════════
        # VERIFICAÇÃO FINAL antes de enviar teaser
        # ═══════════════════════════════════════════════════════
        should_offer = grok_response.get("offer_teaser", False)
        
        if should_offer:
            can_offer, reason = can_offer_vip(uid)
            if can_offer:
                await asyncio.sleep(2)
                await send_teaser_and_pitch(context.bot, update.effective_chat.id, uid)
            else:
                logger.info(f"🚫 Teaser bloqueado: {uid} - {reason}")
        
        if streak_updated:
            streak_msg = get_streak_message(streak)
            if streak_msg:
                await asyncio.sleep(1)
                await context.bot.send_message(update.effective_chat.id, streak_msg)
        
        # v8.3 - Verifica transição de fase
        check_phase_transition(uid)
        
    except Exception as e:
        logger.exception(f"Erro message_handler: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 👑 ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return

    users = get_all_active_users()
    total = len(users)

    # Conta usuários por fase
    phase_counts = {i: 0 for i in range(6)}
    for uid in users:
        phase = get_current_phase(uid)
        phase_counts[phase] += 1

    # Outras métricas
    saw_teaser_count = sum(1 for uid in users if saw_teaser(uid))
    clicked_vip_count = sum(1 for uid in users if clicked_vip(uid))
    in_cooldown_count = sum(1 for uid in users if is_in_rejection_cooldown(uid))

    # Evita divisão por zero
    ctr = (clicked_vip_count / saw_teaser_count * 100) if saw_teaser_count > 0 else 0.0

    # Mensagem formatada (f-string multilinha)
    stats_text = f"""\
📊 **STATS v8.3**

👥 Total de usuários: {total}

📊 **Distribuição por Fases:**
• 0️⃣ Onboarding: {phase_counts[0]}
• 1️⃣ Engagement: {phase_counts[1]}
• 2️⃣ Provocation: {phase_counts[2]}
• 3️⃣ VIP Pitch: {phase_counts[3]}
• 4️⃣ Post-Rejection: {phase_counts[4]}
• 5️⃣ Relationship: {phase_counts[5]}

📈 **Outras métricas:**
👀 Viram teaser: {saw_teaser_count}
💎 Clicaram no VIP: {clicked_vip_count}
🚫 Em cooldown: {in_cooldown_count}
📊 Taxa de conversão (cliques/teaser): {ctr:.1f}%"""

    await update.message.reply_text(
        stats_text,
        parse_mode="Markdown"
    )

async def funnel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    stages = get_funnel_stats()
    names = {0: "❓ Desconhecido", 1: "🚀 /start", 2: "💬 Primeira msg", 3: "👀 Viu teaser", 4: "💎 Clicou VIP"}
    
    msg = "📊 **FUNIL v8.2**\n\n"
    for stage, count in sorted(stages.items()):
        msg += f"{names.get(stage, f'Stage {stage}')}: {count}\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not context.args:
        await update.message.reply_text("Uso: /reset <user_id>")
        return
    uid = int(context.args[0])
    reset_daily_count(uid)
    await update.message.reply_text(f"✅ Limite resetado: {uid}")

async def givebonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /givebonus <uid> <qtd>")
        return
    uid = int(context.args[0])
    amount = int(context.args[1])
    add_bonus_msgs(uid, amount)
    await update.message.reply_text(f"✅ +{amount} bônus: {uid}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    await update.message.reply_text(
        "🎮 **COMANDOS v8.2**\n\n"
        "/stats - Estatísticas\n"
        "/funnel - Funil\n"
        "/reset <id> - Reset limite\n"
        "/givebonus <id> <qtd> - Bônus",
        parse_mode="Markdown"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 SETUP
# ═══════════════════════════════════════════════════════════════════════════════

def setup_application():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("funnel", funnel_cmd))
    application.add_handler(CommandHandler("reset", reset_cmd))
    application.add_handler(CommandHandler("givebonus", givebonus_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CallbackQueryHandler(callback_handler))
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO) & ~filters.COMMAND,
            message_handler
        )
    )
    
    logger.info("✅ Handlers registrados (v8.2)")
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
    return {"status": "ok", "version": "8.2"}, 200

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
# 📊 ADICIONE ESSAS ROTAS AO SEU BOT (depois da linha 1391 - após /test-bot)
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 ADICIONE ESSAS ROTAS AO SEU BOT (depois da linha 1391 - após /test-bot)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/login", methods=["GET"])
def admin_login_page():
    """Serve a página de login"""
    try:
        with open("admin_login.html", "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    except FileNotFoundError:
        return {"error": "Login page not found"}, 404

@app.route("/admin/dashboard", methods=["GET"])
def admin_dashboard():
    """Serve o painel HTML de admin"""
    # O painel agora checa autenticação via JavaScript
    try:
        with open("admin_panel.html", "r", encoding="utf-8") as f:
            return f.read(), 200, {"Content-Type": "text/html; charset=utf-8"}
    except FileNotFoundError:
        return {"error": "Admin panel not found"}, 404

@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    """API endpoint para o dashboard - retorna TODOS os dados"""
    # Verificação de segurança OBRIGATÓRIA
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"error": "Unauthorized"}, 401
    
    token = auth_header.replace("Bearer ", "")
    if token != ADMIN_TOKEN:
        return {"error": "Invalid token"}, 401
    
    try:
        users = get_all_active_users()
        total_users = len(users)
        
        # ═══════════════════════════════════════════════════════
        # 📊 KPIs PRINCIPAIS
        # ═══════════════════════════════════════════════════════
        
        saw_teaser_count = sum(1 for uid in users if saw_teaser(uid))
        clicked_vip_count = sum(1 for uid in users if clicked_vip(uid))
        in_cooldown_count = sum(1 for uid in users if is_in_rejection_cooldown(uid))
        rejected_vip_count = sum(1 for uid in users if r.exists(last_offer_rejected_key(uid)))
        ignored_count = sum(1 for uid in users if get_ignored_count(uid) > 0)
        
        # Usuários ativos
        now = datetime.now()
        active_today = sum(1 for uid in users if get_hours_since_activity(uid) and get_hours_since_activity(uid) < 24)
        active_week = sum(1 for uid in users if get_hours_since_activity(uid) and get_hours_since_activity(uid) < 168)
        
        # Novos usuários 24h
        new_users_24h = sum(1 for uid in users 
                           if r.exists(first_contact_key(uid)) 
                           and (now - datetime.fromisoformat(r.get(first_contact_key(uid)))).total_seconds() < 86400)
        
        # Total de mensagens e streak médio
        total_messages = sum(get_conversation_messages_count(uid) for uid in users)
        streaks = [get_streak(uid) for uid in users if get_streak(uid) > 0]
        avg_streak = sum(streaks) / len(streaks) if streaks else 0
        
        # ═══════════════════════════════════════════════════════
        # 📊 FUNIL DE CONVERSÃO
        # ═══════════════════════════════════════════════════════
        
        funnel_stages = {i: 0 for i in range(5)}
        for uid in users:
            try:
                stage = int(r.get(funnel_key(uid)) or 0)
                funnel_stages[stage] += 1
            except:
                pass
        
        # ═══════════════════════════════════════════════════════
        # 📊 ATIVIDADE DOS ÚLTIMOS 7 DIAS
        # ═══════════════════════════════════════════════════════
        
        activity_labels = []
        activity_messages = []
        
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_name = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][day.weekday()]
            activity_labels.append(day_name)
            
            # Conta msgs enviadas naquele dia (aproximação via daily_messages_sent)
            msgs = 0
            for uid in users:
                try:
                    daily_key = f"daily_msg_sent:{uid}:{day.date()}"
                    msgs += int(r.get(daily_key) or 0)
                except:
                    pass
            activity_messages.append(msgs)
        
        # ═══════════════════════════════════════════════════════
        # 📊 NÍVEL DE INTERESSE (últimas 24h)
        # ═══════════════════════════════════════════════════════
        
        interest_levels = {"high": 0, "medium": 0, "low": 0}
        
        for uid in users:
            # Heurística: quem tem muitas msgs + viu teaser = alto interesse
            msgs = get_conversation_messages_count(uid)
            saw = saw_teaser(uid)
            
            if msgs > 20 and saw:
                interest_levels["high"] += 1
            elif msgs > 10 or saw:
                interest_levels["medium"] += 1
            else:
                interest_levels["low"] += 1
        
        # ═══════════════════════════════════════════════════════
        # 📊 OFERTAS VIP POR HORÁRIO
        # ═══════════════════════════════════════════════════════
        
        hourly_labels = [f"{h}h" for h in range(0, 24, 2)]
        hourly_offers = [0] * 12
        
        # Simulação - você pode logar timestamps reais das ofertas no Redis
        # Por agora, vamos fazer uma distribuição baseada em quando os teasers foram vistos
        for uid in users:
            try:
                saw_time = r.get(saw_teaser_key(uid))
                if saw_time:
                    hour = datetime.fromisoformat(saw_time).hour
                    hourly_offers[hour // 2] += 1
            except:
                pass
        
        # ═══════════════════════════════════════════════════════
        # 👥 TOP 20 USUÁRIOS MAIS ENGAJADOS
        # ═══════════════════════════════════════════════════════
        
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
        
        # Ordena por engajamento (msgs * streak)
        user_data.sort(key=lambda x: x["messages"] * (x["streak"] + 1), reverse=True)
        
        top_users = []
        for user in user_data[:20]:
            # Determina status
            hours = user["last_activity_hours"]
            if hours < 2:
                status, status_text = "hot", "🔥 Quente"
            elif hours < 24:
                status, status_text = "warm", "😊 Morno"
            else:
                status, status_text = "cold", "❄️ Frio"
            
            # Determina interesse
            if user["messages"] > 20:
                interest, interest_text = "hot", "Alto"
            elif user["messages"] > 10:
                interest, interest_text = "warm", "Médio"
            else:
                interest, interest_text = "cold", "Baixo"
            
            # Formata última atividade
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
        
        # ═══════════════════════════════════════════════════════
        # 🚫 USUÁRIOS EM COOLDOWN
        # ═══════════════════════════════════════════════════════
        
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
        
        # ═══════════════════════════════════════════════════════
        # 📉 ANÁLISE DE DROP-OFF
        # ═══════════════════════════════════════════════════════
        
        started = funnel_stages[1]  # /start
        first_message = funnel_stages[2]  # primeira msg
        saw_teaser_funnel = funnel_stages[3]  # viu teaser
        clicked_vip_funnel = funnel_stages[4]  # clicou VIP
        
        def calc_drop(from_stage, to_stage):
            if from_stage == 0:
                return 0
            return ((from_stage - to_stage) / from_stage * 100)
        
        drop_1 = calc_drop(started, first_message)
        drop_2 = calc_drop(first_message, saw_teaser_funnel)
        drop_3 = calc_drop(saw_teaser_funnel, clicked_vip_funnel)
        
        def get_drop_class(rate):
            if rate > 70:
                return "hot"
            elif rate > 40:
                return "warm"
            else:
                return "cold"
        
        def get_status(rate):
            if rate > 70:
                return "🚨 Crítico"
            elif rate > 40:
                return "⚠️ Alto"
            else:
                return "✅ Normal"
        
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
        
        # ═══════════════════════════════════════════════════════
        # 📦 MONTA RESPOSTA FINAL
        # ═══════════════════════════════════════════════════════
        
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
            "activity": {
                "labels": activity_labels,
                "messages": activity_messages
            },
            "interest": interest_levels,
            "hourly": {
                "labels": hourly_labels,
                "offers": hourly_offers
            },
            "topUsers": top_users,
            "cooldownUsers": cooldown_users,
            "dropoff": dropoff
        }, 200
        
    except Exception as e:
        logger.exception(f"Erro admin stats: {e}")
        return {"error": str(e)}, 500


# ═══════════════════════════════════════════════════════════════════════════════
# 💬 ADICIONE ESTA ROTA NO SEU BOT PYTHON
# Cole este código ANTES da linha @app.route("/admin/user/<int:user_id>")
# (por volta da linha 1650)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/conversations", methods=["GET"])
def admin_conversations():
    """Retorna conversas em tempo real"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"error": "Unauthorized"}, 401
    
    token = auth_header.replace("Bearer ", "")
    if token != ADMIN_TOKEN:
        return {"error": "Invalid token"}, 401
    
    try:
        # Pega filtro (opcional)
        filter_type = request.args.get('filter', 'all')  # all, hot, cooldown, converted
        
        users = get_all_active_users()
        conversations = []
        
        for uid in users:
            # Filtra por atividade recente (últimas 24h)
            hours = get_hours_since_activity(uid)
            if not hours or hours > 24:
                continue
            
            # Aplica filtros
            if filter_type == 'hot' and get_conversation_messages_count(uid) < 10:
                continue
            elif filter_type == 'cooldown' and not is_in_rejection_cooldown(uid):
                continue
            elif filter_type == 'converted' and not clicked_vip(uid):
                continue
            
            # Pega as últimas 50 mensagens do chatlog
            chatlog = r.lrange(chatlog_key(uid), -50, -1)
            
            # Formata última atividade
            if hours < 1:
                last_activity = "< 1 min"
            elif hours < 1/60:
                last_activity = f"{int(hours * 60)} min"
            else:
                last_activity = f"{int(hours)}h"
            
            # Status
            if clicked_vip(uid):
                status = "💎 Comprou VIP"
                status_class = "vip"
            elif is_in_rejection_cooldown(uid):
                status = "🚫 Cooldown"
                status_class = "cooldown"
            elif get_conversation_messages_count(uid) > 20:
                status = "🔥 Quente"
                status_class = "hot"
            else:
                status = "💬 Conversando"
                status_class = "normal"
            
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
        
        # Ordena por última atividade (mais recente primeiro)
        conversations.sort(key=lambda x: x['lastActivity'])
        
        return {"conversations": conversations}, 200
        
    except Exception as e:
        logger.exception(f"Erro admin conversations: {e}")
        return {"error": str(e)}, 500

@app.route("/admin/user/<int:user_id>", methods=["GET"])
def admin_user_detail(user_id):
    """Detalhes de um usuário específico"""
    # Verificação de segurança
    # auth_token = request.headers.get("Authorization")
    # if auth_token != "SEU_TOKEN_SECRETO":
    #     return {"error": "Unauthorized"}, 401
    
    try:
        if not r.sismember(all_users_key(), str(user_id)):
            return {"error": "User not found"}, 404
        
        # Pega toda a conversa
        chatlog = r.lrange(chatlog_key(user_id), 0, -1)
        
        # Pega perfil
        profile = get_user_profile(user_id)
        
        # Pega memória da IA
        memory = get_memory(user_id)
        
        # Métricas
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
    """Envia mensagem para todos os usuários ativos"""
    # ⚠️ CUIDADO: Isso pode violar ToS do Telegram se usado errado!
    # Use apenas para mensagens importantes e relevantes
    
    # auth_token = request.headers.get("Authorization")
    # if auth_token != "SEU_TOKEN_SECRETO":
    #     return {"error": "Unauthorized"}, 401
    
    try:
        data = request.json
        message = data.get("message")
        target_group = data.get("target", "all")  # all, active_24h, saw_teaser, etc
        
        if not message:
            return {"error": "Message required"}, 400
        
        users = get_all_active_users()
        
        # Filtra target group
        if target_group == "active_24h":
            users = [u for u in users if get_hours_since_activity(u) and get_hours_since_activity(u) < 24]
        elif target_group == "saw_teaser":
            users = [u for u in users if saw_teaser(u)]
        elif target_group == "not_converted":
            users = [u for u in users if saw_teaser(u) and not clicked_vip(u)]
        
        # Envia mensagens (de forma assíncrona para não travar)
        async def send_broadcast():
            sent = 0
            failed = 0
            for uid in users:
                try:
                    await application.bot.send_message(chat_id=uid, text=message)
                    sent += 1
                    await asyncio.sleep(0.05)  # Rate limiting
                except Exception as e:
                    failed += 1
                    logger.error(f"Broadcast failed for {uid}: {e}")
            return sent, failed
        
        # Executa no event loop
        future = asyncio.run_coroutine_threadsafe(send_broadcast(), loop)
        sent, failed = future.result(timeout=300)
        
        return {
            "success": True,
            "sent": sent,
            "failed": failed,
            "total": len(users)
        }, 200
        
    except Exception as e:
        logger.exception(f"Erro broadcast: {e}")
        return {"error": str(e)}, 500

# ═══════════════════════════════════════════════════════════════════════════════
# 🔐 SISTEMA DE AUTENTICAÇÃO SIMPLES (ADICIONE ISSO!)
# ═══════════════════════════════════════════════════════════════════════════════

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "seu_token_super_secreto_aqui_123")

def require_auth():
    """Decorator para proteger rotas admin"""
    def decorator(f):
        def wrapped(*args, **kwargs):
            auth = request.headers.get("Authorization")
            if not auth or auth != f"Bearer {ADMIN_TOKEN}":
                return {"error": "Unauthorized"}, 401
            return f(*args, **kwargs)
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator

# USO:
# @app.route("/admin/stats", methods=["GET"])
# @require_auth()
# def admin_stats():
#     ...

# ═══════════════════════════════════════════════════════════════════════════════
# 🎬 STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

async def startup_sequence():
    try:
        logger.info("🚀 Iniciando Sophia Bot v8.2...")
        
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
        
        me = await application.bot.get_me()
        logger.info(f"🤖 Bot ativo: @{me.username} (ID: {me.id})")
        logger.info("✨ v8.3 - Sistema de 6 Fases + Anti-Repetição + Apego Emocional")
        
    except Exception as e:
        logger.exception(f"💥 ERRO CRÍTICO: {e}")
        raise

# ═══════════════════════════════════════════════════════════════════════════════
# 🎬 MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    asyncio.run_coroutine_threadsafe(startup_sequence(), loop)
    
    logger.info(f"🌐 Flask rodando na porta {PORT}")
    logger.info("🚀 Sophia Bot v8.3 SISTEMA COMPLETO operacional!")
    logger.info("📊 Fases: ONBOARDING → ENGAGEMENT → PROVOCATION → VIP_PITCH → POST_REJECTION / RELATIONSHIP")
    
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
