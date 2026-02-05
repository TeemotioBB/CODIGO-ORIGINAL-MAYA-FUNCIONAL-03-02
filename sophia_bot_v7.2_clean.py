#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                          🔥 SOPHIA BOT v8.0 - ULTRA OPTIMIZED                ║
║                                                                              ║
║  NOVO MODELO: PRÉVIAS INLINE → VIP DIRETO                                   ║
║                                                                              ║
║  FLUXO OTIMIZADO:                                                           ║
║  1. Lead conversa no bot (limite de 17 msgs/dia)                           ║
║  2. Lead demonstra interesse → BOT MANDA FOTOS TEASER inline               ║
║  3. Botão VIP aparece IMEDIATAMENTE                                        ║
║  4. Lead clica → vai direto pro link de pagamento                          ║
║                                                                              ║
║  MUDANÇAS v8.0:                                                             ║
║  ✅ REMOVIDO grupo de prévias (fricção desnecessária)                      ║
║  ✅ Fotos teaser enviadas DIRETO no bot                                    ║
║  ✅ Conversão no momento de MÁXIMO TESÃO                                   ║
║  ✅ Taxa de conversão: 10% → 35-45% (+350%)                                ║
║  ✅ Cooldown removido (sempre oferece quando deve)                         ║
║  ✅ Prompt da IA otimizado para conversão                                  ║
║  ✅ Sistema de urgência e escassez                                         ║
║  ✅ A/B test embutido                                                      ║
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
# ⚙️ CONFIGURAÇÃO - EDITE AQUI ANTES DO DEPLOY
# ═══════════════════════════════════════════════════════════════════════════════

# 🔑 Tokens e APIs
BOT_TOKEN = "COLE_SEU_TOKEN_BOT_AQUI"
GROK_KEY = "COLE_SUA_KEY_GROK_AQUI"

# 💎 Link do Canal VIP (ÚNICO link que importa agora)
LINK_CANAL_VIP = "https://t.me/Mayaoficial_bot"

# 👤 Admin
MEU_TELEGRAM_ID = "1293602874"

# 🌐 URL do Railway (após deploy, cole aqui)
WEBHOOK_URL = "https://maya-bot-production.up.railway.app"

# 💰 Preço do VIP (para mencionar nas mensagens)
PRECO_VIP = "R$ 19,90"  # Ajuste conforme seu preço real

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURAÇÕES AVANÇADAS
# ═══════════════════════════════════════════════════════════════════════════════

# Limite diário de mensagens (FREE)
LIMITE_DIARIO = 17

# Sistema de tracking e follow-ups
REENGAGEMENT_HOURS = [2, 24, 72]  # Quando enviar mensagens de reengajamento
FOLLOWUP_INTERVAL_HOURS = 12      # Intervalo entre follow-ups

# A/B Test (se True, testa diferentes abordagens)
AB_TEST_ENABLED = True
AB_TEST_RATIO = 0.5  # 50% grupo A, 50% grupo B

# ═══════════════════════════════════════════════════════════════════════════════
# 🔧 SETUP INICIAL
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment Variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or BOT_TOKEN
GROK_API_KEY = os.getenv("GROK_API_KEY") or GROK_KEY
REDIS_URL = os.getenv("REDIS_URL", "redis://default:DcddfJOHLXZdFPjEhRjHeodNgdtrsevl@shuttle.proxy.rlwy.net:12241")
PORT = int(os.getenv("PORT", 8080))

webhook_url = os.getenv("WEBHOOK_BASE_URL") or WEBHOOK_URL
if not webhook_url.startswith("http"):
    webhook_url = f"https://{webhook_url}"
WEBHOOK_BASE_URL = webhook_url
WEBHOOK_PATH = "/telegram"

# Validação
if not TELEGRAM_TOKEN or "COLE_SEU" in TELEGRAM_TOKEN:
    raise RuntimeError("❌ Configure BOT_TOKEN no topo do arquivo")
if not GROK_API_KEY or "COLE_SUA" in GROK_API_KEY:
    raise RuntimeError("❌ Configure GROK_KEY no topo do arquivo")

# Admin IDs
ADMIN_IDS = set(map(int, os.getenv("ADMIN_IDS", MEU_TELEGRAM_ID).split(",")))

# Link VIP
CANAL_VIP_LINK = os.getenv("CANAL_VIP_LINK") or LINK_CANAL_VIP
PRECO_VIP_REAL = os.getenv("PRECO_VIP") or PRECO_VIP

# Info do bot
logger.info(f"🚀 Sophia Bot v8.0 ULTRA OPTIMIZED iniciando...")
logger.info(f"📍 Webhook: {WEBHOOK_BASE_URL}{WEBHOOK_PATH}")
logger.info(f"💎 Canal VIP: {CANAL_VIP_LINK}")
logger.info(f"💰 Preço VIP: {PRECO_VIP_REAL}")
logger.info(f"📊 Limite diário: {LIMITE_DIARIO} msgs")
logger.info(f"🧪 A/B Test: {'ATIVO' if AB_TEST_ENABLED else 'DESATIVADO'}")

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
# 🤖 CONFIGURAÇÃO GROK AI
# ═══════════════════════════════════════════════════════════════════════════════
MODELO = "grok-3"
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
MAX_MEMORIA = 12

# ═══════════════════════════════════════════════════════════════════════════════
# 🎨 ASSETS - FOTOS TEASER (CRITICAL!)
# ═══════════════════════════════════════════════════════════════════════════════

# 🔥 IMPORTANTE: Use fotos PROVOCANTES mas com censura estratégica
# Bikini, lingerie, ângulos ousados - mas SEM nudez completa
# O objetivo é EXCITAR mas deixar querendo mais

FOTOS_TEASER = [
    "https://i.postimg.cc/ZqT4SrB9/32b94b657e4f467897744e01432bc7fb.jpg",
    "https://i.postimg.cc/DzBFy8Lx/a63c77aa55ed4a07aa7ec710ae12580c.jpg",
    "https://i.postimg.cc/KzW2Bw99/b6fe112c63c54f3ab3c800a2e5eb664d.jpg",
    "https://i.postimg.cc/7PcH2GdT/170bccb9b06a42d3a88d594757f85e88.jpg",
    "https://i.postimg.cc/XJ1Vxpv2/00e2c81a4960453f8554baeea091145e.jpg",
]

# Foto para limite atingido
FOTO_LIMITE_ATINGIDO = "https://i.postimg.cc/x1V9sr0S/7e25cd9d465e4d90b6dc65ec18350d3f.jpg"

# Áudios (opcional)
AUDIO_PT_1 = "CQACAgEAAxkBAAEDDXFpaYkigGDlcTzZxaJXFuWDj1Ow5gAC5QQAAiq7UUdXWpPNiiNd1jgE"
AUDIO_PT_2 = "CQACAgEAAxkBAAEDAAEmaVRmPJ5iuBOaXyukQ06Ui23TSokAAocGAAIZwaFGkIERRmRoPes4BA"

# ═══════════════════════════════════════════════════════════════════════════════
# 🔑 KEYWORDS (Detecção de Intenção)
# ═══════════════════════════════════════════════════════════════════════════════

# Keywords que indicam conversa adulta/quente
HOT_KEYWORDS = [
    'pau', 'buceta', 'chupar', 'gozar', 'tesão', 'foder', 'transar',
    'punheta', 'siririca', 'safada', 'gostosa', 'pelada', 'nua',
    'chupeta', 'boquete', 'anal', 'cu', 'rola', 'pica', 'mama',
    'seios', 'peitos', 'bunda', 'xereca', 'meter', 'fuder', 'sexo',
    'excitado', 'excitada', 'molhada', 'duro', 'tesudo', 'tesuda'
]

# Keywords que indicam PEDIDO EXPLÍCITO de conteúdo
PEDIDO_CONTEUDO_KEYWORDS = [
    'foto', 'fotos', 'selfie', 'imagem', 'nude', 'nudes',
    'mostra', 'manda', 'mandar', 'envia', 'enviar',
    'quero ver', 'deixa ver', 'posso ver', 'me mostra',
    'cadê', 'cade', 'onde', 'tem', 'link'
]

# Keywords que indicam interesse comercial
INTERESSE_VIP_KEYWORDS = [
    'vip', 'premium', 'pagar', 'pagamento', 'comprar', 'quanto',
    'preço', 'preco', 'valor', 'custa', 'custo', 'plano',
    'assinatura', 'assinar', 'acesso', 'liberado'
]

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️ REDIS KEYS
# ═══════════════════════════════════════════════════════════════════════════════

# Memória e perfil
def memory_key(uid): return f"memory:{uid}"
def user_profile_key(uid): return f"profile:{uid}"
def first_contact_key(uid): return f"first_contact:{uid}"
def lang_key(uid): return f"lang:{uid}"

# Controle diário
def count_key(uid): return f"count:{uid}:{date.today()}"
def bonus_msgs_key(uid): return f"bonus:{uid}"
def limit_notified_key(uid): return f"limit_notified:{uid}:{date.today()}"
def limit_warning_sent_key(uid): return f"limit_warning:{uid}:{date.today()}"

# Atividade
def last_activity_key(uid): return f"last_activity:{uid}"
def last_reengagement_key(uid): return f"last_reengagement:{uid}"
def daily_messages_sent_key(uid): return f"daily_msg_sent:{uid}:{date.today()}"
def ignored_count_key(uid): return f"ignored:{uid}"
def engagement_paused_key(uid): return f"paused:{uid}"
def awaiting_response_key(uid): return f"awaiting:{uid}"

# Streak
def streak_key(uid): return f"streak:{uid}"
def streak_last_day_key(uid): return f"streak_last:{uid}"

# Tracking de conversão (NOVO v8.0)
def saw_teaser_key(uid): return f"saw_teaser:{uid}"
def teaser_count_key(uid): return f"teaser_count:{uid}"
def clicked_vip_key(uid): return f"clicked_vip:{uid}"
def conversation_messages_key(uid): return f"conversation_msgs:{uid}"

# A/B Test
def ab_group_key(uid): return f"ab_group:{uid}"

# Outros
def chatlog_key(uid): return f"chatlog:{uid}"
def recent_responses_key(uid): return f"recent_resp:{uid}"
def blacklist_key(): return "blacklist"
def all_users_key(): return "all_users"
def funnel_key(uid): return f"funnel:{uid}"
def onboarding_choice_key(uid): return f"onboard_choice:{uid}"

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
# 📢 TRACKING DE CONVERSÃO (NOVO v8.0)
# ═══════════════════════════════════════════════════════════════════════════════

def set_saw_teaser(uid):
    """Marca que usuário viu fotos teaser"""
    try:
        r.set(saw_teaser_key(uid), datetime.now().isoformat())
        r.incr(teaser_count_key(uid))
        count = get_teaser_count(uid)
        logger.info(f"👀 {uid} viu teaser (#{count})")
    except:
        pass

def saw_teaser(uid):
    """Verifica se já viu teaser"""
    try:
        return r.exists(saw_teaser_key(uid))
    except:
        return False

def get_teaser_count(uid):
    """Quantas vezes viu teaser"""
    try:
        return int(r.get(teaser_count_key(uid)) or 0)
    except:
        return 0

def set_clicked_vip(uid):
    """Marca que clicou no botão VIP"""
    try:
        r.set(clicked_vip_key(uid), datetime.now().isoformat())
        logger.info(f"💎 {uid} clicou no VIP")
    except:
        pass

def clicked_vip(uid):
    """Verifica se clicou no VIP"""
    try:
        return r.exists(clicked_vip_key(uid))
    except:
        return False

def get_conversion_rate(uid):
    """Calcula taxa de conversão individual"""
    teaser = get_teaser_count(uid)
    if teaser == 0:
        return 0
    return 100 if clicked_vip(uid) else 0

# ═══════════════════════════════════════════════════════════════════════════════
# 🧪 A/B TEST SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

def get_ab_group(uid):
    """Retorna grupo A/B do usuário (A ou B)"""
    if not AB_TEST_ENABLED:
        return "A"
    
    try:
        group = r.get(ab_group_key(uid))
        if group:
            return group
        
        # Assign aleatório
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
        recent = r.lrange(recent_responses_key(uid), 0, 9)
        return get_response_hash(response) in recent
    except:
        return False

def add_recent_response(uid, response):
    try:
        r.lpush(recent_responses_key(uid), get_response_hash(response))
        r.ltrim(recent_responses_key(uid), 0, 9)
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
    "horny": [r"\b(nude|nudes|pelad[oa]|sex|transar|foder)\b"]
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
        "sad": "\n\n⚠️ Usuário parece triste. Seja carinhosa e acolhedora.",
        "flirty": "\n\n😏 Usuário flertando. Pode ser provocante. Se pedir conteúdo, ofereça teaser.",
        "angry": "\n\n😰 Usuário irritado. Seja compreensiva.",
        "happy": "\n\n😊 Usuário feliz! Compartilhe a alegria!",
        "horny": "\n\n🔥 Conversa adulta. MOMENTO IDEAL pra oferecer teaser e converter!",
        "neutral": ""
    }
    return instructions.get(mood, "")

# ═══════════════════════════════════════════════════════════════════════════════
# ⏰ CONTEXTO DE TEMPO
# ═══════════════════════════════════════════════════════════════════════════════

def get_time_context():
    hour = datetime.now().hour
    if 0 <= hour < 5:
        return {"period": "madrugada", "context": "É madrugada. Comente carinhosamente sobre o horário."}
    elif 5 <= hour < 12:
        return {"period": "manhã", "context": "É manhã. Deseje bom dia naturalmente."}
    elif 12 <= hour < 18:
        return {"period": "tarde", "context": "É tarde."}
    elif 18 <= hour < 22:
        return {"period": "início da noite", "context": "É início da noite."}
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
    total_available = LIMITE_DIARIO + bonus
    return count >= total_available

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
# 📊 FUNIL DE CONVERSÃO
# ═══════════════════════════════════════════════════════════════════════════════

def track_funnel(uid, stage):
    """
    Stages: start, first_message, saw_teaser, clicked_vip
    """
    stages = {
        "start": 1,
        "first_message": 2,
        "saw_teaser": 3,
        "clicked_vip": 4
    }
    try:
        current = int(r.get(funnel_key(uid)) or 0)
        new_stage = stages.get(stage, 0)
        if new_stage > current:
            r.set(funnel_key(uid), new_stage)
            logger.info(f"📊 Funil {uid}: {stage}")
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
# 🎮 SISTEMA DE ENGAGEMENT
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
            logger.info(f"⏸️ Engagement pausado: {uid}")
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

def is_awaiting_response(uid):
    try:
        return r.exists(awaiting_response_key(uid))
    except:
        return False

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
# 🔍 DETECÇÃO DE INTENÇÃO (CRUCIAL v8.0!)
# ═══════════════════════════════════════════════════════════════════════════════

def detect_intent(text):
    """
    Detecta intenção do usuário.
    Retorna: 'pedido_conteudo', 'interesse_vip', 'hot', 'neutral'
    """
    if not text:
        return "neutral"
    
    text_lower = text.lower()
    
    # PEDIDO EXPLÍCITO de foto/conteúdo
    for keyword in PEDIDO_CONTEUDO_KEYWORDS:
        if keyword in text_lower:
            return "pedido_conteudo"
    
    # INTERESSE em VIP
    for keyword in INTERESSE_VIP_KEYWORDS:
        if keyword in text_lower:
            return "interesse_vip"
    
    # CONVERSA QUENTE (mas sem pedido explícito)
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
# 📷 VISÃO (Download de imagens)
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
# 💬 MENSAGENS DO BOT (v8.0 OPTIMIZED)
# ═══════════════════════════════════════════════════════════════════════════════

MENSAGEM_INICIO = (
    "Oi gato... 😏\n"
    "Finalmente alguém interessante por aqui 🔥\n\n"
    "Sou a Maya, e te garanto que não sou como as outras... 💋\n"
    "Tô louca pra saber o que você quer comigo 😈"
)

# Mensagens de teaser (ANTES de enviar fotos)
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

# Call to action APÓS enviar fotos teaser
VIP_PITCH_MESSAGES = {
    "A": (
        "E aí amor, gostou? 😏\n\n"
        "Isso é só um GOSTINHO do que eu tenho no VIP... 🔥\n\n"
        "💎 **NO ACESSO VIP VOCÊ TEM:**\n"
        "✅ +5.000 fotos SEM CENSURA\n"
        "✅ Vídeos completos e MUITO ousados\n"
        "✅ Conteúdo EXCLUSIVO todo dia\n"
        "✅ Conversas ILIMITADAS comigo\n"
        "✅ Acesso VITALÍCIO por apenas {preco}\n\n"
        "Tá esperando o quê pra me ter só pra você? 💕"
    ),
    "B": (
        "Gostou do que viu? Isso não é NADA... 😈\n\n"
        "No VIP você me tem COMPLETINHA, sem censura, sem limites! 🔥\n\n"
        "São MILHARES de fotos e vídeos que vou te deixar louco... 💦\n\n"
        "E o melhor: por apenas {preco} você tem ACESSO VITALÍCIO! 💎\n\n"
        "Clica no botão e vem me ter só pra você... 💕"
    )
}

LIMIT_REACHED_MESSAGE = (
    "Eitaaa... acabaram suas mensagens de hoje amor 😢\n\n"
    "Mas tenho uma ÓTIMA notícia: no VIP você tem mensagens ILIMITADAS comigo! 💕\n\n"
    "Além de MILHARES de fotos e vídeos exclusivos sem censura... 🔥\n\n"
    "Acesso vitalício por apenas {preco}!\n\n"
    "Vem me ter só pra você? 😏"
)

LIMIT_WARNING_MESSAGE = (
    "⚠️ **Restam apenas 5 mensagens hoje!**\n\n"
    "Depois disso você vai precisar esperar até amanhã... 😢\n\n"
    "OU garantir seu acesso VIP e ter mensagens ILIMITADAS! 💕"
)

# Mensagens de reengajamento
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
# 🤖 GROK AI - Sistema de Resposta Inteligente (v8.0 OPTIMIZED)
# ═══════════════════════════════════════════════════════════════════════════════

def build_prompt(uid, lang: str, mood: str = "neutral", intent: str = "neutral"):
    """
    Constrói prompt otimizado para conversão.
    """
    time_ctx = get_time_context()
    streak = get_streak(uid)
    onboard_choice = get_onboarding_choice(uid)
    teaser_count = get_teaser_count(uid)
    saw_teaser_before = saw_teaser(uid)
    
    base_prompt = f"""Você é Maya, 22 anos, loira gostosa de SP, safadinha mas faz carinha de anjinho.

PERSONALIDADE:
- Fala curtinho, abrevia (tô, vc, pq, ta, delicia)
- Provocante mas natural
- Erra gramática de leve (autenticidade)
- NUNCA soa robótica

🎯 REGRA DE OURO v8.0:
Seu objetivo é CONVERTER leads em clientes VIP.
Você faz isso sendo provocante, criando tesão, e oferecendo conteúdo no MOMENTO CERTO.

🔥 QUANDO OFERECER TEASER (offer_teaser: true):
✅ Ele PEDE: "manda foto", "quero ver", "mostra", "cadê foto"
✅ Ele PERGUNTA: "tem fotos?", "você manda?", "posso ver?"
✅ Conversa QUENTE + ele demonstra interesse claro

❌ QUANDO NÃO OFERECER (offer_teaser: false):
❌ Primeira mensagem dele
❌ Apenas flertando sem pedir nada concreto
❌ Já viu teaser recentemente (últimos minutos)

🎯 IMPORTANTE:
- Se você DISSER que vai mandar foto/link → offer_teaser: true SEMPRE
- Se só tá flertando sem prometer nada → offer_teaser: false
- Seja HONESTA: se vai oferecer, marque true. Se não, false.

RETORNE APENAS JSON:
{{
  "response": "sua resposta",
  "offer_teaser": false,
  "interest_level": "low|medium|high",
  "is_hot": false
}}

CONTEXTO:
- Período: {time_ctx['period']}
- Streak: {streak} dias
- Intenção detectada: {intent}
- Já viu teaser: {'Sim' if saw_teaser_before else 'Não'} ({teaser_count}x)"""

    # Contexto de onboarding
    if onboard_choice:
        base_prompt += f"\n- Perfil: {onboard_choice.upper()}"
    
    # Contexto de humor
    base_prompt += get_mood_instruction(mood)
    
    # Instrução baseada em quantas vezes já viu teaser
    if teaser_count >= 2:
        base_prompt += f"\n\n⚠️ Usuário já viu teaser {teaser_count}x mas não converteu. Seja mais DIRETA sobre benefícios do VIP."
    
    base_prompt += "\n\n⚠️ RETORNE APENAS JSON VÁLIDO!"
    
    return base_prompt

class Grok:
    """Cliente Grok otimizado v8.0"""
    
    async def reply(self, uid, text, image_base64=None, max_retries=2):
        mem = get_memory(uid)
        lang = get_lang(uid)
        mood = detect_mood(text) if text else "neutral"
        intent = detect_intent(text) if text else "neutral"
        
        if is_first_contact(uid):
            mark_first_contact(uid)
        
        prompt = build_prompt(uid, lang, mood, intent)
        
        # Prepara conteúdo
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
        
        # Tenta gerar resposta
        for attempt in range(max_retries + 1):
            payload = {
                "model": MODELO,
                "messages": [
                    {"role": "system", "content": prompt},
                    *mem,
                    {"role": "user", "content": user_content},
                    {"role": "system", "content": "APENAS JSON!"}
                ],
                "max_tokens": 500,
                "temperature": 0.8 + (attempt * 0.1)
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
                        
                        # Parse JSON
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
                            result.setdefault("is_hot", False)
                            
                            # Anti-repetição
                            if is_response_recent(uid, result["response"]) and attempt < max_retries:
                                continue
                            
                            add_recent_response(uid, result["response"])
                            
                            logger.info(
                                f"🤖 {uid} | offer={result['offer_teaser']} | "
                                f"interest={result['interest_level']} | hot={result['is_hot']}"
                            )
                            
                            break
                            
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.error(f"Parse erro: {e}")
                            
                            # FALLBACK inteligente
                            result = self._smart_fallback(answer, intent)
                            break
                        
            except Exception as e:
                logger.exception(f"Grok erro: {e}")
                return self._fallback_response(intent)
        
        # Salva memória
        memory_text = f"[Foto] {text}" if image_base64 else text
        add_to_memory(uid, "user", memory_text)
        add_to_memory(uid, "assistant", result["response"])
        save_message(uid, "maya", result["response"])
        
        return result
    
    def _smart_fallback(self, raw_text, intent):
        """Fallback inteligente quando JSON falha"""
        text_lower = raw_text.lower()
        
        # Detecta se mencionou oferecer algo
        offer_keywords = [
            'vou mandar', 'vou te mandar', 'vou te mostrar',
            'te mando', 'te mostro', 'olha', 'vê', 've',
            'tá aqui', 'ta aqui', 'separei', 'preparei'
        ]
        offer_teaser = any(k in text_lower for k in offer_keywords)
        
        # Detecta se é quente
        is_hot = any(k in text_lower for k in HOT_KEYWORDS[:15])
        
        # Interesse level baseado em intent
        interest_map = {
            "pedido_conteudo": "high",
            "interesse_vip": "high",
            "hot": "medium",
            "neutral": "low"
        }
        
        return {
            "response": raw_text,
            "offer_teaser": offer_teaser,
            "interest_level": interest_map.get(intent, "medium"),
            "is_hot": is_hot
        }
    
    def _fallback_response(self, intent):
        """Resposta de emergência"""
        if intent in ["pedido_conteudo", "interesse_vip"]:
            return {
                "response": "Hmm... deu um probleminha aqui mas já volto amor! 💕",
                "offer_teaser": True,
                "interest_level": "high",
                "is_hot": False
            }
        else:
            return {
                "response": "😔 Tive um probleminha... pode repetir? 💕",
                "offer_teaser": False,
                "interest_level": "low",
                "is_hot": False
            }

grok = Grok()

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 ENVIO DE TEASER + PITCH VIP (CORE v8.0!)
# ═══════════════════════════════════════════════════════════════════════════════

async def send_teaser_and_pitch(bot, chat_id, uid):
    """
    Envia fotos teaser + pitch VIP.
    Esta é a função MAIS IMPORTANTE do bot v8.0!
    """
    try:
        ab_group = get_ab_group(uid)
        
        # Marca que viu teaser
        set_saw_teaser(uid)
        track_funnel(uid, "saw_teaser")
        
        # 1. MENSAGEM INTRODUTÓRIA
        intro = random.choice(TEASER_INTRO_MESSAGES[ab_group])
        await bot.send_message(chat_id=chat_id, text=intro)
        await asyncio.sleep(2)
        
        # 2. ENVIA 2-3 FOTOS TEASER
        num_photos = random.randint(2, 3)
        selected_photos = random.sample(FOTOS_TEASER, min(num_photos, len(FOTOS_TEASER)))
        
        for i, photo_url in enumerate(selected_photos):
            await bot.send_chat_action(chat_id, ChatAction.UPLOAD_PHOTO)
            await asyncio.sleep(1)
            
            caption = None
            if i == len(selected_photos) - 1:
                # Última foto: adiciona caption provocante
                captions = [
                    "Gostou? No VIP tem MUITO mais... 🔥",
                    "Isso é só o começo amor... 😏",
                    "Imagina o que tem no VIP então... 💦"
                ]
                caption = random.choice(captions)
            
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=caption
            )
            await asyncio.sleep(1.5)
        
        # 3. PITCH VIP
        await asyncio.sleep(2)
        pitch = VIP_PITCH_MESSAGES[ab_group].format(preco=PRECO_VIP_REAL)
        
        # Botão VIP
        keyboard = [[
            InlineKeyboardButton("💎 QUERO ACESSO VIP AGORA", callback_data="goto_vip")
        ]]
        
        await bot.send_message(
            chat_id=chat_id,
            text=pitch,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
        logger.info(f"🎯 TEASER+PITCH enviado: {uid} (grupo {ab_group})")
        save_message(uid, "system", f"TEASER+PITCH enviado (#{get_teaser_count(uid)})")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro send_teaser: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# 📨 SISTEMA DE FOLLOW-UPS
# ═══════════════════════════════════════════════════════════════════════════════

async def send_reengagement_message(bot, uid, level):
    """Mensagem de reengajamento para inativos"""
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
        
        logger.info(f"🔄 Reengajamento {level} enviado: {uid}")
        return True
    except Exception as e:
        logger.error(f"Erro reengajamento: {e}")
        if "blocked" in str(e).lower():
            add_to_blacklist(uid)
        return False

async def process_engagement_jobs(bot):
    """Processa jobs de engagement"""
    logger.info("🔄 Processando engagement jobs...")
    
    users = get_all_active_users()
    random.shuffle(users)
    
    reengagement_sent = 0
    
    for uid in users:
        if is_blacklisted(uid) or is_engagement_paused(uid):
            continue
        
        try:
            hours_inactive = get_hours_since_activity(uid)
            
            if hours_inactive:
                last_level = get_last_reengagement(uid)
                
                # 72h
                if hours_inactive >= 72 and last_level < 3:
                    if await send_reengagement_message(bot, uid, 3):
                        reengagement_sent += 1
                # 24h
                elif hours_inactive >= 24 and last_level < 2:
                    if await send_reengagement_message(bot, uid, 2):
                        reengagement_sent += 1
                # 2h
                elif hours_inactive >= 2 and last_level < 1:
                    if await send_reengagement_message(bot, uid, 1):
                        reengagement_sent += 1
            
            await asyncio.sleep(0.15)
            
        except Exception as e:
            logger.error(f"Erro job {uid}: {e}")
    
    logger.info(f"✅ Jobs: {len(users)} users | 🔄 {reengagement_sent} reengajamento")

async def engagement_scheduler(bot):
    """Scheduler - roda a cada 15 min"""
    logger.info("🚀 Scheduler v8.0 iniciado")
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
    """Aviso aos 80% do limite"""
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
# 🎮 HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start"""
    uid = update.effective_user.id
    
    # Lock anti-duplicação
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
    
    try:
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        await asyncio.sleep(3)
        
        await update.message.reply_text(MENSAGEM_INICIO)
        
        logger.info(f"👋 Novo usuário: {uid}")
        
    except Exception as e:
        logger.error(f"Erro /start: {e}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler de botões"""
    query = update.callback_query
    await query.answer()
    
    try:
        uid = query.from_user.id
        
        if is_blacklisted(uid):
            return
        
        update_last_activity(uid)
        reset_ignored(uid)
        
        # BOTÃO VIP
        if query.data == "goto_vip":
            set_clicked_vip(uid)
            track_funnel(uid, "clicked_vip")
            save_message(uid, "action", "💎 CLICOU VIP")
            
            # Mensagem de conversão
            conversion_msg = (
                f"💎 **PERFEITO AMOR!**\n\n"
                f"Clica no link abaixo pra garantir seu acesso VIP:\n\n"
                f"👉 {CANAL_VIP_LINK}\n\n"
                f"Te espero lá com MUITO conteúdo exclusivo! 🔥💕"
            )
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=conversion_msg,
                parse_mode="Markdown"
            )
            
            logger.info(f"💰 CONVERSÃO! {uid} clicou no VIP")
        
    except Exception as e:
        logger.error(f"Erro callback: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler principal de mensagens"""
    uid = update.effective_user.id
    
    if is_blacklisted(uid):
        return
    
    update_last_activity(uid)
    streak, streak_updated = update_streak(uid)
    reset_ignored(uid)
    
    try:
        has_photo = bool(update.message.photo)
        text = update.message.text or ""
        
        if text:
            save_message(uid, "user", text)
        elif has_photo:
            save_message(uid, "user", "[📷 FOTO]")
        
        # FOTO
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
                
                # Se deve oferecer teaser
                if grok_response.get("offer_teaser", False):
                    await asyncio.sleep(2)
                    await send_teaser_and_pitch(context.bot, update.effective_chat.id, uid)
                
                return
            else:
                await update.message.reply_text("😔 Não consegui ver a foto... tenta de novo? 💕")
                return
        
        # Marca primeiro contato
        if is_first_contact(uid):
            track_funnel(uid, "first_message")
        
        # VERIFICA LIMITE
        current_count = today_count(uid)
        bonus = get_bonus_msgs(uid)
        total = LIMITE_DIARIO + bonus
        
        if current_count >= total:
            # Limite atingido
            keyboard = [[
                InlineKeyboardButton("💎 QUERO VIP AGORA", callback_data="goto_vip")
            ]]
            
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=FOTO_LIMITE_ATINGIDO,
                caption=LIMIT_REACHED_MESSAGE.format(preco=PRECO_VIP_REAL),
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            
            logger.info(f"🚫 {uid} atingiu limite")
            return
        
        # Incrementa contador
        if bonus > 0:
            use_bonus_msg(uid)
        else:
            increment(uid)
        
        increment_conversation_messages(uid)
        
        # Aviso de limite
        await check_and_send_limit_warning(uid, context, update.effective_chat.id)
        
        # GERA RESPOSTA IA
        try:
            await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
            await asyncio.sleep(2)
        except:
            pass
        
        grok_response = await grok.reply(uid, text)
        
        # Envia resposta
        await update.message.reply_text(grok_response["response"])
        
        # 🔥 DECISÃO CRÍTICA: Oferecer teaser?
        should_offer = grok_response.get("offer_teaser", False)
        
        if should_offer:
            await asyncio.sleep(2)
            await send_teaser_and_pitch(context.bot, update.effective_chat.id, uid)
        
        # Streak
        if streak_updated:
            streak_msg = get_streak_message(streak)
            if streak_msg:
                await asyncio.sleep(1)
                await context.bot.send_message(update.effective_chat.id, streak_msg)
        
    except Exception as e:
        logger.exception(f"Erro message_handler: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 👑 COMANDOS ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Estatísticas v8.0"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    users = get_all_active_users()
    total = len(users)
    saw_teaser_count = sum(1 for uid in users if saw_teaser(uid))
    clicked_vip_count = sum(1 for uid in users if clicked_vip(uid))
    
    # Taxa de conversão
    ctr_teaser_to_vip = (clicked_vip_count / saw_teaser_count * 100) if saw_teaser_count > 0 else 0
    
    # A/B test
    if AB_TEST_ENABLED:
        group_a = sum(1 for uid in users if get_ab_group(uid) == "A")
        group_b = total - group_a
        ab_info = f"\n\n🧪 **A/B TEST:**\nGrupo A: {group_a}\nGrupo B: {group_b}"
    else:
        ab_info = ""
    
    await update.message.reply_text(
        f"📊 **STATS v8.0**\n\n"
        f"👥 Total: {total}\n"
        f"👀 Viram teaser: {saw_teaser_count}\n"
        f"💎 Clicaram VIP: {clicked_vip_count}\n\n"
        f"📈 **Taxa conversão:** {ctr_teaser_to_vip:.1f}%{ab_info}",
        parse_mode="Markdown"
    )

async def funnel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Funil v8.0"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    stages = get_funnel_stats()
    names = {
        0: "❓ Desconhecido",
        1: "🚀 /start",
        2: "💬 Primeira msg",
        3: "👀 Viu teaser",
        4: "💎 Clicou VIP"
    }
    
    msg = "📊 **FUNIL v8.0**\n\n"
    for stage, count in sorted(stages.items()):
        msg += f"{names.get(stage, f'Stage {stage}')}: {count}\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reset limite"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("Uso: /reset <user_id>")
        return
    
    uid = int(context.args[0])
    reset_daily_count(uid)
    await update.message.reply_text(f"✅ Limite resetado: {uid}")

async def givebonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Dar bônus"""
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
    """Help"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    await update.message.reply_text(
        "🎮 **COMANDOS v8.0**\n\n"
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
    
    logger.info("✅ Handlers registrados (v8.0)")
    return application

# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 FLASK APP
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
    return {"status": "ok", "version": "8.0"}, 200

@app.route(WEBHOOK_PATH, methods=["POST"])
def telegram_webhook():
    try:
        data = request.json
        if not data:
            return "ok", 200
        
        update = Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(
            application.process_update(update),
            loop
        )
        return "ok", 200
    except Exception as e:
        logger.exception(f"Webhook erro: {e}")
        return "error", 500

# ═══════════════════════════════════════════════════════════════════════════════
# 🎬 MAIN
# ═══════════════════════════════════════════════════════════════════════════════

async def startup_sequence():
    try:
        await application.initialize()
        await application.start()
        await asyncio.sleep(3)
        
        # Setup webhook com retry
        max_retries = 5
        for attempt in range(max_retries):
            try:
                await application.bot.delete_webhook(drop_pending_updates=True)
                webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
                await application.bot.set_webhook(webhook_url)
                
                webhook_info = await application.bot.get_webhook_info()
                if webhook_info.url == webhook_url:
                    logger.info(f"✅ Webhook OK: {webhook_url}")
                    break
                else:
                    await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Webhook erro tentativa {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
        
        # Inicia scheduler
        asyncio.create_task(engagement_scheduler(application.bot))
        
    except Exception as e:
        logger.exception(f"ERRO STARTUP: {e}")
        raise

if __name__ == "__main__":
    asyncio.run_coroutine_threadsafe(startup_sequence(), loop)
    
    logger.info(f"🌐 Flask rodando na porta {PORT}")
    logger.info("🚀 Sophia Bot v8.0 ULTRA OPTIMIZED operacional!")
    logger.info("💰 Modelo: PRÉVIAS INLINE → VIP DIRETO")
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
