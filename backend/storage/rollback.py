"""Rollback degli acquisti MVC.

Se un utente sbaglia un acquisto (sblocco feature/categoria o pacchetto
consumabili) puo' annullarlo: l'effetto viene rimosso e i MVC spesi tornano
disponibili, tranne una tariffa fissa di rollback (ROLLBACK_FEE) che resta
trattenuta come penalita'.
"""

from db import get_conn, put_conn
from storage.mevacoins import adjust_balance
from storage.store import CONSUMABLES, get_inventory
from chat_engine import FEATURES
from characters import get_categories

# Tariffa fissa (in MVC) per effettuare un rollback. "Un buon numero":
# sufficiente a scoraggiare abusi ma inferiore al costo medio di un acquisto.
ROLLBACK_FEE = 20


def _category_name(cat_id):
    try:
        for c in get_categories():
            if c.get("id") == cat_id:
                return c.get("name", cat_id)
    except Exception:
        pass
    return cat_id


def get_purchases(user_id):
    """Restituisce la lista degli acquisti rollbackabili dell'utente."""
    conn = get_conn()
    items = []
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT content_type, content_id, spent_amount, unlocked_at "
            "FROM content_unlocks WHERE user_id=%s ORDER BY unlocked_at DESC",
            (user_id,),
        )
        for r in cur.fetchall():
            ct = r["content_type"]
            cid = r["content_id"]
            cost = r["spent_amount"]
            name = cid
            if ct == "feature":
                name = FEATURES.get(cid, {}).get("name", cid)
            elif ct == "category":
                name = _category_name(cid)
            items.append({
                "purchase_id": f"{ct}:{cid}",
                "type": ct,
                "name": name,
                "cost": cost,
                "created_at": str(r["unlocked_at"]) if r["unlocked_at"] else None,
                "rollback_fee": ROLLBACK_FEE,
            })

        inv = get_inventory(user_id)
        for item, qty in inv.items():
            if qty > 0 and item in CONSUMABLES:
                unit = CONSUMABLES[item]["cost"]
                items.append({
                    "purchase_id": f"consumable:{item}",
                    "type": "consumable",
                    "name": CONSUMABLES[item]["name"],
                    "cost": unit * qty,
                    "unit": unit,
                    "quantity": qty,
                    "created_at": None,
                    "rollback_fee": ROLLBACK_FEE,
                })
    finally:
        put_conn(conn)
    return items


def rollback_purchase(user_id, purchase_id):
    """Annulla un acquisto. Ritorna (ok, payload, msg).

    - trattiene ROLLBACK_FEE (deve esserci saldo sufficiente)
    - riaccredita il resto (costo - fee) sul bilancio
    - rimuove l'effetto (unlock o consumabile posseduto)
    """
    fee = ROLLBACK_FEE

    conn = get_conn()
    try:
        cur = conn.cursor()

        if purchase_id.startswith("consumable:"):
            item = purchase_id.split(":", 1)[1]
            inv = get_inventory(user_id)
            qty = inv.get(item, 0)
            if qty <= 0 or item not in CONSUMABLES:
                return False, None, "acquisto_non_trovato"
            cost = CONSUMABLES[item]["cost"] * qty
            cur.execute(
                "DELETE FROM user_consumables WHERE user_id=%s AND item=%s",
                (user_id, item),
            )
        else:
            if ":" not in purchase_id:
                return False, None, "acquisto_non_valido"
            ct, cid = purchase_id.split(":", 1)
            cur.execute(
                "SELECT spent_amount FROM content_unlocks "
                "WHERE user_id=%s AND content_type=%s AND content_id=%s",
                (user_id, ct, cid),
            )
            row = cur.fetchone()
            if not row:
                return False, None, "acquisto_non_trovato"
            cost = row["spent_amount"]
            cur.execute(
                "DELETE FROM content_unlocks "
                "WHERE user_id=%s AND content_type=%s AND content_id=%s",
                (user_id, ct, cid),
            )

        # La tariffa di rollback viene sempre trattenuta.
        new_balance = adjust_balance(user_id, -fee, "rollback_fee")
        if new_balance is False:
            conn.rollback()
            return False, None, "saldo_insufficiente_rollback"

        refund = cost - fee if cost > fee else 0
        if refund > 0:
            adjust_balance(user_id, refund, f"rollback_refund:{purchase_id}")

        conn.commit()
        cur.execute("SELECT balance FROM mevacoins WHERE user_id=%s", (user_id,))
        row = cur.fetchone()
        final_balance = row["balance"] if row else new_balance
        return True, {
            "balance": final_balance,
            "cost": cost,
            "fee": fee,
            "refund": refund,
        }, "ok"
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        conn.rollback()
        return False, None, "Rollback non riuscito"
    finally:
        put_conn(conn)
