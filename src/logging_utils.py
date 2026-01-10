import json
import logging
from datetime import datetime, timezone


logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("news_digest")


def log_event(event: str, **fields):
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }

    logger.info(json.dumps(payload))
