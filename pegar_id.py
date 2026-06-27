import logging
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Configuração básica para veres erros, se existirem
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

async def receber_foto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # O Telegram envia sempre a mesma foto em vários tamanhos (miniaturas).
    # O tamanho original/maior é sempre o último da lista [-1].
    file_id = update.message.photo[-1].file_id
    
    # Imprime no terminal/console
    print("\n" + "="*50)
    print("📸 NOVO FILE ID RECEBIDO:")
    print(file_id)
    print("="*50 + "\n")
    
    # O bot também te responde no próprio Telegram para ser mais fácil copiar
    await update.message.reply_text(
        f"Aqui está o `file_id` da tua fotografia:\n\n`{file_id}`\n\nPodes copiar e colar diretamente no teu ficheiro JSON.",
        parse_mode='Markdown'
    )

def main():
    # ⚠️ SUBSTITUI AQUI PELO TOKEN DO TEU BOT
    TOKEN = "8528168785:AAFfgtaB0vEagd1cdfZ3hWDyL9PKFZrmRjk" 
    
    application = Application.builder().token(TOKEN).build()
    
    # Adiciona a regra: Se receber uma FOTO, executa a função receber_foto
    application.add_handler(MessageHandler(filters.PHOTO, receber_foto))
    
    print("🤖 Bot auxiliar iniciado! Vai ao Telegram e envia-lhe uma fotografia (como imagem normal, não como documento).")
    application.run_polling()

if __name__ == '__main__':
    main()
