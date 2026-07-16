"""Avatar animation using SadTalker."""

import os
import shutil
import tempfile

from avatar.config import STATIC_AVATARS


def find_avatars():
    avatars = []
    for root, dirs, files in os.walk(STATIC_AVATARS):
        for f in files:
            if f.endswith(".png") and not f.endswith("_anim.png"):
                full = os.path.join(root, f)
                rel = os.path.relpath(full, STATIC_AVATARS)
                category = os.path.dirname(rel)
                char_id = f[:-4]
                avatars.append({"path": full, "category": category, "id": char_id})
    return avatars


def animate_avatar(avatar_path, category, char_id):
    from gtts import gTTS
    from gradio_client import Client

    output_dir = os.path.join(STATIC_AVATARS, category)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{char_id}_anim.mp4")
    if os.path.isfile(output_path):
        return "already_exists"

    print(f"  Animo {char_id}...")

    audio_path = None
    try:
        name_for_tts = char_id.replace("_", " ")
        audio_path = tempfile.mktemp(suffix=".mp3")
        tts = gTTS(text=f"Ciao, sono {name_for_tts}. Piacere di conoscerti!", lang="it")
        tts.save(audio_path)

        client = Client("John6666/SadTalker")
        result = client.predict(
            avatar_path, audio_path,
            "crop", True, True, 2, 256, 0, "facevid2vid", 1.0,
            False, None, "pose", False, 5, True,
            api_name="/test"
        )

        video_path = None
        if result and isinstance(result, dict):
            video_path = result.get("video") or result.get("generated_video")

        if video_path and os.path.isfile(video_path):
            shutil.copy2(video_path, output_path)
            print(f"  Salvato: {output_path}")
            return "ok"
        else:
            print(f"  Nessun video restituito per {char_id}")
            return "failed"

    except Exception as e:
        print(f"  ERRORE animazione {char_id}: {e}")
        return "failed"
    finally:
        try:
            if audio_path and os.path.isfile(audio_path):
                os.unlink(audio_path)
        except Exception:
            pass
