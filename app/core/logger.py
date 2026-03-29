import logging
from collections import deque
from datetime import datetime, timezone

# Circular in-memory log buffer — exposed via GET /logs
LOG_BUFFER: deque[dict] = deque(maxlen=1000)


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        LOG_BUFFER.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })


def setup_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric_level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    )
    root.addHandler(console)
    root.addHandler(_BufferHandler())


# Default setup — reconfigured on startup with settings.LOG_LEVEL
setup_logging()
