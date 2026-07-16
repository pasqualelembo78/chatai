"""Generation status tracking for avatar/bio/scenario tasks."""

import json
import os
import time

from avatar.config import STATUS_FILE, GEN_TASKS


def load_gen_status():
    """Carica lo stato delle generazioni completate dal file di tracking."""
    if os.path.isfile(STATUS_FILE):
        try:
            with open(STATUS_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_gen_status(status):
    """Salva lo stato delle generazioni su file."""
    tmp = STATUS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STATUS_FILE)


def is_char_done(char_id, tasks=GEN_TASKS):
    """True se il personaggio ha tutti i task specificati marcati come fatti."""
    status = load_gen_status()
    entry = status.get(char_id, {})
    return all(entry.get(t) for t in tasks)


def mark_char_done(char_id, task):
    """Marca un singolo task come completato per il personaggio."""
    status = load_gen_status()
    entry = status.setdefault(char_id, {})
    entry[task] = True
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_gen_status(status)


def mark_char_done_all(char_id):
    """Marca tutti i task come completati per il personaggio."""
    status = load_gen_status()
    entry = status.setdefault(char_id, {})
    for t in GEN_TASKS:
        entry[t] = True
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_gen_status(status)


def reset_char_status(char_id):
    """Resetta lo stato di un personaggio."""
    status = load_gen_status()
    if char_id in status:
        del status[char_id]
        save_gen_status(status)
