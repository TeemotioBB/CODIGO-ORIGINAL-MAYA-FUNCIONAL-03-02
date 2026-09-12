# Sophia/Maya v8.5 — Funil literal, confiança e contexto real do PIX

Este pacote foi gerado a partir do backup de 12/09/2026. O objetivo foi corrigir a leitura artificial do funil e separar curiosidade de intenção comercial real, sem desmontar as integrações já existentes.

## 1. Painel: cada etapa agora é literal

O painel não completa mais etapas anteriores só porque o usuário chegou numa etapa posterior. `first_message` depende de `first_message_seen`; `saw_teaser` depende do teaser realmente enviado; clique VIP depende do clique; PIX depende de PIX realmente criado/pendente/pago; compra depende de pagamento confirmado.

Os índices do painel receberam novas versões de bootstrap para reconstruir os agregados sem reutilizar a lógica antiga. Também foi incluído filtro por atribuição, com foco em `ads_meta_landing`, `telegram_direct` ou todos.

## 2. PIX agora guarda o contexto que o originou

Os botões usam callbacks como `pagar_vip|teaser`, `pagar_vip|followup`, `pagar_vip|limit`, `pagar_vip|objection`, `pagar_vip|resend`, `pagar_vip|pix_recovery` e `pagar_vip|remarketing`.

O primeiro e o último contexto ficam registrados em `sp:pix_origin:<uid>`. O painel mostra a tabela **PIX por contexto real**, incluindo PIX criados, qualificados e pagos por origem.

## 3. Meta CAPI: PIX criado não significa automaticamente InitiateCheckout

O sistema continua publicando internamente `payment_created`, mas o evento só vira `InitiateCheckout` na Meta quando existe contexto comercial qualificado. Hoje são considerados fortes: `teaser`, `direct_intent`, `followup`, `objection` e `resend`, desde que exista ao menos uma primeira mensagem real ou teaser real.

PIX de `limit`, `remarketing`, `pix_recovery` ou origem desconhecida continuam registrados no sistema, mas não ensinam a Meta como se fossem checkouts fortes. `Purchase` continua sendo enviado normalmente quando o webhook confirma pagamento.

## 4. Usuário silencioso não recebe cobrança de venda como primeiro follow-up

Foi criado um fluxo separado de recuperação silenciosa. Quem deu `/start` e ainda não mandou nenhuma mensagem recebe tentativas de retomar a conversa **sem botão de PIX**. Ao responder, a recuperação silenciosa é cancelada.

Há também uma proteção de migração: caso uma sequência comercial antiga tenha ficado ativa para alguém que nunca respondeu, o scheduler cancela a sequência comercial e move esse lead para a recuperação silenciosa.

## 5. Hard Wall entende objeções comerciais

Depois do pitch, o bot diferencia tentativa de obter conteúdo gratuito de perguntas legítimas como confiança, funcionamento, entrega, pagamento, preço e pedido de prévia.

Quando existe uma prévia real configurada e ainda não enviada, ela pode ser usada como prova. Caso contrário, o bot responde a objeção sem fingir que uma mídia inexistente será entregue. O Hard Wall continua bloqueando gratificação gratuita fora das regras comerciais.

## 6. Proteção contra promessa de mídia inexistente

O prompt das IAs e uma segunda camada de código impedem promessas como “vou gravar agora”, “vou mandar agora”, câmera/vídeo ao vivo ou material personalizado quando o sistema não consegue cumprir literalmente aquilo naquele momento.

Quando uma resposta gerada contém esse tipo de promessa, ela é substituída por uma oferta honesta de prévia já disponível, quando houver.

## 7. Webhook SyncPay mais robusto

O parser aceita o formato atual com transação no corpo raiz e também envelopes legados em `data`/`transaction`. Status `completed` é tratado como pago; `paid_out` foi mantido por compatibilidade com a integração anterior.

O processamento ganhou idempotência por identificador de transação (`sp:processed_tx:<identifier>`), evitando liberação/processamento duplicado em retries simultâneos. O mapeamento `identifier -> uid` e o snapshot de customer foram ampliados para 7 dias para reduzir falhas em confirmações atrasadas.

Pagamento confirmado não inventa `clicked_vip`, `saw_teaser` ou `first_message` no painel.

## 8. O que não foi alterado automaticamente

A experiência que o banco exibe ao colar o PIX (nome do beneficiário, instituição e apresentação final) depende da conta SyncPay/banco e precisa ser verificada externamente após deploy. A pré-qualificação do **criativo Meta Ads** também é externa ao ZIP do bot; o código agora fornece dados melhores para medir esse teste.

## 9. Validação incluída

Execute `python VALIDAR_V8_5.py`. O teste não acessa rede e valida sintaxe/AST, JSON, parser dos formatos de webhook, regras de qualificação do checkout, wiring crítico e ausência da inferência antiga no registrador do funil.
