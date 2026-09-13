#!/usr/bin/env python3
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parent
LANDING = ROOT.parent / 'VIP_Access_Portal_TRACKING_CORRIGIDO' / 'src' / 'routes' / 'index.tsx'


def check_python():
    for p in ROOT.glob('*.py'):
        ast.parse(p.read_text(encoding='utf-8'), filename=str(p))


def check_main_tracking():
    s = (ROOT / 'sophia_bot_v7.2_clean.py').read_text(encoding='utf-8')
    assert '@app.route("/tracking/telegram/go", methods=["GET"])' in s
    assert 'def _create_meta_tracking_token(payload):' in s
    assert '_schedule_tracking_geo_enrichment(start_token, client_ip)' in s
    assert 'pipe.watch(key)' in s
    assert 'linked_uid' in s
    assert 'r.delete(key)  # token de uso único' not in s
    assert 'redirect(target, code=302)' in s


def check_syncpay_transaction_snapshot():
    s = (ROOT / 'syncpay_integration.py').read_text(encoding='utf-8')
    assert 'sp:customer_tx:' in s
    assert 'sp:tx:' in s
    assert '_salvar_customer(uid, query.from_user, pix_data["identifier"])' in s
    assert '_recuperar_customer(uid, identifier)' in s
    assert 'current_pix.get("identifier") == identifier' in s


def check_capi_config():
    s = (ROOT / 'meta_capi.py').read_text(encoding='utf-8')
    assert 'os.getenv("META_PIXEL_ID", "").strip()' in s
    assert '988265177099445' not in s


def check_landing():
    if not LANDING.exists():
        raise AssertionError(f'Landing não encontrada: {LANDING}')
    s = LANDING.read_text(encoding='utf-8')
    assert 'tracking/telegram/go' in s
    assert 'waitForFbp' not in s
    assert 'sendTrackingToBackend' not in s
    assert 'https://t.me/MayaIAbot' not in s
    assert 'event.currentTarget.href = buildTrackingRedirectHref();' in s
    assert 'preventDefault' not in s


def main():
    checks = [
        ('Sintaxe Python', check_python),
        ('Tracking click-through', check_main_tracking),
        ('Snapshot por transação', check_syncpay_transaction_snapshot),
        ('Pixel ID sem fallback antigo', check_capi_config),
        ('Landing sem race de 5s', check_landing),
    ]
    for name, fn in checks:
        fn()
        print(f'[OK] {name}')
    print('\nVALIDAÇÃO V8.6 TRACKING: PASSOU')

if __name__ == '__main__':
    main()
