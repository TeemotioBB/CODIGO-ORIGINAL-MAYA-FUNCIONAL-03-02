# Integração da foto personalizada

Este projeto chama o serviço **Gerador-Placa-com-Nome-IA** via HTTP.

## Variáveis no Railway do bot

```env
PERSONALIZED_PHOTO_API_URL=https://SEU-GERADOR.up.railway.app
PERSONALIZED_PHOTO_API_KEY=
PERSONALIZED_PHOTO_TIMEOUT_SECONDS=20
PERSONALIZED_PHOTO_SENT_TTL_DAYS=365
```

Se o gerador tiver `API_KEY` configurada, coloque exatamente o mesmo valor em `PERSONALIZED_PHOTO_API_KEY` no bot.

## Quando a foto é enviada

A foto é usada uma única vez por lead:

1. imediatamente quando ele apresenta objeção de preço ou hesitação (`vou pensar`, `mais tarde`, `agora não` etc.);
2. se ele não disser nada, no primeiro follow-up pré-PIX, aos 10 minutos;
3. se já gerou PIX e ainda não recebeu a personalizada, como fallback aos 30 minutos pós-PIX.

Ela **não** é usada em objeção de confiança como prova de identidade/tempo real.

## Redis

Chaves criadas:

```text
personalized_photo:sent:<uid>
personalized_photo:trigger:<uid>
```

Para repetir um teste com o mesmo Telegram ID, apague essas duas chaves.
