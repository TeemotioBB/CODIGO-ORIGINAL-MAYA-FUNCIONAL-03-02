"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    📢 COMANDOS ADMIN - SOPHIA BOT v8.3                       ║
║                                                                              ║
║  Comandos disponíveis:                                                      ║
║  /stats - Estatísticas gerais                                               ║
║  /funnel - Funil de conversão                                               ║
║  /reset <uid> - Reseta limite diário                                        ║
║  /givebonus <uid> <qtd> - Dá mensagens bônus                                ║
║  /broadcast - Sistema de broadcast completo                                 ║
║  /help - Lista de comandos                                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Estado do broadcast (armazena dados temporários)
broadcast_state = {}

# ═══════════════════════════════════════════════════════════════════════════════
# 📊 COMANDOS DE ESTATÍSTICAS
# ═══════════════════════════════════════════════════════════════════════════════

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS, funcs):
    """Estatísticas gerais do bot"""
    if update.effective_user.id not in ADMIN_IDS:
        return

    users = funcs['get_all_active_users']()
    total = len(users)

    # Conta usuários por fase
    phase_counts = {i: 0 for i in range(6)}
    for uid in users:
        phase = funcs['get_current_phase'](uid)
        phase_counts[phase] += 1

    # Outras métricas
    saw_teaser_count = sum(1 for uid in users if funcs['saw_teaser'](uid))
    clicked_vip_count = sum(1 for uid in users if funcs['clicked_vip'](uid))
    in_cooldown_count = sum(1 for uid in users if funcs['is_in_rejection_cooldown'](uid))

    # Evita divisão por zero
    ctr = (clicked_vip_count / saw_teaser_count * 100) if saw_teaser_count > 0 else 0.0

    stats_text = f"""\
📊 **STATS v8.3**

👥 Total de usuários: {total}

📊 **Distribuição por Fases:**
- 0️⃣ Onboarding: {phase_counts[0]}
- 1️⃣ Engagement: {phase_counts[1]}
- 2️⃣ Provocation: {phase_counts[2]}
- 3️⃣ VIP Pitch: {phase_counts[3]}
- 4️⃣ Post-Rejection: {phase_counts[4]}
- 5️⃣ Relationship: {phase_counts[5]}

📈 **Outras métricas:**
👀 Viram teaser: {saw_teaser_count}
💎 Clicaram no VIP: {clicked_vip_count}
🚫 Em cooldown: {in_cooldown_count}
📊 Taxa de conversão: {ctr:.1f}%"""

    await update.message.reply_text(stats_text, parse_mode="Markdown")


async def funnel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS, funcs):
    """Funil de conversão"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    stages = funcs['get_funnel_stats']()
    names = {
        0: "❓ Desconhecido",
        1: "🚀 /start",
        2: "💬 Primeira msg",
        3: "👀 Viu teaser",
        4: "💎 Clicou VIP"
    }
    
    msg = "📊 **FUNIL v8.3**\n\n"
    for stage, count in sorted(stages.items()):
        msg += f"{names.get(stage, f'Stage {stage}')}: {count}\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS, funcs):
    """Reseta limite diário de um usuário"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /reset <user_id>")
        return
    
    try:
        uid = int(context.args[0])
        funcs['reset_daily_count'](uid)
        await update.message.reply_text(f"✅ Limite resetado para usuário {uid}")
    except ValueError:
        await update.message.reply_text("❌ ID inválido!")


async def resetall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS, funcs):
    """Reseta TUDO de um usuário — memória, fase, contadores, canal free, etc"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if not context.args:
        await update.message.reply_text("❌ Uso: /resetall <user_id>")
        return
    
    try:
        uid = int(context.args[0])
        r = funcs['get_redis']()
        
        # Busca todas as chaves do usuário
        keys = r.keys(f"*:{uid}") + r.keys(f"*:{uid}:*")
        
        deleted = 0
        for k in keys:
            r.delete(k)
            deleted += 1
        
        await update.message.reply_text(
            f"✅ Reset completo para {uid}\n"
            f"🗑️ {deleted} chaves deletadas\n\n"
            f"O usuário vai aparecer como novo lead no próximo /start"
        )
        
    except ValueError:
        await update.message.reply_text("❌ ID inválido!")

async def givebonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS, funcs):
    """Dá mensagens bônus para um usuário"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    if len(context.args) < 2:
        await update.message.reply_text("❌ Uso: /givebonus <user_id> <quantidade>")
        return
    
    try:
        uid = int(context.args[0])
        amount = int(context.args[1])
        funcs['add_bonus_msgs'](uid, amount)
        await update.message.reply_text(f"✅ +{amount} mensagens bônus para {uid}")
    except ValueError:
        await update.message.reply_text("❌ Valores inválidos!")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS):
    """Lista de comandos disponíveis"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    await update.message.reply_text(
        "🎮 **COMANDOS ADMIN v8.3**\n\n"
        "/stats - Estatísticas gerais\n"
        "/funnel - Funil de conversão\n"
        "/reset <id> - Reseta limite diário\n"
        "/givebonus <id> <qtd> - Dá bônus de mensagens\n"
        "/broadcast - Sistema de broadcast\n"
        "/help - Esta mensagem",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 📢 SISTEMA DE BROADCAST COMPLETO
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS):
    """Inicia o processo de broadcast"""
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    uid = update.effective_user.id
    
    # Reseta estado
    broadcast_state[uid] = {
        "step": "waiting_target",
        "target": None,
        "message": None,
        "media_type": None,
        "media_id": None,
        "add_button": False
    }
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Todos os usuários", callback_data="bc_target_all")],
        [InlineKeyboardButton("🔥 Ativos 24h", callback_data="bc_target_active")],
        [InlineKeyboardButton("👀 Viram teaser", callback_data="bc_target_teaser")],
        [InlineKeyboardButton("💔 Não convertidos", callback_data="bc_target_notconv")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="bc_cancel")]
    ])
    
    await update.message.reply_text(
        "📢 **SISTEMA DE BROADCAST**\n\n"
        "Passo 1/3: Para quem você quer enviar?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


async def broadcast_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS, funcs):
    """Handler para os botões do broadcast"""
    query = update.callback_query
    await query.answer()
    
    uid = query.from_user.id
    
    if uid not in ADMIN_IDS:
        return
    
    # Cancela broadcast
    if query.data == "bc_cancel":
        if uid in broadcast_state:
            del broadcast_state[uid]
        await query.edit_message_text("❌ Broadcast cancelado.")
        return
    
    # Seleciona target
    if query.data.startswith("bc_target_"):
        target_map = {
            "bc_target_all": "all",
            "bc_target_active": "active_24h",
            "bc_target_teaser": "saw_teaser",
            "bc_target_notconv": "not_converted"
        }
        
        target_name_map = {
            "all": "Todos os usuários",
            "active_24h": "Ativos nas últimas 24h",
            "saw_teaser": "Que viram teaser",
            "not_converted": "Que viram teaser mas não converteram"
        }
        
        target = target_map[query.data]
        broadcast_state[uid]["target"] = target
        broadcast_state[uid]["step"] = "waiting_button"
        
        # Conta usuários
        users = funcs['get_all_active_users']()
        if target == "active_24h":
            users = [u for u in users if funcs['get_hours_since_activity'](u) and funcs['get_hours_since_activity'](u) < 24]
        elif target == "saw_teaser":
            users = [u for u in users if funcs['saw_teaser'](u)]
        elif target == "not_converted":
            users = [u for u in users if funcs['saw_teaser'](u) and not funcs['clicked_vip'](u)]
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Sim, adicionar botão VIP", callback_data="bc_button_yes")],
            [InlineKeyboardButton("❌ Não, sem botão", callback_data="bc_button_no")],
            [InlineKeyboardButton("🔙 Cancelar", callback_data="bc_cancel")]
        ])
        
        await query.edit_message_text(
            f"📢 **BROADCAST**\n\n"
            f"✅ Target: {target_name_map[target]}\n"
            f"👥 Usuários: {len(users)}\n\n"
            f"Passo 2/3: Adicionar botão 'QUERO VIP'?",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )
    
    # Seleciona se adiciona botão
    elif query.data.startswith("bc_button_"):
        add_button = query.data == "bc_button_yes"
        broadcast_state[uid]["add_button"] = add_button
        broadcast_state[uid]["step"] = "waiting_content"
        
        await query.edit_message_text(
            "📢 **BROADCAST**\n\n"
            "Passo 3/3: Agora me envie:\n\n"
            "📝 Texto simples\n"
            "📷 Foto (com legenda opcional)\n"
            "🎬 Vídeo (com legenda opcional)\n\n"
            "⚠️ Envie na próxima mensagem!"
        )


async def broadcast_content_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS, funcs):
    """Recebe o conteúdo do broadcast"""
    uid = update.effective_user.id
    
    if uid not in ADMIN_IDS:
        return
    
    if uid not in broadcast_state or broadcast_state[uid]["step"] != "waiting_content":
        return
    
    state = broadcast_state[uid]
    
    # Captura conteúdo
    has_photo = bool(update.message.photo)
    has_video = bool(update.message.video)
    text = update.message.text or update.message.caption or ""
    
    if not text and not has_photo and not has_video:
        await update.message.reply_text("❌ Você precisa enviar texto, foto ou vídeo!")
        return
    
    state["message"] = text
    
    if has_photo:
        state["media_type"] = "photo"
        state["media_id"] = update.message.photo[-1].file_id
    elif has_video:
        state["media_type"] = "video"
        state["media_id"] = update.message.video.file_id
    
    # Conta usuários
    users = funcs['get_all_active_users']()
    target = state["target"]
    if target == "active_24h":
        users = [u for u in users if funcs['get_hours_since_activity'](u) and funcs['get_hours_since_activity'](u) < 24]
    elif target == "saw_teaser":
        users = [u for u in users if funcs['saw_teaser'](u)]
    elif target == "not_converted":
        users = [u for u in users if funcs['saw_teaser'](u) and not funcs['clicked_vip'](u)]
    
    target_name_map = {
        "all": "Todos",
        "active_24h": "Ativos 24h",
        "saw_teaser": "Viram teaser",
        "not_converted": "Não convertidos"
    }
    
    media_info = f"📎 Mídia: {state['media_type'].upper()}\n" if state["media_type"] else ""
    button_info = "🔘 Com botão VIP" if state["add_button"] else "⚪ Sem botão"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ CONFIRMAR E ENVIAR", callback_data="bc_confirm")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="bc_cancel")]
    ])
    
    await update.message.reply_text(
        f"📢 **CONFIRMAR BROADCAST**\n\n"
        f"👥 Target: {target_name_map[target]}\n"
        f"📊 Usuários: {len(users)}\n"
        f"{media_info}"
        f"{button_info}\n\n"
        f"📝 Preview:\n{text[:100]}{'...' if len(text) > 100 else ''}\n\n"
        f"⚠️ Confirma envio?",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    state["step"] = "waiting_confirmation"


async def broadcast_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, ADMIN_IDS, funcs, CANAL_VIP_LINK):
    """Confirma e executa o broadcast"""
    query = update.callback_query
    await query.answer()
    
    uid = query.from_user.id
    
    if uid not in ADMIN_IDS or uid not in broadcast_state:
        return
    
    if query.data != "bc_confirm":
        return
    
    state = broadcast_state[uid]
    
    await query.edit_message_text("📤 Enviando broadcast... aguarde...")
    
    # Pega usuários
    users = funcs['get_all_active_users']()
    target = state["target"]
    if target == "active_24h":
        users = [u for u in users if funcs['get_hours_since_activity'](u) and funcs['get_hours_since_activity'](u) < 24]
    elif target == "saw_teaser":
        users = [u for u in users if funcs['saw_teaser'](u)]
    elif target == "not_converted":
        users = [u for u in users if funcs['saw_teaser'](u) and not funcs['clicked_vip'](u)]
    
    # Prepara botão
    keyboard = None
    if state["add_button"]:
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("CLICA AQUI: QUERO ACESSO VIP", url="https://t.me/Mayaoficial_bot")
        ]])
    
    # Envia
    sent = 0
    failed = 0
    blocked = 0
    
    for user_id in users:
        try:
            if state["media_type"] == "photo":
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=state["media_id"],
                    caption=state["message"] or None,
                    reply_markup=keyboard
                )
            elif state["media_type"] == "video":
                await context.bot.send_video(
                    chat_id=user_id,
                    video=state["media_id"],
                    caption=state["message"] or None,
                    reply_markup=keyboard
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=state["message"],
                    reply_markup=keyboard
                )
            
            sent += 1
            await asyncio.sleep(0.05)
            
        except Exception as e:
            if "blocked" in str(e).lower():
                blocked += 1
                funcs['add_to_blacklist'](user_id)
            else:
                failed += 1
            
            logger.error(f"Broadcast error {user_id}: {e}")
    
    await context.bot.send_message(
        chat_id=uid,
        text=(
            f"✅ **BROADCAST CONCLUÍDO**\n\n"
            f"📤 Enviados: {sent}\n"
            f"❌ Falharam: {failed}\n"
            f"🚫 Bloquearam: {blocked}\n"
            f"📊 Total: {len(users)}"
        ),
        parse_mode="Markdown"
    )
    
    del broadcast_state[uid]
    logger.info(f"📢 Broadcast: {sent}/{len(users)} enviados")
