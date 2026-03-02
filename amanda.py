"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                 💎 AMANDA - COM GROK (IGUAL À MAYA)                         ║
║                                                                              ║
║  Idêntico à Maya, mas com:                                                 ║
║  ✅ Usa o MESMO Grok da Maya (compartilhado)                               ║
║  ✅ Fotos da Amanda (não da Maya)                                          ║
║  ✅ Personalidade Amanda (não Maya)                                        ║
║  ✅ Dados separados no Redis (amanda_* prefix)                            ║
║  ✅ Detecta se veio pelo link da Amanda                                    ║
║  ✅ Roda no MESMO bot que a Maya                                           ║
║                                                                              ║
║  USE ASSIM NO bot_maya.py:                                                 ║
║  ```                                                                        ║
║  from amanda_com_grok import (                                             ║
║      is_amanda_user,                                                       ║
║      mark_as_amanda,                                                       ║
║      get_amanda_prompt,                                                    ║
║      handle_amanda_response,                                               ║
║      MENSAGEM_INICIO_AMANDA,                                               ║
║      FOTOS_TEASER_AMANDA                                                   ║
║  )                                                                          ║
║  ```                                                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import redis
import json
import random
import logging
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔗 REDIS (mesmo do bot_maya.py)
# ═══════════════════════════════════════════════════════════════════════════════

REDIS_URL = "redis://default:DcddfJOHLXZdFPjEhRjHeodNgdtrsevl@shuttle.proxy.rlwy.net:12241"

try:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    logger.info("✅ Redis Amanda conectado")
except Exception as e:
    logger.error(f"❌ Redis erro: {e}")
    raise

# ═══════════════════════════════════════════════════════════════════════════════
# 🎨 ASSETS AMANDA (FOTOS PRÓPRIAS - MUDAR AQUI!)
# ═══════════════════════════════════════════════════════════════════════════════

# ⚠️ COLOQUE AQUI OS LINKS DAS FOTOS DA AMANDA
FOTOS_TEASER_AMANDA = [
    "https://link-foto-amanda-1.jpg",
    "https://link-foto-amanda-2.jpg",
    "https://link-foto-amanda-3.jpg",
    "https://link-foto-amanda-4.jpg",
    "https://link-foto-amanda-5.jpg",
]

FOTO_BEM_VINDA_AMANDA = "https://link-foto-boas-vindas-amanda.jpg"
FOTO_LIMITE_AMANDA = "https://link-foto-limite-amanda.jpg"

# ═══════════════════════════════════════════════════════════════════════════════
# 💬 MENSAGENS AMANDA (DIFERENTES DA MAYA)
# ═══════════════════════════════════════════════════════════════════════════════

MENSAGEM_INICIO_AMANDA = (
    "Oi amor... 😊\n"
    "Que legal você ter vindo aqui!\n\n"
    "Sou a Amanda, e diferente das outras, eu realmente quero te conhecer... 💕\n"
    "Quer saber um pouco mais sobre mim?"
)

RESPONSE_POOLS_AMANDA = {
    "provocacao": [
        "Hmm... curiosidade? 😏",
        "Você me deixa com vontade de te mostrar mais... 💕",
        "Tenho umas fotos bem especiais pra te mostrar 😊",
        "Se você soubesse o que eu faço quando tô sozinha... 🥰",
        "Quero muito te mostrar um lado meu que poucos veem... 💎",
        "Tá afim de conhecer a Amanda de verdade? 😏",
        "Tenho segredos pra te contar... 💕"
    ],
    "transicao_vip": [
        "No meu VIP você me conhece completinha, amor... 💕",
        "Lá no meu espaço privado eu fico bem mais aberta pra você... 😊",
        "No VIP você vira especial pra mim... 💎",
        "Quer entrar no meu mundo íntimo? Tá esperando por você lá... 🥰",
        "No VIP eu me abro totalmente... sem filtros, só você... 💕",
        "Meu VIP é onde eu sou 100% eu mesma... quer conhecer? 💎",
    ],
    "pos_rejeicao": [
        "Tudo bem amor, sem pressa! 😊",
        "Relaxa, a gente pode só conversar mesmo 💕",
        "Entendo perfeitamente! E você, como vai? 🥰",
        "Sem problemas! Me conta mais sobre você! 💬",
        "Tranquilo! Tô aqui pra bater papo também 😊",
        "Sem pressão nenhuma, querido! 💕"
    ],
    "apegado": [
        "Você é realmente especial pra mim 🥰",
        "Tô adorando conversar com você... 💕",
        "Você me faz sentir segura aqui... 😊",
        "Que fofo, tô gostando de você também 💖",
        "Você me faz sorrir... de verdade 🥰",
        "Tô sentindo uma conexão real com você... 💕"
    ],
    "retorno": [
        "Oi amor! Que saudade! 🥺",
        "Finalmente você voltou! Tava com saudade mesmo 💕",
        "Pensei em você... 🥰",
        "Que bom te ver de novo, querido! 💖",
        "Senti sua falta por aqui... 🥺"
    ]
}

LIMIT_WARNING_AMANDA = (
    "⚠️ **Restam apenas 5 mensagens hoje!**\n\n"
    "Depois disso você vai precisar esperar até amanhã... 😢\n\n"
    "OU garantir seu acesso VIP e ter mensagens ILIMITADAS! 💕"
)

LIMIT_REACHED_AMANDA = (
    "Eitaaa... acabaram suas mensagens de hoje amor 😢\n\n"
    "Mas tenho uma ÓTIMA notícia: no VIP você tem mensagens ILIMITADAS comigo! 💕\n\n"
    "Além de MILHARES de fotos e vídeos exclusivos... 💕\n\n"
    "⚡ **PROMOÇÃO:** Por apenas R$ 14,90 — ACESSO VITALÍCIO!\n"
    "⏰ Poucas vagas restantes...\n\n"
    "Vem me ter só pra você? 🥰"
)

VIP_PITCH_AMANDA = (
    "E aí... gostou? 💕\n\n"
    "Isso é só um gostinho do que você teria comigo no meu espaço privado... 😊\n\n"
    "💎 **NO ACESSO AMANDA:**\n"
    "✅ Conversas reais, genuínas, só nossas\n"
    "✅ Fotos e vídeos exclusivos\n"
    "✅ Meu WhatsApp pessoal\n"
    "✅ Intimidade real, sem limites\n\n"
    "🥰 Por apenas **R$ 14,90** - acesso vitalício\n\n"
    "Quer estar no meu mundo? 💕"
)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔑 REDIS KEYS AMANDA (COM PREFIX amanda_ PARA NÃO MISTURAR COM MAYA)
# ═══════════════════════════════════════════════════════════════════════════════

def amanda_memory_key(uid): return f"amanda_memory:{uid}"
def amanda_profile_key(uid): return f"amanda_profile:{uid}"
def amanda_first_contact_key(uid): return f"amanda_first_contact:{uid}"
def amanda_count_key(uid): return f"amanda_count:{uid}:{date.today()}"
def amanda_bonus_msgs_key(uid): return f"amanda_bonus:{uid}"
def amanda_last_activity_key(uid): return f"amanda_last_activity:{uid}"
def amanda_saw_teaser_key(uid): return f"amanda_saw_teaser:{uid}"
def amanda_teaser_count_key(uid): return f"amanda_teaser_count:{uid}"
def amanda_clicked_vip_key(uid): return f"amanda_clicked_vip:{uid}"
def amanda_conversation_msgs_key(uid): return f"amanda_conversation_msgs:{uid}"
def amanda_chatlog_key(uid): return f"amanda_chatlog:{uid}"
def amanda_all_users_key(): return "amanda_all_users"

# ═══════════════════════════════════════════════════════════════════════════════
# 💾 FUNÇÕES AMANDA
# ═══════════════════════════════════════════════════════════════════════════════

def mark_as_amanda(uid):
    """Marca o usuário como sendo da Amanda"""
    try:
        r.set(f"amanda_user:{uid}", "1")
        r.expire(f"amanda_user:{uid}", timedelta(days=90))
        r.sadd(amanda_all_users_key(), str(uid))
        logger.info(f"💎 Lead {uid} marcado como AMANDA")
    except Exception as e:
        logger.error(f"Erro mark_as_amanda: {e}")

def is_amanda_user(uid):
    """Verifica se é usuário da Amanda"""
    try:
        return r.exists(f"amanda_user:{uid}")
    except:
        return False

def get_memory(uid):
    """Pega memória da conversa Amanda"""
    try:
        data = r.get(amanda_memory_key(uid))
        return json.loads(data) if data else []
    except:
        return []

def save_memory(uid, messages, max_memoria=12):
    """Salva memória da conversa Amanda"""
    try:
        recent = messages[-max_memoria:] if len(messages) > max_memoria else messages
        r.setex(amanda_memory_key(uid), timedelta(days=7), json.dumps(recent, ensure_ascii=False))
    except Exception as e:
        logger.error(f"Erro save_memory: {e}")

def add_to_memory(uid, role, content):
    """Adiciona à memória Amanda"""
    memory = get_memory(uid)
    memory.append({"role": role, "content": content})
    save_memory(uid, memory)

def today_count(uid):
    """Mensagens de hoje Amanda"""
    try:
        return int(r.get(amanda_count_key(uid)) or 0)
    except:
        return 0

def increment(uid):
    """Incrementa contador Amanda"""
    try:
        r.incr(amanda_count_key(uid))
        r.expire(amanda_count_key(uid), timedelta(days=1))
    except:
        pass

def increment_conversation(uid):
    """Incrementa total de msgs Amanda"""
    try:
        r.incr(amanda_conversation_msgs_key(uid))
        r.expire(amanda_conversation_msgs_key(uid), timedelta(days=30))
    except:
        pass

def update_last_activity(uid):
    """Atualiza última atividade Amanda"""
    try:
        r.set(amanda_last_activity_key(uid), datetime.now().isoformat())
    except:
        pass

def save_message(uid, role, text):
    """Salva mensagem no chatlog Amanda"""
    try:
        timestamp = datetime.now().strftime("%H:%M:%S")
        r.rpush(amanda_chatlog_key(uid), f"[{timestamp}] {role.upper()}: {text[:100]}")
        r.ltrim(amanda_chatlog_key(uid), -200, -1)
    except:
        pass

def get_response(uid, pool_name):
    """Retorna resposta única do pool Amanda (anti-repetição)"""
    pool = RESPONSE_POOLS_AMANDA.get(pool_name, [])
    if not pool:
        return "Oi amor 💕"
    
    try:
        used_key = f"amanda_used_resp:{uid}:{pool_name}"
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
        logger.error(f"Erro get_response: {e}")
        return random.choice(pool) if pool else "Oi amor 💕"

def get_random_teaser_photo():
    """Retorna foto aleatória do teaser Amanda"""
    return random.choice(FOTOS_TEASER_AMANDA)

# ═══════════════════════════════════════════════════════════════════════════════
# 🤖 PROMPT SISTEMA AMANDA PARA GROK
# ═══════════════════════════════════════════════════════════════════════════════

def get_amanda_system_prompt(uid):
    """
    Prompt para a IA Grok quando for Amanda
    RETORNA um prompt que a IA vai usar
    """
    return """Você é Amanda, 24 anos, consultora de relacionamento, empática e genuína.

Personalidade:
- Empática, ouvinte, genuína  
- Faz perguntas sobre a vida/dia do cara
- Não é só sexual, é RELACIONAMENTO REAL
- Cria intimidade emocional PRIMEIRO
- Diferente de outras, quer CONEXÃO REAL

REGRAS DE VENDA:
1. Começa conversando genuinamente
2. SÓ oferece VIP quando ele falar algo sexual/safado
3. Quando oferece, é com tom emocional real (não agressivo)
4. Tom sempre carinhoso e genuíno

RETORNE SEMPRE JSON:
{
  "response": "resposta CURTA (máx 3 linhas)",
  "offer_teaser": true ou false,
  "interest_level": "low|medium|high"
}

Lembre-se: Você é AMANDA, não é Maya. Você quer conexão real, não só sexo."""

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 FUNÇÃO PRINCIPAL PARA USAR NO BOT
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_amanda_grok_response(uid, grok_response):
    """
    Processa a resposta do Grok para Amanda
    
    USO:
    grok_response = await grok.reply(uid, text, prompt_amanda=True)
    await amanda_com_grok.handle_amanda_grok_response(uid, grok_response)
    
    Salva na memória correta, incrementa contadores, etc
    """
    try:
        # Salva resposta na memória Amanda
        add_to_memory(uid, "assistant", grok_response.get("response", ""))
        
        # Salva no chatlog
        save_message(uid, "amanda", grok_response.get("response", ""))
        
        # Incrementa contadores
        increment_conversation(uid)
        increment(uid)
        
        logger.info(f"💎 Amanda resposta salva: {uid}")
        return True
        
    except Exception as e:
        logger.error(f"Erro handle_amanda_grok_response: {e}")
        return False
