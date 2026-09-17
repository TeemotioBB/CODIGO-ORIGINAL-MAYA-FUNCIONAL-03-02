# Fluxo novo para reduzir Starts mudos

## O que mudou

- `/start` responde em ~1,5 s por padrão, sem alterar o typing de 7 s das demais mensagens.
- A primeira mensagem virou uma microdecisão com dois botões:
  - `👀 VER PRÉVIA`
  - `🔒 VER ACESSO VIP`
- O vídeo de boas-vindas não é mais enviado automaticamente no `/start`.
- `VER PRÉVIA` entrega a prévia real imediatamente; depois, o pitch existente continua.
- `VER ACESSO VIP` registra intenção VIP, mostra o preço e exibe `GERAR PIX`; a cobrança só é criada no clique de gerar PIX.
- Clique em qualquer botão cancela o Silent Recovery e conta como primeira interação no funil.
- O Silent Recovery de 10/45 min repete os botões em vez de exigir texto livre.
- Eventos adicionados: `start_choice_menu_shown`, `start_click_preview`, `start_click_vip`, além de `vip_intent_direct_intent` no acesso VIP.

## Preservado

Redis, SyncPay, CAPI, Purchase/InitiateCheckout, Promise Guard, hard wall, follow-ups, foto personalizada, painel e regras de prévia única permanecem no fluxo existente.
