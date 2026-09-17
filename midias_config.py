"""
CONFIGURAÇÃO CENTRAL DE MÍDIAS DO BOT
====================================

Edite SOMENTE este arquivo quando quiser trocar fotos, vídeos ou áudios.

COMO DESATIVAR UMA MÍDIA:
- Campo único (foto/vídeo/áudio): use ""
- Lista de mídias: use []

Também é seguro deixar "" dentro de uma lista: o bot filtra entradas vazias.
"""


def limpar_lista_midias(itens):
    """Remove valores vazios/duplicados sem alterar a ordem."""
    resultado = []
    for item in list(itens or []):
        valor = str(item or "").strip()
        if valor and valor not in resultado:
            resultado.append(valor)
    return resultado


# ========= /START =========
# Foto enviada depois da primeira mensagem do /start.
# Para NÃO enviar foto: FOTO_APOS_START = ""
FOTO_APOS_START = ""

# Vídeo opcional depois do /start.
# Para NÃO enviar vídeo: VIDEO_APOS_START = ""
# OBS.: o envio também depende de START_SEND_WELCOME_VIDEO=1 no Railway.
VIDEO_APOS_START = ""
# ========= PRÉVIA GRÁTIS 1X =========
# O lead recebe NO MÁXIMO UM desses vídeos durante toda a vida.
# Se houver vários IDs, o bot sorteia a ordem e envia somente UM.
# Para NÃO enviar prévia de vídeo: VIDEOS_PREVIA_UNICA = []
VIDEOS_PREVIA_UNICA = [
    "BAACAgEAAxkBAALgKGqpTM91rhoG4-PEbsNB6YDthc4YAAKKBwACNgVQRUc9wSuV5y7FPQQ",
]


# ========= OFERTA VIP =========
# Fotos usadas na apresentação/oferta do VIP.
# Para não enviar fotos no pitch: FOTOS_OFERTA_VIP = []
FOTOS_OFERTA_VIP = [
]

# Vídeos usados na apresentação/oferta do VIP.
# NÃO são usados como fallback da prévia grátis.
# Para não enviar vídeos no pitch: VIDEOS_OFERTA_VIP = []
VIDEOS_OFERTA_VIP = [
    "BAACAgEAAxkBAALgCGqpPZCC6VTPu5J1Joi-aOSi1jKzAAIXCAACNgVIRaljFNOd7K-PPQQ",
]

# Áudio de apresentação do VIP, antes do pitch.
# Para não enviar: AUDIO_APRESENTACAO_VIP = ""
# Cole aqui o file_id do Telegram.
AUDIO_APRESENTACAO_VIP = "AwACAgEAAxkBAALgEGqpPkW3anFEvm2hJkvkSm-zh9E1AAIaCAACNgVIRdo-F8gAATclPT0E"


# ========= PÓS PIX =========
# Áudio usado pelo fluxo de recuperação pós-PIX.
# Para não enviar: AUDIO_POS_PIX = ""
# Cole aqui o file_id do Telegram.
AUDIO_POS_PIX = "CQACAgEAAxkBAALgD2qpPkQcOqShlvgdkons9LbVJXa1AAIZCAACNgVIRUcjp2m9Si-hPQQ"


# ========= LIMITE =========
# Foto mostrada quando o usuário atinge o limite.
# Para não enviar foto: FOTO_LIMITE = ""
FOTO_LIMITE = "AgACAgEAAxkBAALgAmqpPAW94AxhlBWBK46phR8cVdstAAJ8DWsbNgVIRdW3Mzj71fzjAQADAgADeQADPQQ"
