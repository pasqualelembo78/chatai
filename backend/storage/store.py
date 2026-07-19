"""Store MVC: consumabili, livelli e payload per la schermata Negozio.

Il backend espone gia' lo sblocco di feature/categorie via `/user/mevacoins/spend`
e i guadagni (checkin, streak, missioni, referral, share). Qui aggiungiamo:

  * Consumabili: oggetti che l'utente compra con MVC e "consuma" quando li usa
    (es. rigenera messaggio, boost velocita', pack personalita', streak shield).
  * Livelli: derivati dai MVC totali guadagnati (gamification).
  * get_shop_payload(): un unico oggetto che l'app Android usa per disegnare
    la schermata Negozio (saldo, livello, feature sbloccabili, consumabili).
"""
from db import get_conn, put_conn
from storage.mevacoins import get_mevacoins_balance, spend_mevacoins
from chat_engine import FEATURES

# Costo in MVC e metadati dei consumabili acquistabili.
CONSUMABLES = {
    "regenerate_message": {
        "name": "Rigenera messaggio", "cost": 20,
        "desc": "Riscrivi l'ultima risposta dell'IA con un'altra variante",
    },
    "speed_boost": {
        "name": "Boost velocità", "cost": 30,
        "desc": "Metti la tua richiesta in coda prioritaria (risposta più veloce)",
    },
    "personality_pack": {
        "name": "Pack personalità", "cost": 40,
        "desc": "Sblocca toni di conversazione extra per i personaggi",
    },
    "streak_shield": {
        "name": "Streak Shield", "cost": 50,
        "desc": "Proteggi la streak dei 30 giorni se salti un giorno",
    },
}

# MVC cumulativi necessari per salire di un livello.
LEVEL_STEP = 200


def buy_consumable(user_id, item):
    spec = CONSUMABLES.get(item)
    if not spec:
        return False, "item_non_valido"
    if not spend_mevacoins(user_id, spec["cost"], f"buy:{item}"):
        return False, "saldo_insufficiente"
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user_consumables (user_id, item, quantity) VALUES (%s, %s, 1) "
            "ON CONFLICT (user_id, item) DO UPDATE SET "
            "quantity = user_consumables.quantity + 1, updated_at = CURRENT_TIMESTAMP",
            (user_id, item),
        )
        conn.commit()
        return True, "ok"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        put_conn(conn)


def get_inventory(user_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT item, quantity FROM user_consumables WHERE user_id=%s", (user_id,))
        return {r["item"]: r["quantity"] for r in cur.fetchall()}
    finally:
        put_conn(conn)


def use_consumable(user_id, item):
    inv = get_inventory(user_id)
    if inv.get(item, 0) <= 0:
        return False, "non_disponibile"
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE user_consumables SET quantity = quantity - 1, updated_at = CURRENT_TIMESTAMP "
            "WHERE user_id=%s AND item=%s AND quantity > 0",
            (user_id, item),
        )
        conn.commit()
        return True, "ok"
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        put_conn(conn)


def get_level(total_earned):
    lvl = (total_earned // LEVEL_STEP) + 1
    into = total_earned % LEVEL_STEP
    return {
        "level": lvl,
        "into_level": into,
        "needed": LEVEL_STEP,
        "progress": into / LEVEL_STEP,
    }


def get_shop_payload(user_id):
    from storage import get_user_unlocks
    balance = get_mevacoins_balance(user_id)
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT total_earned FROM mevacoins WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        total_earned = row["total_earned"] if row else 0
    finally:
        put_conn(conn)

    unlocks = get_user_unlocks(user_id)
    unlocked_features = {u["content_id"] for u in unlocks if u["content_type"] == "feature"}

    features = [
        {
            "id": k,
            "name": v["name"],
            "cost": v["mvc_cost"],
            "unlocked": k in unlocked_features,
        }
        for k, v in FEATURES.items()
    ]

    inventory = get_inventory(user_id)
    consumables = [
        {
            "id": k,
            "name": v["name"],
            "cost": v["cost"],
            "desc": v["desc"],
            "owned": inventory.get(k, 0),
        }
        for k, v in CONSUMABLES.items()
    ]

    return {
        "balance": balance,
        "total_earned": total_earned,
        "level": get_level(total_earned),
        "features": features,
        "consumables": consumables,
    }
