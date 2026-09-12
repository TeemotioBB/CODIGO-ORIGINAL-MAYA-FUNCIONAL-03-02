# Checklist pós-deploy v8.5

## Antes de trocar tráfego

1. Suba o pacote mantendo as mesmas variáveis de ambiente do projeto atual.
2. Confirme nos logs: `Sophia Bot v8.5`, `SyncPay` iniciado e `Meta CAPI Listener iniciado`.
3. Abra o painel e confirme o filtro **Origem / campanha** e a tabela **PIX por contexto real**.

## Teste A — usuário silencioso

1. Entre com um Telegram novo e dê `/start`.
2. Não responda.
3. Confirme que o primeiro follow-up tenta retomar a conversa e **não mostra botão de PIX**.
4. Responda depois e confirme que a recuperação silenciosa é cancelada.

## Teste B — funil literal

1. Com outro usuário, dê `/start` e não responda: deve contar Start, não 1ª mensagem.
2. Envie uma mensagem: só então deve contar 1ª mensagem.
3. Só conte Teaser depois que a prévia/pitch realmente for enviado.
4. Clique em pagamento e confira o contexto na tabela `PIX por contexto real`.

## Teste C — objeção

Depois do pitch, envie perguntas como “como funciona?”, “é real?” e “tem prévia?”. O bot deve responder à objeção/prova em vez de repetir cegamente a parede de venda. Pedido insistente por conteúdo gratuito continua sujeito ao Hard Wall.

## Teste D — SyncPay / comprador

1. Gere um PIX real de teste.
2. Cole o código no app do banco **antes de confirmar**.
3. Confira exatamente: valor esperado, beneficiário esperado, instituição esperada e validade do código.
4. No SyncPay, confirme que a transação aparece pendente antes do pagamento.
5. Ao realizar um pagamento de teste controlado, confirme que o status chega como concluído, o Telegram libera o VIP uma única vez e o painel marca Compra.
6. Reenvio do mesmo webhook não deve liberar/notificar novamente a mesma transação.

## Teste E — Meta CAPI

Use Eventos de Teste/diagnóstico da Meta se disponível no seu ambiente:

- PIX originado de `teaser`/`direct_intent`/`followup` com contexto real: deve poder enviar `InitiateCheckout`.
- PIX de `limit`, `remarketing` ou `pix_recovery`: fica salvo no seu sistema, mas não deve ser enviado como `InitiateCheckout` qualificado.
- Pagamento aprovado: deve enviar `Purchase` com o identificador da transação e o contexto `pix_origin`.

## Observação sobre dados antigos

A v8.5 reconstrói os índices do painel a partir dos marcadores literais disponíveis no Redis. Métricas novas passam a ser registradas de forma literal. Dados históricos que, em versões muito antigas, tenham sido gravados incorretamente no próprio marcador-fonte não podem ser distinguidos retroativamente sem um log externo; por isso valide as coortes novas após o deploy.
