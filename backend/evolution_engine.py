import logging

logger = logging.getLogger(__name__)


def evaluate_evolution(user_id, character_id, character, user_text, emotion, evo):
    config = character.get("evolution", {})
    stages = config.get("stages", [])
    milestones = config.get("milestones", [])

    evo["total_messages"] = evo.get("total_messages", 0) + 1

    updates = {
        "new_stage": None,
        "unlocked": [],
        "relationship_deltas": {},
        "trait_modifiers": {},
        "dialog_hints": [],
        "mevacoins_reward": 0,
    }

    for stage in stages:
        sid = stage["id"]
        if sid in evo["unlocked_stages"]:
            continue
        if evo["total_messages"] >= stage.get("min_messages", 0):
            updates["new_stage"] = sid
            updates["unlocked"].append(sid)
            updates["trait_modifiers"].update(stage.get("trait_bonus", {}))
            for unlock in stage.get("unlocks", []):
                updates["unlocked"].append(unlock)
                evo["flags"][unlock] = True
            evo["current_stage"] = sid
            evo["unlocked_stages"].append(sid)
            logger.info(f"Evolution: user={user_id} char={character_id} stage={sid}")

    for m in milestones:
        mid = m.get("id", "")
        if m.get("one_shot") and evo["flags"].get(mid):
            continue
        cooldown = m.get("cooldown_messages", 0)
        if cooldown and evo["flags"].get(f"last_{mid}", 0) > evo["total_messages"] - cooldown:
            continue
        if not _check_condition(m, user_text, emotion, evo):
            continue
        updates["unlocked"].append(m.get("unlock_flag", mid))
        effect = m.get("effect", {})
        if isinstance(effect, dict):
            updates["relationship_deltas"].update(
                {k: v for k, v in effect.items() if k != "mevacoins"}
            )
            reward = effect.get("mevacoins", 0)
            if reward:
                updates["mevacoins_reward"] += reward
        if m.get("dialog"):
            updates["dialog_hints"].append(m["dialog"])
        if m.get("unlock_flag"):
            evo["flags"][m["unlock_flag"]] = True
        evo["flags"][mid] = True
        evo["flags"][f"last_{mid}"] = evo["total_messages"]
        logger.info(f"Evolution milestone: user={user_id} char={character_id} milestone={mid}")

    return updates


def _check_condition(milestone, user_text, emotion, evo):
    cond = milestone.get("condition", {})
    ctype = cond.get("type")
    if not ctype:
        return False
    if ctype == "keyword":
        return any(kw in user_text.lower() for kw in cond.get("value", []))
    if ctype == "emotion":
        return emotion in cond.get("value", [])
    if ctype == "message_count":
        return evo["total_messages"] >= cond.get("value", 0)
    if ctype == "intimacy":
        return evo.get("intimacy", 0) >= cond.get("value", 0)
    if ctype == "topic":
        topic_words = cond.get("value", [])
        return any(tw in user_text.lower() for tw in topic_words)
    if ctype == "composite":
        op = cond.get("operator", "AND")
        sub_conditions = cond.get("conditions", [])
        results = [
            _check_condition({"condition": c}, user_text, emotion, evo)
            for c in sub_conditions
        ]
        return all(results) if op == "AND" else any(results)
    return False
