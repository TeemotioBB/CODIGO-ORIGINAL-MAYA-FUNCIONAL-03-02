# Broadcast no painel

Foi adicionado um bloco **Broadcast · oferta com PIX** ao painel admin.

## O que ele faz

- Envia uma mensagem em massa pelo bot.
- Permite anexar **foto** ou **vídeo** opcional.
- Permite escolher o público:
  - viu teaser e ainda não pagou;
  - todos que viram teaser;
  - ativos nas últimas 24h;
  - todos os usuários.
- Permite definir um **valor de PIX exclusivo para aquele broadcast**.
- O usuário recebe um botão `💳 GERAR PIX — R$ X,XX`.
- O PIX só é criado quando o usuário clicar no botão.
- O valor especial não altera `PRECO_VIP` nem o preço dos fluxos normais.
- O painel mostra progresso de enviados/falhas enquanto o broadcast roda.

## Tracking / SyncPay

Cada campanha recebe um ID curto e o callback fica no formato:

`pagar_vip|broadcast_<campaign_id>`

Ao clicar, o SyncPay busca o valor gravado para a campanha e gera a cobrança com esse preço.
O `InitiateCheckout` usa o valor da campanha.

Se o usuário já tiver um PIX normal pendente com outro valor, ele **não é reutilizado** para a oferta do broadcast.

## Follow-ups

As mensagens existentes de follow-up não foram reescritas.
Para evitar conflito de preço, ao clicar em um PIX promocional de broadcast os agendamentos comerciais antigos daquele usuário são cancelados, e o broadcast não inicia os follow-ups padrão de PIX.

## Limites de mídia

- Foto: até 10 MB.
- Vídeo: até 49 MB.
- Texto: até 4096 caracteres.
- Com mídia e texto até 1024 caracteres, o texto vira legenda. Acima disso, a mídia é enviada primeiro e a mensagem com o botão vai logo depois.
