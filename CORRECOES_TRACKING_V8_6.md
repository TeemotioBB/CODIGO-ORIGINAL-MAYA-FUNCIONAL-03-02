# v8.6 — Tracking/atribuição corrigidos

## Problema corrigido
A landing anterior deixava o CTA apontando diretamente para `t.me/MayaIAbot` enquanto aguardava `_fbp` por até 5 segundos e depois ainda esperava o POST/GeoIP. Em celular, o usuário podia tocar antes de o `trk_` existir. O Telegram abria sem `?start=trk_...`, e no PIX o snapshot ficava sem `fbc`, `fbp`, IP e User-Agent.

## Fluxo novo
1. O CTA nunca aponta diretamente ao Telegram. Ele aponta para `/tracking/telegram/go` no Railway.
2. No toque, a landing lê imediatamente `fbclid`, `_fbc` e `_fbp` disponíveis, sem `await`, sem timeout e sem bloquear o clique.
3. O Railway cria o `trk_` no próprio request do clique, capturando IP e User-Agent no servidor.
4. O Railway responde 302 para `https://t.me/MayaIAbot?start=trk_...`.
5. `/start` vincula o token ao Telegram UID de forma concorrente-segura.
6. GeoIP roda em background e atualiza o UID quando terminar; não atrasa o redirecionamento.
7. No PIX, o SyncPay grava um snapshot por `identifier`, não apenas por UID.
8. No pagamento, o Purchase usa o snapshot da transação efetivamente paga.

## Variáveis
Obrigatórias já usadas:
- `META_PIXEL_ID`
- `META_ACCESS_TOKEN`
- `REDIS_URL`
- `TELEGRAM_TOKEN`
- `GROK_API_KEY`
- `SYNCPAY_CLIENT_ID`
- `SYNCPAY_CLIENT_SECRET`

Opcional nova:
- `TELEGRAM_BOT_USERNAME=MayaIAbot`
- `TRACKING_LINKED_TOKEN_TTL_SECONDS=600`

`META_PIXEL_ID` não possui mais fallback para Pixel antigo: se a variável faltar, o CAPI falha explicitamente em vez de enviar silenciosamente ao dataset errado.

## Logs esperados para lead de anúncio
Ao tocar na landing:
```
[META TRACKING] token criado IMEDIATO | fbc=True fbp=<True/False> ip=True ua=True
[META TRACKING] redirect Telegram criado token=...
```
No `/start`:
```
[META TRACKING] token vinculado uid=... | fbc=True fbp=<True/False> ip=True ua=True | ...
```
No PIX:
```
[Meta Tracking] snapshot PIX uid=... tx=... | fbc=True fbp=<True/False> ip=True ua=True | ...
```
No CAPI:
```
Campos: [..., 'fbc', 'client_ip_address', 'client_user_agent', ...]
```

`fbp=False` isoladamente pode ser normal. Para um lead que realmente entrou pela landing corrigida, o sinal importante é que `ip=True` e `ua=True` devem estar presentes, e `fbc=True` deve aparecer quando existe `fbclid`/clique Meta.

## Validação local realizada
- `python -m py_compile *.py`: OK
- `python VALIDAR_V8_5.py`: todas as validações passaram
- TypeScript de `src/routes/index.tsx`: parse sem erros sintáticos; no ambiente de auditoria não havia `node_modules`, portanto o build Vite completo não pôde ser executado ali.
