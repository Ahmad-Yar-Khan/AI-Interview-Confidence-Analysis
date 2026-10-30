"""
confidence_service.py
----------------------
Runs confidence prediction (ffmpeg -> Groq transcription -> feature extraction ->
ensemble classifier) in a separate worker process instead of inside the API
process.

Why a process and not a thread: the prediction includes CPU-heavy feature
extraction and ensemble inference. Run inline in an `async def` route it froze
the event loop, so every other request (including /api/tts for the next
question) waited for it to finish. In a worker process it can't block the event
loop or compete for the API process's GIL; the route just awaits a future.

Lifecycle (driven from main.py's lifespan):
  start()  — creates the pool; each worker initializes the Groq client and
             loads the ensemble model ONCE in its initializer. A warm-up task is
             submitted so the model loads at startup rather than on the first
             user request. Startup does not wait for it — the API is usable
             immediately, and early requests simply queue until the worker is
             ready.
  predict()— awaitable; ships the audio file path to a worker, returns the
             prediction dict ({} on prediction failure, same as before).
  stop()   — shuts the pool down.

The worker-side functions (_init_worker, _warmup, _predict) must stay at
module level: on Windows workers are spawned fresh and re-import this module,
and tasks are sent to them by pickled name.
"""

import asyncio
import logging
from concurrent.futures import Future, ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: ProcessPoolExecutor | None = None
_status = "stopped"   # stopped | loading | ready | failed
_error: str | None = None


# ════════════════════════════════════════
# WORKER-PROCESS SIDE
# ════════════════════════════════════════

def _init_worker() -> None:
    # Imported here, not at module top, so the API process never loads
    # sklearn / xgboost — only the workers do.
    from app.ml.confidence_model import load_models
    load_models()


def _warmup() -> bool:
    return True


def _predict(audio_path: str) -> dict:
    from app.ml.confidence_model import predict_confidence_for_audio_vscode
    return predict_confidence_for_audio_vscode(audio_path)


# ════════════════════════════════════════
# API-PROCESS SIDE
# ════════════════════════════════════════

def _on_warmup_done(fut: Future) -> None:
    global _status, _error
    exc = fut.exception()
    if exc is None:
        if _status != "failed":
            _status = "ready"
            logger.info("Confidence worker ready (ensemble model loaded; Groq transcription configured).")
    else:
        _status = "failed"
        _error = str(exc) or type(exc).__name__
        logger.error(f"Confidence worker failed to load models: {_error}")


def start() -> None:
    global _pool, _status, _error
    workers = max(1, settings.CONFIDENCE_WORKERS)
    _pool = ProcessPoolExecutor(max_workers=workers, initializer=_init_worker)
    _status, _error = "loading", None
    # Workers are spawned on demand, one per submit while none is idle — so
    # one warm-up task per worker gets all of them loading at startup.
    for _ in range(workers):
        _pool.submit(_warmup).add_done_callback(_on_warmup_done)
    logger.info(f"Confidence worker pool starting ({workers} process(es), transcription={settings.GROQ_TRANSCRIBE_MODEL}).")


def stop() -> None:
    global _pool, _status
    if _pool is not None:
        _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None
    _status = "stopped"


def status() -> dict:
    return {"status": _status, "error": _error}


def is_available() -> bool:
    """False only once loading has definitively failed; 'loading' still accepts (queues) requests."""
    return _pool is not None and _status in ("loading", "ready")


async def predict(audio_path: str) -> dict:
    if not is_available():
        raise RuntimeError(f"Confidence worker unavailable ({_status}): {_error or 'not started'}")
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(_pool, _predict, audio_path)
    except BrokenProcessPool:
        # A worker died mid-task (e.g. out of memory). If it had been healthy,
        # replace the pool so later requests can recover; if it never finished
        # loading, the warm-up callback has already marked it failed.
        if _status == "ready":
            logger.error("Confidence worker crashed — restarting the pool.")
            stop()
            start()
        raise
