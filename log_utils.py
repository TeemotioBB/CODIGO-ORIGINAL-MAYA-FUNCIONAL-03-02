import logging
import os
import re

# Redige tokens do Telegram caso algum logger/exception tente imprimir a URL completa.
_TELEGRAM_BOT_TOKEN_RE = re.compile(r"bot\d+:[A-Za-z0-9_-]+")


class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        try:
            message = record.getMessage()
            redacted = _TELEGRAM_BOT_TOKEN_RE.sub("bot<REDACTED>", message)
            if redacted != message:
                record.msg = redacted
                record.args = ()
        except Exception:
            pass
        return True


def configure_clean_logging():
    """Configura uma saída curta e reduz o ruído das bibliotecas no Railway."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        force=True,
    )

    # Bibliotecas que geravam a maior parte da poluição visual.
    # Para depuração temporária no Railway, defina LOG_VERBOSE_HTTP=1.
    noisy_level = logging.INFO if os.getenv("LOG_VERBOSE_HTTP", "0").strip().lower() in {"1", "true", "yes", "on"} else logging.WARNING
    for name in (
        "httpx",
        "httpcore",
        "werkzeug",
        "urllib3",
        "asyncio",
        "apscheduler",
    ):
        logging.getLogger(name).setLevel(noisy_level)

    redactor = SensitiveDataFilter()
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(redactor)


def log_media_ok(logger, media_type, uid, source="-", detail=None):
    suffix = f" detalhe={detail}" if detail else ""
    logger.info(
        "✅ [%s][OK] uid=%s origem=%s%s",
        str(media_type).upper(),
        uid,
        source or "-",
        suffix,
    )


def log_media_error(logger, media_type, uid, error, source="-", detail=None):
    suffix = f" detalhe={detail}" if detail else ""
    logger.error(
        "🚨 [%s][ERROR] uid=%s origem=%s erro=%s%s",
        str(media_type).upper(),
        uid,
        source or "-",
        str(error),
        suffix,
    )


def log_event(logger, category, status, uid=None, **fields):
    pieces = [f"[{str(category).upper()}][{str(status).upper()}]"]
    if uid is not None:
        pieces.append(f"uid={uid}")
    pieces.extend(f"{key}={value}" for key, value in fields.items() if value is not None)
    logger.info(" ".join(pieces))
