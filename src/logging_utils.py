import json
import logging
from datetime import datetime


logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("news_digest")


def log_event(event: str, **fields):
    payload = {
        "ts": datetime.utcnow().isoformat(),
        "event": event,
        **fields,
    }

    logger.info(json.dumps(payload))
