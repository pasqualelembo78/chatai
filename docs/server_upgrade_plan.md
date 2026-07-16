# Server Upgrade Plan — Modello Locale Senza Restrizioni

## Quando migrare
- Quando l'app raggiunge ~50-100 utenti attivi
- Quando il revenue mensile copre il costo del server (~€80/mese)
- Quando i modelli 3B/7B non bastano più per la qualità richiesta

## Specs consigliate

### Tier 1 — Buon compromesso (~€60-80/mese)
- **Provider:** Hetzner (Dedicated Server)
- **RAM:** 64 GB ECC
- **CPU:** AMD Ryzen 9 / Intel Xeon (8+ core)
- **Storage:** 2x 1TB NVMe SSD (RAID 1)
- **Modello:** Qwen2.5-72B-Instruct Q4_K_M (~40 GB RAM)
- **Quantità modelli:** 72B principale + 7B fallback

### Tier 2 — Premium (~€120-150/mese)
- **Provider:** Hetzner / OVH
- **RAM:** 128 GB ECC
- **CPU:** AMD EPYC / Intel Xeon (16+ core)
- **Storage:** 2x 2TB NVMe SSD
- **Modello:** Llama-3.1-70B Q8 o Qwen2.5-72B Q5_K_M
- **Quantità modelli:** 70B principale + 13B + 7B fallback

## Modelli da scaricare

```bash
# Tier 1 (64 GB RAM)
ollama pull qwen2.5:72b-instruct-q4_K_M    # ~40 GB
ollama pull hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M  # ~4 GB

# Tier 2 (128 GB RAM)
ollama pull qwen2.5:72b-instruct-q5_K_M    # ~50 GB
ollama pull hf.co/mradermacher/Qwen2.5-14B-Instruct-abliterated-GGUF:Q4_K_M  # ~8 GB
ollama pull hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M  # ~4 GB
```

## Configurazione Ollama ottimizzata

```bash
# /etc/systemd/system/ollama.service.d/override.conf
[Service]
Environment="OLLAMA_HOST=127.0.0.1:11434"
Environment="OLLAMA_NUM_PARALLEL=2"
Environment="OLLAMA_MAX_LOADED_MODELS=2"
Environment="OLLAMA_KEEP_ALIVE=30m"
Environment="OLLAMA_FLASH_ATTENTION=1"
```

## Code change: switch modello principale

Quando il server è pronto, in `ai_engine.py` cambia:

```python
# Prima (attuale)
OLLAMA_MODELS = [
    "hf.co/mradermacher/Qwen2.5-3B-Instruct-abliterated-RP_SLERP-GGUF:Q4_K_M",
    ...
]

# Dopo (upgrade)
OLLAMA_MODELS = [
    "qwen2.5:72b-instruct-q4_K_M",  # Principale
    "hf.co/mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF:Q4_K_M",  # Fallback
    ...
]
```

## Monitoraggio

```bash
# Watch RAM in tempo reale
watch -n 2 'free -h && echo "---" && ollama ps'

# Check model loaded
curl http://localhost:11434/api/ps
```

## Costi stimati

| Tier | Server | Modello | Costo/mese |
|------|--------|---------|------------|
| Attuale | VPS condiviso | 3B | ~€20 (già pagato) |
| Tier 1 | Hetzner AX102 | 72B Q4 | ~€75 |
| Tier 2 | Hetzner AX162 | 72B Q5 + 14B | ~€130 |

## Checklist prima della migrazione

- [ ] Revenue mensile >= €100
- [ ] Utenti attivi >= 50
- [ ] Backup strategy confermata
- [ ] Test 72B su server temporaneo (Hetzner offre trial)
- [ ] Benchmark qualità risposte vs 3B
- [ ] Monitoraggio RAM/CPU configurato
