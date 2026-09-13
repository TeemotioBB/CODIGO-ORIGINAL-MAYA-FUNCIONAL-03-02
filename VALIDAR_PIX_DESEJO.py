from pathlib import Path
import ast

bot = Path("sophia_bot_v7.2_clean.py").read_text(encoding="utf-8")
sp = Path("syncpay_integration.py").read_text(encoding="utf-8")
ast.parse(bot)
ast.parse(sp)

checks = {
    "cadencia 15m/30m/2h/4h/24h/48h": "PIX_DESIRE_DELAYS_MINUTES = {1: 15, 2: 30, 3: 120, 4: 240, 5: 1440, 6: 2880}" in bot,
    "audio pós-PIX aos 5m": "PIX_AUDIO_RECOVERY_DELAY_MINUTES = int(os.getenv(\"PIX_AUDIO_RECOVERY_DELAY_MINUTES\", \"5\"))" in bot,
    "audio não consome estágio": "pix_desire_audio_5m" in bot,
    "scheduler pos-PIX iniciado": "loop.create_task(pix_desire_followup_scheduler(application.bot))" in bot,
    "novo PIX ativa sequencia": 'activate_pix_desire(uid, created_at=pix_data.get("created_at"), reset_stage=True)' in sp,
    "PIX reutilizado preserva relogio": 'activate_pix_desire(uid, created_at=pix_pendente.get("created_at"), reset_stage=False)' in sp,
    "pagamento cancela sequencia": "cancel_pix_desire(uid, paid=True)" in sp,
    "prompt reconhece PIX_GERADO": "ESTADO: {pix_state} — PÓS-PIX" in bot,
    "CTA pos-PIX usa recuperacao": 'payment_callback_data("pix_recovery")' in bot,
}

for name, ok in checks.items():
    print(("[OK] " if ok else "[FAIL] ") + name)

if not all(checks.values()):
    raise SystemExit(1)

print("\nVALIDACAO POS-PIX: PASSOU")
