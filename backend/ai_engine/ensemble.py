import json
import os
import queue
import threading
import logging

logger = logging.getLogger(__name__)

ENSEMBLE_ENABLED = os.environ.get("ENSEMBLE_ENABLED", "1") == "1"

ENSEMBLE_MODELS = [
    ("cerebras", "gpt-oss-120b"),
    ("groq", "llama-3.3-70b-versatile"),
]
try:
    _env_models = os.environ.get("ENSEMBLE_MODELS", "")
    if _env_models:
        ENSEMBLE_MODELS = json.loads(_env_models)
except (json.JSONDecodeError, TypeError):
    pass


def _ensemble_parallel_stream(messages, user_id=None):
    from ai_engine.registry import PROVIDERS
    from ai_engine.chain import _provider_ready

    result_queue = queue.Queue()
    stop_events = {}

    def _run_provider(pid, model, evt):
        try:
            provider = PROVIDERS.get(pid)
            if not provider:
                return
            if not _provider_ready(pid):
                return
            stream_fn = provider.get("generate_stream") or provider.get("generate")
            if not stream_fn:
                return

            if stream_fn == provider.get("generate"):
                text = stream_fn(messages, model, user_id=user_id)
                if text:
                    result_queue.put(("token", pid, model, text))
                    result_queue.put(("done", pid, model, None))
                return

            gen = stream_fn(messages, model, user_id=user_id)
            for token in gen:
                if evt.is_set():
                    break
                result_queue.put(("token", pid, model, token))
            result_queue.put(("done", pid, model, None))
        except Exception as e:
            logger.warning(f"ensemble {pid}/{model} errore: {e}")
            result_queue.put(("error", pid, model, str(e)))

    ready_models = [(pid, m) for pid, m in ENSEMBLE_MODELS if _provider_ready(pid)]
    if not ready_models:
        logger.info("ensemble: nessun provider pronto, fallback alla catena")
        return

    logger.info(f"ensemble: avvio {len(ready_models)} modelli in parallelo: {[(p, m) for p, m in ready_models]}")

    threads = []
    for pid, model in ready_models:
        evt = threading.Event()
        stop_events[(pid, model)] = evt
        t = threading.Thread(target=_run_provider, args=(pid, model, evt), daemon=True)
        t.start()
        threads.append(t)

    winner = None

    while True:
        try:
            msg_type, pid, model, data = result_queue.get(timeout=60)
        except queue.Empty:
            logger.warning("ensemble: timeout 60s, interrompo")
            break

        if msg_type == "token":
            if winner is None:
                winner = (pid, model)
                logger.info(f"ensemble: vincitore {pid}/{model}")
                for (wpid, wmodel), evt in stop_events.items():
                    if (wpid, wmodel) != winner:
                        evt.set()

            if winner and pid == winner[0] and model == winner[1]:
                yield data, pid, model

        elif msg_type == "done":
            if winner and pid == winner[0] and model == winner[1]:
                break
            if winner is None:
                continue

        elif msg_type == "error":
            if winner is None:
                continue
            # The winning provider errored mid-stream: stop all workers and
            # end the stream instead of blocking until the 60s timeout.
            for evt in stop_events.values():
                evt.set()
            logger.warning(f"ensemble: vincitore {winner[0]}/{winner[1]} in errore, interrompo lo stream")
            break

    for t in threads:
        t.join(timeout=5)

    if winner:
        logger.info(f"ensemble: completato da {winner[0]}/{winner[1]}")
    else:
        logger.warning("ensemble: tutti i provider falliti")
