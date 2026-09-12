#!/usr/bin/env python3
"""Validações locais sem rede para as mudanças críticas da v8.5."""
from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def extract_syncpay_helpers():
    path = ROOT / "syncpay_integration.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    wanted_funcs = {
        "_normalize_pix_origin",
        "_is_checkout_qualified",
        "_parse_syncpay_webhook",
    }
    wanted_assigns = {"PIX_ALLOWED_ORIGINS", "PIX_QUALIFIED_ORIGINS"}
    nodes = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node.target, ast.Name):
                targets = [node.target.id]
            if any(t in wanted_assigns for t in targets):
                nodes.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted_funcs:
            nodes.append(node)
    ns = {}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    return ns


def check_python_syntax():
    for path in ROOT.glob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def check_json():
    json.loads((ROOT / "ias_config.json").read_text(encoding="utf-8"))


def check_syncpay_payloads_and_qualification():
    ns = extract_syncpay_helpers()
    parse = ns["_parse_syncpay_webhook"]
    qualify = ns["_is_checkout_qualified"]
    normalize = ns["_normalize_pix_origin"]

    assert parse({"id": "tx-root", "status": "completed", "amount": 9}) == (
        "tx-root", "completed", 9
    )
    assert parse({"data": {"identifier": "tx-data", "status": "COMPLETED", "final_amount": 9.0}}) == (
        "tx-data", "completed", 9.0
    )
    assert parse({"data": {"transaction": {"id": "tx-nested", "status": "pending", "amount": 9}}}) == (
        "tx-nested", "pending", 9
    )
    assert parse(None) == (None, "", None)

    assert normalize("pagar_vip|teaser") == "teaser"
    assert normalize("pagar_vip|LIMIT") == "limit"
    assert normalize("pagar_vip|nao_existe") == "unknown"
    assert normalize("pagar_vip") == "unknown"

    # Deve sinalizar checkout forte somente com contexto comercial + interação/pitch real.
    assert qualify("teaser", True, False) is True
    assert qualify("followup", False, True) is True
    assert qualify("direct_intent", True, False) is True
    assert qualify("objection", True, False) is True
    assert qualify("limit", True, True) is False
    assert qualify("remarketing", True, True) is False
    assert qualify("pix_recovery", True, True) is False
    assert qualify("teaser", False, False) is False


def check_critical_wiring():
    main = (ROOT / "sophia_bot_v7.2_clean.py").read_text(encoding="utf-8")
    sync = (ROOT / "syncpay_integration.py").read_text(encoding="utf-8")
    capi = (ROOT / "meta_capi.py").read_text(encoding="utf-8")
    html = (ROOT / "admin_panel.html").read_text(encoding="utf-8")

    required_main = [
        "def activate_silent_recovery",
        "def silent_recovery_scheduler",
        "def detect_sales_objection",
        "def send_sales_objection_response",
        "def enforce_deliverable_promises",
        "payment_callback_data(\"teaser\")",
        "payment_callback_data(\"followup\")",
        "payment_callback_data(\"limit\")",
        "payment_callback_data(\"objection\")",
        "loop.create_task(silent_recovery_scheduler(application.bot))",
        '"first_message": bool(x.get("first_message"))',
    ]
    for needle in required_main:
        assert needle in main, f"Ausente no bot principal: {needle}"

    assert 'callback_data="pagar_vip"' not in main
    assert 'callback_data="pagar_vip"' not in sync
    assert "checkout_qualified" in sync
    assert "_parse_syncpay_webhook(payload)" in sync
    assert 'status in {"completed", "paid_out"}' in sync
    assert "sp:processed_tx:" in sync

    assert 'tracking.get("checkout_qualified", True)' in capi
    assert 'send_to_meta("InitiateCheckout", apex_event)' in capi
    assert 'send_to_meta("Purchase", apex_event)' in capi

    assert 'id="funnelSourceFilter"' in html
    assert "pixOrigins" in html
    assert "PIX por contexto real" in html


def check_literal_funnel_function():
    path = ROOT / "sophia_bot_v7.2_clean.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    fn = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "_admin_record_funnel"
    )
    src = ast.get_source_segment(path.read_text(encoding="utf-8"), fn) or ""
    # A função não pode iterar por etapas anteriores nem usar range para completar o funil.
    assert "range(" not in src
    assert "stage_number" in src


def main():
    checks = [
        ("Sintaxe Python", check_python_syntax),
        ("JSON ias_config", check_json),
        ("Parser SyncPay + qualificação CAPI", check_syncpay_payloads_and_qualification),
        ("Wiring crítico", check_critical_wiring),
        ("Funil literal", check_literal_funnel_function),
    ]
    for label, fn in checks:
        fn()
        print(f"[OK] {label}")
    print("\nVALIDAÇÃO V8.5: PASSOU")


if __name__ == "__main__":
    main()
