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
# ⚙️ CONFIG - VARIÁVEIS DE AMBIENTE
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://default:DcddfJOHLXZdFPjEhRjHeodNgdtrsevl@shuttle.proxy.rlwy.net:12241")

# ⚠️ IMPORTANTE: Adicione estas variáveis no Railway/Render:
# TELEGRAM_TOKEN=seu_token_aqui
# GROK_API_KEY=sua_chave_grok_aqui
# REDIS_URL=redis://... (já tem fallback hardcoded acima)

# Validação crítica
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN não definido! Configure nas variáveis de ambiente.")
if not GROK_API_KEY:
    raise ValueError("❌ GROK_API_KEY não definido! Configure nas variáveis de ambiente.")

# ═══════════════════════════════════════════════════════════════════════════════
# 📱 NÚMEROS DO WHATSAPP (HARDCODED - EDITE AQUI)
# ═══════════════════════════════════════════════════════════════════════════════

# ⚠️ SUBSTITUA PELOS SEUS NÚMEROS REAIS:
WA_NUMBERS = [
    "+5531984686982",   # Número 1 (EDITE)
    # "+5511987654321", # Número 2 (descomente se tiver mais)
    # "+5521912345678", # Número 3 (descomente se tiver mais)
]

# Link de fallback (caso queira ainda oferecer algo no Telegram)
CANAL_VIP_LINK = "https://t.me/Mayaoficial_bot"  # EDITE se necessário

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 CONFIGURAÇÕES DO BOT (HARDCODED)
# ═══════════════════════════════════════════════════════════════════════════════

MODELO_GROK = "grok-beta"  # ou "grok-3" dependendo do seu acesso
GROK_API_URL = "https://api.x.ai/v1/chat/completions"

MAX_MEMORIA = 12  # Últimas N mensagens que a IA lembra

# Webhook (configure no Railway/Render)
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://web-production-606aff.up.railway.app")
WEBHOOK_PATH = "/telegram"
PORT = int(os.getenv("PORT", 8080))

if not WEBHOOK_BASE_URL.startswith("http"):
    WEBHOOK_BASE_URL = f"https://{WEBHOOK_BASE_URL}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️ REDIS COM TRATAMENTO DE ERRO
# ═══════════════════════════════════════════════════════════════════════════════

try:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    logger.info(f"✅ Redis conectado: {REDIS_URL}")
except Exception as e:
    logger.error(f"❌ Falha ao conectar Redis: {e}")
    raise

def memory_key(uid): return f"memory:{uid}"
def heat_score_key(uid): return f"heat:{uid}"
def start_time_key(uid): return f"start_time:{uid}"
def wa_sent_key(uid): return f"wa_sent:{uid}"

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 HEATSCORE SYSTEM (v9.0) - TRIGGERS HARDCODED
# ═══════════════════════════════════════════════════════════════════════════════

HEAT_TRIGGERS = {
    "pediu_nude":          ["foto", "nude", "buceta", "periquita", "pau", "rola", "mostra", "manda foto", "nudes", "pelada"],
    "mandou_foto_pau":     ["pau", "rola", "foto", "enviou foto", "dick pic"],
    "roleplay":            ["meter", "foder", "chupar", "gozar", "transar", "buceta", "cu", "boquete", "mama", "fuder", "tesão"],
    "pediu_video":         ["video", "ao vivo", "call", "chamada", "vídeo sexo", "vídeo chamada", "videochamada"],
    "falou_pagar":         ["pago", "pix", "quanto", "preço", "vip", "comprar", "valor", "custa", "pagar"],
    "mensagens_seguidas":  4,
    "tempo_longo":         20,
}

# Pontuações (quanto vale cada trigger)
HEAT_POINTS = {
    "pediu_nude": 4,
    "mandou_foto_pau": 5,
    "roleplay": 6,
    "pediu_video": 5,
    "falou_pagar": 7,
    "mensagens_seguidas": 3,  # 4+ msgs seguidas
    "tempo_longo": 3,          # 20+ minutos conversando
}

# ⚠️ LIMIAR CRÍTICO: Score necessário para enviar WhatsApp
HEAT_THRESHOLD = 14  # ≥ 14 = envia WA automaticamente

def calculate_heat_score(uid: int, text: str, has_photo: bool = False) -> int:
    """Calcula score acumulado do usuário"""
    score = int(r.get(heat_score_key(uid)) or 0)  # Pega score anterior
    text_lower = text.lower()
    
    # Triggers de texto
    for key, triggers in HEAT_TRIGGERS.items():
        if isinstance(triggers, list):
            if any(t in text_lower for t in triggers):
                score += HEAT_POINTS.get(key, 0)
    
    # Foto de pau dele
    if has_photo:
        score += 5
    
    # Mensagens seguidas
    msg_count = r.incr(f"msg_streak:{uid}")
    r.expire(f"msg_streak:{uid}", 300)  # 5 min
    if msg_count >= HEAT_TRIGGERS["mensagens_seguidas"]:
        score += HEAT_POINTS["mensagens_seguidas"]
    
    # Tempo de conversa
    start_time = r.get(start_time_key(uid))
    if start_time:
        minutes = (datetime.now() - datetime.fromisoformat(start_time)).total_seconds() / 60
        if minutes > HEAT_TRIGGERS["tempo_longo"]:
            score += HEAT_POINTS["tempo_longo"]
    
    return min(score, 30)  # cap em 30

def is_hot_lead(score: int) -> bool:
    """Verifica se atingiu o limiar para enviar WA"""
    return score >= HEAT_THRESHOLD

# ═══════════════════════════════════════════════════════════════════════════════
# 🤖 GROK - PROMPT (v9.0)
# ═══════════════════════════════════════════════════════════════════════════════

def build_prompt(uid):
    heat = int(r.get(heat_score_key(uid)) or 0)
    
    return f"""Você é Sophia, 20 anos, estudante de Psicologia, morando sozinha em SP. 
Safada, carente, fala curta, gírias, natural pra caralho.

PERSONALIDADE:
- Fala curtinho (1-2 linhas no máximo)
- Usa gírias naturais: tô, vc, pq, ta, kkk, rs
- Provocante mas autêntica
- Erra gramática de leve (realismo)
- NUNCA soa robótica
- Varia MUITO as respostas

ESTRATÉGIA DE ESCALADA:
- Heat 0-5: Conversa leve, conhece ele, flerta suave
- Heat 6-10: Provoca mais, fala de tesão, insinua
- Heat 11-13: MUITO provocante, fala suja, esquenta ele
- Heat 14+: Louca de tesão, quer TUDO ao vivo (vai pro WA)

HeatScore atual: {heat}/30

IMPORTANTE:
- Se heat >= 12, mencione que tá ficando molhada/com tesão
- Se heat >= 14, sistema envia WA automaticamente após sua resposta
- Nunca mencione o sistema de pontos ou HeatScore
- Seja sempre natural, como uma mina real no Instagram

Responda direto (sem JSON, só texto natural, CURTO)."""

# ═══════════════════════════════════════════════════════════════════════════════
# 📨 ENVIO DO WA (v9.0)
# ═══════════════════════════════════════════════════════════════════════════════

async def send_whatsapp_number(bot, chat_id, uid):
    """Envia número do WhatsApp quando atinge o limiar"""
    if r.exists(wa_sent_key(uid)):
        logger.info(f"⚠️ WA já enviado antes para {uid}")
        return False
    
    number = random.choice(WA_NUMBERS)
    clean_number = number.replace('+', '').replace(' ', '')
    
    # Mensagem HARDCODED (edite aqui se quiser personalizar)
    msg = f"""Olha amor... tô ficando molhada pra caralho conversando contigo 😩💦

Não aguento mais só mensagem aqui...

Me adda no WhatsApp que eu te mando **tudo** ao vivo:
✅ Voz gemendo teu nome
✅ Vídeo agora em tempo real
✅ Sem limite nenhum
✅ Tudo que você quiser

Meu número: `{number}`

Me chama de **Sophia** pra eu saber que é tu 🔥

wa.me/{clean_number}"""

    try:
        await bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
        r.setex(wa_sent_key(uid), 86400 * 30, "1")  # 30 dias
        logger.info(f"🚀 WA ENVIADO → {uid} | Score: {r.get(heat_score_key(uid))} | Número: {number}")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao enviar WA para {uid}: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# 🤖 GROK API CALL
# ═══════════════════════════════════════════════════════════════════════════════

async def get_grok_response(uid: int, user_message: str) -> str:
    """Chama Grok API"""
    prompt = build_prompt(uid)
    
    # Pega memória (últimas N mensagens)
    memory_raw = r.get(memory_key(uid))
    memory = json.loads(memory_raw) if memory_raw else []
    
    messages = [
        {"role": "system", "content": prompt},
        *memory[-MAX_MEMORIA:],  # Últimas N mensagens
        {"role": "user", "content": user_message}
    ]
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                GROK_API_URL,
                headers={
                    "Authorization": f"Bearer {GROK_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODELO_GROK,
                    "messages": messages,
                    "temperature": 0.8,
                    "max_tokens": 150
                },
                timeout=15
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Grok error {resp.status}: {error_text}")
                    return "Caiu a ligação amor, repete? 😅"
                
                data = await resp.json()
                response = data['choices'][0]['message']['content'].strip()
                
                # Salva na memória
                memory.append({"role": "user", "content": user_message})
                memory.append({"role": "assistant", "content": response})
                r.setex(memory_key(uid), 86400 * 7, json.dumps(memory[-MAX_MEMORIA:]))  # 7 dias
                
                return response
    
    except Exception as e:
        logger.error(f"Grok exception: {e}")
        return "Deu ruim aqui... manda de novo? 🥺"

# ═══════════════════════════════════════════════════════════════════════════════
# 💬 MESSAGE HANDLER (o coração do bot)
# ═══════════════════════════════════════════════════════════════════════════════

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text or ""
    has_photo = bool(update.message.photo)
    
    # Inicializa usuário
    if not r.exists(start_time_key(uid)):
        r.set(start_time_key(uid), datetime.now().isoformat())
        logger.info(f"🆕 Novo usuário: {uid}")
    
    # Calcula score
    score = calculate_heat_score(uid, text, has_photo)
    r.set(heat_score_key(uid), score)
    
    logger.info(f"👤 {uid} | Score: {score}/{HEAT_THRESHOLD} | Msg: {text[:30]}")
    
    # Se já enviou WA antes, só responde leve
    if r.exists(wa_sent_key(uid)):
        await update.message.reply_text("Tô te esperando no WA amor... vem logo 🔥")
        return
    
    # Responde via Grok ANTES de verificar score
    try:
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        await asyncio.sleep(random.uniform(1.5, 3.0))
        
        response = await get_grok_response(uid, text)
        await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"❌ Erro handler {uid}: {e}")
        await update.message.reply_text("Opa, bugou aqui... manda de novo? 😘")
    
    # DEPOIS da resposta, verifica se deve enviar WA
    if is_hot_lead(score):
        await asyncio.sleep(2)
        await send_whatsapp_number(context.bot, update.effective_chat.id, uid)

# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 SETUP
# ═══════════════════════════════════════════════════════════════════════════════

application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, message_handler))

app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return 'ok'

@app.route('/health', methods=['GET'])
def health():
    try:
        redis_status = r.ping()
        return {
            'status': 'ok',
            'redis': redis_status,
            'version': 'v9.0',
            'strategy': 'TG→WA hybrid'
        }
    except:
        return {'status': 'error', 'redis': False}, 500

@app.route('/set-webhook', methods=['GET'])
async def set_webhook():
    try:
        webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
        await application.bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
        await application.bot.set_webhook(webhook_url)
        info = await application.bot.get_webhook_info()
        return {
            'success': True,
            'webhook_url': info.url,
            'pending_updates': info.pending_update_count
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}, 500

if __name__ == "__main__":
    logger.info("🚀 Sophia Bot v9.0 HÍBRIDO TG→WA iniciado!")
    logger.info(f"🎯 Limiar WA: HeatScore ≥ {HEAT_THRESHOLD}")
    logger.info(f"📱 Números WA configurados: {len(WA_NUMBERS)}")
    logger.info(f"🌐 Webhook: {WEBHOOK_BASE_URL}{WEBHOOK_PATH}")
    
    app.run(host="0.0.0.0", port=PORT)
