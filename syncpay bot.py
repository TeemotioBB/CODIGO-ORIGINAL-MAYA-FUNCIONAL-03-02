"""
Integração SyncPay + Bot Telegram
==================================
Dependências:
    pip install python-telegram-bot requests flask

Como rodar:
    1. Preencha as variáveis de configuração abaixo
    2. Exponha sua porta 5000 para a internet (use ngrok em testes locais)
       ngrok http 5000  → copie a URL e coloque em WEBHOOK_BASE_URL
    3. python syncpay_bot.py
"""

import threading
import requests
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================================
# CONFIGURAÇÕES — preencha com seus dados
# ============================================================

TELEGRAM_TOKEN = "8589992999:AAGiS3WxeAqSPd94QPmNIuEIUw_TToJ6Qlc"          # Token do BotFather

SYNCPAY_CLIENT_ID     = "S423ab714-71b3-4ee1-8f28-602415b2bf92"      # Painel SyncPay → credenciais
SYNCPAY_CLIENT_SECRET = "65ea61dd-eb51-4ce1-b3e0-fc2fcd838b6b"

# URL pública onde seu servidor recebe os webhooks da SyncPay.
# Em produção: domínio real (ex: https://meusite.com)
# Em testes:   use ngrok → ex: https://abc123.ngrok.io
WEBHOOK_BASE_URL = "https://SEU_DOMINIO_OU_NGROK_AQUI"

SYNCPAY_BASE_URL = "https://api.syncpay.com.br"   # Base da API SyncPay

# ============================================================
# ESTADO EM MEMÓRIA (substitua por banco de dados em produção)
# ============================================================

# Guarda pedidos pendentes: { identifier: { chat_id, amount, ... } }
pedidos_pendentes: dict = {}

# Cache do token de autenticação
_token_cache = {"token": None, "expires_at": None}

# ============================================================
# AUTENTICAÇÃO — gera e cacheia o token (válido 1h)
# ============================================================

def get_syncpay_token() -> str:
    """Retorna o token de acesso, gerando um novo só se expirado."""
    agora = datetime.utcnow()

    if _token_cache["token"] and _token_cache["expires_at"]:
        # Renova 5 minutos antes de expirar
        if agora < _token_cache["expires_at"] - timedelta(minutes=5):
            return _token_cache["token"]

    print("🔄 Gerando novo token SyncPay...")
    resp = requests.post(
        f"{SYNCPAY_BASE_URL}/api/partner/v1/auth-token",
        json={
            "client_id": SYNCPAY_CLIENT_ID,
            "client_secret": SYNCPAY_CLIENT_SECRET,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()

    _token_cache["token"] = data["access_token"]
    # expires_at vem como string ISO — parseia direto
    _token_cache["expires_at"] = datetime.fromisoformat(
        data["expires_at"].replace("Z", "+00:00")
    ).replace(tzinfo=None)

    print(f"✅ Token gerado, expira em: {_token_cache['expires_at']}")
    return _token_cache["token"]


# ============================================================
# GERAR PIX DE PAGAMENTO
# ============================================================

def gerar_pix(amount: float, chat_id: int, nome_cliente: str = "Cliente") -> dict:
    """
    Cria uma cobrança PIX na SyncPay.
    Retorna: { pix_code, identifier }
    """
    token = get_syncpay_token()

    # URL que a SyncPay vai chamar quando o pagamento for confirmado
    webhook_url = f"{WEBHOOK_BASE_URL}/webhook/syncpay"

    payload = {
        "amount": amount,
        "description": f"Pedido Bot Telegram - chat {chat_id}",
        "webhook_url": webhook_url,
        "client": {
            "name": nome_cliente,
            "cpf": "00000000000",        # ideal: coletar CPF do usuário
            "email": "cliente@bot.com",  # ideal: coletar e-mail do usuário
            "phone": "11999999999",
        },
    }

    resp = requests.post(
        f"{SYNCPAY_BASE_URL}/api/partner/v1/cash-in",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()  # { message, pix_code, identifier }


# ============================================================
# CONSULTAR STATUS DA TRANSAÇÃO (polling alternativo ao webhook)
# ============================================================

def consultar_status(identifier: str) -> str:
    """Consulta o status de uma transação pelo identifier."""
    token = get_syncpay_token()
    resp = requests.get(
        f"{SYNCPAY_BASE_URL}/api/partner/v1/transactions/{identifier}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("status", "unknown")


# ============================================================
# COMANDOS DO BOT TELEGRAM
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Olá! Use /pagar <valor> para gerar um PIX.\n"
        "Exemplo: /pagar 29.90"
    )


async def pagar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Valida o argumento de valor
    if not context.args:
        await update.message.reply_text("❌ Use: /pagar <valor>\nEx: /pagar 29.90")
        return

    try:
        valor = float(context.args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Ex: /pagar 29.90")
        return

    if valor <= 0:
        await update.message.reply_text("❌ O valor precisa ser maior que zero.")
        return

    await update.message.reply_text("⏳ Gerando PIX, aguarde...")

    try:
        resultado = gerar_pix(
            amount=valor,
            chat_id=chat_id,
            nome_cliente=update.effective_user.full_name or "Cliente",
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erro ao gerar PIX: {e}")
        return

    pix_code   = resultado["pix_code"]
    identifier = resultado["identifier"]

    # Guarda o pedido pendente para reconhecer quando o webhook chegar
    pedidos_pendentes[identifier] = {
        "chat_id": chat_id,
        "amount": valor,
        "created_at": datetime.utcnow(),
    }

    await update.message.reply_text(
        f"✅ PIX gerado! Valor: R$ {valor:.2f}\n\n"
        f"📋 *Copia e cola o código abaixo:*\n\n"
        f"`{pix_code}`\n\n"
        f"⏰ Válido por 30 minutos. Após pagar, você receberá confirmação aqui!",
        parse_mode="Markdown",
    )


# ============================================================
# SERVIDOR FLASK — recebe webhooks da SyncPay
# ============================================================

flask_app = Flask(__name__)
bot_instance: Bot | None = None  # preenchido na inicialização


@flask_app.route("/webhook/syncpay", methods=["POST"])
def webhook_syncpay():
    """
    SyncPay chama esta rota quando o status da transação muda.
    Quando status == 'completed', liberamos o acesso no bot.
    """
    data = request.get_json(silent=True) or {}
    transacao = data.get("data", {})

    identifier = transacao.get("id")
    status     = transacao.get("status")
    amount     = transacao.get("amount")

    print(f"📥 Webhook recebido | id={identifier} | status={status} | valor={amount}")

    if status == "completed" and identifier in pedidos_pendentes:
        pedido  = pedidos_pendentes.pop(identifier)
        chat_id = pedido["chat_id"]

        # Notifica o usuário no Telegram em thread separada
        threading.Thread(
            target=notificar_pagamento_confirmado,
            args=(chat_id, amount),
            daemon=True,
        ).start()

    # SyncPay exige resposta em até 5 segundos
    return jsonify({}), 200


def notificar_pagamento_confirmado(chat_id: int, amount: float):
    """Envia mensagem de confirmação ao usuário no Telegram."""
    if bot_instance is None:
        return
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            bot_instance.send_message(
                chat_id=chat_id,
                text=(
                    f"✅ *Pagamento confirmado!*\n"
                    f"💰 Valor recebido: R$ {float(amount):.2f}\n\n"
                    f"🎉 Obrigado! Seu acesso foi liberado."
                ),
                parse_mode="Markdown",
            )
        )
        loop.close()
    except Exception as e:
        print(f"Erro ao notificar chat {chat_id}: {e}")


# ============================================================
# INICIALIZAÇÃO
# ============================================================

def rodar_flask():
    """Roda o Flask em thread separada."""
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


def main():
    global bot_instance

    # Inicia o servidor webhook em background
    t = threading.Thread(target=rodar_flask, daemon=True)
    t.start()
    print("🌐 Servidor Flask rodando na porta 5000")

    # Inicia o bot Telegram
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    bot_instance = app.bot

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pagar", pagar))

    print("🤖 Bot Telegram iniciado!")
    app.run_polling()


if __name__ == "__main__":
    main()
