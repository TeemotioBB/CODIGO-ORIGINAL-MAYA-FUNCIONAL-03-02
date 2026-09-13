# Logs limpos no Railway

Esta versão reduz o ruído do Railway sem esconder falhas importantes.

## O que deixa de poluir o INFO

Por padrão, `httpx`, `httpcore`, `werkzeug`, `urllib3`, `asyncio` e `apscheduler` ficam em `WARNING`.
Isso remove a maior parte de:

- `HTTP Request ... 200 OK`
- `GET /admin/summary 200`
- `GET /admin/leads 200`
- `GET /admin/charts 200`

## Prefixos úteis para pesquisar no Railway

- `🚨 [VIDEO][ERROR]` — falha de vídeo
- `🚨 [PHOTO][ERROR]` — falha de foto
- `🚨 [AUDIO][ERROR]` — falha de áudio
- `✅ [VIDEO][OK]` — vídeo enviado
- `✅ [PHOTO][OK]` — foto enviada
- `✅ [AUDIO][OK]` — áudio enviado
- `🚫 [BLOCKED]` — usuário bloqueou o bot; só aparece na primeira detecção
- `[PIX DESIRE]` — follow-up pós-PIX
- `[FOLLOWUP5]` — follow-up pré-PIX

## Usuário que bloqueou o bot

Ao detectar `bot was blocked by the user`, o UID é colocado na blacklist. O Silent Recovery também usa essa regra agora. Isso evita tentar enviar novamente a cada ciclo e evita dezenas de linhas 403 repetidas.

## Voltar temporariamente aos logs HTTP detalhados

No Railway, crie a variável:

`LOG_VERBOSE_HTTP=1`

Depois reinicie/deploy. Para voltar ao modo limpo, remova a variável ou defina `LOG_VERBOSE_HTTP=0`.

## Segurança

Existe um filtro que mascara tokens do Telegram em linhas de log que por acaso cheguem ao logger. Mesmo assim, se um token real já apareceu em logs compartilhados, gere outro token no BotFather e atualize a variável correspondente no Railway.
