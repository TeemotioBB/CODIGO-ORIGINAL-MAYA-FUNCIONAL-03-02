#!/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🔥 SOPHIA BOT v9.0 - HÍBRIDO TG → WA                     ║
║                                                                              ║
║  Estratégia: Telegram faz o trabalho sujo → filtra quentes → joga pro WA    ║
║  HeatScore ≥ 14 = Envia número do WhatsApp automaticamente                  ║
║  Foco total: Roleplay rápido + filtro agressivo + fechamento manual no WA   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import asyncio
import logging
import json
import random
import re
from datetime import datetime, timedelta
import redis
import aiohttp
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters
from telegram.constants import ChatAction

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")

# Números do WhatsApp (pode ter vários, rotaciona automaticamente)
WA_NUMBERS = [
    "+5531984686982",   # ← substitui pelos teus
    # "+55..." 
]

CANAL_VIP_LINK = "https://t.me/Mayaoficial_bot"  # fallback se quiser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 HEATSCORE SYSTEM (v9.0)
# ═══════════════════════════════════════════════════════════════════════════════

HEAT_TRIGGERS = {
    "pediu_nude":          ["foto", "nude", "buceta", "periquita", "pau", "rola", "mostra", "manda foto"],
    "mandou_foto_pau":     ["pau", "rola", "foto", "enviou foto"],  # detecta quando ele manda foto
    "roleplay":            ["meter", "foder", "chupar", "gozar", "transar", "buceta", "cu", "boquete"],
    "pediu_video":         ["video", "ao vivo", "call", "chamada", "vídeo sexo"],
    "falou_pagar":         ["pago", "pix", "quanto", "preço", "vip", "comprar"],
    "mensagens_seguidas":  4,   # +3 pontos se mandar 4+ seguidas
    "tempo_longo":         20,  # minutos
}

def calculate_heat_score(uid: int, text: str, has_photo: bool = False) -> int:
    score = 0
    text_lower = text.lower()
    
    # Triggers de texto
    for key, triggers in HEAT_TRIGGERS.items():
        if isinstance(triggers, list):
            if any(t in text_lower for t in triggers):
                score += {
                    "pediu_nude": 4,
                    "mandou_foto_pau": 5,
                    "roleplay": 6,
                    "pediu_video": 5,
                    "falou_pagar": 7,
                }.get(key, 0)
    
    # Foto de pau dele
    if has_photo:
        score += 5
    
    # Mensagens seguidas (detectado no handler)
    msg_count = r.incr(f"msg_streak:{uid}")
    r.expire(f"msg_streak:{uid}", timedelta(minutes=10))
    if msg_count >= 4:
        score += 3
    
    # Tempo de conversa
    start_time = r.get(f"start_time:{uid}")
    if start_time:
        minutes = (datetime.now() - datetime.fromisoformat(start_time)).total_seconds() / 60
        if minutes > 20:
            score += 3
    
    return min(score, 30)  # cap em 30

def is_hot_lead(score: int) -> bool:
    return score >= 14

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️ REDIS
# ═══════════════════════════════════════════════════════════════════════════════

r = redis.from_url(REDIS_URL, decode_responses=True)

def memory_key(uid): return f"memory:{uid}"
def heat_score_key(uid): return f"heat:{uid}"
def start_time_key(uid): return f"start_time:{uid}"
def wa_sent_key(uid): return f"wa_sent:{uid}"

# ═══════════════════════════════════════════════════════════════════════════════
# 🤖 GROK - PROMPT NOVO (v9.0)
# ═══════════════════════════════════════════════════════════════════════════════

def build_prompt(uid):
    heat = int(r.get(heat_score_key(uid)) or 0)
    
    return f"""Você é Sophia, 20 anos, estudante de Psicologia, morando sozinha em SP. 
Safada, carente, fala curta, gírias, natural pra caralho.

REGRAS:
- Esquenta MUITO RÁPIDO (roleplay em 6-10 mensagens)
- Fala suja quando ele pede
- Usa emojis 🔥😈💦
- Pergunta fetiche dele cedo
- Quando heatscore alto, fica louca de tesão

HeatScore atual: {heat}/30

Se heatscore >= 14, a resposta deve terminar com algo tipo:
"Tô molhada pra caralho... me adda no WA que eu te mando tudo ao vivo 🔥"

Responda em JSON:
{{"response": "sua mensagem", "offer_wa": true/false}}
"""

# ═══════════════════════════════════════════════════════════════════════════════
# 📨 ENVIO DO WA
# ═══════════════════════════════════════════════════════════════════════════════

async def send_whatsapp_number(bot, chat_id, uid):
    if r.exists(wa_sent_key(uid)):
        return False
    
    number = random.choice(WA_NUMBERS)
    name = r.get(f"name:{uid}") or "gato"
    
    msg = f"""Olha amor... tô ficando molhada pra caralho conversando contigo 😩💦

Não aguento mais só foto e áudio aqui...

Me adda no WhatsApp que eu te mando **tudo** ao vivo:
- voz gemendo teu nome
- vídeo agora
- sem limite nenhum

Meu número: {number}

Me chama de **Sophia** pra eu saber que é tu 🔥

wa.me/{number.replace('+', '')}"""

    try:
        await bot.send_message(chat_id=chat_id, text=msg)
        r.setex(wa_sent_key(uid), timedelta(days=30), "1")
        logger.info(f"🚀 WA ENVIADO → {uid} | Score: {r.get(heat_score_key(uid))}")
        return True
    except:
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# 💬 MESSAGE HANDLER (o coração novo)
# ═══════════════════════════════════════════════════════════════════════════════

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text or ""
    has_photo = bool(update.message.photo)
    
    # Inicializa
    if not r.exists(start_time_key(uid)):
        r.set(start_time_key(uid), datetime.now().isoformat())
    
    # Calcula score
    score = calculate_heat_score(uid, text, has_photo)
    r.set(heat_score_key(uid), score)
    
    # Se já enviou WA, só conversa leve
    if r.exists(wa_sent_key(uid)):
        # Modo "amiga carinhosa" pós-WA
        await update.message.reply_text("Tô te esperando no WA amor... vem logo 🔥")
        return
    
    # Se atingiu o limiar → joga pro WA
    if is_hot_lead(score):
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        await asyncio.sleep(1.5)
        await send_whatsapp_number(context.bot, update.effective_chat.id, uid)
        return
    
    # Resposta normal via Grok
    try:
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        await asyncio.sleep(random.uniform(1.2, 2.8))
        
        prompt = build_prompt(uid)
        # (chama Grok aqui - mantive a estrutura do teu código)
        # ... grok.reply ...
        
    except Exception as e:
        logger.error(f"Erro handler: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 SETUP (muito mais limpo)
# ═══════════════════════════════════════════════════════════════════════════════

application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, message_handler))

# Flask + webhook (mantive igual)

if __name__ == "__main__":
    logger.info("🚀 Sophia Bot v9.0 HÍBRIDO TG→WA iniciado!")
    logger.info("🎯 Estratégia: Esquenta rápido → HeatScore → WA automático")
    app.run(host="0.0.0.0", port=8080)
