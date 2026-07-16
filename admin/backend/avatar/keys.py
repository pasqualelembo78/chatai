"""Key rotation classes for API key management and provider fallback."""

import time


class KeyRotator:
    """Rotatore automatico di API keys con gestione rate limit."""

    def __init__(self, keys, provider_name=""):
        self.keys = [k for k in keys if k and k.strip()]
        self.provider_name = provider_name
        self.current_index = 0
        self.failed_keys = {}

    def get_current_key(self):
        if not self.keys:
            return None
        now = time.time()
        for i in range(len(self.keys)):
            idx = (self.current_index + i) % len(self.keys)
            key = self.keys[idx]
            if key not in self.failed_keys or now >= self.failed_keys[key]:
                self.current_index = idx
                return key
        return None

    def wait_for_available_key(self, max_wait=300):
        if not self.keys:
            return None
        now = time.time()
        wait_times = []
        for key in self.keys:
            if key in self.failed_keys:
                wait_times.append(self.failed_keys[key] - now)

        if not wait_times:
            return self.get_current_key()

        wait_time = max(5, min(min(wait_times) + 2, max_wait))

        print(f"\n  ⏳ {self.provider_name}: tutte le keys sono bloccate.")
        print(f"  ⏳ Aspetto {wait_time:.0f} secondi prima di riprovare...")
        print(f"  ⏳ (Ctrl+C per interrompere)")

        try:
            time.sleep(wait_time)
        except KeyboardInterrupt:
            print(f"\n  ⚠️  Interrutto dall'utente")
            return None

        return self.get_current_key()

    def report_failure(self, key, retry_after=60):
        self.failed_keys[key] = time.time() + retry_after
        print(f"  ⚠️  {self.provider_name} key {key[:12]}... bloccata per {retry_after}s")
        next_key = self.get_current_key()
        if next_key and next_key != key:
            print(f"  🔄 Passo alla key successiva: {next_key[:12]}...")
        elif not next_key:
            print(f"  ❌ Tutte le {self.provider_name} keys sono bloccate!")
        return next_key

    def report_success(self, key):
        if key in self.failed_keys:
            del self.failed_keys[key]

    def available_keys(self):
        now = time.time()
        return sum(1 for k in self.keys if k not in self.failed_keys or now >= self.failed_keys[k])

    def all_blocked(self):
        return self.available_keys() == 0


class ProviderRotator:
    """Rotatore tra provider LLM multipli con fallback automatico."""

    def __init__(self):
        self.providers = []
        self.current_provider_idx = 0

    def add_provider(self, name, api_key, model, base_url, headers_func=None, payload_func=None):
        if api_key and api_key.strip():
            self.providers.append({
                "name": name,
                "api_key": api_key.strip(),
                "model": model,
                "base_url": base_url,
                "headers_func": headers_func,
                "payload_func": payload_func
            })

    def get_current_provider(self):
        if not self.providers:
            return None
        return self.providers[self.current_provider_idx]

    def rotate_to_next(self):
        if len(self.providers) > 1:
            self.current_provider_idx = (self.current_provider_idx + 1) % len(self.providers)
            return self.get_current_provider()
        return None

    def call(self, prompt, max_tokens=800, temperature=0.8):
        import requests

        attempts = 0
        max_attempts = len(self.providers) * 2

        while attempts < max_attempts:
            provider = self.get_current_provider()
            if not provider:
                print(f"  ❌ Nessun provider LLM disponibile")
                return None

            try:
                if provider["headers_func"]:
                    headers = provider["headers_func"](provider["api_key"])
                else:
                    headers = {
                        "Authorization": f"Bearer {provider['api_key']}",
                        "Content-Type": "application/json"
                    }

                if provider["payload_func"]:
                    payload = provider["payload_func"](prompt, provider["model"], max_tokens, temperature)
                else:
                    payload = {
                        "model": provider["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }

                resp = requests.post(
                    provider["base_url"],
                    headers=headers, json=payload, timeout=30
                )
                resp.encoding = "utf-8"

                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return {"text": content, "provider": provider["name"]}
                elif resp.status_code == 429:
                    print(f"  ⚠️  {provider['name']} rate limited, provo il prossimo...")
                    self.rotate_to_next()
                    attempts += 1
                    continue
                else:
                    print(f"  ⚠️  {provider['name']} errore {resp.status_code}: {resp.text[:100]}")
                    self.rotate_to_next()
                    attempts += 1
                    continue
            except Exception as e:
                print(f"  ⚠️  {provider['name']} eccezione: {e}")
                self.rotate_to_next()
                attempts += 1
                continue

        print(f"  ❌ Tutti i provider LLM falliti dopo {max_attempts} tentativi")
        return None
