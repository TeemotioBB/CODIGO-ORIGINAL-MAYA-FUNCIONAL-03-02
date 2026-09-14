# Typing humano de 7 segundos

Implementado em 14/09/2026.

## O que mudou

- Toda mensagem automática de **texto** enviada ao lead pelo fluxo principal passa por `send_typing_message(...)`.
- O Telegram exibe **"Digitando..." por 7 segundos** antes do envio.
- A ação de typing é renovada a cada ~4 segundos para não sumir antes de completar o tempo.
- A primeira mensagem enviada após `/start` também respeita os 7 segundos.
- Follow-ups, hard wall, recuperação, remarketing, avisos de limite e textos do fluxo comercial também usam o mesmo comportamento.
- Mensagens transacionais do SyncPay (gerando PIX, PIX, erro e confirmação de pagamento) também usam 7 segundos.
- Textos dos follow-ups não foram alterados.

## Configuração

O padrão é 7 segundos. Opcionalmente, no Railway:

`TYPING_DELAY_SECONDS=7`

Se a variável não existir, o sistema usa 7 automaticamente.

## Exceções intencionais

- Comandos administrativos e mensagens manuais do painel não recebem atraso automático.
- Broadcast em massa não recebe 7 segundos por destinatário, para não transformar um envio para 100 pessoas em mais de 11 minutos de espera sequencial.
- Uploads de foto/vídeo continuam usando as ações próprias do Telegram (`UPLOAD_PHOTO` / `UPLOAD_VIDEO`).
