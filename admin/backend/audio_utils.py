import os
import time
import logging
import subprocess
import json
from pathlib import Path
import security_utils

logger = logging.getLogger(__name__)

UPLOAD_DIR = security_utils.UPLOAD_DIR
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_AUDIO_EXTENSIONS = security_utils.ALLOWED_AUDIO_EXTS
ALLOWED_AUDIO_MIMES = security_utils.ALLOWED_AUDIO_MIMES
MAX_AUDIO_SIZE = security_utils.AUDIO_MAX_SIZE

CLEANUP_AGE = security_utils.CLEANUP_AGE

VOICE_MAP = {
    "luna": "it_IT-paola-medium",
    "sofia": "it_IT-paola-medium",
    "marco_amicizia": "it_IT-riccardo-medium",
    "anna_amicizia": "it_IT-paola-medium",
    "elara": "it_IT-paola-medium",
    "kael": "it_IT-riccardo-medium",
    "mister_shadow": "it_IT-riccardo-medium",
    "la_custode": "it_IT-paola-medium",
    "yuki": "it_IT-paola-medium",
    "akira": "it_IT-riccardo-medium",
    "prof_rossi_scuola": "it_IT-riccardo-medium",
    "sara_scuola": "it_IT-paola-medium",
    "alex_gamer": "it_IT-riccardo-medium",
    "nexus": "it_IT-riccardo-medium",
    "detective_mason": "it_IT-riccardo-medium",
    "agente_noir": "it_IT-riccardo-medium",
    "ginecologa": "it_IT-paola-medium",
    "dottor_luca": "it_IT-riccardo-medium",
    "ceo_riccardo": "it_IT-riccardo-medium",
    "coach_martina": "it_IT-paola-medium",
    "explorer_max": "it_IT-riccardo-medium",
    "giulia_travel": "it_IT-paola-medium",
    "coach_titan": "it_IT-riccardo-medium",
    "mentore_zen": "it_IT-riccardo-medium",
    "chef_mario": "it_IT-riccardo-medium",
    "chef_emma": "it_IT-paola-medium",
    "hacker_neo": "it_IT-riccardo-medium",
    "ingegnere_alex": "it_IT-riccardo-medium",
    "storico_leonardo": "it_IT-riccardo-medium",
    "archeologa_sara": "it_IT-paola-medium",
    "volt": "it_IT-riccardo-medium",
    "dark_wing": "it_IT-riccardo-medium",
    "hunter_mike": "it_IT-riccardo-medium",
    "lara_wild": "it_IT-paola-medium",
    "comandante_orion": "it_IT-riccardo-medium",
    "astra": "it_IT-paola-medium",
    "insegnante_nuoto": "it_IT-paola-medium",
    "coach_marco_sport": "it_IT-riccardo-medium",
    "mia_flirt": "it_IT-paola-medium",
    "eva_flirt": "it_IT-paola-medium",
    "clara_relazioni": "it_IT-paola-medium",
    "david_relazioni": "it_IT-riccardo-medium",
    "valentina_confessioni": "it_IT-paola-medium",
    "leon_confessioni": "it_IT-riccardo-medium",
    "bianca_seduzione": "it_IT-paola-medium",
    "christian_seduzione": "it_IT-riccardo-medium",
    "insegnante_matematica": "it_IT-riccardo-medium",
    "prof_italiano": "it_IT-riccardo-medium",
    "andrea_tecnico": "it_IT-riccardo-medium",
    "prof_moretti": "it_IT-riccardo-medium",
    "consulente_startup": "it_IT-riccardo-medium",
    "esperto_marketing": "it_IT-paola-medium",
    "consulente_fiscale": "it_IT-riccardo-medium",
    "senior_dev": "it_IT-riccardo-medium",
    "analista_dati": "it_IT-paola-medium",
    "fixer_tecnico": "it_IT-riccardo-medium",
    "guida_config": "it_IT-riccardo-medium",
    "assistente_automazione": "it_IT-paola-medium",
    "coach_disciplina": "it_IT-riccardo-medium",
    "coach_focus": "it_IT-paola-medium",
    "stratega_personale": "it_IT-riccardo-medium",
    "organizzatore_vita": "it_IT-paola-medium",
    "confidente": "it_IT-paola-medium",
    "amico_ironico": "it_IT-riccardo-medium",
    "compagno_chat": "it_IT-paola-medium",
    "supporto_motivazionale": "it_IT-riccardo-medium",
    "narratore_interattivo": "it_IT-riccardo-medium",
    "game_master": "it_IT-riccardo-medium",
    "sceneggiatore": "it_IT-riccardo-medium",
    "costruttore_mondi": "it_IT-paola-medium",
    "chef_personale": "it_IT-paola-medium",
    "trainer_fitness": "it_IT-paola-medium",
}


def get_voice_profile(character):
    explicit = character.get("voice_profile")
    if explicit:
        return explicit

    model = "it_IT-riccardo-medium"
    speed = 1.0

    cid = character.get("id", "")
    if cid in VOICE_MAP:
        model = VOICE_MAP[cid]

    traits = character.get("core_traits", {})
    playfulness = traits.get("playfulness", 5)
    warmth = traits.get("warmth", 5)

    if playfulness >= 7:
        speed = 1.1
    elif warmth <= 3:
        speed = 0.85
    else:
        speed = 1.0

    return {"model": model, "speed": speed, "pitch": 1.0}


def allowed_audio_file(filename):
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_AUDIO_EXTENSIONS


def save_upload(file_storage):
    path, ext = security_utils.secure_save_upload(file_storage, prefix="audio")
    return path


def transcribe_audio(audio_path):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.error("faster-whisper not installed")
        return None

    try:
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, info = model.transcribe(audio_path, language="it")
        text = " ".join(seg.text for seg in segments)
        return text.strip() if text.strip() else None
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return None


def text_to_speech(text, voice_profile):
    model = voice_profile.get("model", "it_IT-riccardo-medium")
    speed = voice_profile.get("speed", 1.0)

    try:
        result = subprocess.run(
            ["which", "piper"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            logger.error("piper not found in PATH")
            return None

        model_path = None
        possible_paths = [
            f"/usr/share/piper/voices/{model}.onnx",
            f"/usr/local/share/piper/voices/{model}.onnx",
            f"./piper_voices/{model}.onnx",
            f"/models/piper/{model}.onnx",
        ]
        for p in possible_paths:
            if os.path.isfile(p):
                model_path = p
                break

        if not model_path:
            logger.error(f"Piper voice model not found: {model}")
            return None

        output_path = str(UPLOAD_DIR / f"tts_{int(time.time())}_{os.urandom(4).hex()}.wav")

        cmd = ["piper", "--model", model_path, "--output-raw"]
        if speed != 1.0:
            cmd.extend(["--length-scale", str(1.0 / speed)])

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = proc.communicate(
            input=text.encode("utf-8"),
            timeout=30
        )

        if proc.returncode != 0:
            logger.error(f"Piper TTS failed: {stderr.decode()}")
            return None

        import soundfile as sf
        import numpy as np

        sample_rate = 22050
        samples = np.frombuffer(stdout, dtype=np.int16)
        if len(samples) == 0:
            logger.error("Piper produced no audio output")
            return None

        sf.write(output_path, samples, sample_rate)
        return output_path

    except subprocess.TimeoutExpired:
        logger.error("Piper TTS timed out")
        return None
    except ImportError:
        try:
            import wave
            import struct

            os.makedirs(str(UPLOAD_DIR), exist_ok=True)
            output_path = str(UPLOAD_DIR / f"tts_{int(time.time())}_{os.urandom(4).hex()}.wav")

            cmd = ["piper", "--model", model_path, "--output", output_path]
            if speed != 1.0:
                cmd.extend(["--length-scale", str(1.0 / speed)])

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = proc.communicate(
                input=text.encode("utf-8"),
                timeout=30
            )

            if proc.returncode != 0:
                logger.error(f"Piper TTS (direct) failed: {stderr.decode()}")
                return None

            if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
                return output_path
            return None

        except Exception as e:
            logger.error(f"Piper TTS (fallback) failed: {e}")
            return None
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return None


def cleanup_old_files():
    security_utils.cleanup_old_files()
