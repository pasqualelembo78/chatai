"""Generazione di immagini/video di chat tramite HuggingFace/SadTalker."""
import os
import base64
import uuid
import logging

logger = logging.getLogger(__name__)

_CHAT_GEN_MODEL = "black-forest-labs/FLUX.1-schnell"
_CHAT_GEN_API_URL = "https://router.huggingface.co/hf-inference/models/"


def _get_hf_token():
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        token_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".hf_token")
        if os.path.isfile(token_file):
            with open(token_file) as f:
                token = f.read().strip()
    return token


def _generate_chat_image(prompt):
    token = _get_hf_token()
    if not token:
        return None
    try:
        import requests as _req
        resp = _req.post(
            _CHAT_GEN_API_URL + _CHAT_GEN_MODEL,
            headers={"Authorization": f"Bearer {token}"},
            json={
                "inputs": prompt,
                "parameters": {
                    "negative_prompt": "cartoon, anime, illustration, low quality, blurry, distorted face, bad anatomy",
                    "guidance_scale": 7.5,
                    "num_inference_steps": 4
                }
            },
            timeout=120
        )
        if resp.status_code == 200:
            return base64.b64encode(resp.content).decode("utf-8")
        return None
    except Exception as e:
        logger.error(f"Image gen error: {e}")
        return None


def _generate_chat_video(prompt):
    image_b64 = _generate_chat_image(prompt)
    if not image_b64:
        return None, None
    import tempfile
    import shutil
    import wave
    img_path = None
    audio_path = None
    try:
        img_data = base64.b64decode(image_b64)
        img_path = tempfile.mktemp(suffix=".png")
        with open(img_path, "wb") as f:
            f.write(img_data)
        tts_text = prompt[:150] if prompt else "Ciao, sono un avatar animato."
        try:
            from gtts import gTTS
            audio_path = tempfile.mktemp(suffix=".mp3")
            tts = gTTS(text=tts_text, lang="it")
            tts.save(audio_path)
        except Exception:
            audio_path = tempfile.mktemp(suffix=".wav")
            with wave.open(audio_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(22050)
                wf.writeframes(b"\x00\x00" * 22050)
        from gradio_client import Client
        client = Client("John6666/SadTalker")
        result = client.predict(
            img_path, audio_path, "crop", True, True, 2, 256, 0,
            "facevid2vid", 1.0, False, None, "pose", False, 5, True,
            api_name="/test"
        )
        video_url = None
        if result and isinstance(result, dict):
            video_path = result.get("video") or result.get("generated_video")
            if video_path:
                backend_dir = os.path.dirname(os.path.abspath(__file__))
                video_dir = os.path.join(backend_dir, "static", "videos")
                os.makedirs(video_dir, exist_ok=True)
                video_filename = f"{uuid.uuid4().hex}.mp4"
                dest = os.path.join(video_dir, video_filename)
                shutil.copy2(video_path, dest)
                video_url = f"/static/videos/{video_filename}"
        return video_url, image_b64
    except Exception as e:
        logger.error(f"Video gen error: {e}")
        return None, None
    finally:
        for p in [img_path, audio_path]:
            try:
                if p and os.path.isfile(p):
                    os.unlink(p)
            except Exception:
                pass
