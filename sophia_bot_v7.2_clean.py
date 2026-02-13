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
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters, CommandHandler
from telegram.constants import ChatAction
import threading
import traceback

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️ CONFIG - VARIÁVEIS DE AMBIENTE
# ═══════════════════════════════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROK_API_KEY = os.getenv("GROK_API_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://default:DcddfJOHLXZdFPjEhRjHeodNgdtrsevl@shuttle.proxy.rlwy.net:12241")

# Validação crítica
if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN não definido!")
if not GROK_API_KEY:
    raise ValueError("❌ GROK_API_KEY não definido!")

# ═══════════════════════════════════════════════════════════════════════════════
# 📱 NÚMEROS DO WHATSAPP
# ═══════════════════════════════════════════════════════════════════════════════

WA_NUMBERS = ["+5531984686982"]
CANAL_VIP_LINK = "https://t.me/Mayaoficial_bot"

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 CONFIGURAÇÕES DO BOT
# ═══════════════════════════════════════════════════════════════════════════════

MODELO_GROK = "grok-3"  # ← CORRIGIDO DO SEU CÓDIGO ORIGINAL
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
MAX_MEMORIA = 12

WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://web-production-606aff.up.railway.app")
WEBHOOK_PATH = "/telegram"
PORT = int(os.getenv("PORT", 8080))

if not WEBHOOK_BASE_URL.startswith("http"):
    WEBHOOK_BASE_URL = f"https://{WEBHOOK_BASE_URL}"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 🗄️ REDIS
# ═══════════════════════════════════════════════════════════════════════════════

try:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    logger.info(f"✅ Redis conectado")
except Exception as e:
    logger.error(f"❌ Falha ao conectar Redis: {e}")
    raise

def memory_key(uid): return f"memory:{uid}"
def heat_score_key(uid): return f"heat:{uid}"
def start_time_key(uid): return f"start_time:{uid}"
def wa_sent_key(uid): return f"wa_sent:{uid}"

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 HEATSCORE SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

HEAT_TRIGGERS = {
    "pediu_nude":          ["foto", "nude", "buceta", "periquita", "pau", "rola", "mostra", "manda foto", "nudes", "pelada"],
    "mandou_foto_pau":     ["pau", "rola", "foto", "enviou foto", "dick pic"],
    "roleplay":            ["meter", "foder", "chupar", "gozar", "transar", "buceta", "cu", "boquete", "mama", "fuder", "tesão"],
    "pediu_video":         ["video", "ao vivo", "call", "chamada", "vídeo sexo"],
    "falou_pagar":         ["pago", "pix", "quanto", "preço", "vip", "comprar", "valor", "custa", "pagar"],
    "mensagens_seguidas":  4,
    "tempo_longo":         20,
}

HEAT_POINTS = {
    "pediu_nude": 4,
    "mandou_foto_pau": 5,
    "roleplay": 6,
    "pediu_video": 5,
    "falou_pagar": 7,
    "mensagens_seguidas": 3,
    "tempo_longo": 3,
}

HEAT_THRESHOLD = 14

def calculate_heat_score(uid: int, text: str, has_photo: bool = False) -> int:
    score = int(r.get(heat_score_key(uid)) or 0)
    text_lower = text.lower()
    
    for key, triggers in HEAT_TRIGGERS.items():
        if isinstance(triggers, list):
            if any(t in text_lower for t in triggers):
                score += HEAT_POINTS.get(key, 0)
    
    if has_photo:
        score += 5
    
    msg_count = r.incr(f"msg_streak:{uid}")
    r.expire(f"msg_streak:{uid}", 300)
    if msg_count >= HEAT_TRIGGERS["mensagens_seguidas"]:
        score += HEAT_POINTS["mensagens_seguidas"]
    
    start_time = r.get(start_time_key(uid))
    if start_time:
        minutes = (datetime.now() - datetime.fromisoformat(start_time)).total_seconds() / 60
        if minutes > HEAT_TRIGGERS["tempo_longo"]:
            score += HEAT_POINTS["tempo_longo"]
    
    return min(score, 30)

def is_hot_lead(score: int) -> bool:
    return score >= HEAT_THRESHOLD

# ═══════════════════════════════════════════════════════════════════════════════
# 🤖 GROK (COM LOGS DETALHADOS)
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

async def get_grok_response(uid: int, user_message: str) -> str:
    prompt = build_prompt(uid)
    
    memory_raw = r.get(memory_key(uid))
    memory = json.loads(memory_raw) if memory_raw else []
    
    messages = [
        {"role": "system", "content": prompt},
        *memory[-MAX_MEMORIA:],
        {"role": "user", "content": user_message}
    ]
    
    logger.info(f"🤖 Chamando Grok API para {uid}...")
    logger.info(f"📝 Modelo: {MODELO_GROK}")
    logger.info(f"💬 Mensagens na memória: {len(memory)}")
    
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
                logger.info(f"📡 Grok status: {resp.status}")
                
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"❌ Grok error {resp.status}: {error_text}")
                    
                    # Tenta identificar o erro específico
                    if "model" in error_text.lower():
                        logger.error("⚠️ ERRO DE MODELO! Verifique se 'grok-3' está correto")
                    elif "auth" in error_text.lower() or "key" in error_text.lower():
                        logger.error("⚠️ ERRO DE AUTENTICAÇÃO! Verifique GROK_API_KEY")
                    
                    return "Caiu a ligação amor, repete? 😅"
                
                data = await resp.json()
                logger.info(f"✅ Grok respondeu com sucesso")
                
                response = data['choices'][0]['message']['content'].strip()
                logger.info(f"💬 Resposta: {response[:100]}")
                
                memory.append({"role": "user", "content": user_message})
                memory.append({"role": "assistant", "content": response})
                r.setex(memory_key(uid), 86400 * 7, json.dumps(memory[-MAX_MEMORIA:]))
                
                return response
    
    except asyncio.TimeoutError:
        logger.error(f"⏱️ Timeout na chamada do Grok")
        return "Demorou demais amor... tenta de novo? 🥺"
    except aiohttp.ClientError as e:
        logger.error(f"🌐 Erro de conexão com Grok: {e}")
        return "Deu ruim na conexão... manda de novo? 🥺"
    except Exception as e:
        logger.error(f"❌ Grok exception: {e}")
        logger.error(traceback.format_exc())
        return "Deu ruim aqui... manda de novo? 🥺"

# ═══════════════════════════════════════════════════════════════════════════════
# 📨 ENVIO DO WA
# ═══════════════════════════════════════════════════════════════════════════════

async def send_whatsapp_number(bot, chat_id, uid):
    if r.exists(wa_sent_key(uid)):
        logger.info(f"⚠️ WA já enviado antes para {uid}")
        return False
    
    number = random.choice(WA_NUMBERS)
    clean_number = number.replace('+', '').replace(' ', '')
    
    msg = f"""Olha amor... tô ficando molhada pra caralho conversando contigo 😩💦

Não aguento mais só mensagem aqui...

Meu número: `{number}`

Me chama de **Maya** pra eu saber que é tu 🔥

wa.me/{clean_number}"""

    try:
        await bot.send_message(chat_id=chat_id, text=msg, parse_mode='Markdown')
        r.setex(wa_sent_key(uid), 86400 * 30, "1")
        logger.info(f"🚀 WA ENVIADO → {uid} | Score: {r.get(heat_score_key(uid))} | Número: {number}")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao enviar WA para {uid}: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# 💬 HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username or "unknown"
    
    logger.info(f"🆕 /start do usuário: {uid} (@{username})")
    
    # Inicializa usuário
    r.set(start_time_key(uid), datetime.now().isoformat())
    r.set(heat_score_key(uid), 0)
    
    try:
        await update.message.reply_text(
            "Oi gato... 😏\n"
            "Finalmente alguém interessante por aqui 🔥\n\n"
            "Sou a Maya, e te garanto que não sou como as outras... 💋\n"
            "Tô louca pra saber o que você quer comigo 😈"
        )
        logger.info(f"✅ Resposta /start enviada para {uid}")
    except Exception as e:
        logger.error(f"❌ Erro /start para {uid}: {e}")
        logger.error(traceback.format_exc())

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username or "unknown"
    text = update.message.text or ""
    has_photo = bool(update.message.photo)
    
    logger.info(f"📨 Mensagem recebida de {uid} (@{username}): {text[:50]}")
    
    # Inicializa se não existe
    if not r.exists(start_time_key(uid)):
        r.set(start_time_key(uid), datetime.now().isoformat())
        r.set(heat_score_key(uid), 0)
        logger.info(f"🆕 Novo usuário (sem /start): {uid}")
    
    # Calcula score
    score = calculate_heat_score(uid, text, has_photo)
    r.set(heat_score_key(uid), score)
    
    logger.info(f"🔥 {uid} | Score: {score}/{HEAT_THRESHOLD}")
    
    # Se já enviou WA antes
    if r.exists(wa_sent_key(uid)):
        await update.message.reply_text("Tô te esperando no WA amor... vem logo 🔥")
        return
    
    # Responde via Grok
    try:
        logger.info(f"🤖 Chamando Grok para {uid}...")
        
        await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
        await asyncio.sleep(random.uniform(1.5, 2.5))
        
        response = await get_grok_response(uid, text)
        logger.info(f"✅ Grok respondeu para {uid}: {response[:50]}")
        
        await update.message.reply_text(response)
        logger.info(f"✅ Resposta enviada para {uid}")
        
    except Exception as e:
        logger.error(f"❌ Erro handler {uid}: {e}")
        logger.error(traceback.format_exc())
        await update.message.reply_text("Opa, bugou aqui... manda de novo? 😘")
    
    # Verifica se deve enviar WA
    if is_hot_lead(score):
        logger.info(f"🔥 {uid} atingiu limiar! Enviando WA...")
        await asyncio.sleep(2)
        await send_whatsapp_number(context.bot, update.effective_chat.id, uid)

# ═══════════════════════════════════════════════════════════════════════════════
# 🚀 SETUP COM EVENT LOOP
# ═══════════════════════════════════════════════════════════════════════════════

application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start_handler))
application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, message_handler))

app = Flask(__name__)

# Event loop global
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def start_loop():
    loop.run_forever()

threading.Thread(target=start_loop, daemon=True).start()

# ═══════════════════════════════════════════════════════════════════════════════
# 🌐 FLASK ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        logger.info(f"📥 Webhook recebido: update_id={data.get('update_id', 'N/A')}")
        
        if not data:
            logger.warning("⚠️ Webhook vazio")
            return 'ok', 200
        
        update = Update.de_json(data, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        
        return 'ok', 200
    except Exception as e:
        logger.exception(f"❌ Webhook erro: {e}")
        return 'error', 500

@app.route('/health', methods=['GET'])
def health():
    try:
        redis_status = r.ping()
        return jsonify({
            'status': 'ok',
            'redis': redis_status,
            'version': 'v9.0',
            'webhook_path': WEBHOOK_PATH,
            'modelo_grok': MODELO_GROK
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'error', 'redis': False, 'error': str(e)}), 500

@app.route('/set-webhook', methods=['GET'])
def set_webhook_route():
    try:
        webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
        
        async def setup():
            await application.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(1)
            success = await application.bot.set_webhook(webhook_url, allowed_updates=["message"])
            await asyncio.sleep(1)
            info = await application.bot.get_webhook_info()
            return success, info
        
        success, info = asyncio.run_coroutine_threadsafe(setup(), loop).result(timeout=15)
        
        return jsonify({
            'success': success,
            'webhook_url': info.url,
            'pending_updates': info.pending_update_count,
            'last_error': info.last_error_message
        }), 200
    except Exception as e:
        logger.error(f"❌ Erro set webhook: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/webhook-info', methods=['GET'])
def webhook_info_route():
    try:
        async def get_info():
            return await application.bot.get_webhook_info()
        
        info = asyncio.run_coroutine_threadsafe(get_info(), loop).result(timeout=10)
        return jsonify({
            'url': info.url,
            'pending_update_count': info.pending_update_count,
            'last_error_message': info.last_error_message,
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════════════════
# 🎬 STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

async def startup_sequence():
    try:
        logger.info("🚀 Iniciando Sophia Bot v9.0...")
        
        await application.initialize()
        await application.start()
        await asyncio.sleep(2)
        
        webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
        
        await application.bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
        
        success = await application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message"]
        )
        
        if success:
            info = await application.bot.get_webhook_info()
            logger.info(f"✅ Webhook configurado: {info.url}")
            logger.info(f"📊 Pending updates: {info.pending_update_count}")
        
        me = await application.bot.get_me()
        logger.info(f"🤖 Bot ativo: @{me.username} (ID: {me.id})")
        logger.info(f"🎯 Limiar WA: HeatScore ≥ {HEAT_THRESHOLD}")
        logger.info(f"🧠 Modelo Grok: {MODELO_GROK}")
        
    except Exception as e:
        logger.exception(f"💥 ERRO CRÍTICO: {e}")
        raise

if __name__ == "__main__":
    asyncio.run_coroutine_threadsafe(startup_sequence(), loop)
    
    logger.info(f"🌐 Flask rodando na porta {PORT}")
    logger.info("🚀 Sophia Bot v9.0 operacional!")
    
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
