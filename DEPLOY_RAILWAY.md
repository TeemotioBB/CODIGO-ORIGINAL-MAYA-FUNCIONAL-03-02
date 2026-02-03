# 🚀 GUIA DE DEPLOY NO RAILWAY - PASSO A PASSO

## 📦 ARQUIVOS NECESSÁRIOS NO GITHUB

Certifique-se que seu repositório tem TODOS esses arquivos:

```
seu-repositorio/
├── sophia_bot_v7.2_clean.py    ✅ Código principal
├── requirements.txt             ✅ Dependências Python
├── Procfile                     ✅ Comando de start
├── runtime.txt                  ✅ Versão do Python
├── railway.json                 ✅ Configuração Railway
├── .gitignore                   ✅ Arquivos ignorados
├── README_v7.2.md              ✅ Documentação
└── CHANGELOG_v7.2.md           ✅ Mudanças
```

---

## 🔧 PASSO 1: CONFIGURAR NO CÓDIGO

Abra `sophia_bot_v7.2_clean.py` e edite as linhas 40-60:

```python
# ❌ REMOVA estas linhas (se quiser usar variáveis de ambiente):
BOT_TOKEN = "COLE_SEU_TOKEN_BOT_AQUI"
GROK_KEY = "COLE_SUA_KEY_GROK_AQUI"

# ✅ OU mantenha mas coloque seus tokens reais:
BOT_TOKEN = "7123456789:AAH..."
GROK_KEY = "xai-abc123..."
LINK_CANAL_PREVIAS = "https://t.me/previasdamayaofc"
LINK_CANAL_VIP = "https://t.me/+SEU_LINK_VIP"
MEU_TELEGRAM_ID = "1293602874"
```

**⚠️ IMPORTANTE:** Se colocar tokens direto no código, **NÃO FAÇA COMMIT** em repo público!

---

## 🌐 PASSO 2: CRIAR PROJETO NO RAILWAY

### 2.1 - Acesse Railway
1. Acesse [railway.app](https://railway.app)
2. Faça login com GitHub
3. Clique em **"New Project"**

### 2.2 - Conectar GitHub
1. Selecione **"Deploy from GitHub repo"**
2. Escolha seu repositório
3. Selecione a branch (normalmente `main` ou `master`)

### 2.3 - Railway vai detectar automaticamente
✅ Python pelo `requirements.txt`  
✅ Start command pelo `Procfile`  
✅ Configurações pelo `railway.json`

---

## ⚙️ PASSO 3: CONFIGURAR VARIÁVEIS DE AMBIENTE

No dashboard do Railway, clique em **"Variables"** e adicione:

### Variáveis OBRIGATÓRIAS:

```bash
TELEGRAM_TOKEN=7123456789:AAH...
GROK_API_KEY=xai-abc123...
REDIS_URL=redis://default:senha@host:porta
PORT=8080
```

### Variáveis OPCIONAIS:

```bash
CANAL_PREVIAS_LINK=https://t.me/previasdamayaofc
CANAL_VIP_LINK=https://t.me/+SEU_LINK_VIP
ADMIN_IDS=1293602874
WEBHOOK_BASE_URL=https://seu-app.up.railway.app
```

**💡 DICA:** Railway gera automaticamente `PORT` e `RAILWAY_STATIC_URL`, não precisa adicionar manualmente.

---

## 📊 PASSO 4: CONFIGURAR REDIS

### Opção A: Redis do Railway (Recomendado)

1. No seu projeto Railway, clique **"+ New"**
2. Selecione **"Database" → "Add Redis"**
3. Railway vai criar e conectar automaticamente
4. A variável `REDIS_URL` será gerada automaticamente

### Opção B: Redis Externo (Upstash)

1. Acesse [upstash.com](https://upstash.com)
2. Crie conta e database
3. Copie a URL de conexão
4. Adicione como variável `REDIS_URL`

---

## 🚀 PASSO 5: FAZER O DEPLOY

### 5.1 - Commit no GitHub

```bash
git add .
git commit -m "Setup Railway deploy"
git push origin main
```

### 5.2 - Deploy Automático

Railway detecta o push e inicia deploy automaticamente!

Você verá:
```
📦 Building...
🔨 Installing dependencies...
✅ Build successful
🚀 Deploying...
✅ Deployment live
```

### 5.3 - Se Deploy NÃO Iniciar

Clique em **"Deploy"** → **"Redeploy"** manualmente

---

## 🔗 PASSO 6: CONFIGURAR WEBHOOK

### 6.1 - Pegar URL do Railway

No dashboard, você verá algo como:
```
https://sophia-bot-production.up.railway.app
```

### 6.2 - Configurar Webhook

**Opção A: Automático (Recomendado)**
```bash
# Acesse no navegador:
https://seu-app.up.railway.app/set-webhook
```

**Opção B: Manual via curl**
```bash
curl -X GET https://seu-app.up.railway.app/set-webhook
```

**Resposta esperada:**
```
Webhook configurado
```

---

## ✅ PASSO 7: TESTAR

### 7.1 - Health Check
```bash
curl https://seu-app.up.railway.app/
# Resposta: ok
```

### 7.2 - Testar Bot
1. Abra seu bot no Telegram
2. Envie `/start`
3. Bot deve responder

### 7.3 - Ver Logs
No Railway: **"Deployments"** → **"View Logs"**

Procure por:
```
✅ Redis conectado
✅ Webhook configurado: https://...
🌐 Servidor Flask rodando na porta 8080
🚀 Sophia Bot v7.2 CLEAN totalmente operacional!
```

---

## 🐛 TROUBLESHOOTING

### ❌ Problema: "Application failed to respond"

**Causa:** Bot não consegue se conectar ao Redis

**Solução:**
1. Verifique `REDIS_URL` nas variáveis
2. Teste conexão Redis:
```python
redis-cli -u $REDIS_URL ping
# Resposta: PONG
```

### ❌ Problema: "ModuleNotFoundError"

**Causa:** Dependência faltando no `requirements.txt`

**Solução:**
1. Verifique se `requirements.txt` existe
2. Commit e push novamente

### ❌ Problema: "Port already in use"

**Causa:** Variável PORT conflitando

**Solução:**
1. Remova variável `PORT` manual
2. Deixe Railway gerar automaticamente

### ❌ Problema: Deploy não inicia

**Causa:** Railway não detectou o projeto

**Solução:**
1. Verifique se `requirements.txt` existe no root
2. Clique em **"Settings"** → **"Build Command"**
3. Configure manualmente:
   - Build: `pip install -r requirements.txt`
   - Start: `python sophia_bot_v7.2_clean.py`

### ❌ Problema: "Webhook failed"

**Causa:** URL incorreta ou Telegram bloqueou

**Solução:**
1. Verifique URL no navegador
2. Reconfigure webhook:
```bash
https://seu-app.up.railway.app/set-webhook
```
3. Se persistir, delete webhook antigo:
```bash
curl https://api.telegram.org/bot<TOKEN>/deleteWebhook
```

---

## 📋 CHECKLIST FINAL

Antes de considerar deploy completo:

- [ ] Todos arquivos commitados no GitHub
- [ ] Railway conectado ao repositório
- [ ] Variáveis de ambiente configuradas
- [ ] Redis funcionando
- [ ] Deploy com sucesso (✅ verde)
- [ ] Webhook configurado (`/set-webhook`)
- [ ] Bot responde no Telegram (`/start`)
- [ ] Logs sem erros críticos
- [ ] `/stats` funciona (se admin)

---

## 🔄 REDEPLOY APÓS MUDANÇAS

Sempre que fizer mudanças no código:

```bash
git add .
git commit -m "Descrição da mudança"
git push origin main
```

Railway faz redeploy automático! 🎉

---

## 📞 PRECISA DE AJUDA?

**Logs com erro?** Copie e cole aqui  
**Deploy travado?** Mande print do Railway  
**Bot não responde?** Verifique webhook primeiro

---

**🔥 Boa sorte com o deploy!**
