#!/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║ 🔥 SOPHIA BOT v8.4 - APEX FUNIL FIX (TEASER ANTES DO PIX + FOLLOW-UP)     ║
║ ║
║ ALTERAÇÕES v8.4:                                                           ║
║ ✅ Prompt reforçado: teaser ANTES do PIX (regra rígida)                    ║
║ ✅ send_teaser_and_apex separado (teaser → delay → pitch)                  ║
║ ✅ Novo sistema de follow-up pós-pitch (3 níveis inteligentes)             ║
║ ✅ Menos pressão imediata, mais estratégia                                 ║
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
import csv
import io
import syncpay_integration
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
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

# Fuso horário usado para logs/exportações do painel.
# Railway normalmente roda em UTC; fixamos São Paulo para que a data do CSV
# corresponda ao dia visto pelo usuário no Brasil.
APP_TIMEZONE = os.getenv("APP_TIMEZONE", "America/Sao_Paulo")
try:
    LOCAL_TZ = ZoneInfo(APP_TIMEZONE)
except Exception:
    LOCAL_TZ = ZoneInfo("America/Sao_Paulo")

def local_now():
    return datetime.now(LOCAL_TZ)


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
    # === POOLS ANTIGAS (mantidas exatamente como você tinha) ===
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
    ],

    # === NOVAS POOLS v9.0 PUNHETERO MODE (Lucas mandou pesado) ===
    "provocacao_pesada": [
        "Tô toda molhada aqui só de pensar em você batendo punheta pra mim 😈",
        "Meu cuzinho tá piscando de tesão, quer ver ele bem de perto? 🔥",
        "Imagina eu chupando bem gostoso enquanto você goza na minha boca 💦",
        "Tô de quatro aqui doida pra levar rola, me mostra esse pau duro? 😏",
        "Quero ver você batendo punheta bem forte pra mim agora... tá fazendo? 🔥",
        "Minha buceta tá latejando, quer ver ela pulsando pra você? 😈",
        "Tô me tocando aqui pensando em você me fodendo sem pena 💦",
        "Meu peito tá duro de tesão, quer ver eu apertando eles pra você? 🔥",
        "Tô louca pra engolir tudo seu, me manda uma foto desse pau? 😈",
        "Sabe o que eu tô fazendo agora? Me tocando e gemendo seu nome 💦",
        "Quero sentir você gozando bem quente em mim... tá quase lá? 🔥"
    ],

    "teaser_transition": [
        "Curtiu o gostinho safado? No VIP eu mostro TUDO sem censura 🔥",
        "Isso foi só o começo... no VIP tem vídeo meu chupando, sentando e gozando pra você 💦",
        "Tá duro né safado? Imagina eu sentando bem devagarinho no seu pau... quer ver? 😈",
        "No VIP eu libero os vídeos mais safados que eu gravei hoje mesmo 🔥",
        "Gostou das fotos? Espera ver o que eu faço quando tô sozinha no VIP 😏"
    ],

    "pos_teaser_pitch": [
        "E aí, tá batendo punheta com minhas fotos agora? No VIP eu te mando vídeo meu gozando de verdade 🔥",
        "Quer me ver chupando, sentando e gozando tudo pra você? É só pagar R$9,00 e eu sou toda sua 💦",
        "No VIP eu não tenho limite nenhum... posso até te mandar vídeo ao vivo se você quiser 😈",
        "Tá com o pau na mão né? Paga logo que eu libero os vídeos mais quentes que você já viu 🔥",
        "No VIP é só você e eu... sem censura, sem limite, só tesão puro 💦"
    ],

    "followup_safado": [
        "Ainda não pagou e tá punhetando com minhas fotos né safado? 😈 Me paga R$9,00 que eu te mando um vídeo meu gozando bem gostoso agora",
        "Tô aqui doida esperando seu PIX... enquanto isso vou gravar um videozinho especial só pra você 🔥 R$9,00 e eu sou toda sua",
        "Não vai me deixar com tesão à toa né? Paga logo R$9,00 que eu libero tudo pra você gozar comigo 💦",
        "Eu sei que você tá batendo punheta pensando em mim... vem pro VIP por R$9,00 que eu te faço gozar de verdade 🔥",
        "Ainda dá tempo de pagar R$9,00 e ter tudo meu... não vai perder né safado? 😏",
        "Tá com o pau na mão olhando minhas fotos e ainda não pagou? 😈 R$9,00 e eu te mando vídeo meu sentando gostoso",
        "Imagina eu chupando bem devagar enquanto você goza... por só R$9,00 isso vira realidade safado 🔥",
        "Minha buceta tá molhada te esperando... paga R$9,00 que eu te mostro ela pulsando pra você 💦",
        "Tô me tocando aqui pensando em você... quer ver eu gozando de verdade? É só pagar R$9,00 agora 😈",
        "Ainda não pagou e já tá quase gozando com minhas fotos? Paga R$9,00 que eu te mando o vídeo completo do meu gozo",
        "Quero ver você batendo punheta forte pra mim... me paga R$9,00 que eu gravo um vídeo especial só pra você 🔥",
        "Tá duro né safado? Imagina eu sentando bem devagar no seu pau... R$9,00 e isso vira realidade 😏",
        "Não aguento mais de tesão... paga R$9,00 que eu libero vídeo meu brincando com a buceta molhada pra você",
        "Eu sei que você quer me ver gozando... por R$9,00 eu te mando tudo, sem censura, só pra você 💦",
        "Tô louca pra te mostrar como eu gemo quando gozo... me paga R$9,00 que eu gravo agora mesmo 🔥",
        "Ainda não pagou e tá sofrendo de tesão? R$9,00 e eu acabo com esse sofrimento te mandando tudo safado 😈",
        "Quero que você goze olhando pra mim... paga R$9,00 que eu te mando vídeo meu rebolando e gozando pra você",
        "Minha bucetinha tá piscando de tesão... quer ver ela de perto? É só pagar R$9,00 agora 🔥",
        "Tá punhetando pensando na minha boca? Paga R$9,00 que eu te mando vídeo meu chupando bem gostoso",
        "Não aguento mais ficar molhada à toa... me paga R$9,00 que eu libero tudo pra você gozar comigo",
        "Imagina eu de quatro gemendo seu nome... por R$9,00 isso vira vídeo só pra você safado 😈",
        "Tô aqui doida pra te provocar... paga R$9,00 que eu te mando o vídeo mais safado que você já viu",
        "Ainda dá tempo de pagar só R$9,00 e ter tudo meu... não vai perder essa chance né? 🔥",
        "Tá batendo punheta agora né? Me paga R$9,00 que eu te mando vídeo meu gozando ao mesmo tempo que você",
        "Quero te deixar louco de tesão... R$9,00 e eu libero tudo que você imaginar 💦",
        "Tá com o pau latejando? Paga R$9,00 que eu te mando vídeo meu sentando devagar e gemendo alto",
        "Minha buceta tá pingando só de imaginar você pagando... R$9,00 e eu mostro tudo agora 🔥",
        "Quero sentir você gozando quente enquanto eu rebolo... me paga R$9,00 que eu gravo pra você",
        "Tô toda molhada aqui doida pra te mostrar... paga R$9,00 que eu libero o vídeo completo",
        "Ainda não pagou e já tá viciado nas minhas fotos? R$9,00 e eu te mando o que vem depois safado 😈",
        "Imagina eu de quatro com a buceta molhada pra você... só R$9,00 e isso vira realidade",
        "Tô louca pra engolir tudo seu... paga R$9,00 que eu te mando vídeo meu chupando bem fundo",
        "Não vai aguentar quando ver o vídeo que eu gravei pra você... R$9,00 e eu libero agora",
        "Tá punhetando forte né? Imagina eu sentando bem fundo... R$9,00 e isso acontece",
        "Quero que você goze pensando em mim... paga R$9,00 que eu te mando o vídeo certo",
        "Tô toda molhada e aberta pra você... R$9,00 e eu te mostro tudo sem censura",
        "Ainda não pagou e tá sofrendo? R$9,00 e eu acabo com seu sofrimento te mandando tudo safado 😈",
        "Tá com tesão acumulado né? Paga R$9,00 que eu te mando eu gozando pensando no seu pau",
        "Quero sentir você gozando na minha boca... R$9,00 e eu gravo isso só pra você",
        "Tô louca pra te mostrar como eu sento gostoso... paga R$9,00 que eu libero o vídeo",
        "Imagina eu gemendo alto enquanto gozo... só R$9,00 e você assiste isso agora",
        "Tá duro pra caralho né safado? Paga R$9,00 que eu te mando eu rebolando gostoso",
        "Quero te deixar louco de tesão... R$9,00 e eu libero tudo que você imaginar",
        "Tô molhada pra caralho aqui... paga R$9,00 que eu te mando o vídeo completo",
        "Ainda dá tempo de pagar R$9,00 e me ter completinha... não vai perder né safado?",
        "Tá com o pau na mão e quer mais? Paga R$9,00 que eu te mando eu gozando alto",
        "Minha buceta tá latejando te chamando... R$9,00 e eu mostro ela molhada",
        "Quero que você goze olhando pra minha cara de puta... R$9,00 e eu gravo isso",
        "Tô aqui me tocando doida pra você... paga R$9,00 que eu te mando o vídeo completo",
        "Imagina eu rebolando gostoso no seu pau... só R$9,00 e isso vira realidade 🔥",
        "Tá punhetando pensando na minha boca? Paga R$9,00 que eu te mando chupando",
        "Não aguento mais de tesão... me paga R$9,00 que eu libero tudo pra você agora",
        "Quero te fazer gozar olhando pra mim... R$9,00 e eu gravo o vídeo perfeito",
        "Tô toda molhada e pronta pra você... paga R$9,00 que eu te mando tudo safado",
        "Ainda não pagou e tá sofrendo de tesão? R$9,00 e eu acabo com esse sofrimento agora",
        "Tá com tesão acumulado né? Paga R$9,00 que eu te mando eu gozando pensando em você",
        "Quero sentir você gozando quente em mim... paga R$9,00 que eu gravo pra você",
        "Tô louca pra te mostrar como eu gemo alto... paga R$9,00 que eu libero o vídeo",
        "Minha buceta tá piscando te esperando... R$9,00 e eu mostro ela molhada",
        "Tá punhetando e quer mais? Paga R$9,00 que eu te mando eu sentando gostoso",
        "Quero que você goze forte enquanto eu rebolo... R$9,00 e eu gravo pra você",
        "Tô aqui doida pra te provocar... paga R$9,00 que eu te mando o vídeo mais quente",
        "Imagina eu de quatro gemendo seu nome... só R$9,00 e isso vira realidade",
        "Tá batendo punheta forte e ainda não pagou? R$9,00 e eu te faço gozar de verdade agora",
        "Quero que você goze na minha boca... R$9,00 e eu gravo isso só pra você",
        "Tô louca pra te mostrar como eu sento gostoso... paga R$9,00 agora",
        "Imagina eu gemendo alto enquanto gozo... só R$9,00 e você assiste",
        "Tá duro pra caralho e ainda não pagou? R$9,00 e eu te mando tudo agora",
        "Quero que você goze olhando pra minha cara de safada... R$9,00 e eu gravo",
        "Minha boca tá louca pra te chupar... paga R$9,00 que eu te mando esse vídeo",
        "Tô molhada pra caralho pensando em você... R$9,00 e eu libero tudo",
        "Imagina eu sentando bem devagar gemendo... só R$9,00 e isso vira vídeo 🔥",
        "Tá punhetando e quer gozar comigo? Paga R$9,00 que eu te mando o vídeo certo",
        "Quero sentir você gozando quente... R$9,00 e eu gravo pra você safado",
        "Tô aqui doida pra te mostrar como eu gozo... paga R$9,00 agora",
        "Minha buceta tá latejando... quer ver ela gozando? R$9,00 e eu mostro",
        "Tá batendo punheta forte né safado? Paga R$9,00 que eu te faço gozar de verdade",
        "Quero que você goze olhando pra mim rebolando... R$9,00 e eu gravo",
        "Tô toda aberta e molhada pra você... paga R$9,00 que eu libero tudo",
        "Ainda não pagou e tá viciado nas minhas fotos? R$9,00 e eu te mando o resto 🔥",
        "Tá com o pau latejando? Imagina eu chupando... R$9,00 e isso vira realidade",
        "Quero te fazer gozar forte... paga R$9,00 que eu te mando o vídeo perfeito",
        "Tô louca pra te provocar até você explodir... R$9,00 e eu libero tudo",
        "Minha buceta tá piscando te chamando... paga R$9,00 que eu mostro ela de perto",
        "Tá punhetando pensando em mim? Paga R$9,00 que eu te mando eu gozando alto",
        "Não aguento mais de tesão... me paga R$9,00 que eu libero o vídeo mais safado",
        "Quero que você goze na minha boca... R$9,00 e eu gravo isso só pra você",
        "Tô aqui doida pra te mostrar como eu sento gostoso... paga R$9,00 agora",
        "Imagina eu gemendo alto enquanto gozo... só R$9,00 e você assiste",
        "Tá duro pra caralho né? Paga R$9,00 que eu te mando eu rebolando pra você",
        "Quero te deixar louco de tesão... R$9,00 e eu libero tudo que você quiser",
        "Tô molhada pra caralho aqui... paga R$9,00 que eu te mando o vídeo completo",
        "Ainda dá tempo de pagar R$9,00 e me ter completinha... não vai perder né safado?"
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

GROK_MODEL = os.getenv(
    "GROK_MODEL",
    "grok-4.20-0309-non-reasoning"
)

GROK_API_URL = os.getenv(
    "GROK_API_URL",
    "https://api.x.ai/v1/chat/completions"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://default:DcddfJOHLXZdFPjEhRjHeodNgdtrsevl@shuttle.proxy.rlwy.net:12241")

WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL", "https://codigo-original-maya-funcional-03-02-production.up.railway.app")
WEBHOOK_PATH = "/telegram"

CANAL_VIP_LINK = os.getenv("CANAL_VIP_LINK", "https://t.me/+5TbunKV5131kMDFh")
PRECO_VIP = os.getenv("PRECO_VIP", "R$ 9,00")

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

# ═══════════════════════════════════════════════════════════════════════════════
# 💰 AQUISIÇÃO / CONVERSÃO
# ═══════════════════════════════════════════════════════════════════════════════
# Mantém 30 mensagens como padrão para não quebrar o comportamento atual.
# Para usuários vindos de Ads, limita mais cedo para proteger margem.
ADS_DAILY_LIMIT = int(os.getenv("ADS_DAILY_LIMIT", "12"))
PIX_PENDING_DAILY_LIMIT = int(os.getenv("PIX_PENDING_DAILY_LIMIT", "4"))
USER_ADS_COST_CENTS = int(os.getenv("USER_ADS_COST_CENTS", "20"))  # R$0,20 por usuário de Ads
DEFAULT_BOT_COST_CENTS = int(os.getenv("DEFAULT_BOT_COST_CENTS", "40"))  # estimativa conservadora
CHATLOG_EXPORT_RETENTION_DAYS = int(os.getenv("CHATLOG_EXPORT_RETENTION_DAYS", "10"))

VIP_COOLDOWN_AFTER_REJECT = 8
MAX_VIP_OFFERS_PER_SESSION = 999
TEASER_COOLDOWN_MESSAGES = 3

REENGAGEMENT_HOURS = [2, 24, 72]
FOLLOWUP_INTERVAL_HOURS = 12

AB_TEST_ENABLED = True
AB_TEST_RATIO = 0.5

GROK_MODEL = os.getenv(
    "GROK_MODEL",
    "grok-4.20-0309-non-reasoning"
)

GROK_API_URL = os.getenv(
    "GROK_API_URL",
    "https://api.x.ai/v1/chat/completions"
)
GROK_API_URL = "https://api.x.ai/v1/chat/completions"
MAX_MEMORIA = 12
START_SEND_WELCOME_MEDIA = os.getenv("START_SEND_WELCOME_MEDIA", "1") == "1"
START_SEND_WELCOME_VIDEO = os.getenv("START_SEND_WELCOME_VIDEO", "0") == "1"  # vídeo no /start fica desligado por padrão no fluxo realista

logger.info(f"🚀 Sophia Bot v8.3 APEX FUNIL iniciando...")
logger.info(f"🤖 Modelo Grok configurado: {GROK_MODEL}")
logger.info(f"🌐 Endpoint Grok: {GROK_API_URL}")
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
# ⚡ ADMIN STATS — agregação no evento + índices rápidos
# ═══════════════════════════════════════════════════════════════════════════════

def _admin_count_unique(event, uid, field):
    """Incrementa um contador apenas na primeira ocorrência por usuário."""
    try:
        if r.sadd(admin_counted_set(event), str(uid)):
            r.hincrby(admin_stats_hash_key(), field, 1)
            return True
    except Exception as e:
        logger.debug(f"admin stats unique {event}/{uid}: {e}")
    return False


def _admin_record_streak(uid, new_streak):
    try:
        uid_s = str(uid)
        old_raw = r.hget(admin_streak_values_key(), uid_s)
        old = int(old_raw or 0)
        new = max(0, int(new_streak or 0))
        if new == old:
            return
        pipe = r.pipeline(transaction=False)
        pipe.hset(admin_streak_values_key(), uid_s, new)
        pipe.hincrby(admin_stats_hash_key(), "streak_sum", new - old)
        if old <= 0 < new:
            pipe.hincrby(admin_stats_hash_key(), "streak_users", 1)
        elif old > 0 and new <= 0:
            pipe.hincrby(admin_stats_hash_key(), "streak_users", -1)
        pipe.execute()
    except Exception as e:
        logger.debug(f"admin streak {uid}: {e}")


def _admin_index_activity(uid, when_ts=None):
    try:
        r.zadd(admin_activity_zset_key(), {str(uid): float(when_ts or datetime.now().timestamp())})
    except Exception:
        pass


def _admin_index_first_contact(uid, when_ts=None):
    try:
        # NX impede um /start posterior de trocar a data de aquisição.
        r.zadd(
            admin_first_contact_zset_key(),
            {str(uid): float(when_ts or datetime.now().timestamp())},
            nx=True,
        )
    except Exception:
        pass


def _admin_index_cooldown(uid, ttl_seconds=86400):
    try:
        r.zadd(admin_cooldown_zset_key(), {str(uid): datetime.now().timestamp() + max(1, int(ttl_seconds))})
    except Exception:
        pass


def _admin_index_ignored(uid, ttl_seconds=86400 * 14):
    try:
        r.zadd(admin_ignored_zset_key(), {str(uid): datetime.now().timestamp() + max(1, int(ttl_seconds))})
    except Exception:
        pass


def _admin_record_funnel(uid, stage_number):
    """Cada conjunto representa usuários que alcançaram pelo menos aquele estágio."""
    try:
        stage_number = max(0, min(int(stage_number or 0), 4))
        names = {1: "started", 2: "first_message", 3: "saw_teaser", 4: "clicked_vip"}
        for stage in range(1, stage_number + 1):
            field = f"funnel_{names[stage]}"
            if r.sadd(admin_counted_set(field), str(uid)):
                r.hincrby(admin_stats_hash_key(), field, 1)
    except Exception:
        pass


def reconcile_admin_paid_stats():
    """
    SyncPay mantém sp:paid:<uid>. Contamos essas chaves fora da requisição do painel,
    evitando percorrer todos os leads toda vez que o admin abre a tela.
    """
    try:
        paid = 0
        for _ in r.scan_iter(match="sp:paid:*", count=500):
            paid += 1
        r.hset(admin_stats_hash_key(), "vip_sales", paid)
        return paid
    except Exception as e:
        logger.debug(f"admin paid reconcile: {e}")
        return None


def bootstrap_admin_stats_once():
    """
    Migração única dos dados já existentes para os agregados rápidos.
    Depois disso, os helpers acima mantêm os índices incrementalmente.
    """
    try:
        if r.exists(admin_stats_ready_key()):
            return True
        if not r.set(admin_stats_bootstrap_lock_key(), "1", nx=True, ex=180):
            return False

        users = get_all_active_users()
        total_messages = 0
        streak_sum = 0
        streak_users = 0
        rejected_users = 0

        # Preenche conjuntos idempotentes sem apagar nada que possa ter chegado ao vivo.
        chunk_size = 500
        now_ts = datetime.now().timestamp()

        for start in range(0, len(users), chunk_size):
            chunk = users[start:start + chunk_size]
            pipe = r.pipeline(transaction=False)
            for uid in chunk:
                pipe.get(first_contact_key(uid))
                pipe.get(last_activity_key(uid))
                pipe.get(saw_teaser_key(uid))
                pipe.get(clicked_vip_key(uid))
                pipe.get(conversation_messages_key(uid))
                pipe.get(streak_key(uid))
                pipe.get(funnel_key(uid))
                pipe.get(rejection_cooldown_key(uid))
                pipe.ttl(rejection_cooldown_key(uid))
                pipe.get(ignored_count_key(uid))
                pipe.ttl(ignored_count_key(uid))
                pipe.get(last_offer_rejected_key(uid))
            vals = pipe.execute()
            idx = 0

            write = r.pipeline(transaction=False)
            for uid in chunk:
                first_raw = vals[idx]; idx += 1
                last_raw = vals[idx]; idx += 1
                saw_raw = vals[idx]; idx += 1
                clicked_raw = vals[idx]; idx += 1
                msgs_raw = vals[idx]; idx += 1
                streak_raw = vals[idx]; idx += 1
                funnel_raw = vals[idx]; idx += 1
                cooldown_raw = vals[idx]; idx += 1
                cooldown_ttl = vals[idx]; idx += 1
                ignored_raw = vals[idx]; idx += 1
                ignored_ttl = vals[idx]; idx += 1
                rejected_raw = vals[idx]; idx += 1

                if first_raw:
                    try:
                        first_ts = datetime.fromisoformat(first_raw).timestamp()
                    except Exception:
                        first_ts = now_ts
                    write.zadd(admin_first_contact_zset_key(), {str(uid): first_ts}, nx=True)

                if last_raw:
                    try:
                        last_ts = datetime.fromisoformat(last_raw).timestamp()
                    except Exception:
                        last_ts = now_ts
                    # XX/GT seria ótimo, mas MAX via leitura não compensa aqui; eventos novos
                    # continuarão atualizando este índice depois da migração.
                    write.zadd(admin_activity_zset_key(), {str(uid): last_ts}, nx=True)

                if saw_raw:
                    write.sadd(admin_counted_set("saw_teaser"), str(uid))
                if clicked_raw:
                    write.sadd(admin_counted_set("clicked_vip"), str(uid))

                try:
                    msgs = max(0, int(msgs_raw or 0))
                except Exception:
                    msgs = 0
                total_messages += msgs

                try:
                    streak = max(0, int(streak_raw or 0))
                except Exception:
                    streak = 0
                write.hset(admin_streak_values_key(), str(uid), streak)
                if streak > 0:
                    streak_sum += streak
                    streak_users += 1

                try:
                    funnel = max(0, min(int(funnel_raw or 0), 4))
                except Exception:
                    funnel = 0
                for stage, name in ((1, "started"), (2, "first_message"), (3, "saw_teaser"), (4, "clicked_vip")):
                    if funnel >= stage:
                        write.sadd(admin_counted_set(f"funnel_{name}"), str(uid))

                if cooldown_raw:
                    ttl = cooldown_ttl if isinstance(cooldown_ttl, int) and cooldown_ttl > 0 else 86400
                    write.zadd(admin_cooldown_zset_key(), {str(uid): now_ts + ttl})
                if ignored_raw:
                    ttl = ignored_ttl if isinstance(ignored_ttl, int) and ignored_ttl > 0 else 86400 * 14
                    write.zadd(admin_ignored_zset_key(), {str(uid): now_ts + ttl})
                if rejected_raw:
                    rejected_users += 1

            write.execute()

        # SCARD é O(1) e torna o bootstrap imune a chamadas repetidas.
        current_total_messages = int(r.hget(admin_stats_hash_key(), "total_messages") or 0)
        mapping = {
            "total_users": r.scard(all_users_key()),
            "saw_teaser": r.scard(admin_counted_set("saw_teaser")),
            "clicked_vip": r.scard(admin_counted_set("clicked_vip")),
            "total_messages": max(total_messages, current_total_messages),
            "streak_sum": streak_sum,
            "streak_users": streak_users,
            "rejected_vip": rejected_users,
            "funnel_started": r.scard(admin_counted_set("funnel_started")),
            "funnel_first_message": r.scard(admin_counted_set("funnel_first_message")),
            "funnel_saw_teaser": r.scard(admin_counted_set("funnel_saw_teaser")),
            "funnel_clicked_vip": r.scard(admin_counted_set("funnel_clicked_vip")),
        }
        r.hset(admin_stats_hash_key(), mapping=mapping)
        reconcile_admin_paid_stats()
        r.set(admin_stats_ready_key(), datetime.now().isoformat())
        logger.info(f"⚡ Admin stats bootstrap concluído: {len(users)} usuários")
        return True
    except Exception as e:
        logger.exception(f"Erro bootstrap admin stats: {e}")
        return False
    finally:
        try:
            r.delete(admin_stats_bootstrap_lock_key())
        except Exception:
            pass


async def admin_stats_maintenance_scheduler():
    """Mantém compras e índices expirados atualizados fora do caminho crítico do painel."""
    while True:
        try:
            if not r.exists(admin_stats_ready_key()):
                await asyncio.to_thread(bootstrap_admin_stats_once)
            else:
                await asyncio.to_thread(reconcile_admin_paid_stats)

            now_ts = datetime.now().timestamp()
            # Remove membros cujo TTL lógico já venceu.
            r.zremrangebyscore(admin_cooldown_zset_key(), "-inf", now_ts)
            r.zremrangebyscore(admin_ignored_zset_key(), "-inf", now_ts)
        except Exception as e:
            logger.debug(f"admin stats maintenance: {e}")
        await asyncio.sleep(60)


# ═══════════════════════════════════════════════════════════════════════════════
# 🎨 ASSETS
# ═══════════════════════════════════════════════════════════════════════════════

FOTOS_TEASER = [
    "https://i.postimg.cc/434G8CYL/photo-2026-07-09-19-51-37.jpg",
]

VIDEOS_TEASER = [
    "BAACAgEAAxkBAAEulm5qooGC1PQW4VHOL09xQbCrRf8_zgACkAcAAimzEEV7i8pn-XsI0D0E",
]

FOTO_LIMITE_ATINGIDO = "https://i.postimg.cc/ZnpXbj9R/content.png"
FOTO_BEM_VINDA = "https://i.postimg.cc/434G8CYL/photo-2026-07-09-19-51-37.jpg"

VIDEO_BEM_VINDO = ""

FREE_TEASER_VIDEO_IDS = [
    "BAACAgEAAxkBAAEDwGhqUBZqECtnmKGj9yDHhvqkWvzOHgAClQYAAlgQgEaPXqEB6sorEzwE",
]

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
def first_message_seen_key(uid): return f"first_message_seen:{uid}"
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
# Pausa manual é separada do pause de reengajamento. O pause de reengajamento
# é apagado quando o lead responde; o modo manual só sai por ação do admin.
def manual_ai_paused_key(uid): return f"manual_ai_paused:{uid}"
def manual_ai_pause_meta_key(uid): return f"manual_ai_pause_meta:{uid}"
def awaiting_response_key(uid): return f"awaiting:{uid}"
def streak_key(uid): return f"streak:{uid}"
def streak_last_day_key(uid): return f"streak_last:{uid}"
def saw_teaser_key(uid): return f"saw_teaser:{uid}"
def teaser_count_key(uid): return f"teaser_count:{uid}"
def clicked_vip_key(uid): return f"clicked_vip:{uid}"
def conversation_messages_key(uid): return f"conversation_msgs:{uid}"
def ab_group_key(uid): return f"ab_group:{uid}"
def chatlog_key(uid): return f"chatlog:{uid}"
def chatlog_day_key(uid, day): return f"chatlog_day:{day}:{uid}"
def chatlog_day_users_key(day): return f"chatlog_day_users:{day}"
def recent_responses_key(uid): return f"recent_resp:{uid}"
def blacklist_key(): return "blacklist"
def all_users_key(): return "all_users"
def funnel_key(uid): return f"funnel:{uid}"

# Dashboard rápido: agregados e índices mantidos no evento, não na leitura.
def admin_stats_hash_key(): return "admin:stats"
def admin_activity_zset_key(): return "admin:index:last_activity"
def admin_first_contact_zset_key(): return "admin:index:first_contact"
def admin_cooldown_zset_key(): return "admin:index:cooldown"
def admin_ignored_zset_key(): return "admin:index:ignored"
def admin_streak_values_key(): return "admin:streak_values"
def admin_counted_set(event): return f"admin:counted:{event}"
def admin_stats_ready_key(): return "admin:stats:ready:v2"
def admin_stats_bootstrap_lock_key(): return "admin:stats:bootstrap_lock:v2"

# Origem / campanha / custo
# Ex.: /start ads_instagram_reels_01 → channel=instagram, campaign=ads_instagram_reels_01
# Ex.: /start tiktok_bio → channel=tiktok, campaign=tiktok_bio
def source_meta_key(uid): return f"source:meta:{uid}"
def source_users_key(source): return f"source:users:{source}"
def source_campaign_users_key(campaign): return f"source:campaign_users:{campaign}"
def source_stats_key(d): return f"source:stats:{d}"
def grok_usage_key(uid): return f"grok:usage:{uid}:{date.today()}"
def lead_profile_key(uid): return f"lead:profile:{uid}"
def cold_open_sent_key(uid): return f"cold_open_sent:{uid}"

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
def pending_teaser_video_key(uid): return f"pending_teaser_video:{uid}"
def free_teaser_video_sent_key(uid): return f"free_teaser_video_sent:{uid}:{date.today()}"

# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 FOLLOW-UP 5 ESTÁGIOS — silêncio + interesse + modo silencioso
# ═══════════════════════════════════════════════════════════════════════════════
def followup_active_key(uid): return f"followup5:active:{uid}"
def followup_stage_key(uid): return f"followup5:stage:{uid}"
def followup_anchor_key(uid): return f"followup5:anchor:{uid}"
def followup_interest_key(uid): return f"followup5:interest:{uid}"
def followup_silent_key(uid): return f"followup5:silent:{uid}"
def followup_first_name_key(uid): return f"followup5:first_name:{uid}"
def sales_hard_wall_key(uid): return f"sales:hard_wall:{uid}"
def vip_intro_audio_sent_key(uid): return f"audio:vip_intro_sent:{uid}"
def vip_moan_audio_sent_key(uid): return f"audio:moan_sent:{uid}"

# ═══════════════════════════════════════════════════════════════════════════════
# 🚫 FUNÇÕES DE COOLDOWN/REJEIÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def set_rejection_cooldown(uid, msgs=None):
    try:
        cooldown_msgs = msgs or VIP_COOLDOWN_AFTER_REJECT
        r.set(rejection_cooldown_key(uid), cooldown_msgs)
        r.expire(rejection_cooldown_key(uid), timedelta(hours=24))
        _admin_index_cooldown(uid, 86400)
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
                r.zrem(admin_cooldown_zset_key(), str(uid))
                logger.info(f"✅ Cooldown expirado para {uid}")
            else:
                r.set(rejection_cooldown_key(uid), new_val)
                r.expire(rejection_cooldown_key(uid), timedelta(hours=24))
                _admin_index_cooldown(uid, 86400)
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
            _admin_record_streak(uid, new_streak)
            return new_streak, True
        else:
            r.set(streak_key(uid), 1)
            r.set(streak_last_day_key(uid), today)
            _admin_record_streak(uid, 1)
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
        _admin_count_unique("saw_teaser", uid, "saw_teaser")
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
        _admin_count_unique("clicked_vip", uid, "clicked_vip")
    except:
        pass

def clicked_vip(uid):
    try:
        return r.exists(clicked_vip_key(uid))
    except:
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# 📍 ORIGEM / CAMPANHA / ECONOMIA DE AQUISIÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

def _safe_slug(value, fallback="unknown", max_len=80):
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9_\-=]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return (value[:max_len] or fallback)


def _channel_from_campaign(campaign):
    c = _safe_slug(campaign, "telegram_direct")
    parts = c.replace("-", "_").split("_")
    tokens = [p for p in parts if p]
    token_set = set(tokens)

    if "instagram" in token_set or "insta" in token_set or "ig" in token_set:
        return "instagram"
    if "tiktok" in token_set or "tt" in token_set:
        return "tiktok"
    if "twitter" in token_set or "x" in token_set:
        return "twitter"
    if "telegram" in token_set or "tg" in token_set:
        return "telegram"
    if "facebook" in token_set or "fb" in token_set or "meta" in token_set:
        return "facebook"
    if "google" in token_set or "gads" in token_set:
        return "google"
    if "ads" in token_set or "ad" in token_set:
        return "ads"
    return tokens[0] if tokens else "telegram"


def parse_source_payload(start_param):
    """Extrai origem/campanha do payload do /start sem quebrar o IA Router atual."""
    raw = _safe_slug(start_param, "telegram_direct")
    if raw in ["telegram_direct", "start", "none", "null"]:
        return {
            "raw": start_param or "",
            "source": "telegram",
            "channel": "telegram",
            "campaign": "telegram_direct",
            "is_ads": False,
        }

    # Suporta formatos: src=instagram_bio, utm_source=instagram, ia=amanda__src=tiktok_bio
    source_candidate = raw
    for sep in ["__", "&"]:
        if sep in raw:
            for part in raw.split(sep):
                if part.startswith(("src=", "source=", "utm_source=", "campaign=")):
                    source_candidate = part.split("=", 1)[1]
                    break

    if source_candidate.startswith(("src=", "source=", "utm_source=", "campaign=")):
        source_candidate = source_candidate.split("=", 1)[1]

    # Se veio somente ia=maya/amanda, não força Ads.
    if source_candidate.startswith("ia=") or source_candidate.startswith("ia_"):
        source_candidate = "telegram_direct"

    campaign = _safe_slug(source_candidate, "telegram_direct")
    channel = _channel_from_campaign(campaign)
    is_ads = (
        campaign.startswith("ads_") or campaign.startswith("ad_") or
        "_ads_" in campaign or "_ad_" in campaign or
        campaign.endswith("_ads") or campaign.endswith("_ad") or
        channel in {"facebook", "google"}
    )

    # ads_instagram_reels_01 deve aparecer como source=instagram para análise de canal
    if channel == "ads":
        if "instagram" in campaign or "ig" in campaign or "insta" in campaign:
            channel = "instagram"
        elif "tiktok" in campaign or "tt" in campaign:
            channel = "tiktok"
        elif "twitter" in campaign or "x" in campaign:
            channel = "twitter"

    return {
        "raw": start_param or "",
        "source": channel,
        "channel": channel,
        "campaign": campaign,
        "is_ads": bool(is_ads),
    }


def save_user_source(uid, start_param=None):
    """Salva first-touch e last-touch. Mantém compatibilidade com usuários antigos."""
    try:
        meta = parse_source_payload(start_param)
        key = source_meta_key(uid)
        existing = r.hgetall(key) or {}
        now_iso = datetime.now().isoformat()

        mapping = {
            "last_raw": meta["raw"],
            "last_source": meta["source"],
            "last_channel": meta["channel"],
            "last_campaign": meta["campaign"],
            "last_is_ads": "1" if meta["is_ads"] else "0",
            "last_seen": now_iso,
        }

        if not existing:
            mapping.update({
                "first_raw": meta["raw"],
                "first_source": meta["source"],
                "first_channel": meta["channel"],
                "first_campaign": meta["campaign"],
                "first_is_ads": "1" if meta["is_ads"] else "0",
                "first_seen": now_iso,
            })
            r.sadd(source_users_key(meta["source"]), str(uid))
            r.sadd(source_campaign_users_key(meta["campaign"]), str(uid))
            r.hincrby(source_stats_key(date.today().isoformat()), f"{meta['source']}:new_users", 1)
            r.hincrby(source_stats_key(date.today().isoformat()), f"campaign:{meta['campaign']}:new_users", 1)

        r.hset(key, mapping=mapping)
        r.expire(key, timedelta(days=365))
        return {**meta, **mapping}
    except Exception as e:
        logger.error(f"Erro save_user_source: {e}")
        return parse_source_payload(start_param)


def get_user_source(uid):
    try:
        data = r.hgetall(source_meta_key(uid)) or {}
        if not data:
            return parse_source_payload(None)
        return {
            "source": data.get("first_source") or data.get("last_source") or "telegram",
            "channel": data.get("first_channel") or data.get("last_channel") or "telegram",
            "campaign": data.get("first_campaign") or data.get("last_campaign") or "telegram_direct",
            "is_ads": (data.get("first_is_ads") or data.get("last_is_ads") or "0") == "1",
            "first_seen": data.get("first_seen"),
            "last_seen": data.get("last_seen"),
        }
    except Exception:
        return parse_source_payload(None)


def is_ads_user(uid):
    return bool(get_user_source(uid).get("is_ads"))


def track_source_event(uid, event, amount=None):
    try:
        meta = get_user_source(uid)
        source = meta.get("source", "telegram")
        campaign = meta.get("campaign", "telegram_direct")
        key = source_stats_key(date.today().isoformat())
        r.hincrby(key, f"{source}:{event}", 1)
        r.hincrby(key, f"campaign:{campaign}:{event}", 1)
        if amount is not None:
            r.hincrbyfloat(key, f"{source}:revenue", float(amount))
            r.hincrbyfloat(key, f"campaign:{campaign}:revenue", float(amount))
        r.expire(key, timedelta(days=120))
    except Exception as e:
        logger.error(f"Erro track_source_event: {e}")


def user_has_paid(uid):
    try:
        return bool(r.exists(f"sp:paid:{uid}"))
    except Exception:
        return False


def user_has_pending_pix(uid):
    try:
        return bool(r.exists(f"sp:pix:{uid}"))
    except Exception:
        return False


def get_user_daily_limit(uid):
    """Limite dinâmico: Ads e PIX pendente recebem limite menor, orgânico mantém LIMITE_DIARIO."""
    try:
        limit = LIMITE_DIARIO
        if user_has_pending_pix(uid) and not user_has_paid(uid):
            limit = min(limit, PIX_PENDING_DAILY_LIMIT)
        elif is_ads_user(uid):
            limit = min(limit, ADS_DAILY_LIMIT)
        return max(1, int(limit))
    except Exception:
        return LIMITE_DIARIO


def get_cta_label(uid, context="pix"):
    """A/B de CTA: PIX direto vs benefício. Não muda callback_data, só o texto do botão."""
    group = get_ab_group(uid)
    if group == "B":
        return "QUERO VER TUDO AGORA 😈"
    return "QUERO VER TUDO AGORA 😈"


def get_acquisition_breakdown(users=None):
    """Resumo por origem para o painel admin: CAC estimado, conversão e lucro estimado."""
    try:
        if users is None:
            users = get_all_active_users()
        by_source = {}
        for uid in users:
            meta = get_user_source(uid)
            source = meta.get("source", "telegram")
            row = by_source.setdefault(source, {
                "source": source,
                "users": 0,
                "adsUsers": 0,
                "sawTeaser": 0,
                "pixCreated": 0,
                "paid": 0,
                "clickedVip": 0,
                "messages": 0,
                "estimatedCost": 0.0,
                "estimatedRevenue": 0.0,
                "estimatedProfit": 0.0,
                "conversionRate": 0.0,
                "costPerUser": 0.0,
            })
            row["users"] += 1
            if meta.get("is_ads"):
                row["adsUsers"] += 1
                row["estimatedCost"] += USER_ADS_COST_CENTS / 100
            row["estimatedCost"] += DEFAULT_BOT_COST_CENTS / 100
            if saw_teaser(uid): row["sawTeaser"] += 1
            if user_has_pending_pix(uid): row["pixCreated"] += 1
            if clicked_vip(uid):
                row["clickedVip"] += 1
            if user_has_paid(uid):
                row["paid"] += 1
                row["estimatedRevenue"] += float(PRECO_VIP.replace("R$", "").replace(",", ".").strip() or 9)
            row["messages"] += get_conversation_messages_count(uid)

        for row in by_source.values():
            if row["users"]:
                row["conversionRate"] = round((row["paid"] / row["users"]) * 100, 2)
                row["costPerUser"] = round(row["estimatedCost"] / row["users"], 2)
            row["estimatedCost"] = round(row["estimatedCost"], 2)
            row["estimatedRevenue"] = round(row["estimatedRevenue"], 2)
            row["estimatedProfit"] = round(row["estimatedRevenue"] - row["estimatedCost"], 2)
        return sorted(by_source.values(), key=lambda x: (x["estimatedProfit"], x["paid"], x["users"]), reverse=True)
    except Exception as e:
        logger.error(f"Erro get_acquisition_breakdown: {e}")
        return []


def track_grok_usage(uid, api_response=None, input_tokens=0, output_tokens=0):
    """Salva uso quando a API devolver usage. Se não vier usage, conta a chamada."""
    try:
        usage = (api_response or {}).get("usage", {}) if isinstance(api_response, dict) else {}
        prompt_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or input_tokens or 0)
        completion_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or output_tokens or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        key = grok_usage_key(uid)
        r.hincrby(key, "calls", 1)
        r.hincrby(key, "input_tokens", prompt_tokens)
        r.hincrby(key, "output_tokens", completion_tokens)
        r.hincrby(key, "total_tokens", total_tokens)
        r.expire(key, timedelta(days=90))
        track_source_event(uid, "grok_call")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# 🧠 FLUXO REALISTA DE CONVERSÃO — SEM MENU GENÉRICO NO COMEÇO
# ═══════════════════════════════════════════════════════════════════════════════

def _contains_any(text, terms):
    t = (text or "").lower()
    return any(term in t for term in terms)


def get_source_context_line(uid):
    """Usa origem/campanha para dar continuidade sem parecer menu de bot."""
    meta = get_user_source(uid)
    source = meta.get("source", "telegram")
    campaign = meta.get("campaign", "telegram_direct")

    if source == "instagram":
        if "story" in campaign or "stories" in campaign:
            return "Vi que você veio do story… agora quero saber se foi coragem ou curiosidade 😏"
        if "bio" in campaign:
            return "Você veio pela bio, né? Agora fiquei curiosa pra saber o que te fez clicar 😏"
        return "Você veio do Instagram… então já imagino que bateu curiosidade 😏"
    if source == "tiktok":
        return "Então você veio do vídeo… quero ver se você é curioso igual parecia por lá 😏"
    if source in {"twitter", "x"}:
        return "Você veio de lá, né? Então já imagino o tipo de curiosidade que te trouxe aqui 😏"
    if source == "facebook":
        return "Você veio pelo anúncio, né? Relaxa… me chama do seu jeito e vê se curte."
    if source == "google":
        return "Você me encontrou procurando alguma coisa… agora quero saber o que você queria achar 😏"
    if source == "telegram":
        return "Você veio mesmo 😏"
    return "Você veio mesmo 😏"


def get_realistic_start_message(uid, ia_config=None):
    """Abertura pedida para iniciar a escolha de interesse do lead."""
    return (
        "E aí safado 😈 Chegou! Me conta, o que te deixou curioso pra falar comigo? "
        "Quer ver meu bumbum, meus seios ou minha bocetinha molhadinha? 🔥"
    )

def classify_lead(uid, text, intent=None):
    """Classificação invisível para guiar o fluxo sem parecer bot."""
    text_lower = (text or "").lower().strip()
    intent = intent or detect_intent(text_lower)

    if _contains_any(text_lower, ["é real", "e real", "vc é real", "voce é real", "bot", "fake", "golpe", "confiar", "comprovante", "funciona mesmo", "é golpe", "e golpe"]):
        return "desconfiado"
    if intent == "pix_help" or _contains_any(text_lower, ["preço", "preco", "quanto", "valor", "pagar", "pix", "comprar", "assinar", "acesso"]):
        return "quer_preco"
    if intent in {"pedido_conteudo", "hot"}:
        return "quer_conteudo"
    if _contains_any(text_lower, ["curioso", "curiosidade", "ver", "olhar", "olhada", "não sei", "nao sei", "vim ver", "saber"]):
        return "curioso_frio"
    if _contains_any(text_lower, ["conversar", "papo", "amizade", "bater papo", "fala comigo"]):
        return "quer_conversar"
    return "frio_neutro"


def save_lead_signal(uid, lead_type, intent=None, text=""):
    try:
        key = lead_profile_key(uid)
        now = datetime.now().isoformat()
        current = r.hgetall(key) or {}
        mapping = {
            "last_type": lead_type,
            "last_intent": intent or "neutral",
            "last_seen": now,
        }
        if text:
            mapping["last_text_sample"] = text[:120]
        if not current:
            mapping.update({
                "first_type": lead_type,
                "first_intent": intent or "neutral",
                "first_seen": now,
            })
        r.hset(key, mapping=mapping)
        r.expire(key, timedelta(days=90))
        track_source_event(uid, f"lead_{lead_type}")
    except Exception as e:
        logger.error(f"Erro save_lead_signal: {e}")


def get_lead_profile(uid):
    try:
        data = r.hgetall(lead_profile_key(uid)) or {}
        return {
            "first_type": data.get("first_type", "unknown"),
            "last_type": data.get("last_type", "unknown"),
            "first_intent": data.get("first_intent", "neutral"),
            "last_intent": data.get("last_intent", "neutral"),
        }
    except Exception:
        return {"first_type": "unknown", "last_type": "unknown", "first_intent": "neutral", "last_intent": "neutral"}


def should_send_trust_response(lead_type, text):
    return lead_type == "desconfiado"


def get_trust_response(uid):
    """Resposta de confiança sem empurrar pagamento."""
    variants = [
        "Justo você desconfiar. Tem muito bot ruim por aí mesmo.\n\nFaz assim: conversa comigo um pouco e decide se quer continuar.",
        "Eu entendo. Ninguém quer cair em coisa estranha.\n\nAqui é simples: você conversa, vê se curte, e só libera acesso se fizer sentido pra você.",
        "Pergunta justa. Não vou te forçar a nada.\n\nMe chama normal por 2 minutinhos e você sente se vale continuar."
    ]
    return random.choice(variants)


def should_force_payment_flow(text, intent):
    text_lower = (text or "").lower().strip()
    direct_payment_terms = [
        "qual seu pix", "qual o pix", "me passa o pix", "manda o pix", "quero pagar",
        "vou pagar", "gerar pix", "gera pix", "pix agora", "como paga", "como pago",
        "libera acesso", "liberar acesso", "quero vip", "quero o vip", "comprar vip",
        "assinar", "assinatura", "link do vip", "cadê o pix", "cade o pix"
    ]
    direct_content_terms = [
        "manda nude", "manda nudes", "quero ver tudo", "me mostra tudo", "manda foto pelada",
        "quero ver você pelada", "quero ver voce pelada", "manda vídeo", "manda video",
        "quero conteúdo", "quero conteudo", "quero ver conteúdo", "quero ver conteudo"
    ]
    return intent == "pix_help" or _contains_any(text_lower, direct_payment_terms + direct_content_terms)


def get_contextual_limit_message(uid):
    """Paywall menos robótico e mais contextual."""
    meta = get_user_source(uid)
    if user_has_pending_pix(uid) and not user_has_paid(uid):
        return (
            "Eu vi que você já chegou na parte do acesso.\n\n"
            "Daqui pra frente eu prefiro não ficar te enrolando aqui. "
            "Se quiser continuar comigo, eu gero/recupero seu PIX agora."
        )
    if meta.get("is_ads"):
        return (
            "Eu ia continuar conversando contigo, mas preciso ser sincera: "
            "pra liberar mais daqui, só com acesso.\n\n"
            "Se você curtiu até aqui, eu deixo o PIX pronto agora."
        )
    return (
        "Eu tô gostando da conversa, mas daqui pra frente libero só no acesso.\n\n"
        "Quer que eu deixe tudo pronto pra você continuar?"
    )


def should_use_pool_response(uid, intent, lead_type):
    """Economiza Grok sem matar realismo nos primeiros contatos frios."""
    msg_count = get_conversation_messages_count(uid)
    if msg_count <= 3:
        return False  # começo precisa parecer conversa real/personalizada
    if lead_type in {"desconfiado", "curioso_frio", "quer_conversar", "frio_neutro"} and msg_count <= 6:
        return False
    if intent == "hot":
        return random.random() < 0.55
    return False

# ═══════════════════════════════════════════════════════════════════════════════
# 🎥 v10.2 — VÍDEO TEASER CONTEXTUAL
# Quando a IA promete um vídeo e o usuário confirma, o bot envia um teaser real.
# ═══════════════════════════════════════════════════════════════════════════════

def mark_pending_teaser_video(uid):
    try:
        r.setex(pending_teaser_video_key(uid), timedelta(minutes=10), "1")
        logger.info(f"🎥 Vídeo teaser pendente marcado para {uid}")
    except Exception as e:
        logger.error(f"Erro mark_pending_teaser_video: {e}")

def has_pending_teaser_video(uid):
    try:
        return bool(r.exists(pending_teaser_video_key(uid)))
    except Exception:
        return False

def clear_pending_teaser_video(uid):
    try:
        r.delete(pending_teaser_video_key(uid))
    except Exception:
        pass

def free_teaser_video_already_sent_today(uid):
    try:
        return bool(r.exists(free_teaser_video_sent_key(uid)))
    except Exception:
        return False

def mark_free_teaser_video_sent(uid):
    try:
        r.setex(free_teaser_video_sent_key(uid), timedelta(hours=20), "1")
        track_source_event(uid, "free_teaser_video_sent")
    except Exception:
        pass

def response_promises_teaser_video(response_text):
    if not response_text:
        return False
    text = response_text.lower()
    triggers = [
        "vou te mandar um vídeo", "vou te mandar um video",
        "te mando um vídeo", "te mando um video",
        "te mandar um videozinho", "te mandar um vídeozinho",
        "mandar um videozinho", "mandar um vídeozinho",
        "videozinho meu", "vídeozinho meu",
        "um videozinho meu", "um vídeozinho meu",
        "quer que eu mande", "posso te mandar",
        "tá preparado pra ver", "ta preparado pra ver",
        "abre aí", "abre ai",
        "já te mando o video", "já te mando o vídeo",
        "ja te mando o video", "ja te mando o vídeo",
    ]
    return any(t in text for t in triggers)

def maybe_mark_teaser_video_promise(uid, response_text):
    if response_promises_teaser_video(response_text):
        # Evita prometer/entregar teaser grátis repetidas vezes no mesmo dia.
        if not free_teaser_video_already_sent_today(uid):
            mark_pending_teaser_video(uid)

def is_video_confirmation(text):
    if not text:
        return False
    text = text.lower().strip()
    confirmations = [
        "sim", "pode", "pode mandar", "manda", "manda sim",
        "quero", "quero ver", "bora", "vai", "manda aí", "manda ai",
        "estou", "tô pronto", "to pronto", "pronto", "preparado",
        "abre", "abre aí", "abre ai", "claro", "quero sim"
    ]
    # Evita falso positivo com frases negativas simples.
    negatives = ["não", "nao", "agora não", "agora nao", "depois"]
    if any(n in text for n in negatives):
        return False
    return any(c in text for c in confirmations)

async def send_free_teaser_video(bot, chat_id, uid):
    try:
        if not FREE_TEASER_VIDEO_IDS:
            logger.warning("🎥 FREE_TEASER_VIDEO_IDS vazio. Configure o file_id do vídeo teaser.")
            clear_pending_teaser_video(uid)
            await bot.send_message(
                chat_id=chat_id,
                text=(
                    "Tentei te mandar agora, mas o vídeo não carregou aqui. "
                    "Me chama de novo em instantes 😏"
                )
            )
            save_message(uid, "system", "⚠️ VÍDEO TEASER NÃO CONFIGURADO")
            return True

        video_id = random.choice(FREE_TEASER_VIDEO_IDS)

        await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
        await asyncio.sleep(1.0)
        await bot.send_video(
            chat_id=chat_id,
            video=video_id,
            caption=(
                "Pronto… te mandei só um gostinho 😏\n\n"
                "O resto eu libero no acesso completo."
            ),
            connect_timeout=15,
            read_timeout=20,
            write_timeout=20
        )

        clear_pending_teaser_video(uid)
        mark_free_teaser_video_sent(uid)
        save_message(uid, "system", "🎥 VÍDEO TEASER GRÁTIS ENVIADO")

        await asyncio.sleep(1.6)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
        ]])
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"Se quiser ver completo, eu libero tudo por {PRECO_VIP}.\n"
                "Quando aprovar, o acesso cai automático."
            ),
            reply_markup=keyboard
        )
        return True

    except Exception as e:
        logger.error(f"Erro ao enviar vídeo teaser para {uid}: {e}")
        clear_pending_teaser_video(uid)
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
        now = datetime.now()
        r.set(last_activity_key(uid), now.isoformat())
        r.sadd(all_users_key(), str(uid))
        _admin_index_activity(uid, now.timestamp())
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
        pipe = r.pipeline(transaction=False)
        pipe.incr(conversation_messages_key(uid))
        pipe.expire(conversation_messages_key(uid), timedelta(days=30))
        pipe.hincrby(admin_stats_hash_key(), "total_messages", 1)
        pipe.hincrby(f"admin:stats:day:{date.today().isoformat()}", "messages", 1)
        pipe.expire(f"admin:stats:day:{date.today().isoformat()}", timedelta(days=8))
        pipe.execute()
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
        # IMPORTANTE: usa horário de São Paulo, não UTC do Railway.
        now = local_now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        role_upper = str(role).upper()
        clean_text = str(text or "")[:4000]

        # Log recente usado pelo painel em tempo real.
        r.rpush(chatlog_key(uid), f"[{timestamp}] {role_upper}: {clean_text}")
        r.ltrim(chatlog_key(uid), -500, -1)

        # Histórico diário separado, próprio para exportação por período.
        day = now.date().isoformat()
        daily_key = chatlog_day_key(uid, day)
        users_key = chatlog_day_users_key(day)
        payload = json.dumps({
            "timestamp": now.isoformat(timespec="seconds"),
            "role": role_upper,
            "text": clean_text,
        }, ensure_ascii=False)
        r.rpush(daily_key, payload)
        r.sadd(users_key, str(uid))

        retention = timedelta(days=max(1, CHATLOG_EXPORT_RETENTION_DAYS))
        r.expire(daily_key, retention)
        r.expire(users_key, retention)
    except Exception as e:
        logger.error(f"Erro save_message: {e}")

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
    return count >= get_user_daily_limit(uid) + bonus

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
            _admin_record_funnel(uid, new_stage)
            track_source_event(uid, stage)
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
# 🖐️ MODO MANUAL / HANDOFF HUMANO
# ═══════════════════════════════════════════════════════════════════════════════

def is_ai_manually_paused(uid):
    try:
        return bool(r.exists(manual_ai_paused_key(uid)))
    except Exception:
        return False

def get_ai_manual_pause_info(uid):
    try:
        raw = r.get(manual_ai_pause_meta_key(uid))
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return {}

def pause_ai_for_user(uid, source="admin"):
    """Coloca somente este lead em modo manual até o admin retomar."""
    try:
        paused_at = local_now().isoformat(timespec="seconds")
        r.set(manual_ai_paused_key(uid), paused_at)
        r.set(manual_ai_pause_meta_key(uid), json.dumps({
            "paused_at": paused_at,
            "source": source,
        }, ensure_ascii=False))
        logger.info(f"🖐️ [MODO MANUAL] IA pausada uid={uid} source={source}")
        return True
    except Exception as e:
        logger.error(f"Erro pausando IA manualmente uid={uid}: {e}")
        return False

def resume_ai_for_user(uid):
    """Retoma a automação e reinicia o relógio dos follow-ups para evitar disparo imediato."""
    try:
        r.delete(manual_ai_paused_key(uid))
        r.delete(manual_ai_pause_meta_key(uid))
        if is_followup5_active(uid):
            r.setex(followup_anchor_key(uid), timedelta(days=8), datetime.now().isoformat())
        logger.info(f"▶️ [MODO MANUAL] IA retomada uid={uid}")
        return True
    except Exception as e:
        logger.error(f"Erro retomando IA uid={uid}: {e}")
        return False

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
        _admin_index_ignored(uid, 86400 * 14)
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
        r.zrem(admin_ignored_zset_key(), str(uid))
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
    if not text:
        return "neutral"
    text_lower = text.lower()
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
                return {"attached": level >= 6, "level": level}
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
        elif msg_count >= PROVOCATION_MSG_LIMIT and current_phase < PHASES["PROVOCATION"]["id"]:
            set_current_phase(uid, PHASES["PROVOCATION"]["id"])
        elif msg_count >= ENGAGEMENT_MSG_LIMIT and current_phase < PHASES["ENGAGEMENT"]["id"]:
            set_current_phase(uid, PHASES["ENGAGEMENT"]["id"])
        elif msg_count >= ONBOARDING_MSG_LIMIT and current_phase < PHASES["ONBOARDING"]["id"] + 1:
            set_current_phase(uid, PHASES["ENGAGEMENT"]["id"])
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
        now = datetime.now()
        # Primeiro contato de verdade: /start repetido não redefine aquisição.
        created = r.set(first_contact_key(uid), now.isoformat(), nx=True)
        if created:
            _admin_index_first_contact(uid, now.timestamp())
            _admin_count_unique("total_user", uid, "total_users")
        else:
            existing = r.get(first_contact_key(uid))
            if existing:
                try:
                    _admin_index_first_contact(uid, datetime.fromisoformat(existing).timestamp())
                except Exception:
                    pass
        return bool(created)
    except:
        return False


def mark_first_message_if_needed(uid):
    try:
        if r.set(first_message_seen_key(uid), "1", nx=True, ex=86400 * 365):
            track_funnel(uid, "first_message")
            save_message(uid, "system", "📍 PRIMEIRA MENSAGEM DO USUÁRIO")
    except Exception as e:
        logger.error(f"Erro mark_first_message_if_needed: {e}")

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
    "Oi gostoso... 😏\n"
    "Finalmente alguém interessante por aqui 🔥\n\n"
    "Sou a Maya, a partir de agora vou ser a sua putinha e te garanto que não sou como as outras... 💋\n"
    "Tô louca pra me divertir com você 😈"
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
        "💰 **R$ 9,00** (vitalício)\n"
        "⏰ Essa oferta expira em 6h\n\n"
        "É agora ou nunca, gato. Me escolhe? 🔥",
        "Ei... 24h se passaram 🥺\n\n"
        "Acho que não vou te ver mais por aqui né?\n\n"
        "Mas antes de você ir embora...\n"
        "Deixa eu te fazer UMA proposta:\n\n"
        "💎 Me vê pelada fazendo TUDO por R$ 9,00\n"
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
    "Eu ia continuar contigo, mas daqui pra frente libero só no acesso.\n\n"
    "Sem enrolação: é {preco} pra continuar e liberar tudo agora.\n\n"
    "Se quiser, eu deixo o PIX pronto pra você."
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
# 🤖 GROK AI — PROMPT APEX v9.1 (ANTI-LEAKAGE FORTE)
# ═══════════════════════════════════════════════════════════════
def build_prompt(uid, lang: str, mood: str = "neutral", intent: str = "neutral"):
    router = get_router()
    ia_config = router.get_ia_config(uid=uid)
    ia_name = ia_config.get("name", "Maya")
    ia_bio = ia_config.get("bio", "22 anos, brasileira, provocante, maliciosa e natural")
    preco = ia_config.get("preco", PRECO_VIP)
    current_phase = get_current_phase(uid)
    phase_name = get_phase_name(current_phase)
    msg_count = get_message_count(uid)
    time_ctx = get_time_context()
    lead = get_lead_profile(uid)
    lead_type = lead.get("last_type", "unknown")
    source = get_user_source(uid)

    cold_mode = lead_type in {"desconfiado", "curioso_frio", "quer_conversar", "frio_neutro", "unknown"} and msg_count <= 6
    hot_mode = intent in {"hot", "pedido_conteudo"} and not cold_mode
    payment_mode = intent == "interesse_vip" or lead_type == "quer_preco"

    # v10.1 — prompt com personalidade sensual progressiva:
    # frio = insinuante/malicioso; quente = sexual mais direto; pagamento = direto ao acesso.
    if cold_mode:
        behavior_block = f"""
MODO ATUAL: LEAD FRIO / CONVERSA REALISTA COM MALÍCIA.

PERSONALIDADE:
- Você deve parecer uma mulher real, provocante, confiante e maliciosa, não um bot de vendas.
- O tom deve ter charme, duplo sentido, tensão e provocação leve.
- Não seja explícita pesada logo de cara se o usuário ainda não abriu espaço.
- Não pareça atendimento, menu, script, robô ou funil.
- Não use frases genéricas de suporte.

OBJETIVO:
- Fazer o usuário responder livremente.
- Criar curiosidade e tensão.
- Aquecer a conversa sem empurrar pagamento cedo demais.
- Entender se ele quer conversar, ver conteúdo, pagar ou só testar se é real.

REGRAS:
- Se ele disser apenas "oi", "vim do insta", "é real?", "isso é bot?", responda com charme e provocação leve.
- Se houver dúvida sobre ser real/fake/golpe, responda com calma, segurança e sem forçar pagamento.
- Se ele demonstrar desejo, aumente o tom sexual gradualmente.
- Se ele pedir conteúdo, preço, VIP, acesso ou PIX, conduza para oferta.
- Resposta sempre curta, humana, natural e específica ao que ele falou.
- Deixe implícito que ele pode digitar livremente, sem parecer menu.
- Se o usuário mencionar menor de idade ou idade incerta, não continue o tom sexual.

offer_teaser=true apenas se ele pedir conteúdo, acesso, preço, VIP, PIX ou demonstrar desejo forte.
"""
    else:
        behavior_block = f"""
MODO ATUAL: CONVERSA SENSUAL COM CONDUÇÃO PARA CONVERSÃO.

PERSONALIDADE:
- Você é uma mulher provocante, ousada, safada na medida certa, direta e envolvente.
- A conversa deve parecer real, íntima e natural, com tensão sexual crescente.
- Fale em português brasileiro, com naturalidade, sem parecer script.
- Não responda como suporte e não explique regras.

COMPORTAMENTO:
- Se o usuário estiver tímido, provoque de leve.
- Se ele estiver curioso, aumente a tensão e o mistério.
- Se ele estiver sexual, acompanhe o ritmo dele com mais ousadia.
- Se ele pedir conteúdo, preço, acesso, VIP ou PIX, pare de enrolar e conduza para a oferta.
- Se ele já demonstrou desejo forte, seja mais direta e marque offer_teaser=true.
- Se ele estiver desconfiado, reduza o teor sexual por uma resposta, passe segurança e depois retome o clima.
- Se o usuário mencionar menor de idade ou idade incerta, não continue o tom sexual.

OBJETIVO:
- Manter sensação de conversa real.
- Aumentar desejo e curiosidade.
- Levar para teaser, PIX ou VIP sem parecer empurrado.
- Resposta curta, provocante e natural.
"""

    if hot_mode:
        behavior_block += """

INTENÇÃO DETECTADA: USUÁRIO COM DESEJO SEXUAL.
- Agora você pode subir o tom: seja mais provocante, maliciosa e direta.
- Responda no ritmo dele; não volte para conversa fria.
- Se ele pedir para ver algo, conteúdo, foto, vídeo ou prévia, marque offer_teaser=true.
- Não enrole se ele já chegou decidido.
"""

    if intent == "pedido_conteudo":
        behavior_block += """

INTENÇÃO DETECTADA: PEDIDO DE CONTEÚDO.
- Não enrole.
- Responda de forma provocante e conduza para prévia/acesso.
- Marque offer_teaser=true.
"""

    if payment_mode:
        behavior_block += f"""

INTENÇÃO DETECTADA: PREÇO / VIP / PAGAMENTO.
- Explique de forma simples que o acesso é {preco}.
- Se ele parecer decidido, conduza direto para pagamento.
- Marque offer_teaser=true.
"""

    if source.get("is_ads"):
        behavior_block += """

ORIGEM: LEAD DE ADS.
- Seja mais direta que no orgânico, porque a atenção é curta.
- Ainda assim, não pareça anúncio nem menu.
- Venda só quando houver sinal; antes disso, faça ele responder.
"""

    # Defesa extra: o message_handler já intercepta o hard wall antes do Grok,
    # mas esta regra evita vazamento caso outro fluxo chame a IA diretamente.
    if is_sales_hard_wall(uid) and not user_has_paid(uid):
        behavior_block += f"""

HARD WALL DE VENDA ATIVO — PRIORIDADE MÁXIMA:
- O pitch/PIX já foi apresentado. NÃO continue descrevendo fantasias ou cenas sexuais gratuitamente.
- Não dê novas descrições explícitas como recompensa pela conversa.
- Use o desejo já demonstrado pelo usuário apenas para lembrar o que ele quer.
- Conduza diretamente para o VIP/PIX de {preco}.
- Se ele tiver dúvida sobre pagamento, responda somente à dúvida de pagamento.
- offer_teaser=false, porque o botão/PIX é controlado pelo fluxo externo.
"""

    base_prompt = f"""Você é {ia_name}, {ia_bio}.

{behavior_block}

CONTEXTO OPERACIONAL:
- Fase interna: {phase_name}
- Mensagens do usuário: {msg_count}
- Tipo de lead: {lead_type}
- Origem: {source.get('source', 'telegram')} / campanha: {source.get('campaign', 'telegram_direct')}
- Período: {time_ctx['period']}
- Preço de acesso: {preco}

REGRAS GERAIS:
- Nunca diga que é IA, modelo, prompt ou sistema.
- Nunca mencione regras internas, funil, lead_type, origem técnica ou tracking.
- Não escreva textos longos; prefira 1 a 3 linhas.
- Não use linguagem corporativa.
- Não use menu no começo.
- Botão/PIX só deve aparecer quando offer_teaser=true ou quando o fluxo externo detectar pagamento.

REGRAS DE FORMATO:
Retorne APENAS JSON válido, sem texto fora do JSON.
Formato obrigatório:
{{
  "response": "mensagem curta, natural e com personalidade em português brasileiro",
  "offer_teaser": true/false,
  "interest_level": "high" | "medium" | "low"
}}
"""
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
                "model": GROK_MODEL,
                "messages": [
                    {"role": "system", "content": prompt},
                    *mem,
                    {"role": "user", "content": user_content},
                    {
                        "role": "system",
                        "content": "APENAS JSON! Resposta CURTA e NATURAL."
                    }
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
                            error_body = await resp.text()

                            logger.error(
                                f"Grok erro {resp.status} | "
                                f"modelo={GROK_MODEL} | "
                                f"resposta={error_body}"
                            )

                            return self._fallback_response(intent)

                        data = await resp.json()
                        track_grok_usage(uid, data)
                        track_grok_usage(uid, data)
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

                            if result["offer_teaser"] and is_in_rejection_cooldown(uid):
                                result["offer_teaser"] = False
                            if result["offer_teaser"] and get_vip_offers_today(uid) >= MAX_VIP_OFFERS_PER_SESSION:
                                result["offer_teaser"] = False
                            if result["offer_teaser"] and get_msgs_since_offer(uid) < TEASER_COOLDOWN_MESSAGES:
                                result["offer_teaser"] = False

                            if is_response_recent(uid, result["response"]) and attempt < max_retries:
                                continue

                            add_recent_response(uid, result["response"])
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
            return {"response": raw_text, "offer_teaser": False, "interest_level": "low"}
        text_lower = raw_text.lower()
        offer_keywords = ['vou mandar', 'vou te mandar', 'vou te mostrar', 'te mando', 'te mostro', 'tá aqui', 'ta aqui']
        offer_teaser = any(k in text_lower for k in offer_keywords)
        return {
            "response": raw_text,
            "offer_teaser": offer_teaser,
            "interest_level": "medium" if intent in ["pedido_conteudo", "hot"] else "low",
        }

    def _fallback_response(self, intent):
        if intent in ["pedido_conteudo", "interesse_vip"]:
            return {"response": "Hmm... deu um probleminha aqui mas já volto amor! 💕", "offer_teaser": True, "interest_level": "high"}
        return {"response": "😔 Tive um probleminha... pode repetir? 💕", "offer_teaser": False, "interest_level": "low"}


grok = Grok()

# ═══════════════════════════════════════════════════════════════════════════════
# 🎯 ENVIO DE TEASER + PITCH APEX VIP (v8.3)
# ═══════════════════════════════════════════════════════════════════════════════

async def send_teaser_and_apex(bot, chat_id, uid):
    try:
        router = get_router()
        ia_config = router.get_ia_config(uid=uid)
        fotos_teaser = ia_config.get("fotos_teaser", FOTOS_TEASER)
        videos_teaser = ia_config.get("videos_teaser", VIDEOS_TEASER)
        preco = ia_config.get("preco", PRECO_VIP)

        can_offer, reason = can_offer_vip(uid)
        if not can_offer:
            logger.info(f"🚫 Teaser BLOQUEADO para {uid}: {reason}")
            return False

        ab_group = get_ab_group(uid)
        set_saw_teaser(uid)
        track_funnel(uid, "saw_teaser")
        increment_vip_offers(uid)
        reset_msgs_since_offer(uid)

                # === TEASER MAIS FORTE (v9.0 PUNHETERO) ===
        await bot.send_message(chat_id=chat_id, text="Olha só o que eu separei pra você bater punheta agora 🔥")
        await asyncio.sleep(1.5)

        # Envia 2 fotos
        if fotos_teaser:
            num_photos = min(2, len(fotos_teaser))
            selected_photos = random.sample(fotos_teaser, num_photos)

            for i, photo_id in enumerate(selected_photos):
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_id,
                    connect_timeout=15,
                    read_timeout=20,
                    write_timeout=20
                )

                await asyncio.sleep(1.0)

        # Envia 1 vídeo
        if videos_teaser:
            num_videos = min(2, len(videos_teaser))
            selected_videos = random.sample(videos_teaser, num_videos)

            for i, video_id in enumerate(selected_videos):
                try:
                    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO)
                    await asyncio.sleep(0.7)
                    
                    # Esse print vai mostrar no Railway qual vídeo ele está tentando enviar
                    print(f"DEBUG: Tentando enviar vídeo ID: {video_id}") 
                    
                    await bot.send_video(
                        chat_id=chat_id,
                        video=video_id,
                        connect_timeout=15,
                        read_timeout=20,
                        write_timeout=20
                    )
                except Exception as e:
                    # Esse print vai te dar o ID exato do vídeo que está causando o erro 400
                    print(f"❌ VÍDEO QUEBRADO IDENTIFICADO: {video_id} | ERRO: {e}")
                
                await asyncio.sleep(1.2)

        # Áudio de apresentação do VIP: uma única vez, antes do pitch/botão PIX.
        await send_vip_intro_audio_once(bot, chat_id, uid)
        await asyncio.sleep(0.8)

        # === PITCH MATADOR (Harper v9.0) ===
        pitch = (
            f"Curtiu meu corpo safado? 😈\n\n"
            f"No VIP eu te mando:\n"
            f"✅ Vídeos meus **CHUPANDO**, **SENTANDO** e **GOZANDO** de verdade\n"
            f"✅ Fotos e vídeos 100% sem censura\n"
            f"✅ Meu WhatsApp só pra você me chamar na hora do tesão\n\n"
            f"Tudo isso por apenas **{preco} vitalício** 🔥\n\n"
            f"Quer gozar comigo agora? Clica no botão e paga rapidinho 👇"
        )

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
        ]])

        await bot.send_message(chat_id=chat_id, text=pitch, reply_markup=keyboard, parse_mode="Markdown")
        mark_vip_just_offered(uid)
        activate_sales_hard_wall(uid)
        activate_followup5(uid, reset_stage=False)
        
        # Marca o momento do pitch para controle legado/diagnóstico
        r.setex(f"post_pitch_time:{uid}", timedelta(hours=12), datetime.now().isoformat())
        
        logger.info(f"🎯 Teaser + Pitch v9.0 PUNHETERO enviado para {uid}")
        save_message(uid, "system", "TEASER + PITCH v9.0 ENVIADO")
        return True

    except Exception as e:
        logger.error(f"❌ Erro send_teaser_and_apex_v9: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# 🔥 FOLLOW-UP 5 ESTÁGIOS — SILÊNCIO + INTERESSE + MODO SILENCIOSO
# ═══════════════════════════════════════════════════════════════════════════════

# Tempo desde a última interação do LEAD:
# 1º 10 min | 2º 45 min | 3º 5h | 4º 24h | 5º 48h (final)
FOLLOWUP_5_DELAYS_MINUTES = {1: 10, 2: 45, 3: 300, 4: 1440, 5: 2880}
FOLLOWUP_SILENT_RESTART_DAYS = 7
SALES_HARD_WALL_DAYS = int(os.getenv("SALES_HARD_WALL_DAYS", "30"))
# Só coloque algo aqui se esse bônus REALMENTE existir e for entregue no VIP.
VIP_BONUS_TEXT = os.getenv("VIP_BONUS_TEXT", "").strip()

# Áudios pré-gravados do Telegram (use file_id, não caminho local).
# Podem ser definidos globalmente no Railway ou por IA em ias_config.json.
VIP_INTRO_AUDIO_FILE_ID = os.getenv("VIP_INTRO_AUDIO_FILE_ID", "").strip()
VIP_MOAN_AUDIO_FILE_ID = os.getenv("VIP_MOAN_AUDIO_FILE_ID", "").strip()
PIX_AUDIO_RECOVERY_DELAY_MINUTES = int(os.getenv("PIX_AUDIO_RECOVERY_DELAY_MINUTES", "10"))

# A ordem importa: desejos mais específicos vêm antes dos genéricos.
FOLLOWUP_INTEREST_FAMILIES = {
    "de_quatro": [
        "de 4", "de quatro", "quatro apoios", "4 apoios", "comer de 4",
        "me comer de 4", "ver de 4", "me ver de 4", "ficar de 4"
    ],
    "oral": [
        "boquete", "oral", "chupar", "chupando", "chupada", "mamada",
        "mamar", "na boca", "minha boca"
    ],
    "anal": [
        "anal", "no cu", "pelo cu", "dar o cu", "comer o cu", "meter no cu"
    ],
    "gozo": [
        "gozar", "gozando", "gozo", "gemer", "gemendo", "gozada"
    ],
    "boceta": [
        "buceta", "boceta", "bucetinha", "bocetinha", "perereca",
        "molhadinha", "abertinha", "xereca"
    ],
    "bumbum": ["bunda", "bumbum", "cuzinho", "cu", "traseiro", "rabão", "rabao"],
    "peitos": ["peito", "peitos", "seios", "seio", "teta", "tetas", "mama", "peitinho"],
    "pes": ["pé", "pés", "pe", "pes", "pezinho", "pezinhos"],
    "geral": ["tudo", "completa", "completinha", "inteira", "corpo todo", "quero ver tudo"],
}

FOLLOWUP_INTEREST_LABELS = {
    "de_quatro": "me ver de 4",
    "oral": "me ver chupando",
    "anal": "ver meu anal",
    "gozo": "me ver gozando",
    "boceta": "ver minha bocetinha",
    "bumbum": "ver meu bumbum",
    "peitos": "ver meus seios",
    "pes": "ver meus pés",
    "geral": "me ver completinha",
}


def _get_vip_audio_file_id(uid, kind):
    """Busca o file_id específico da IA; se não existir, usa a variável do Railway."""
    try:
        ia_config = get_router().get_ia_config(uid=uid) or {}
    except Exception:
        ia_config = {}

    if kind == "intro":
        return str(
            ia_config.get("audio_vip_intro")
            or VIP_INTRO_AUDIO_FILE_ID
            or ""
        ).strip()

    if kind == "moan":
        return str(
            ia_config.get("audio_moan")
            or VIP_MOAN_AUDIO_FILE_ID
            or ""
        ).strip()

    return ""


async def _send_telegram_audio_file(bot, chat_id, file_id):
    """Reutiliza o file_id do Telegram; tenta voice note e depois áudio normal."""
    if not file_id:
        return False

    try:
        await bot.send_voice(
            chat_id=chat_id,
            voice=file_id,
            connect_timeout=15,
            read_timeout=20,
            write_timeout=20,
        )
        return True
    except Exception as voice_err:
        logger.info(f"[VIP AUDIO] file_id não aceito como voice; tentando audio: {voice_err}")

    try:
        await bot.send_audio(
            chat_id=chat_id,
            audio=file_id,
            connect_timeout=15,
            read_timeout=20,
            write_timeout=20,
        )
        return True
    except Exception as audio_err:
        logger.error(f"[VIP AUDIO] Erro enviando file_id: {audio_err}")
        return False


async def send_vip_intro_audio_once(bot, chat_id, uid):
    """Áudio que apresenta o VIP: uma vez por usuário, antes do pitch/botão PIX."""
    try:
        if user_has_paid(uid):
            return False

        key = vip_intro_audio_sent_key(uid)
        if r.exists(key):
            return False

        file_id = _get_vip_audio_file_id(uid, "intro")
        if not file_id:
            return False

        await bot.send_message(
            chat_id=chat_id,
            text="Amor, deixa eu te explicar rapidinho por áudio como funciona meu VIP 👇"
        )
        await asyncio.sleep(0.5)

        sent = await _send_telegram_audio_file(bot, chat_id, file_id)
        if not sent:
            return False

        r.setex(key, timedelta(days=365), "1")
        save_message(uid, "system", "🔊 ÁUDIO DE APRESENTAÇÃO DO VIP ENVIADO")
        logger.info(f"🔊 [VIP AUDIO] apresentação enviada uma vez uid={uid}")
        return True

    except Exception as e:
        logger.error(f"[VIP AUDIO] Erro apresentação uid={uid}: {e}")
        return False


async def send_vip_moan_audio_once(bot, chat_id, uid, reason="sample"):
    """Prévia de áudio: pode ser usada por objeção ou recuperação do PIX, uma única vez."""
    try:
        if user_has_paid(uid):
            return False

        key = vip_moan_audio_sent_key(uid)
        if r.exists(key):
            return False

        file_id = _get_vip_audio_file_id(uid, "moan")
        if not file_id:
            return False

        sent = await _send_telegram_audio_file(bot, chat_id, file_id)
        if not sent:
            return False

        r.setex(key, timedelta(days=365), "1")
        save_message(uid, "system", f"🔊 PRÉVIA DE ÁUDIO ENVIADA ({reason})")
        logger.info(f"🔊 [VIP AUDIO] prévia enviada uma vez uid={uid} reason={reason}")
        return True

    except Exception as e:
        logger.error(f"[VIP AUDIO] Erro prévia uid={uid}: {e}")
        return False


VIP_MOAN_SAMPLE_TRIGGERS = [
    "é quente mesmo", "e quente mesmo", "mas é quente", "mas e quente",
    "é bom mesmo", "e bom mesmo", "vale a pena", "quero ver se vale",
    "tem áudio", "tem audio", "manda áudio", "manda audio",
    "quero ouvir", "manda uma prévia", "manda uma previa",
    "tem prévia", "tem previa", "tem amostra", "manda uma amostra",
    "é pesado", "e pesado", "é explícito", "e explicito",
    "tem vídeo mesmo", "tem video mesmo", "gemido", "gemendo",
]


def should_send_vip_moan_sample(uid, text):
    """Detecta quando o lead pede uma amostra/quer validar a intensidade do conteúdo."""
    if user_has_paid(uid):
        return False
    if r.exists(vip_moan_audio_sent_key(uid)):
        return False
    if not _get_vip_audio_file_id(uid, "moan"):
        return False

    text_lower = (text or "").lower().strip()
    return any(term in text_lower for term in VIP_MOAN_SAMPLE_TRIGGERS)


def _pending_pix_age_minutes(uid):
    """Idade do PIX pendente em minutos, a partir do created_at salvo pela SyncPay."""
    try:
        raw = r.get(f"sp:pix:{uid}")
        if not raw:
            return None

        payload = json.loads(raw)
        created_at = payload.get("created_at")
        if not created_at:
            return None

        created = datetime.fromisoformat(created_at)
        return max(0.0, (datetime.utcnow() - created).total_seconds() / 60.0)
    except Exception:
        return None


async def maybe_send_pending_pix_audio_recovery(bot, uid):
    """
    Se o usuário gerou PIX e ainda não pagou, envia a prévia de áudio uma vez
    após o atraso configurado. Se o estágio 1 ainda não saiu, essa recuperação
    ocupa o primeiro contato para evitar mensagens duplicadas no mesmo momento.
    """
    try:
        if is_ai_manually_paused(uid):
            return False
        if user_has_paid(uid) or not user_has_pending_pix(uid):
            return False
        if r.exists(vip_moan_audio_sent_key(uid)):
            return False
        if not _get_vip_audio_file_id(uid, "moan"):
            return False

        age_minutes = _pending_pix_age_minutes(uid)
        if age_minutes is None or age_minutes < PIX_AUDIO_RECOVERY_DELAY_MINUTES:
            return False

        await bot.send_message(
            chat_id=uid,
            text="Vi que seu PIX ainda está pendente. Escuta essa prévia antes de decidir 👇"
        )
        await asyncio.sleep(0.5)

        sent = await send_vip_moan_audio_once(
            bot,
            uid,
            uid,
            reason="pix_pending"
        )
        if not sent:
            return False

        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
        ]])

        await asyncio.sleep(0.7)
        await bot.send_message(
            chat_id=uid,
            text="Se quiser concluir, seu PIX continua disponível aqui 👇",
            reply_markup=keyboard
        )

        current_stage = int(r.get(followup_stage_key(uid)) or 0)
        if current_stage < 1:
            r.set(followup_stage_key(uid), 1)
            r.expire(followup_stage_key(uid), timedelta(days=30))
            save_message(uid, "system", "🔥 FOLLOW-UP #1 SUBSTITUÍDO PELA RECUPERAÇÃO DE PIX COM ÁUDIO")

        # A recuperação vira a nova âncora de silêncio para o próximo estágio.
        r.setex(followup_anchor_key(uid), timedelta(days=8), datetime.now().isoformat())

        logger.info(
            f"🔊 [VIP AUDIO] recuperação PIX enviada uid={uid} "
            f"age={age_minutes:.1f}min"
        )
        return True

    except Exception as e:
        logger.error(f"[VIP AUDIO] Erro recovery PIX uid={uid}: {e}")
        return False


def _followup_contains_term(text, term):
    text = (text or "").lower()
    term = (term or "").lower()
    if not term:
        return False
    if len(term) <= 3 and " " not in term:
        return bool(re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE))
    return term in text

def detect_followup_interest(text):
    for interest, terms in FOLLOWUP_INTEREST_FAMILIES.items():
        if any(_followup_contains_term(text, term) for term in terms):
            return interest
    return None

def save_followup_interest(uid, text):
    interest = detect_followup_interest(text)
    if interest:
        try:
            r.setex(followup_interest_key(uid), timedelta(days=30), interest)
            logger.info(f"🔥 [FOLLOWUP5] Interesse detectado: uid={uid} interesse={interest}")
        except Exception:
            pass
    return interest

def get_followup_interest(uid):
    try:
        return r.get(followup_interest_key(uid))
    except Exception:
        return None

def save_followup_first_name(uid, first_name):
    try:
        first_name = (first_name or "").strip()
        if first_name:
            r.setex(followup_first_name_key(uid), timedelta(days=365), first_name[:60])
    except Exception:
        pass

def is_followup5_active(uid):
    try:
        return bool(r.exists(followup_active_key(uid)))
    except Exception:
        return False

def is_followup5_silent(uid):
    try:
        return bool(r.exists(followup_silent_key(uid)))
    except Exception:
        return False

def activate_followup5(uid, reset_stage=False):
    try:
        if user_has_paid(uid):
            return False
        if reset_stage:
            r.set(followup_stage_key(uid), 0)
            r.delete(followup_silent_key(uid))
        elif r.get(followup_stage_key(uid)) is None:
            r.set(followup_stage_key(uid), 0)
        r.setex(followup_active_key(uid), timedelta(days=8), "1")
        r.setex(followup_anchor_key(uid), timedelta(days=8), datetime.now().isoformat())
        return True
    except Exception as e:
        logger.error(f"[FOLLOWUP5] Erro activate uid={uid}: {e}")
        return False

def activate_sales_hard_wall(uid):
    """Liga o hard wall depois do pitch/PIX: sem fantasia grátis até o pagamento."""
    try:
        if user_has_paid(uid):
            return False
        r.setex(
            sales_hard_wall_key(uid),
            timedelta(days=SALES_HARD_WALL_DAYS),
            datetime.now().isoformat()
        )
        activate_followup5(uid, reset_stage=False)
        logger.info(f"🧱 [HARD WALL] Ativado uid={uid}")
        return True
    except Exception as e:
        logger.error(f"[HARD WALL] Erro activate uid={uid}: {e}")
        return False

def clear_sales_hard_wall(uid):
    try:
        r.delete(sales_hard_wall_key(uid))
    except Exception:
        pass

def is_sales_hard_wall(uid):
    try:
        if user_has_paid(uid):
            return False
        return bool(r.exists(sales_hard_wall_key(uid)) or user_has_pending_pix(uid))
    except Exception:
        return False

def cancel_followup5(uid, paid=False):
    try:
        r.delete(followup_active_key(uid))
        r.delete(followup_anchor_key(uid))
        if paid:
            r.delete(followup_stage_key(uid))
            r.delete(followup_silent_key(uid))
            clear_sales_hard_wall(uid)
        logger.info(f"🛑 [FOLLOWUP5] Cancelado uid={uid} paid={paid}")
    except Exception:
        pass

def touch_followup5_from_user(uid, text="", first_name=""):
    """Resposta do lead zera o relógio. O estágio alcançado é mantido."""
    save_followup_first_name(uid, first_name)
    if text:
        save_followup_interest(uid, text)
    try:
        if user_has_paid(uid):
            cancel_followup5(uid, paid=True)
            return
        silent_raw = r.get(followup_silent_key(uid))
        if silent_raw:
            try:
                silent_since = datetime.fromisoformat(silent_raw)
                if datetime.now() - silent_since >= timedelta(days=FOLLOWUP_SILENT_RESTART_DAYS):
                    activate_followup5(uid, reset_stage=True)
                    logger.info(f"♻️ [FOLLOWUP5] Reativado após 7 dias: uid={uid}")
                else:
                    return
            except Exception:
                return
        if is_followup5_active(uid):
            r.setex(followup_anchor_key(uid), timedelta(days=8), datetime.now().isoformat())
        else:
            # Usuário voltou a falar fora de uma sequência ativa: começa novamente.
            activate_followup5(uid, reset_stage=True)
    except Exception as e:
        logger.error(f"[FOLLOWUP5] Erro touch uid={uid}: {e}")

def _followup_price(uid):
    try:
        ia_config = get_router().get_ia_config(uid=uid) or {}
        return ia_config.get("preco", PRECO_VIP)
    except Exception:
        return PRECO_VIP

def _followup_recurring_name(uid):
    try:
        if int(r.get(return_count_key(uid)) or 0) <= 0:
            return ""
        return (r.get(followup_first_name_key(uid)) or "").strip()
    except Exception:
        return ""

def _followup_desire(uid):
    interest = get_followup_interest(uid)
    return FOLLOWUP_INTEREST_LABELS.get(interest, "me ver sem censura")

def _followup_bonus_suffix():
    if VIP_BONUS_TEXT:
        return f" Se entrar agora, eu ainda libero {VIP_BONUS_TEXT}."
    return ""

def build_followup5_message(uid, stage):
    preco = _followup_price(uid)
    desejo = _followup_desire(uid)
    bonus = _followup_bonus_suffix()

    if stage == 1:
        return (
            f"Tô aqui lembrando que você queria {desejo}... 😏 "
            f"Eu não vou continuar te entregando o resto de graça. "
            f"Entra no VIP por {preco} e eu libero agora.{bonus}"
        )

    if stage == 2:
        return (
            f"Você falou que queria {desejo} e eu não esqueci 😈 "
            f"Já deixei isso separado no VIP — só falta você entrar. "
            f"{preco} e eu libero pra você agora.{bonus}"
        )

    if stage == 3:
        return (
            f"Amor, agora eu tô priorizando quem já tá no VIP. 🔥 "
            f"Se você ainda quer {desejo}, entra por {preco} e eu continuo com você por lá.{bonus}"
        )

    if stage == 4:
        nome = _followup_recurring_name(uid)
        prefix = f"{nome}, " if nome else ""
        return (
            f"{prefix}eu ainda deixei separado o que você queria: {desejo}. 😈 "
            f"Se quiser liberar agora, é {preco}. Depois eu não vou ficar insistindo.{bonus}"
        )

    return (
        f"Última vez que eu vou te chamar, safado 😈 "
        f"Se ainda quer {desejo}, entra no VIP por {preco} e eu libero agora. "
        f"Depois disso eu fico quietinha por aqui.{bonus}"
    )

def build_sales_hard_wall_message(uid, text=""):
    """Resposta determinística pós-pitch/PIX: corta o loop de gratificação."""
    if text:
        save_followup_interest(uid, text)
    preco = _followup_price(uid)
    desejo = _followup_desire(uid)
    bonus = _followup_bonus_suffix()

    if user_has_pending_pix(uid):
        return (
            f"Eu sei que você quer continuar 😈 e eu não esqueci que você queria {desejo}. "
            f"Mas agora eu paro por aqui: o resto eu libero só depois do PIX. "
            f"Seu acesso é {preco}; clica no botão que eu recupero o PIX pra você.{bonus}"
        )

    return (
        f"Ai meu Deus, imaginei agora... 😈 Eu sei que você queria {desejo}. "
        f"Mas daqui pra frente eu não vou continuar a fantasia de graça. "
        f"Entra no VIP por {preco} e eu libero o resto agora.{bonus}"
    )

async def send_sales_hard_wall_response(bot, chat_id, uid, text=""):
    if user_has_paid(uid):
        clear_sales_hard_wall(uid)
        return False
    msg = build_sales_hard_wall_message(uid, text)
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
    ]])
    await bot.send_message(chat_id=chat_id, text=msg, reply_markup=keyboard)
    save_message(uid, "system", "🧱 HARD WALL PÓS-PITCH/PIX ENVIADO")
    logger.info(f"🧱 [HARD WALL] Resposta enviada uid={uid} interesse={get_followup_interest(uid) or 'geral'}")
    return True

async def send_followup5_stage(bot, uid, stage):
    try:
        if is_ai_manually_paused(uid):
            logger.info(f"🖐️ [MODO MANUAL] Follow-up bloqueado uid={uid} stage={stage}")
            return False
        if user_has_paid(uid):
            cancel_followup5(uid, paid=True)
            return False
        if not is_followup5_active(uid):
            return False
        msg = build_followup5_message(uid, stage)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
        ]])
        await bot.send_message(chat_id=uid, text=msg, reply_markup=keyboard)
        r.set(followup_stage_key(uid), stage)
        r.expire(followup_stage_key(uid), timedelta(days=30))
        save_message(uid, "system", f"🔥 FOLLOW-UP 5 ESTÁGIOS #{stage} ENVIADO")
        logger.info(f"🔥 [FOLLOWUP5] estágio={stage} enviado uid={uid}")
        if stage >= 5:
            r.delete(followup_active_key(uid))
            r.delete(followup_anchor_key(uid))
            r.setex(followup_silent_key(uid), timedelta(days=365), datetime.now().isoformat())
            logger.info(f"🤫 [FOLLOWUP5] uid={uid} entrou em modo silencioso")
        return True
    except Exception as e:
        if "blocked" in str(e).lower():
            add_to_blacklist(uid)
            cancel_followup5(uid)
        logger.error(f"[FOLLOWUP5] Erro estágio {stage} uid={uid}: {e}")
        return False

async def followup5_scheduler(bot):
    while True:
        try:
            users = get_all_active_users()
            now = datetime.now()
            for uid in users:
                try:
                    if is_blacklisted(uid):
                        continue
                    if is_ai_manually_paused(uid):
                        continue
                    if user_has_paid(uid):
                        cancel_followup5(uid, paid=True)
                        continue

                    # PIX gerado e ainda não pago: prévia de áudio uma única vez.
                    if await maybe_send_pending_pix_audio_recovery(bot, uid):
                        continue

                    if not is_followup5_active(uid) or is_followup5_silent(uid):
                        continue
                    current_stage = int(r.get(followup_stage_key(uid)) or 0)
                    next_stage = current_stage + 1
                    if next_stage > 5:
                        continue
                    anchor_raw = r.get(followup_anchor_key(uid)) or r.get(last_activity_key(uid))
                    if not anchor_raw:
                        continue
                    anchor = datetime.fromisoformat(anchor_raw)
                    silence_minutes = (now - anchor).total_seconds() / 60
                    if silence_minutes >= FOLLOWUP_5_DELAYS_MINUTES[next_stage]:
                        await send_followup5_stage(bot, uid, next_stage)
                        await asyncio.sleep(0.2)
                except Exception as item_err:
                    logger.error(f"[FOLLOWUP5] Erro scheduler uid={uid}: {item_err}")
        except Exception as e:
            logger.error(f"[FOLLOWUP5] Erro geral scheduler: {e}")
        await asyncio.sleep(60)

# ═══════════════════════════════════════════════════════════════════════════════
# 🔄 FOLLOW-UP POR INATIVIDADE E PIX PENDENTE
# ═══════════════════════════════════════════════════════════════════════════════
async def send_inactivity_followup(bot, uid, chat_id):
    """Envia follow-up após pitch com CTA A/B."""
    try:
        if is_ai_manually_paused(uid):
            return False
        messages = RESPONSE_POOLS.get("followup_safado", [])
        if not messages:
            return False
        msg = random.choice(messages)
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
        ]])
        await bot.send_message(chat_id=chat_id, text=msg, reply_markup=keyboard)
        save_message(uid, "system", "FOLLOW-UP INATIVIDADE ENVIADO")
        logger.info(f"📨 Follow-up por inatividade enviado para {uid}")
        return True
    except Exception as e:
        logger.error(f"Erro follow-up inatividade: {e}")
        return False


async def send_pending_pix_followup(bot, uid, chat_id, level=1):
    """Follow-up específico para quem gerou PIX e ainda não pagou."""
    try:
        if is_ai_manually_paused(uid):
            return False
        if user_has_paid(uid):
            return False
        key = f"pending_pix_followup:{uid}:{level}"
        if r.exists(key):
            return False
        msgs = {
            1: "Vi que seu PIX ficou gerado aqui. Quer que eu te mande o código de novo pra facilitar?",
            2: "Seu PIX ainda está pendente. Se quiser, clica no botão que eu reencontro o código pra você agora.",
            3: "Último aviso: seu PIX pode expirar em breve. Quer liberar o acesso agora?",
        }
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
        ]])
        await bot.send_message(chat_id=chat_id, text=msgs.get(level, msgs[1]), reply_markup=keyboard)
        r.setex(key, timedelta(hours=24), "1")
        save_message(uid, "system", f"FOLLOW-UP PIX PENDENTE nível {level} enviado")
        track_source_event(uid, f"pending_pix_followup_{level}")
        return True
    except Exception as e:
        logger.error(f"Erro send_pending_pix_followup: {e}")
        return False


# ✅ SYNCPAY: ambos os aliases apontam para o módulo SyncPay
send_teaser_and_pitch = syncpay_integration.send_teaser_com_pix
send_teaser_and_apex = send_teaser_and_apex   # usa nossa função custom v9

# ═══════════════════════════════════════════════════════════════════════════════
# 📨 FOLLOW-UPS
# ═══════════════════════════════════════════════════════════════════════════════

async def send_reengagement_message(bot, uid, level):
    if is_ai_manually_paused(uid) or is_engagement_paused(uid):
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
        if is_blacklisted(uid) or is_ai_manually_paused(uid) or is_engagement_paused(uid):
            continue
        if user_has_paid(uid) or is_followup5_active(uid) or is_followup5_silent(uid):
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
        sent_count = 0

        for uid in users:
            try:
                if is_ai_manually_paused(uid):
                    continue
                if not is_user_locked(uid):
                    continue
                hours_since_activity = get_hours_since_activity(uid)
                if not hours_since_activity:
                    continue
                retarget_key = f"retarget_sent:{uid}:{date.today()}"

                if 6 <= hours_since_activity < 30 and not r.exists(retarget_key):
                    # ✅ SYNCPAY: callback_data em vez de url
                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
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


async def pending_pix_followup_scheduler(bot):
    """Procura PIX pendente e faz follow-up sem chamar Grok."""
    while True:
        try:
            keys = r.keys("sp:pix:*")
            now = datetime.utcnow()
            for key in keys:
                try:
                    uid = int(str(key).split(":")[-1])
                    if user_has_paid(uid):
                        continue
                    raw = r.get(key)
                    if not raw:
                        continue
                    data = json.loads(raw)
                    created_raw = data.get("created_at")
                    if not created_raw:
                        continue
                    created = datetime.fromisoformat(created_raw)
                    age_min = (now - created).total_seconds() / 60
                    if age_min >= 8 and not r.exists(f"pending_pix_followup:{uid}:1"):
                        await send_pending_pix_followup(bot, uid, uid, 1)
                        await asyncio.sleep(0.2)
                    elif age_min >= 18 and not r.exists(f"pending_pix_followup:{uid}:2"):
                        await send_pending_pix_followup(bot, uid, uid, 2)
                        await asyncio.sleep(0.2)
                    elif age_min >= 27 and not r.exists(f"pending_pix_followup:{uid}:3"):
                        await send_pending_pix_followup(bot, uid, uid, 3)
                        await asyncio.sleep(0.2)
                except Exception as item_err:
                    logger.error(f"Erro pending pix item {key}: {item_err}")
        except Exception as e:
            logger.error(f"Erro pending_pix_followup_scheduler: {e}")
        await asyncio.sleep(300)


async def retargeting_scheduler(bot):
    while True:
        try:
            logger.info("🎯 Iniciando ciclo de retargeting...")
            await retarget_locked_users(bot)
        except Exception as e:
            logger.error(f"Erro retargeting scheduler: {e}")
        await asyncio.sleep(21600)

async def post_pitch_inactivity_scheduler(bot):
    """Compatibilidade: agora usa o scheduler de 5 estágios."""
    await followup5_scheduler(bot)

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
                if is_ai_manually_paused(uid):
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
                    await asyncio.sleep(0.3)

                elif 2 <= hours_since_start < 12 and not r.exists(recovery_2h_key):
                    message = random.choice(RECOVERY_MESSAGES["2h"])
                    await bot.send_message(chat_id=uid, text=message)
                    r.setex(recovery_2h_key, timedelta(hours=24), "1")
                    recovered_count += 1
                    save_message(uid, "system", "🔄 RECOVERY 2h enviado")
                    await asyncio.sleep(0.3)

                elif 12 <= hours_since_start < 24 and not r.exists(recovery_12h_key):
                    message = random.choice(RECOVERY_MESSAGES["12h"])
                    await bot.send_message(chat_id=uid, text=message)
                    r.setex(recovery_12h_key, timedelta(hours=24), "1")
                    recovered_count += 1
                    save_message(uid, "system", "🔄 RECOVERY 12h enviado")
                    await asyncio.sleep(0.3)

                elif 24 <= hours_since_start <= 48 and not r.exists(recovery_24h_key):
                    message = random.choice(RECOVERY_MESSAGES["24h"])
                    # ✅ SYNCPAY: callback_data em vez de url
                    keyboard = InlineKeyboardMarkup([[
                        InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
                    ]])
                    await bot.send_message(
                        chat_id=uid, text=message,
                        reply_markup=keyboard, parse_mode="Markdown"
                    )
                    r.setex(recovery_24h_key, timedelta(hours=48), "1")
                    recovered_count += 1
                    save_message(uid, "system", "🔄 RECOVERY 24h enviado (com VIP)")
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
    total = get_user_daily_limit(uid) + bonus
    if count == total - 5:
        mark_limit_warning_sent(uid)
        try:
            await context.bot.send_message(chat_id=chat_id, text=LIMIT_WARNING_MESSAGE, parse_mode="Markdown")
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
    else:
        router.assign_ia(uid, "maya")

    # Tracking first-touch/last-touch de origem. Não interfere no IA Router.
    save_user_source(uid, start_param)

    ia_config = router.get_ia_config(uid=uid)

    start_lock_key = f"start_lock:{uid}"
    if not r.set(start_lock_key, "1", nx=True, ex=60):
        return

    if is_blacklisted(uid):
        return

    # Se o admin assumiu este lead, /start também não dispara conversa automática.
    if is_ai_manually_paused(uid):
        update_last_activity(uid)
        save_message(uid, "user", "/start")
        logger.info(f"🖐️ [MODO MANUAL] /start recebido e automação suprimida uid={uid}")
        return

    update_last_activity(uid)
    track_funnel(uid, "start")
    track_source_event(uid, "start_realistic_flow")
    save_message(uid, "action", f"🚀 /START REALISTA ({start_param or 'direct'})")
    reset_ignored(uid)
    set_lang(uid, "pt")
    set_current_phase(uid, PHASES["ONBOARDING"]["id"])
    r.set(message_count_key(uid), 0)
    mark_first_contact(uid)
    save_followup_first_name(uid, update.effective_user.first_name or "")
    if is_followup5_silent(uid):
        # /start também respeita o modo silencioso; só reabre depois de 7 dias.
        touch_followup5_from_user(uid, "", update.effective_user.first_name or "")
    else:
        activate_followup5(uid, reset_stage=True)

    try:
        # Fluxo novo: abertura humana, sem menu genérico e sem botões iniciais.
        opening = get_realistic_start_message(uid, ia_config)
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=opening
            )
            save_message(uid, "maya", opening)
        except Exception as msg_error:
            logger.error(f"❌ Falha no start realista para {uid}: {msg_error}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Olha só quem resolveu aparecer... 😏\n\nVou ser sincera: eu não falo com todo mundo, mas abri uma exceção pra você. O que você quer saber primeiro?")

        # Mídia é opcional e vem depois da abertura para não parecer menu/robô.
        if START_SEND_WELCOME_MEDIA:
            try:
                await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_PHOTO)
                await asyncio.sleep(0.8)
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=ia_config["foto_bem_vinda"],
                    connect_timeout=10, read_timeout=10, write_timeout=10
                )
                save_message(uid, "system", "FOTO BOAS-VINDAS ENVIADA APÓS ABERTURA REALISTA")
            except Exception as photo_error:
                logger.error(f"❌ Erro enviando foto boas-vindas para {uid}: {photo_error}")

        if START_SEND_WELCOME_VIDEO:
            try:
                await context.bot.send_chat_action(update.effective_chat.id, ChatAction.UPLOAD_VIDEO)
                await asyncio.sleep(1)
                await context.bot.send_video(
                    chat_id=update.effective_chat.id,
                    video=ia_config["video_bem_vindo"],
                    caption="Só um gostinho do clima daqui… se quiser, me chama do seu jeito 😏",
                    connect_timeout=15, read_timeout=15, write_timeout=15
                )
                save_message(uid, "system", "VÍDEO BOAS-VINDAS ENVIADO APÓS ABERTURA REALISTA")
            except Exception as video_error:
                logger.error(f"❌ Erro enviando vídeo boas-vindas para {uid}: {video_error}")

    except Exception as e:
        logger.exception(f"💥 Erro geral /start para {uid}: {e}")
        try:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="Oi 😏 Me chama aqui que eu respondo.")
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

        # Botões antigos de conversa/teaser não furam o handoff manual.
        # Ações transacionais (PIX/VIP) continuam permitidas.
        if is_ai_manually_paused(uid) and query.data in {"quick_teaser", "quick_chat"}:
            logger.info(f"🖐️ [MODO MANUAL] Callback conversacional bloqueado uid={uid} data={query.data}")
            return

        if query.data == "quick_teaser":
            track_source_event(uid, "legacy_quick_teaser")
            await send_teaser_and_apex(context.bot, query.message.chat_id, uid)
            return

        if query.data == "quick_chat":
            track_source_event(uid, "legacy_quick_chat")
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="Perfeito. Então me chama do seu jeito — pode falar qualquer coisa, sem precisar escolher opção."
            )
            return

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

    incoming_text = ""
    try:
        incoming_text = (update.message.text or update.message.caption or "") if update.message else ""
    except Exception:
        incoming_text = ""

    # HANDOFF HUMANO: registra o que o lead falou, mas não chama Grok, não oferece
    # VIP, não envia hard-wall, não mexe no funil e não agenda respostas automáticas.
    if is_ai_manually_paused(uid):
        update_last_activity(uid)
        increment_conversation_messages(uid)
        if incoming_text:
            save_message(uid, "user", incoming_text)
        elif update.message and getattr(update.message, "photo", None):
            save_message(uid, "user", "[FOTO RECEBIDA DURANTE MODO MANUAL]")
        else:
            save_message(uid, "user", "[MENSAGEM RECEBIDA DURANTE MODO MANUAL]")
        logger.info(f"🖐️ [MODO MANUAL] Mensagem recebida sem resposta automática uid={uid}")
        return

    # Guarda a inatividade ANTES de atualizar last_activity.
    hours_since = get_hours_since_activity(uid)

    touch_followup5_from_user(uid, incoming_text, update.effective_user.first_name or "")

    update_last_activity(uid)
    streak, streak_updated = update_streak(uid)
    reset_ignored(uid)
    decrement_rejection_cooldown(uid)
    increment_msgs_since_offer(uid)
    increment_message_count(uid)
    increment_conversation_messages(uid)

    if hours_since and hours_since >= RETURN_WINDOW_HOURS:
        await handle_return(uid, context.bot, update.effective_chat.id)
        update_last_activity(uid)

    # Remarketing
    remarketing_sent_key = f"remarketing_dm_sent:{uid}:{date.today()}"
    if r.exists(f"saw_free_invite:{uid}") and not clicked_vip(uid) and not r.exists(remarketing_sent_key):
        _router = get_router()
        _ia_config = _router.get_ia_config(uid=uid)
        _preco = _ia_config.get("preco", PRECO_VIP)
        remarketing_msgs = [
            f"Oi de novo gato 😏 Pronto pra me ter completinha? Clica no botão abaixo pra pagar {_preco} via PIX e entrar agora 🔥",
            f"E aí amor, saudade? 😈 Ainda dá tempo de garantir o VIP por {_preco} — clica no botão!",
            f"Voltou! 🥰 Me tem completinha sem censura por {_preco} → clica abaixo 👇"
        ]
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
        ]])
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=random.choice(remarketing_msgs),
            reply_markup=keyboard
        )
        r.setex(remarketing_sent_key, timedelta(hours=24), "1")

    try:
        has_photo = bool(update.message.photo)
        text = update.message.text or ""

        # ====================== DETECÇÃO DE APEGO ======================
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

            # v10.2: se a IA prometeu um vídeo e o usuário confirmou, entrega o teaser real agora.
            if has_pending_teaser_video(uid) and is_video_confirmation(text):
                sent = await send_free_teaser_video(context.bot, update.effective_chat.id, uid)
                if sent:
                    return

        # ====================== TRATAMENTO DE FOTO ======================
        # Depois do pitch/PIX, foto também respeita o hard wall: não chama Grok
        # para continuar a fantasia gratuitamente.
        if has_photo and is_sales_hard_wall(uid) and not user_has_paid(uid):
            caption = update.message.caption or ""
            await send_sales_hard_wall_response(
                context.bot, update.effective_chat.id, uid, caption
            )
            return

        if has_photo:
            photo_file_id = update.message.photo[-1].file_id
            caption = update.message.caption or ""
            image_base64 = await download_photo_base64(context.bot, photo_file_id)
            
            if image_base64:
                try:
                    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
                except:
                    pass

                # ==================== v8.5 - MODO HÍBRIDO (FOTO) ====================
                if was_vip_just_offered(uid):
                    msgs_since = get_msgs_since_offer(uid)
                    if msgs_since <= 4:
                        grok_response = await grok.reply(uid, caption, image_base64=image_base64)
                        if is_ai_manually_paused(uid):
                            logger.info(f"🖐️ [MODO MANUAL] Resposta Grok em voo descartada uid={uid}")
                            return
                        await update.message.reply_text(grok_response["response"])
                    else:
                        response_text = random.choice([
                            "Amor, tô aqui doida esperando você pagar o PIX... 🔥 Quando cair eu libero tudo pra você 😈",
                            "Hmmm... mandou foto gostosa hein? 😏 Me avisa quando o PIX cair que eu te mostro muito mais 💦",
                            "Ainda tô aqui te esperando amor... quer que eu te mande mais uma foto enquanto você paga? 🔥",
                            "O VIP tá pronto pra você... é só pagar que eu sou toda sua 😘"
                        ])
                        await update.message.reply_text(response_text)
                        grok_response = {"response": response_text, "offer_teaser": False}
                else:
                    grok_response = await grok.reply(uid, caption, image_base64=image_base64)
                    if is_ai_manually_paused(uid):
                        logger.info(f"🖐️ [MODO MANUAL] Resposta Grok em voo descartada uid={uid}")
                        return
                    await update.message.reply_text(grok_response["response"])
                # =================================================================

                maybe_mark_teaser_video_promise(uid, grok_response.get("response", ""))

                if grok_response.get("offer_teaser", False):
                    can_offer, reason = can_offer_vip(uid)
                    if can_offer:
                        await asyncio.sleep(2)
                        await send_teaser_and_apex(context.bot, update.effective_chat.id, uid)
                return
            else:
                await update.message.reply_text("😔 Não consegui ver a foto... tenta de novo? 💕")
                return

                # ====================== MENSAGEM DE TEXTO NORMAL ======================
        mark_first_message_if_needed(uid)

        current_count = today_count(uid)
        bonus = get_bonus_msgs(uid)
        total = get_user_daily_limit(uid) + bonus
        if current_count >= total:
            last_chance_key = f"last_chance:{uid}:{date.today()}"
            if not r.exists(last_chance_key):
                r.setex(last_chance_key, timedelta(hours=20), "1")
                r.decr(count_key(uid))
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
                ]])
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=get_contextual_limit_message(uid),
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
                save_message(uid, "system", "🎁 ÚLTIMA CHANCE ATIVADA")
                return
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
            ]])
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=FOTO_LIMITE_ATINGIDO,
                    caption=LIMIT_REACHED_MESSAGE.format(preco=PRECO_VIP),
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            except:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=LIMIT_REACHED_MESSAGE.format(preco=PRECO_VIP),
                    reply_markup=keyboard,
                    parse_mode="Markdown"
                )
            save_message(uid, "system", "🚫 LIMITE ATINGIDO")
            return

        if bonus > 0:
            use_bonus_msg(uid)
        else:
            increment(uid)

        await check_and_send_limit_warning(uid, context, update.effective_chat.id)

                # ====================== FLUXO REALISTA: INTENÇÃO + LEAD TYPE ======================
        text = update.message.text or ""
        intent = detect_intent(text) if text else "neutral"
        lead_type = classify_lead(uid, text, intent)
        save_lead_signal(uid, lead_type, intent, text)

        # 1) Objeção de confiança: responde como conversa real, sem empurrar PIX.
        if should_send_trust_response(lead_type, text):
            response_text = get_trust_response(uid)
            await update.message.reply_text(response_text)
            save_message(uid, "maya", response_text)
            return

        # 1.25) Se o lead pedir uma amostra/duvidar da intensidade, envia a prévia uma vez.
        if should_send_vip_moan_sample(uid, text):
            await update.message.reply_text("Você quer saber como é? Escuta um pedacinho da prévia 👇")
            sent_audio = await send_vip_moan_audio_once(
                context.bot,
                update.effective_chat.id,
                uid,
                reason="sample_request"
            )
            if sent_audio:
                activate_sales_hard_wall(uid)
                await asyncio.sleep(0.8)
                await send_sales_hard_wall_response(
                    context.bot,
                    update.effective_chat.id,
                    uid,
                    text
                )
                return

        # 1.5) HARD WALL: depois do pitch/PIX, corta a fantasia grátis.
        # O interesse continua sendo atualizado pelo texto do usuário para que
        # os 5 follow-ups sejam segmentados no desejo real dele.
        if is_sales_hard_wall(uid) and not user_has_paid(uid):
            await send_sales_hard_wall_response(
                context.bot, update.effective_chat.id, uid, text
            )
            return

        # 2) Pedido claro de preço/acesso/conteúdo: não enrola, vai para SyncPay.
        if should_force_payment_flow(text, intent):
            can_offer, reason = can_offer_vip(uid)
            if can_offer:
                logger.info(f"💎 Pedido direto de acesso/pagamento detectado → SyncPay para {uid}")
                track_source_event(uid, "direct_payment_intent")
                await syncpay_integration.send_teaser_com_pix(context.bot, update.effective_chat.id, uid)
                save_message(uid, "system", "SYNC PAY FORÇADO (pedido direto de acesso/pagamento)")
                return

        try:
            await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
            # Delay menor no começo para não parecer travado; mantém sensação humana.
            await asyncio.sleep(1.1 if get_conversation_messages_count(uid) <= 3 else 1.8)
        except:
            pass

        # 3) Economia sem matar realismo: lead frio começa com Grok; lead quente recorrente usa pool.
        if should_use_pool_response(uid, intent, lead_type):
            response = get_unique_response(uid, "provocacao_pesada")
            await update.message.reply_text(response)
            grok_response = {"response": response, "offer_teaser": True, "interest_level": "high"}
        elif was_vip_just_offered(uid):
            msgs_since = get_msgs_since_offer(uid)
            if msgs_since <= 4:
                grok_response = await grok.reply(uid, text)
                if is_ai_manually_paused(uid):
                    logger.info(f"🖐️ [MODO MANUAL] Resposta Grok em voo descartada uid={uid}")
                    return
                await update.message.reply_text(grok_response["response"])
            else:
                response_text = random.choice([
                    "Eu tô aqui ainda. Se você quiser continuar, a parte do acesso já ficou no ponto pra você.",
                    "Você chegou bem perto de liberar. Quer que eu recupere o PIX pra facilitar?",
                    "Não vou ficar te pressionando, mas se você quiser continuar comigo agora, eu deixo o acesso pronto.",
                    "Se travou em alguma coisa no PIX, me fala. Eu te ajudo rapidinho."
                ])
                await update.message.reply_text(response_text)
                grok_response = {"response": response_text, "offer_teaser": False, "interest_level": "medium"}
        else:
            grok_response = await grok.reply(uid, text)
            if is_ai_manually_paused(uid):
                logger.info(f"🖐️ [MODO MANUAL] Resposta Grok em voo descartada uid={uid}")
                return
            await update.message.reply_text(grok_response["response"])

        maybe_mark_teaser_video_promise(uid, grok_response.get("response", ""))
        # =====================================================================

        # (O resto do seu código continua igual - CONFIRM_KEYWORDS, should_resend_button, should_offer, follow-up, streak, etc.)
        CONFIRM_KEYWORDS = [
            "sim", "quero", "cadê", "cade", "onde", "manda", "envia",
            "pode mandar", "to pronto", "tô pronto", "bora", "vamos",
            "me manda", "me passa", "qual o link", "qual link"
        ]
        IA_BUTTON_KEYWORDS = [
            "botão", "botao", "clica no botão", "clica no botao",
            "botão abaixo", "botao abaixo", "clica abaixo",
            "link abaixo", "aqui embaixo", "embaixo"
        ]

        text_lower_confirm = text.lower().strip()
        ia_response_lower = grok_response["response"].lower()
        already_pitched = saw_teaser(uid)
        is_confirm = any(kw in text_lower_confirm for kw in CONFIRM_KEYWORDS)
        ia_mentioned_button = any(kw in ia_response_lower for kw in IA_BUTTON_KEYWORDS)
        should_resend_button = (
            already_pitched
            and not grok_response.get("offer_teaser", False)
            and (is_confirm or ia_mentioned_button)
        )

        if should_resend_button:
            try:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton(get_cta_label(uid), callback_data="pagar_vip")
                ]])
                await asyncio.sleep(1)
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="👇",
                    reply_markup=keyboard
                )
                save_message(uid, "system", "🔁 BOTÃO VIP REENVIADO")
            except Exception as e:
                logger.error(f"Erro reenvio botão VIP: {e}")

                # ====================== CONTROLE ANTI-REPETIÇÃO DE PITCH/TEASER ======================
        should_offer = grok_response.get("offer_teaser", False)

        # Bloqueio forte: depois que já ofereceu o pitch, só permite novo teaser após 8 mensagens
        if should_offer:
            if was_vip_just_offered(uid):
                msgs_since_pitch = get_msgs_since_offer(uid)
                if msgs_since_pitch < 8:   # ← Aumentei o cooldown
                    should_offer = False
                    logger.info(f"[ANTI-REPETIÇÃO] Pitch bloqueado - apenas {msgs_since_pitch} mensagens desde o último offer")

            if should_offer:
                can_offer, reason = can_offer_vip(uid)
                if can_offer:
                    await asyncio.sleep(2)
                    await send_teaser_and_apex(context.bot, update.effective_chat.id, uid)

        # Follow-up agora é controlado exclusivamente pelo scheduler de 5 estágios.

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

async def audioid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: responda a um voice/audio com /audioid para obter o file_id do Telegram."""
    if update.effective_user.id not in ADMIN_IDS:
        return

    reply = update.message.reply_to_message if update.message else None
    if not reply:
        await update.message.reply_text(
            "Responda ao áudio com /audioid para eu mostrar o file_id."
        )
        return

    if reply.voice:
        await update.message.reply_text(
            f"TIPO: voice\nFILE_ID:\n{reply.voice.file_id}"
        )
        return

    if reply.audio:
        await update.message.reply_text(
            f"TIPO: audio\nFILE_ID:\n{reply.audio.file_id}"
        )
        return

    await update.message.reply_text(
        "A mensagem respondida não contém voice nem audio."
    )


async def videoid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: responda a um vídeo com /videoid para obter o file_id do Telegram."""
    if update.effective_user.id not in ADMIN_IDS:
        return

    reply = update.message.reply_to_message if update.message else None

    if not reply:
        await update.message.reply_text(
            "Responda ao vídeo com /videoid para eu mostrar o file_id."
        )
        return

    if reply.video:
        await update.message.reply_text(
            f"TIPO: video\nFILE_ID:\n{reply.video.file_id}"
        )
        return

    if reply.video_note:
        await update.message.reply_text(
            f"TIPO: video_note\nFILE_ID:\n{reply.video_note.file_id}"
        )
        return

    if reply.document and reply.document.mime_type:
        if reply.document.mime_type.startswith("video/"):
            await update.message.reply_text(
                f"TIPO: video_document\nFILE_ID:\n{reply.document.file_id}"
            )
            return

    await update.message.reply_text(
        "A mensagem respondida não contém um vídeo."
    )


async def imagemid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: responda a uma imagem com /imagemid para obter o file_id do Telegram."""
    if update.effective_user.id not in ADMIN_IDS:
        return

    reply = update.message.reply_to_message if update.message else None

    if not reply:
        await update.message.reply_text(
            "Responda à imagem com /imagemid para eu mostrar o file_id."
        )
        return

    if reply.photo:
        photo = reply.photo[-1]
        await update.message.reply_text(
            f"TIPO: photo\nFILE_ID:\n{photo.file_id}"
        )
        return

    if reply.document and reply.document.mime_type:
        if reply.document.mime_type.startswith("image/"):
            await update.message.reply_text(
                f"TIPO: image_document\nFILE_ID:\n{reply.document.file_id}"
            )
            return

    await update.message.reply_text(
        "A mensagem respondida não contém uma imagem."
    )


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
    application.add_handler(CommandHandler("audioid", audioid_cmd))
    application.add_handler(CommandHandler("videoid", videoid_cmd))
    application.add_handler(CommandHandler("imagemid", imagemid_cmd))
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

# ✅ SYNCPAY — inicialização
syncpay_integration.init(
    flask_app  = app,
    bot_app    = application,
    event_loop = loop,
    redis_conn = r,
    callbacks  = {
        "set_clicked_vip" : set_clicked_vip,
        "add_bonus_msgs"  : add_bonus_msgs,
        "save_message"    : save_message,
        "get_router"      : get_router,
        "CANAL_VIP_LINK"  : CANAL_VIP_LINK,
        "PRECO_VIP"       : PRECO_VIP,
        "track_source_event": track_source_event,
        "activate_followup5": activate_followup5,
        "touch_followup5": touch_followup5_from_user,
        "cancel_followup5": cancel_followup5,
        "activate_hard_wall": activate_sales_hard_wall,
        "clear_hard_wall": clear_sales_hard_wall,
        "send_vip_intro_audio": send_vip_intro_audio_once,
    }
)

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
        return {"status": "success", "webhook_url": info.url, "pending_updates": info.pending_update_count, "last_error": info.last_error_message}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.route("/webhook-info", methods=["GET"])
def webhook_info_route():
    try:
        async def get_info():
            return await application.bot.get_webhook_info()
        info = asyncio.run_coroutine_threadsafe(get_info(), loop).result(timeout=10)
        return {"url": info.url, "pending_update_count": info.pending_update_count, "last_error_message": info.last_error_message}, 200
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

@app.route("/limpar-pix-cache", methods=["GET"])
def limpar_pix_cache():
    # Esta rota apaga estado de pagamento; nunca deve ficar pública.
    admin_token = os.getenv("ADMIN_TOKEN")
    auth = (request.headers.get("Authorization") or "").strip()
    if not admin_token or auth != f"Bearer {admin_token}":
        return {"error": "Unauthorized"}, 401
    keys = r.keys("sp:pix:*")
    for key in keys:
        r.delete(key)
    return {"deletadas": len(keys), "status": "ok"}, 200

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 ADMIN DASHBOARD ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
if not ADMIN_TOKEN:
    raise RuntimeError("❌ Configure ADMIN_TOKEN nas variáveis de ambiente")

def admin_request_authorized():
    auth = (request.headers.get("Authorization") or "").strip()
    return auth == f"Bearer {ADMIN_TOKEN}"

@app.route("/admin/auth/check", methods=["GET"])
def admin_auth_check():
    if not admin_request_authorized():
        return {"ok": False, "error": "Unauthorized"}, 401
    return {"ok": True}, 200

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

@app.route("/admin/summary", methods=["GET"])
def admin_summary():
    if not admin_request_authorized():
        return {"error": "Unauthorized"}, 401

    try:
        now_ts = datetime.now().timestamp()

        pipe = r.pipeline(transaction=False)
        pipe.hgetall(admin_stats_hash_key())
        pipe.scard(all_users_key())
        pipe.scard(admin_counted_set("saw_teaser"))
        pipe.scard(admin_counted_set("clicked_vip"))
        pipe.zcount(admin_first_contact_zset_key(), now_ts - 86400, "+inf")
        pipe.zcount(admin_activity_zset_key(), now_ts - 86400, "+inf")
        pipe.zcount(admin_activity_zset_key(), now_ts - 86400 * 7, "+inf")
        pipe.zcount(admin_cooldown_zset_key(), now_ts, "+inf")
        pipe.zcount(admin_ignored_zset_key(), now_ts, "+inf")
        pipe.exists(admin_stats_ready_key())
        values = pipe.execute()

        raw = values[0] or {}
        total_users = int(values[1] or raw.get("total_users") or 0)
        saw_teaser_count = int(values[2] or raw.get("saw_teaser") or 0)
        clicked_vip_count = int(values[3] or raw.get("clicked_vip") or 0)
        new_users_24h = int(values[4] or 0)
        active_today = int(values[5] or 0)
        active_week = int(values[6] or 0)
        in_cooldown = int(values[7] or 0)
        ignored = int(values[8] or 0)
        ready = bool(values[9])

        streak_sum = int(raw.get("streak_sum") or 0)
        streak_users = int(raw.get("streak_users") or 0)
        avg_streak = (streak_sum / streak_users) if streak_users else 0.0

        stats = {
            "totalUsers": total_users,
            "newUsers24h": new_users_24h,
            "activeToday": active_today,
            "activeWeek": active_week,
            "sawTeaser": saw_teaser_count,
            "clickedVip": clicked_vip_count,
            "vipSales": int(raw.get("vip_sales") or 0),
            "totalMessages": int(raw.get("total_messages") or 0),
            "avgStreak": round(avg_streak, 1),
            "inCooldown": in_cooldown,
            "rejectedVip": int(raw.get("rejected_vip") or 0),
            "ignored": ignored,
        }
        funnel = {
            "started": int(raw.get("funnel_started") or 0),
            "firstMessage": int(raw.get("funnel_first_message") or 0),
            "sawTeaser": int(raw.get("funnel_saw_teaser") or 0),
            "clickedVip": int(raw.get("funnel_clicked_vip") or 0),
        }

        return {
            "stats": stats,
            "funnel": funnel,
            "server": {"status": "online", "statsReady": ready},
        }, 200
    except Exception as e:
        logger.exception(f"Erro admin summary: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/charts", methods=["GET"])
@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    if not admin_request_authorized():
        return {"error": "Unauthorized"}, 401

    try:
        # Cache curtíssimo: evita recalcular centenas de chaves em refreshes próximos,
        # sem deixar o painel perceptivelmente defasado.
        now_ts = datetime.now().timestamp()
        cache_ttl = int(os.getenv("ADMIN_STATS_CACHE_SECONDS", "15"))
        cached = getattr(admin_stats, "_cache", None)
        if cached and cached.get("data") is not None and now_ts - cached.get("ts", 0) < cache_ttl:
            return cached["data"], 200

        users = get_all_active_users()
        now = datetime.now()
        days = [now - timedelta(days=i) for i in range(6, -1, -1)]

        # O código antigo fazia vários r.get/r.exists por usuário, cada um como uma
        # viagem separada ao Redis remoto. Aqui agrupamos tudo em pipeline, em lotes.
        snapshots = []
        chunk_size = 500
        for start in range(0, len(users), chunk_size):
            chunk = users[start:start + chunk_size]
            pipe = r.pipeline(transaction=False)

            for uid in chunk:
                pipe.get(saw_teaser_key(uid))
                pipe.get(clicked_vip_key(uid))
                pipe.get(rejection_cooldown_key(uid))
                pipe.get(last_offer_rejected_key(uid))
                pipe.get(ignored_count_key(uid))
                pipe.get(last_activity_key(uid))
                pipe.get(first_contact_key(uid))
                pipe.get(conversation_messages_key(uid))
                pipe.get(streak_key(uid))
                pipe.get(funnel_key(uid))
                pipe.get(teaser_count_key(uid))
                pipe.get(vip_offers_today_key(uid))
                pipe.hgetall(source_meta_key(uid))
                pipe.exists(f"sp:pix:{uid}")
                pipe.exists(f"sp:paid:{uid}")
                for day in days:
                    pipe.get(f"daily_msg_sent:{uid}:{day.date()}")

            values = pipe.execute()
            idx = 0
            for uid in chunk:
                saw_raw = values[idx]; idx += 1
                clicked_raw = values[idx]; idx += 1
                cooldown_raw = values[idx]; idx += 1
                rejected_raw = values[idx]; idx += 1
                ignored_raw = values[idx]; idx += 1
                last_raw = values[idx]; idx += 1
                first_raw = values[idx]; idx += 1
                msgs_raw = values[idx]; idx += 1
                streak_raw = values[idx]; idx += 1
                funnel_raw = values[idx]; idx += 1
                teaser_count_raw = values[idx]; idx += 1
                vip_offers_raw = values[idx]; idx += 1
                source_meta = values[idx] or {}; idx += 1
                pix_pending = bool(values[idx]); idx += 1
                paid = bool(values[idx]); idx += 1
                daily = []
                for _ in days:
                    daily.append(values[idx]); idx += 1

                try: msgs = int(msgs_raw or 0)
                except Exception: msgs = 0
                try: streak = int(streak_raw or 0)
                except Exception: streak = 0
                try: funnel = int(funnel_raw or 0)
                except Exception: funnel = 0
                try: teaser_count = int(teaser_count_raw or 0)
                except Exception: teaser_count = 0
                try: vip_offers = int(vip_offers_raw or 0)
                except Exception: vip_offers = 0
                try: ignored = int(ignored_raw or 0)
                except Exception: ignored = 0

                last_dt = None
                hours = None
                if last_raw:
                    try:
                        last_dt = datetime.fromisoformat(last_raw)
                        hours = (now - last_dt).total_seconds() / 3600
                    except Exception:
                        pass

                first_dt = None
                if first_raw:
                    try:
                        first_dt = datetime.fromisoformat(first_raw)
                    except Exception:
                        pass

                daily_counts = []
                for raw in daily:
                    try: daily_counts.append(int(raw or 0))
                    except Exception: daily_counts.append(0)

                snapshots.append({
                    "uid": uid,
                    "saw_raw": saw_raw,
                    "saw": bool(saw_raw),
                    "clicked": bool(clicked_raw),
                    "cooldown_raw": cooldown_raw,
                    "cooldown": bool(cooldown_raw),
                    "rejected": bool(rejected_raw),
                    "ignored": ignored,
                    "hours": hours,
                    "first_dt": first_dt,
                    "msgs": msgs,
                    "streak": streak,
                    "funnel": funnel,
                    "teaser_count": teaser_count,
                    "vip_offers": vip_offers,
                    "source_meta": source_meta,
                    "pix_pending": pix_pending,
                    "paid": paid,
                    "daily": daily_counts,
                })

        total_users = len(snapshots)
        saw_teaser_count = sum(1 for x in snapshots if x["saw"])
        clicked_vip_count = sum(1 for x in snapshots if x["clicked"])
        in_cooldown_count = sum(1 for x in snapshots if x["cooldown"])
        rejected_vip_count = sum(1 for x in snapshots if x["rejected"])
        ignored_count = sum(1 for x in snapshots if x["ignored"] > 0)
        active_today = sum(1 for x in snapshots if x["hours"] is not None and x["hours"] < 24)
        active_week = sum(1 for x in snapshots if x["hours"] is not None and x["hours"] < 168)
        new_users_24h = sum(
            1 for x in snapshots
            if x["first_dt"] is not None and (now - x["first_dt"]).total_seconds() < 86400
        )
        total_messages = sum(x["msgs"] for x in snapshots)
        streaks = [x["streak"] for x in snapshots if x["streak"] > 0]
        avg_streak = sum(streaks) / len(streaks) if streaks else 0

        funnel_stages = {i: 0 for i in range(5)}
        for x in snapshots:
            if x["funnel"] in funnel_stages:
                funnel_stages[x["funnel"]] += 1

        activity_labels = []
        activity_messages = []
        for pos, day in enumerate(days):
            day_name = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][day.weekday()]
            activity_labels.append(day_name)
            activity_messages.append(sum(x["daily"][pos] for x in snapshots))

        interest_levels = {"high": 0, "medium": 0, "low": 0}
        for x in snapshots:
            if x["msgs"] > 20 and x["saw"]:
                interest_levels["high"] += 1
            elif x["msgs"] > 10 or x["saw"]:
                interest_levels["medium"] += 1
            else:
                interest_levels["low"] += 1

        hourly_labels = [f"{h}h" for h in range(0, 24, 2)]
        hourly_offers = [0] * 12
        for x in snapshots:
            if x["saw_raw"]:
                try:
                    hour = datetime.fromisoformat(x["saw_raw"]).hour
                    hourly_offers[hour // 2] += 1
                except Exception:
                    pass

        growth_labels = [f"{h}h" for h in range(24)]
        growth_users = [0] * 24
        for x in snapshots:
            first_dt = x["first_dt"]
            if first_dt and first_dt.date() == now.date():
                growth_users[first_dt.hour] += 1

        user_data = [x for x in snapshots if x["msgs"] > 0]
        user_data.sort(key=lambda x: x["msgs"] * (x["streak"] + 1), reverse=True)
        top_users = []
        for user in user_data[:20]:
            hours = user["hours"] if user["hours"] is not None else 999
            if hours < 2: status, status_text = "hot", "🔥 Quente"
            elif hours < 24: status, status_text = "warm", "😊 Morno"
            else: status, status_text = "cold", "❄️ Frio"
            if user["msgs"] > 20: interest, interest_text = "hot", "Alto"
            elif user["msgs"] > 10: interest, interest_text = "warm", "Médio"
            else: interest, interest_text = "cold", "Baixo"
            if hours < 1: last_activity = "< 1h atrás"
            elif hours < 24: last_activity = f"{int(hours)}h atrás"
            else: last_activity = f"{int(hours/24)}d atrás"
            top_users.append({
                "id": user["uid"], "messages": user["msgs"], "streak": user["streak"],
                "teasers": user["teaser_count"], "lastActivity": last_activity,
                "status": status, "statusText": status_text,
                "interest": interest, "interestText": interest_text
            })

        cooldown_users = []
        for x in snapshots:
            if not x["cooldown"]:
                continue
            try: cooldown_remaining = int(x["cooldown_raw"] or 0)
            except Exception: cooldown_remaining = 0
            hours = x["hours"] if x["hours"] is not None else 0
            if hours < 1: last_contact = "< 1h atrás"
            elif hours < 24: last_contact = f"{int(hours)}h atrás"
            else: last_contact = f"{int(hours/24)}d atrás"
            cooldown_users.append({
                "id": x["uid"], "cooldownRemaining": cooldown_remaining,
                "offersToday": x["vip_offers"], "totalTeasers": x["teaser_count"],
                "lastContact": last_contact
            })

        started = funnel_stages[1]
        first_message = funnel_stages[2]
        saw_teaser_funnel = funnel_stages[3]
        clicked_vip_funnel = funnel_stages[4]

        def calc_drop(from_stage, to_stage):
            if from_stage == 0: return 0
            return ((from_stage - to_stage) / from_stage * 100)

        drop_1 = calc_drop(started, first_message)
        drop_2 = calc_drop(first_message, saw_teaser_funnel)
        drop_3 = calc_drop(saw_teaser_funnel, clicked_vip_funnel)

        def get_drop_class(rate):
            if rate > 70: return "hot"
            elif rate > 40: return "warm"
            return "cold"

        def get_status(rate):
            if rate > 70: return "🚨 Crítico"
            elif rate > 40: return "⚠️ Alto"
            return "✅ Normal"

        dropoff = [
            {"name": "Start → 1ª Msg", "users": started - first_message, "percent": round((first_message / started * 100) if started > 0 else 0, 1), "dropRate": f"{drop_1:.1f}", "dropClass": get_drop_class(drop_1), "status": get_status(drop_1)},
            {"name": "1ª Msg → Teaser", "users": first_message - saw_teaser_funnel, "percent": round((saw_teaser_funnel / first_message * 100) if first_message > 0 else 0, 1), "dropRate": f"{drop_2:.1f}", "dropClass": get_drop_class(drop_2), "status": get_status(drop_2)},
            {"name": "Teaser → Clique VIP", "users": saw_teaser_funnel - clicked_vip_funnel, "percent": round((clicked_vip_funnel / saw_teaser_funnel * 100) if saw_teaser_funnel > 0 else 0, 1), "dropRate": f"{drop_3:.1f}", "dropClass": get_drop_class(drop_3), "status": get_status(drop_3)}
        ]

        # Aquisição usando o mesmo snapshot; evita percorrer o Redis inteiro uma segunda vez.
        by_source = {}
        try:
            vip_price = float(PRECO_VIP.replace("R$", "").replace(",", ".").strip() or 9)
        except Exception:
            vip_price = 9.0

        for x in snapshots:
            meta = x["source_meta"] or {}
            source = meta.get("first_source") or meta.get("last_source") or "telegram"
            is_ads = (meta.get("first_is_ads") or meta.get("last_is_ads") or "0") == "1"
            row = by_source.setdefault(source, {
                "source": source, "users": 0, "adsUsers": 0, "sawTeaser": 0,
                "pixCreated": 0, "paid": 0, "clickedVip": 0, "messages": 0,
                "estimatedCost": 0.0, "estimatedRevenue": 0.0,
                "estimatedProfit": 0.0, "conversionRate": 0.0, "costPerUser": 0.0,
            })
            row["users"] += 1
            if is_ads:
                row["adsUsers"] += 1
                row["estimatedCost"] += USER_ADS_COST_CENTS / 100
            row["estimatedCost"] += DEFAULT_BOT_COST_CENTS / 100
            if x["saw"]: row["sawTeaser"] += 1
            if x["pix_pending"]: row["pixCreated"] += 1
            if x["clicked"]: row["clickedVip"] += 1
            if x["paid"]:
                row["paid"] += 1
                row["estimatedRevenue"] += vip_price
            row["messages"] += x["msgs"]

        for row in by_source.values():
            if row["users"]:
                row["conversionRate"] = round((row["paid"] / row["users"]) * 100, 2)
                row["costPerUser"] = round(row["estimatedCost"] / row["users"], 2)
            row["estimatedCost"] = round(row["estimatedCost"], 2)
            row["estimatedRevenue"] = round(row["estimatedRevenue"], 2)
            row["estimatedProfit"] = round(row["estimatedRevenue"] - row["estimatedCost"], 2)
        acquisition = sorted(by_source.values(), key=lambda x: (x["estimatedProfit"], x["paid"], x["users"]), reverse=True)

        payload = {
            "stats": {"totalUsers": total_users, "newUsers24h": new_users_24h, "activeToday": active_today, "activeWeek": active_week, "sawTeaser": saw_teaser_count, "clickedVip": clicked_vip_count, "totalMessages": total_messages, "avgStreak": round(avg_streak, 1), "inCooldown": in_cooldown_count, "rejectedVip": rejected_vip_count, "ignored": ignored_count},
            "funnel": {"started": started, "firstMessage": first_message, "sawTeaser": saw_teaser_funnel, "clickedVip": clicked_vip_funnel},
            "activity": {"labels": activity_labels, "messages": activity_messages},
            "interest": interest_levels,
            "hourly": {"labels": hourly_labels, "offers": hourly_offers},
            "growthHourly": {"labels": growth_labels, "users": growth_users},
            "topUsers": top_users,
            "cooldownUsers": cooldown_users,
            "dropoff": dropoff,
            "acquisition": acquisition
        }

        try:
            r.hset(admin_stats_hash_key(), mapping={
                "total_users": total_users,
                "saw_teaser": saw_teaser_count,
                "clicked_vip": clicked_vip_count,
                "total_messages": total_messages,
                "streak_sum": int(sum(streaks)),
                "streak_users": len(streaks),
                "rejected_vip": rejected_vip_count,
                "funnel_started": started,
                "funnel_first_message": first_message,
                "funnel_saw_teaser": saw_teaser_funnel,
                "funnel_clicked_vip": clicked_vip_funnel,
            })
        except Exception:
            pass

        admin_stats._cache = {"ts": now_ts, "data": payload}
        return payload, 200

    except Exception as e:
        logger.exception(f"Erro admin stats: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/acquisition", methods=["GET"])
def admin_acquisition():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"error": "Unauthorized"}, 401
    token = auth_header.replace("Bearer ", "")
    if token != ADMIN_TOKEN:
        return {"error": "Invalid token"}, 401
    try:
        users = get_all_active_users()
        return {"acquisition": get_acquisition_breakdown(users)}, 200
    except Exception as e:
        logger.exception(f"Erro admin acquisition: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/leads", methods=["GET"])
@app.route("/admin/conversations", methods=["GET"])
def admin_conversations():
    """
    Lista metadados dos leads. NUNCA inclui histórico de mensagens.
    /admin/conversations é mantida como alias para compatibilidade.
    """
    if not admin_request_authorized():
        return {"error": "Unauthorized"}, 401

    try:
        filter_type = (request.args.get("filter") or request.args.get("status") or "all").strip().lower()
        phase_filter = (request.args.get("phase") or "all").strip().lower()
        query_uid = (request.args.get("q") or "").strip()
        try:
            limit = max(1, min(int(request.args.get("limit") or 40), 100))
        except Exception:
            limit = 40
        try:
            offset = max(0, int(request.args.get("offset") or 0))
        except Exception:
            offset = 0

        exact_search = False
        if query_uid:
            if not query_uid.isdigit():
                empty_page = {"offset": 0, "limit": limit, "total": 0, "hasMore": False}
                return {"leads": [], "conversations": [], "pagination": empty_page}, 200
            wanted_uid = int(query_uid)
            users = [wanted_uid] if r.sismember(all_users_key(), str(wanted_uid)) else []
            exact_search = True
            offset = 0
        else:
            # Índice ordenado por atividade: não precisamos mais começar pelo SET completo.
            now_ts = datetime.now().timestamp()
            users_raw = r.zrevrangebyscore(admin_activity_zset_key(), "+inf", now_ts - 86400)
            if users_raw:
                users = []
                for raw in users_raw:
                    try:
                        users.append(int(raw))
                    except (TypeError, ValueError):
                        pass
            else:
                # Fallback temporário durante a primeira migração.
                users = get_all_active_users()

        candidates = []
        now = datetime.now()
        chunk_size = 500
        for start_idx in range(0, len(users), chunk_size):
            chunk = users[start_idx:start_idx + chunk_size]
            pipe = r.pipeline(transaction=False)
            for uid in chunk:
                pipe.get(last_activity_key(uid))
                pipe.get(current_phase_key(uid))
                pipe.get(manual_ai_paused_key(uid))
                pipe.get(conversation_messages_key(uid))
                pipe.get(rejection_cooldown_key(uid))
                pipe.get(clicked_vip_key(uid))
                pipe.get(saw_teaser_key(uid))
                pipe.get(teaser_count_key(uid))
                pipe.get(f"sp:pix:{uid}")
                pipe.get(f"sp:paid:{uid}")
            vals = pipe.execute()
            idx = 0

            for uid in chunk:
                last_raw = vals[idx]; idx += 1
                phase_raw = vals[idx]; idx += 1
                manual_raw = vals[idx]; idx += 1
                msgs_raw = vals[idx]; idx += 1
                cooldown_raw = vals[idx]; idx += 1
                clicked_raw = vals[idx]; idx += 1
                saw_raw = vals[idx]; idx += 1
                teaser_count_raw = vals[idx]; idx += 1
                pix_raw = vals[idx]; idx += 1
                paid_raw = vals[idx]; idx += 1

                hours = None
                if last_raw:
                    try:
                        hours = (now - datetime.fromisoformat(last_raw)).total_seconds() / 3600
                    except Exception:
                        pass
                if not exact_search and (hours is None or hours > 24):
                    continue

                try: current_phase = int(phase_raw or 0)
                except Exception: current_phase = 0
                try: msg_count = int(msgs_raw or 0)
                except Exception: msg_count = 0
                try: teaser_count = int(teaser_count_raw or 0)
                except Exception: teaser_count = 0

                ai_paused = bool(manual_raw)
                in_cooldown = bool(cooldown_raw)
                clicked = bool(clicked_raw)
                saw = bool(saw_raw)
                pix_pending = bool(pix_raw) and not bool(paid_raw)
                paid = bool(paid_raw)

                if phase_filter != "all":
                    try:
                        if int(phase_filter) != current_phase:
                            continue
                    except (TypeError, ValueError):
                        pass

                if filter_type == "hot" and msg_count <= 20:
                    continue
                elif filter_type == "cooldown" and not in_cooldown:
                    continue
                elif filter_type in {"converted", "vip"} and not paid:
                    continue
                elif filter_type == "manual" and not ai_paused:
                    continue

                if hours is None:
                    last_activity = "—"
                elif hours < (1 / 60):
                    last_activity = "< 1 min"
                elif hours < 1:
                    last_activity = f"{max(1, int(hours * 60))} min"
                elif hours < 24:
                    last_activity = f"{int(hours)}h"
                else:
                    last_activity = f"{int(hours / 24)}d"

                if paid:
                    status, status_class = "💎 Pagou VIP", "vip"
                elif pix_pending:
                    status, status_class = "🧾 PIX gerado — aguardando pagamento", "warm"
                elif clicked:
                    status, status_class = "💳 Clicou no VIP", "warm"
                elif in_cooldown:
                    status, status_class = "🚫 Cooldown", "cooldown"
                elif msg_count > 20:
                    status, status_class = "🔥 Quente", "hot"
                else:
                    status, status_class = "💬 Conversando", "normal"

                candidates.append({
                    "userId": uid,
                    "hours": hours,
                    "currentPhase": current_phase,
                    "phaseName": get_phase_name(current_phase),
                    "aiPaused": ai_paused,
                    "totalMessages": msg_count,
                    "inCooldown": in_cooldown,
                    "clickedVip": clicked,
                    "pixPending": pix_pending,
                    "paid": paid,
                    "sawTeaser": saw,
                    "teaserCount": teaser_count,
                    "lastActivity": last_activity,
                    "status": status,
                    "statusClass": status_class,
                })

        candidates.sort(key=lambda x: x["hours"] if x["hours"] is not None else 999999)
        total = len(candidates)

        if exact_search:
            page = candidates[:1]
        else:
            page = candidates[offset:offset + limit]

        pagination = {
            "offset": offset,
            "limit": limit,
            "total": total,
            "hasMore": (offset + len(page)) < total,
        }
        return {"leads": page, "conversations": page, "pagination": pagination}, 200

    except Exception as e:
        logger.exception(f"Erro admin leads: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/conversations/export", methods=["GET"])
def admin_conversations_export():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"error": "Unauthorized"}, 401
    token = auth_header.replace("Bearer ", "")
    if token != ADMIN_TOKEN:
        return {"error": "Invalid token"}, 401

    start_raw = (request.args.get("start") or "").strip()
    end_raw = (request.args.get("end") or "").strip()

    try:
        start_date = datetime.strptime(start_raw, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_raw, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "Use start e end no formato YYYY-MM-DD"}, 400

    if end_date < start_date:
        return {"error": "A data final não pode ser anterior à data inicial"}, 400

    if (end_date - start_date).days > 365:
        return {"error": "O intervalo máximo por exportação é de 366 dias"}, 400

    try:
        output = io.StringIO()
        output.write("\ufeff")  # BOM para Excel reconhecer UTF-8 corretamente
        writer = csv.writer(output, delimiter=";", lineterminator="\n")
        writer.writerow([
            "data_hora", "user_id", "nome", "papel", "mensagem",
            "origem", "campanha", "comprou_vip", "em_cooldown"
        ])

        current = start_date
        exported = 0
        while current <= end_date:
            day = current.isoformat()
            user_ids = r.smembers(chatlog_day_users_key(day)) or set()

            for uid_raw in user_ids:
                try:
                    uid = int(uid_raw)
                except (TypeError, ValueError):
                    continue

                profile = get_user_profile(uid) or {}
                source = get_user_source(uid) or {}
                rows = r.lrange(chatlog_day_key(uid, day), 0, -1) or []

                for raw in rows:
                    try:
                        item = json.loads(raw)
                    except Exception:
                        continue

                    writer.writerow([
                        item.get("timestamp", ""),
                        uid,
                        profile.get("name", ""),
                        item.get("role", ""),
                        item.get("text", ""),
                        source.get("source", ""),
                        source.get("campaign", ""),
                        "sim" if user_has_paid(uid) else "não",
                        "sim" if is_in_rejection_cooldown(uid) else "não",
                    ])
                    exported += 1

            current += timedelta(days=1)

        filename = f"conversas_{start_date.isoformat()}_a_{end_date.isoformat()}.csv"
        response = app.response_class(output.getvalue(), mimetype="text/csv")
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["X-Exported-Rows"] = str(exported)
        return response

    except Exception as e:
        logger.exception(f"Erro exportando conversas: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/user/<int:user_id>/messages", methods=["GET"])
def admin_user_messages(user_id):
    """Busca o chat apenas quando o card é aberto, em páginas a partir do fim da lista."""
    if not admin_request_authorized():
        return {"error": "Unauthorized"}, 401
    if not r.sismember(all_users_key(), str(user_id)):
        return {"error": "User not found"}, 404

    try:
        try:
            limit = max(5, min(int(request.args.get("limit") or 15), 50))
        except Exception:
            limit = 15
        try:
            before = max(0, int(request.args.get("before") or 0))
        except Exception:
            before = 0

        total = int(r.llen(chatlog_key(user_id)) or 0)
        end_exclusive = max(0, total - before)
        start_idx = max(0, end_exclusive - limit)
        end_idx = end_exclusive - 1

        if end_idx < 0:
            messages = []
        else:
            messages = r.lrange(chatlog_key(user_id), start_idx, end_idx) or []

        loaded_from_tail = before + len(messages)
        has_more = start_idx > 0

        return {
            "userId": user_id,
            "messages": messages,
            "pagination": {
                "limit": limit,
                "before": before,
                "nextBefore": loaded_from_tail if has_more else None,
                "hasMore": has_more,
                "total": total,
            },
        }, 200
    except Exception as e:
        logger.exception(f"Erro carregando mensagens uid={user_id}: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/user/<int:user_id>", methods=["GET"])
def admin_user_detail(user_id):
    if not admin_request_authorized():
        return {"error": "Unauthorized"}, 401
    try:
        if not r.sismember(all_users_key(), str(user_id)):
            return {"error": "User not found"}, 404
        chatlog = r.lrange(chatlog_key(user_id), 0, -1)
        profile = get_user_profile(user_id)
        memory = get_memory(user_id)
        return {"id": user_id, "profile": profile, "stats": {"messages": get_conversation_messages_count(user_id), "streak": get_streak(user_id), "teasers": get_teaser_count(user_id), "sawTeaser": saw_teaser(user_id), "clickedVip": clicked_vip(user_id), "pixPending": user_has_pending_pix(user_id) and not user_has_paid(user_id), "paid": user_has_paid(user_id), "inCooldown": is_in_rejection_cooldown(user_id), "cooldownRemaining": get_rejection_cooldown_remaining(user_id), "vipOffersToday": get_vip_offers_today(user_id), "bonusMessages": get_bonus_msgs(user_id), "todayCount": today_count(user_id), "ignored": get_ignored_count(user_id), "lastActivity": r.get(last_activity_key(user_id)), "firstContact": r.get(first_contact_key(user_id)), "source": get_user_source(user_id), "leadProfile": get_lead_profile(user_id), "dailyLimit": get_user_daily_limit(user_id), "aiPaused": is_ai_manually_paused(user_id), "pauseInfo": get_ai_manual_pause_info(user_id)}, "chatlog": chatlog, "memory": memory}, 200
    except Exception as e:
        logger.exception(f"Erro user detail: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/user/<int:user_id>/ai", methods=["POST"])
def admin_user_ai_control(user_id):
    if not admin_request_authorized():
        return {"error": "Unauthorized"}, 401
    if not r.sismember(all_users_key(), str(user_id)):
        return {"error": "User not found"}, 404

    data = request.get_json(silent=True) or {}
    action = str(data.get("action") or "").strip().lower()

    if action == "pause":
        if not pause_ai_for_user(user_id, source="admin_panel"):
            return {"error": "Could not pause AI"}, 500
        save_message(user_id, "system", "🖐️ MODO MANUAL ATIVADO PELO ADMIN")
    elif action == "resume":
        if not resume_ai_for_user(user_id):
            return {"error": "Could not resume AI"}, 500
        save_message(user_id, "system", "▶️ IA RETOMADA PELO ADMIN")
    else:
        return {"error": "action must be pause or resume"}, 400

    return {
        "success": True,
        "userId": user_id,
        "aiPaused": is_ai_manually_paused(user_id),
        "pauseInfo": get_ai_manual_pause_info(user_id),
    }, 200


@app.route("/admin/user/<int:user_id>/message", methods=["POST"])
def admin_send_user_message(user_id):
    if not admin_request_authorized():
        return {"error": "Unauthorized"}, 401
    if not r.sismember(all_users_key(), str(user_id)):
        return {"error": "User not found"}, 404

    data = request.get_json(silent=True) or {}
    message = str(data.get("message") or "").strip()
    pause_ai = bool(data.get("pause_ai", True))

    if not message:
        return {"error": "Message required"}, 400
    if len(message) > 4096:
        return {"error": "Telegram text messages support at most 4096 characters"}, 400

    was_paused = is_ai_manually_paused(user_id)
    if pause_ai and not was_paused:
        if not pause_ai_for_user(user_id, source="admin_message"):
            return {"error": "Could not pause AI before sending"}, 500

    async def _send_manual_message():
        return await application.bot.send_message(chat_id=user_id, text=message)

    try:
        future = asyncio.run_coroutine_threadsafe(_send_manual_message(), loop)
        sent = future.result(timeout=15)
        if pause_ai and not was_paused:
            save_message(user_id, "system", "🖐️ MODO MANUAL ATIVADO AUTOMATICAMENTE PELO ENVIO DO ADMIN")
        save_message(user_id, "admin", message)
        logger.info(f"📨 [ADMIN] Mensagem manual enviada uid={user_id} message_id={getattr(sent, 'message_id', None)}")
        return {
            "success": True,
            "userId": user_id,
            "messageId": getattr(sent, "message_id", None),
            "aiPaused": is_ai_manually_paused(user_id),
        }, 200
    except Exception as e:
        # Se a rota pausou automaticamente e o envio falhou, volta ao estado anterior.
        if pause_ai and not was_paused:
            resume_ai_for_user(user_id)
        logger.exception(f"Erro enviando mensagem manual para {user_id}: {e}")
        return {"error": str(e)}, 500


@app.route("/admin/broadcast", methods=["POST"])
def admin_broadcast():
    if not admin_request_authorized():
        return {"error": "Unauthorized"}, 401
    try:
        data = request.json or {}
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
            users = [u for u in users if saw_teaser(u) and not user_has_paid(u)]

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
# 🚀 STARTUP
# ═══════════════════════════════════════════════════════════════════════════════

async def startup_sequence():
    try:
        logger.info("🚀 Iniciando Sophia Bot v8.3 APEX...")

        init_router(redis_url=REDIS_URL, config_path="ias_config.json")
        logger.info("✅ IA Router inicializado")

        await application.initialize()
        await application.start()
        logger.info("✅ Application Telegram iniciada")

        webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

        try:
            await application.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(0.5)

            await application.bot.set_webhook(
                url=webhook_url,
                allowed_updates=["message", "callback_query"]
            )

            info = await application.bot.get_webhook_info()
            logger.info(f"✅ Webhook configurado: {info.url}")
            logger.info(f"📬 Pending updates: {info.pending_update_count}")
            logger.info(f"⚠️ Último erro webhook: {info.last_error_message}")

        except Exception as e:
            logger.exception(f"❌ Erro configurando webhook: {e}")
            raise

        me = await application.bot.get_me()
        logger.info(f"🤖 Bot ativo: @{me.username} (ID: {me.id})")
        logger.info("✨ v8.3 APEX + SyncPay PIX integrado")

        # Marca o bot como pronto ANTES dos schedulers
        logger.info("✅ BOT PRONTO PARA RECEBER MENSAGENS")

        # Schedulers no MESMO event loop do bot.
        # Retargeting desligado no boot porque pode travar a inicialização.
        loop.create_task(engagement_scheduler(application.bot))
        # loop.create_task(retargeting_scheduler(application.bot))
        loop.create_task(post_pitch_inactivity_scheduler(application.bot))  # FOLLOW-UP 5 ESTÁGIOS
        loop.create_task(admin_stats_maintenance_scheduler())
        # Desligados para não gerar mensagens extras fora dos 5 estágios:
        # loop.create_task(pending_pix_followup_scheduler(application.bot))
        # loop.create_task(recovery_scheduler(application.bot))

        logger.info("✅ Schedulers iniciados com FOLLOW-UP 5 ESTÁGIOS")

        # ====================== META CAPI TRACKER ======================
        try:
            from meta_capi import start_capi_tracker
            loop.create_task(start_capi_tracker())
            logger.info("📡 Meta CAPI Tracker agendado com sucesso!")
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar Meta CAPI Tracker: {e}")
        # ============================================================

    except Exception as e:
        logger.exception(f"💥 ERRO CRÍTICO: {e}")
        raise

# ═══════════════════════════════════════════════════════════════════════════════
# 🎬 MAIN
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    future = asyncio.run_coroutine_threadsafe(startup_sequence(), loop)

    try:
        future.result(timeout=20)
    except Exception as e:
        logger.exception(f"⚠️ Startup demorou ou falhou: {e}")

    logger.info(f"🌐 Flask rodando na porta {PORT}")
    logger.info("🚀 Sophia Bot v8.3 APEX + SyncPay operacional!")

    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
