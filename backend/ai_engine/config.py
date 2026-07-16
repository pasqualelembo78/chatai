import os
import time
import logging

logger = logging.getLogger(__name__)

CHAT_PROVIDER = os.environ.get("CHAT_PROVIDER", "groq").lower()

GROQ_CHAT_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
    "qwen/qwen3.6-27b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]


class ChatKeyRotator:
    def __init__(self):
        self.keys = []
        self.current_index = 0
        self.failed_keys = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        multi_val = os.environ.get("GROQ_API_KEYS", "")
        if multi_val:
            self.keys = [k.strip() for k in multi_val.split(",") if k.strip()]
        if not self.keys:
            single_val = os.environ.get("GROQ_API_KEY", "")
            if single_val:
                self.keys = [single_val]
        self._loaded = True
        if self.keys:
            logger.info(f"Chat Groq key rotator: {len(self.keys)} keys loaded")

    def get_key(self):
        self._ensure_loaded()
        if not self.keys:
            return None
        now = time.time()
        for i in range(len(self.keys)):
            idx = (self.current_index + i) % len(self.keys)
            key = self.keys[idx]
            if key not in self.failed_keys or now >= self.failed_keys[key]:
                self.current_index = idx
                return key
        return self._wait_for_key()

    def _wait_for_key(self, max_wait=30):
        if not self.keys:
            return None
        now = time.time()
        earliest_available = float('inf')
        for key in self.keys:
            if key in self.failed_keys:
                earliest_available = min(earliest_available, self.failed_keys[key])
            else:
                return key
        if earliest_available == float('inf'):
            return self.keys[0]
        remaining = earliest_available - now
        if remaining <= 0:
            return self.get_key()
        if remaining > max_wait:
            logger.warning(f"Chat Groq: tutte le key rate-limited, prossima disponibile tra {remaining:.0f}s")
            return None
        time.sleep(min(remaining + 0.5, max_wait))
        return self.get_key()

    def report_failure(self, key, retry_after=30):
        self.failed_keys[key] = time.time() + retry_after
        logger.warning(f"Chat Groq key {key[:12]}... rate limited, retry after {retry_after}s")

    def report_success(self, key):
        if key in self.failed_keys:
            del self.failed_keys[key]


_chat_key_rotator = ChatKeyRotator()

_MODEL_CACHE = {}
_CACHE_TTL = int(os.environ.get("MODEL_REFRESH_TTL", 3600))

import requests


def _cached_fetch(url, headers=None, timeout=10, cache_key=None):
    cache_key = cache_key or url
    now = time.time()
    if cache_key in _MODEL_CACHE and now - _MODEL_CACHE[cache_key]["ts"] < _CACHE_TTL:
        return _MODEL_CACHE[cache_key]["data"]
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            _MODEL_CACHE[cache_key] = {"data": data, "ts": now}
            return data
    except Exception:
        pass
    return None


def clear_model_cache():
    _MODEL_CACHE.clear()
    logger.info("Model cache cleared")
