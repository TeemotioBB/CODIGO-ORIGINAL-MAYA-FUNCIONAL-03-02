"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                  🎭 PERSONAS CONFIG - Multi-Bot Support                     ║
║                                                                              ║
║  Gerencia múltiplas personas (Maya, Amanda, etc) em UM ÚNICO BOT             ║
║  - Detecta qual persona cada user usa                                       ║
║  - Aplica configs certas (respostas, fotos, prompts)                        ║
║  - Dados completamente separados no Redis                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import redis
import os
import logging

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# ⚙️ REDIS CONNECTION
# ═══════════════════════════════════════════════════════════════════════════════

REDIS_URL = os.getenv("REDIS_URL", "redis://default:password@host:port")

try:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    r.ping()
    logger.info("✅ Redis conectado (personas_config)")
except Exception as e:
    logger.error(f"❌ Erro Redis: {e}")
    raise

# ═══════════════════════════════════════════════════════════════════════════════
# 🎭 FUNÇÕES DE DETECÇÃO DE PERSONA
# ═══════════════════════════════════════════════════════════════════════════════

def get_user_persona(uid):
    """
    Retorna qual persona o usuário está usando.
    Padrão: "maya" se não definido
    """
    try:
        persona = r.get(f"user_persona:{uid}")
        return persona if persona else "maya"
    except:
        return "maya"

def set_user_persona(uid, persona):
    """
    Define qual persona o usuário está usando.
    Chamado quando ele clica no deep link.
    """
    try:
        valid_personas = ["maya", "amanda"]
        if persona not in valid_personas:
            persona = "maya"
        
        r.set(f"user_persona:{uid}", persona)
        logger.info(f"🎭 User {uid} persona set to: {persona}")
        return True
    except Exception as e:
        logger.error(f"Erro set_user_persona: {e}")
        return False

def is_maya_user(uid):
    return get_user_persona(uid) == "maya"

def is_amanda_user(uid):
    return get_user_persona(uid) == "amanda"

# ═══════════════════════════════════════════════════════════════════════════════
# 📋 CONFIGS POR PERSONA
# ═══════════════════════════════════════════════════════════════════════════════

PERSONA_CONFIGS = {
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 💼 MAYA - Consultoria/Coaching
    # ═══════════════════════════════════════════════════════════════════════════
    "maya": {
        "name": "Maya",
        "emoji": "💼",
        "nicho": "consultoria, coaching, negócios",
        "description": "Especialista em consultoria e coaching",
        "tone": "profissional e direto",
        
        # Mensagens
        "message_inicio": (
            "Oi gato... 😏\n"
            "Finalmente alguém interessante por aqui 🔥\n\n"
            "Sou a Maya, e te garanto que não sou como as outras... 💋\n"
            "Tô louca pra saber o que você quer comigo 😈"
        ),
        
        # Fotos (SUBSTITUA pelos links reais da sua Maya)
        "foto_boas_vindas": "https://i.postimg.cc/0NghLJD3/image.png",
        "foto_limite": "https://i.postimg.cc/x1V9sr0S/7e25cd9d465e4d90b6dc65ec18350d3f.jpg",
        
        "fotos_teaser": [
            "https://i.postimg.cc/ZqT4SrB9/32b94b657e4f467897744e01432bc7fb.jpg",
            "https://i.postimg.cc/DzBFy8Lx/a63c77aa55ed4a07aa7ec710ae12580c.jpg",
            "https://i.postimg.cc/KzW2Bw99/b6fe112c63c54f3ab3c800a2e5eb664d.jpg",
            "https://i.postimg.cc/7PcH2GdT/170bccb9b06a42d3a88d594757f85e88.jpg",
            "https://i.postimg.cc/XJ1Vxpv2/00e2c81a4960453f8554baeea091145e.jpg",
        ],
        
        # Vídeo de boas-vindas (file_id do Telegram)
        "video_boas_vindas": "BAACAgEAAxkBAAEDIhhpimNFnzssGJ8BSFE0onUYINKHnAACdQgAAo1pWUSKPuxK2bPRYjoE",
        
        # Audio (opcional)
        "audio_bem_vindo": None,
        
        # Links para VIP
        "vip_link": "https://t.me/Mayaoficial_bot",
        "vip_price": "R$ 14,90",
        
        # Mensagens de limite
        "limit_reached_msg": (
            "Eitaaa... acabaram suas mensagens de hoje amor 😢\n\n"
            "Mas tenho uma ÓTIMA notícia: no VIP você tem mensagens ILIMITADAS comigo! 💕\n\n"
            "Além de MILHARES de fotos e vídeos exclusivos sem censura... 🔥\n\n"
            "⚡ **PROMOÇÃO:** De R$ 39,90 por apenas R$14,90 — ACESSO VITALÍCIO!\n"
            "⏰ Poucas vagas restantes nesse preço...\n\n"
            "Tá esperando o quê pra me ter só pra você? 💕"
        ),
        
        "limit_warning_msg": (
            "⚠️ **Restam apenas 5 mensagens hoje!**\n\n"
            "Depois disso você vai precisar esperar até amanhã... 😢\n\n"
            "OU garantir seu acesso VIP e ter mensagens ILIMITADAS! 💕"
        ),
    },
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ✨ AMANDA - Lifestyle/Bem-estar
    # ═══════════════════════════════════════════════════════════════════════════
    "amanda": {
        "name": "Amanda",
        "emoji": "✨",
        "nicho": "lifestyle, bem-estar, fitness",
        "description": "Especialista em bem-estar e estilo de vida",
        "tone": "amigável e empático",
        
        # Mensagens
        "message_inicio": (
            "Oi lindeza... 💕\n"
            "Que legal você tá aqui! Sou a Amanda 😊\n\n"
            "Sou expert em bem-estar, lifestyle e tudo que te deixa mais bonita e confiante 🌸\n"
            "Tô louca pra conversar com você! 💖"
        ),
        
        # Fotos (SUBSTITUA pelos links reais da sua Amanda)
        "foto_boas_vindas": "https://i.postimg.cc/amanda_welcome.jpg",
        "foto_limite": "https://i.postimg.cc/amanda_limit.jpg",
        
        "fotos_teaser": [
            "https://i.postimg.cc/amanda_1.jpg",
            "https://i.postimg.cc/amanda_2.jpg",
            "https://i.postimg.cc/amanda_3.jpg",
            "https://i.postimg.cc/amanda_4.jpg",
            "https://i.postimg.cc/amanda_5.jpg",
        ],
        
        # Vídeo (opcional)
        "video_boas_vindas": None,
        
        # Audio (opcional)
        "audio_bem_vindo": None,
        
        # Links para VIP
        "vip_link": "https://t.me/Amandaoficial_bot",
        "vip_price": "R$ 14,90",
        
        # Mensagens de limite
        "limit_reached_msg": (
            "Eitaa... acabaram suas mensagens de hoje amor 😢\n\n"
            "Mas tenho uma ÓTIMA notícia: no VIP você tem mensagens ILIMITADAS comigo! 💕\n\n"
            "Além de CENTENAS de vídeos exclusivos de bem-estar, fitness e lifestyle... 🌸\n\n"
            "⚡ **PROMOÇÃO:** De R$ 39,90 por apenas R$14,90 — ACESSO VITALÍCIO!\n"
            "⏰ Poucas vagas restantes nesse preço...\n\n"
            "Vem fazer parte do meu mundo? 💖✨"
        ),
        
        "limit_warning_msg": (
            "⚠️ **Restam apenas 5 mensagens hoje!**\n\n"
            "Depois disso você vai precisar esperar até amanhã... 😢\n\n"
            "OU garantir seu acesso VIP e ter mensagens ILIMITADAS! 💕"
        ),
    }
}

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 FUNÇÕES GETTER (retornam config da persona correta)
# ═══════════════════════════════════════════════════════════════════════════════

def get_persona_config(uid):
    """Retorna a configuração completa da persona do usuário"""
    persona = get_user_persona(uid)
    return PERSONA_CONFIGS.get(persona, PERSONA_CONFIGS["maya"])

def get_persona_name(uid):
    config = get_persona_config(uid)
    return config["name"]

def get_persona_emoji(uid):
    config = get_persona_config(uid)
    return config["emoji"]

def get_inicio_message(uid):
    config = get_persona_config(uid)
    return config["message_inicio"]

def get_fotos_teaser(uid):
    config = get_persona_config(uid)
    return config["fotos_teaser"]

def get_foto_boas_vindas(uid):
    config = get_persona_config(uid)
    return config["foto_boas_vindas"]

def get_foto_limite(uid):
    config = get_persona_config(uid)
    return config["foto_limite"]

def get_video_boas_vindas(uid):
    config = get_persona_config(uid)
    return config.get("video_boas_vindas", None)

def get_vip_link(uid):
    config = get_persona_config(uid)
    return config["vip_link"]

def get_vip_price(uid):
    config = get_persona_config(uid)
    return config["vip_price"]

def get_limit_reached_message(uid):
    config = get_persona_config(uid)
    return config["limit_reached_msg"]

def get_limit_warning_message(uid):
    config = get_persona_config(uid)
    return config["limit_warning_msg"]

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 UTILS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_personas():
    """Retorna lista de todas as personas disponíveis"""
    return list(PERSONA_CONFIGS.keys())

def persona_exists(persona_name):
    """Verifica se uma persona existe"""
    return persona_name in PERSONA_CONFIGS

def get_persona_stats(persona_name):
    """Retorna estatísticas de uma persona"""
    if not persona_exists(persona_name):
        return None
    
    try:
        # Conta usuários dessa persona
        all_users = r.smembers("all_users")
        users_count = sum(1 for uid in all_users if get_user_persona(int(uid)) == persona_name)
        
        return {
            "name": persona_name,
            "total_users": users_count,
            "config": PERSONA_CONFIGS[persona_name]
        }
    except Exception as e:
        logger.error(f"Erro get_persona_stats: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# 🔧 SETUP UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════

def setup_persona_for_user(uid, persona="maya", deep_link_ref=""):
    """
    Setup completo de uma persona para um usuário novo.
    Chamado quando user clica no /start.
    """
    try:
        set_user_persona(uid, persona)
        
        logger.info(
            f"🎭 Setup persona para {uid}: {persona} "
            f"(ref: {deep_link_ref})"
        )
        
        return True
    except Exception as e:
        logger.error(f"Erro setup_persona_for_user: {e}")
        return False

def get_user_stats(uid):
    """Retorna stats do usuário com sua persona"""
    persona = get_user_persona(uid)
    config = get_persona_config(uid)
    
    return {
        "user_id": uid,
        "persona": persona,
        "persona_name": config["name"],
        "persona_emoji": config["emoji"],
    }

# ═══════════════════════════════════════════════════════════════════════════════
# 📝 DEBUG/LOG
# ═══════════════════════════════════════════════════════════════════════════════

def debug_user_persona(uid):
    """Print debug info de um usuário"""
    persona = get_user_persona(uid)
    config = get_persona_config(uid)
    
    debug_info = f"""
    🎭 DEBUG User {uid}
    ├─ Persona: {persona}
    ├─ Nome: {config['name']}
    ├─ Nicho: {config['nicho']}
    ├─ Tone: {config['tone']}
    ├─ VIP Link: {config['vip_link']}
    └─ VIP Price: {config['vip_price']}
    """
    
    logger.info(debug_info)
    return debug_info

def list_all_personas_info():
    """Lista info de todas as personas"""
    info = "🎭 PERSONAS DISPONÍVEIS:\n"
    for persona_name, config in PERSONA_CONFIGS.items():
        info += f"\n{config['emoji']} {persona_name.upper()}\n"
        info += f"  └─ {config['description']}\n"
    return info

# ═══════════════════════════════════════════════════════════════════════════════
# 🔐 VALIDAÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def validate_persona_config():
    """Valida se todas as personas têm campos obrigatórios"""
    required_fields = [
        "name", "emoji", "nicho", "description", "tone",
        "message_inicio", "foto_boas_vindas", "fotos_teaser",
        "vip_link", "vip_price", "limit_reached_msg", "limit_warning_msg"
    ]
    
    errors = []
    
    for persona_name, config in PERSONA_CONFIGS.items():
        for field in required_fields:
            if field not in config:
                errors.append(f"❌ {persona_name}: missing field '{field}'")
    
    if errors:
        logger.error("Validation errors in PERSONA_CONFIGS:")
        for error in errors:
            logger.error(f"  {error}")
        return False
    
    logger.info("✅ PERSONA_CONFIGS validado com sucesso!")
    return True

# Roda validação ao importar
try:
    validate_persona_config()
except:
    pass

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 INIT LOG
# ═══════════════════════════════════════════════════════════════════════════════

logger.info("✨ Personas Config Loaded")
logger.info(list_all_personas_info())
