"""Background runner for the avatar generation pipeline (avatar + bio + scenario).

This mirrors the pattern used by ``import_engine`` for character imports: a
generate job is started in a daemon thread and its progress is exposed via a
process-wide status dict that the API can poll.

The job invokes the same pipeline used by ``generate_avatars.sh``
(``backend/avatar_tool.py --generate-all --model pollinations --bio``), so it
produces avatars, Italian biographies and opening scenarios for characters.
"""

import os
import re
import subprocess
import threading

_lock = threading.Lock()

_state = {
    "running": False,
    "progress": 0,
    "total": 0,
    "generated": 0,
    "bios": 0,
    "errors": 0,
    "message": "",
    "log": [],
}

_proc = None  # active subprocess.Popen, guarded by _lock
_MAX_LOG = 200


def get_avatar_status():
    """Return a thread-safe copy of the current avatar generation status."""
    with _lock:
        return dict(_state)


def _set(**kwargs):
    with _lock:
        _state.update(kwargs)


def _append_log(line):
    with _lock:
        _state["log"].append(line)
        if len(_state["log"]) > _MAX_LOG:
            _state["log"] = _state["log"][-_MAX_LOG:]


def _load_env(env_file):
    env = dict(os.environ)
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    env[key] = value
    except FileNotFoundError:
        pass
    return env


def start_avatar_generation(limit=50, force=False):
    """Start the avatar generation in a background thread.

    ``limit`` of 0 means "all" (every missing character). Returns a dict with
    either ``{"status": "started", ...}`` or ``{"error": ...}``.
    """
    if _state["running"]:
        return {"error": "Una generazione avatar è già in esecuzione"}

    backend_dir = os.path.dirname(os.path.abspath(__file__))
    tool = os.path.join(backend_dir, "avatar_tool.py")
    if not os.path.isfile(tool):
        return {"error": f"avatar_tool.py non trovato in {backend_dir}"}

    # Use the same virtualenv that generate_avatars.sh provisions (it has
    # requests/pillow/pydotenv). Fall back to system python3 only if missing.
    venv_py = os.path.join(backend_dir, "venv", "bin", "python3")
    python_bin = venv_py if os.path.isfile(venv_py) else "python3"

    env = _load_env(os.path.join(backend_dir, ".env"))

    cmd = [
        python_bin, tool,
        "--generate-all",
        "--model", "pollinations",
        "--bio",
        "--limit", str(limit),
    ]
    if force:
        cmd.append("--force")

    def _run():
        global _proc
        _set(
            running=True,
            progress=0,
            total=0,
            generated=0,
            bios=0,
            errors=0,
            message="Avvio generazione avatar (bio + scenario)...",
            log=[],
        )
        try:
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=backend_dir,
                    env=env,
                    text=True,
                    bufsize=1,
                )
            except FileNotFoundError as e:
                _set(running=False, message=f"Python non trovato: {e}")
                return
            with _lock:
                _proc = proc
            total_re = re.compile(r"Genero avatar per (\d+) personaggi")
            for line in proc.stdout:
                line = line.rstrip("\n")
                if not line:
                    continue
                _append_log(line)

                m = total_re.search(line)
                if m:
                    _set(total=int(m.group(1)))

                if "✅ Avatar salvato" in line:
                    with _lock:
                        gen = _state["generated"] + 1
                    _set(generated=gen, progress=gen, message=line.strip())
                elif "✅ Biografia salvata" in line:
                    _set(bios=_state["bios"] + 1)
                elif "FALLITO" in line or "ERRORE" in line:
                    _set(errors=_state["errors"] + 1, message=line.strip())

            proc.wait()
            with _lock:
                _proc = None
            if proc.returncode == 0:
                _set(running=False, message="Generazione avatar completata!")
            elif proc.returncode == -9:
                _set(running=False, message="Generazione interrotta dall'utente.")
            else:
                _set(
                    running=False,
                    message=f"Generazione terminata con codice {proc.returncode}",
                )
        except Exception as e:  # pragma: no cover - defensive
            with _lock:
                _proc = None
            _set(running=False, message=f"Errore generazione avatar: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "limit": limit, "force": force}


def stop_avatar_generation():
    """Terminate a running avatar generation, if any."""
    with _lock:
        proc = _proc
    if proc is None:
        return {"status": "not_running"}
    proc.terminate()  # SIGTERM; avatar_tool flushes what it has so far
    try:
        proc.wait(timeout=10)
    except Exception:
        proc.kill()
    with _lock:
        _proc = None
    _set(running=False, message="Generazione interrotta dall'utente.")
    return {"status": "stopped"}


if __name__ == "__main__":
    print(start_avatar_generation(limit=2))
