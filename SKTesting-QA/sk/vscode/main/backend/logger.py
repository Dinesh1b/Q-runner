"""logger.py — Thread-safe log buffer for Q-Audit Runner."""

import threading

log_buffer: list[str] = []
log_lock = threading.Lock()
_generation = 0


def log(msg: str) -> None:
    """Append a message to the shared log buffer."""
    with log_lock:
        log_buffer.append(msg)


def reset() -> None:
    """Clear the log buffer between runs."""
    global _generation
    with log_lock:
        log_buffer.clear()
        _generation += 1


def generation() -> int:
    """Incremented on every reset(); read while holding log_lock."""
    return _generation
