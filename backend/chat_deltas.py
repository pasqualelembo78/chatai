"""Delta di relazione/personalità e risposte di fallback in base all'emozione."""


def _compute_relationship_deltas(emotion, intensity):
    deltas = {"trust": 0, "affinity": 0, "respect": 0, "conflict": 0}
    d = round(intensity * 2)
    if emotion == "anger":
        deltas.update({"conflict": d, "trust": -d, "affinity": -d})
    elif emotion == "romance":
        deltas.update({"affinity": d, "trust": round(d * 0.5)})
    elif emotion == "challenge":
        deltas.update({"respect": d, "trust": round(d * 0.3)})
    elif emotion == "joy":
        deltas.update({"affinity": round(d * 0.5), "trust": round(d * 0.3)})
    elif emotion == "sadness":
        deltas.update({"trust": round(d * 0.5), "affinity": round(d * 0.3)})
    elif emotion == "fear":
        deltas["trust"] = round(d * 0.7)
    return deltas


def _compute_personality_deltas(emotion, intensity, relationship):
    deltas = {"warmth": 0, "strictness": 0, "patience": 0, "sarcasm": 0}
    d = round(intensity)
    if emotion == "anger":
        deltas.update({"patience": -d, "strictness": d, "sarcasm": round(d * 0.5)})
    elif emotion == "romance":
        deltas.update({"warmth": d, "sarcasm": -round(d * 0.5)})
    elif emotion == "challenge":
        deltas.update({"strictness": round(d * 0.5), "sarcasm": d})
    elif relationship.get("conflict", 0) > 50:
        deltas.update({"patience": -1, "sarcasm": 1})
    elif relationship.get("affinity", 0) > 50:
        deltas.update({"warmth": 1, "patience": 1})
    return deltas


def _fallback_response(character, emotion):
    name = character["name"]
    fb = {
        "anger": f"{name} incrocia le braccia. «Calma. Raccontami cosa c'è che non va.»",
        "romance": f"{name} sorride. «Sei molto gentile.»",
        "challenge": f"{name} alza un sopracciglio. «Una sfida? Mi piace.»",
        "sadness": f"{name} ti guarda con comprensione. «Se vuoi parlare, io sono qui.»",
        "fear": f"{name} si avvicina. «Tranquillo, sono qui con te.»",
        "joy": f"{name} ride. «Che bello vederti di buon umore!»",
    }
    return fb.get(emotion, f"{name} annuisce. «Raccontami di più.»")
