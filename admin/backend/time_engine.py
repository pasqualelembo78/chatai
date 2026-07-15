"""
Time Engine - Sistema temporale per ChatAI.

Gestisce:
- Epoch fissa dell'universo (1 Gennaio 2025)
- Calcolo età dinamico dei personaggi
- Scaling invecchiamento per diverse specie
- compleanni e crescita nel tempo
"""

from datetime import datetime, date, timedelta
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)

# ── Epoch dell'universo ──────────────────────────────────────────────────────
# Data fissa in cui l'universo di ChatAI "inizia"
# Tutti i personaggi sono stati creati con questa data come riferimento
UNIVERSE_EPOCH = date(2025, 1, 1)

# ── Specie e scaling invecchiamento ──────────────────────────────────────────
# Ogni specie ha un factor di scaling: 1.0 = invecchiamento umano normale
# < 1.0 = invecchiamento più lento, > 1.0 = più veloce
SPECIES_SCALING = {
    # Umani
    "umano": 1.0,
    "umana": 1.0,
    
    # Fantasy
    "elfo": 0.1,           # 1 anno elfo = ~10 anni umani
    "elfa": 0.1,
    "nano": 0.15,
    "gobbo": 0.2,
    "halfling": 0.25,
    "orco": 0.3,
    
    # Maghi e creature antiche
    "mago": 0.05,          # 1 anno mago = ~20 anni umani
    "maga": 0.05,
    "stregone": 0.05,
    "strega": 0.05,
    "druido": 0.08,
    "druida": 0.08,
    
    # Divinità ed entità
    "divinità": 0.001,     # Praticamente immortali
    "entità": 0.001,
    "demone": 0.002,
    "demonesse": 0.002,
    "angelo": 0.001,
    "angela": 0.001,
    "vampiro": 0.02,
    "lycan": 0.05,
    
    # Creature speciali
    "dragone": 0.005,
    "fata": 0.03,
    "fata": 0.03,
    "spirito": 0.001,
    "non-morto": 0.01,
    
    # Sci-fi
    "cyborg": 0.8,
    "androide": 0.9,
    "alieno": 0.3,
    "aliena": 0.3,
    
    # Zombie e simili
    "zombie": 0.0,        # Non invecchiano più
    "scheletro": 0.0,
}

# ── Enum orientamento sessuale ──────────────────────────────────────────────
SEXUAL_ORIENTATIONS = {
    "etero": "eterosessuale",
    "gay": "omosessuale",
    "lesbica": "omosessuale",
    "bi": "bisessuale",
    "pan": "pansessuale",
    "ace": "asessuale",
    "aro": "aromantico",
    "queer": "queer",
    " fluid": "fluido",
}

# ── Enum gender ──────────────────────────────────────────────────────────────
GENDERS = {
    "M": "maschile",
    "F": "femminile",
    "NB": "non binario",
    "genderfluid": "genderfluid",
    "agender": "agender",
}


class TimeEngine:
    """Motore temporale principale."""
    
    def __init__(self, epoch: date = UNIVERSE_EPOCH):
        self.epoch = epoch
        self.today = date.today()
    
    def update_today(self):
        """Aggiorna la data corrente (da chiamare ogni giorno)."""
        self.today = date.today()
    
    def days_since_epoch(self) -> int:
        """Giorni trascorsi dall'epoch."""
        return (self.today - self.epoch).days
    
    def years_since_epoch(self) -> float:
        """Anni trascorsi dall'epoch (con decimali)."""
        return self.days_since_epoch() / 365.25
    
    def calculate_age(self, birth_date, species: str = "umano") -> float:
        """
        Calcola l'età attuale del personaggio basandosi su:
        - Data di nascita (date o dict con 'year', 'month', 'day')
        - Specie (per scaling)
        - Data corrente
        """
        if not birth_date:
            return 0.0
        
        # Handle dict format (for ancient dates)
        if isinstance(birth_date, dict):
            birth_year = birth_date.get("year", 2000)
            birth_month = birth_date.get("month", 6)
            birth_day = birth_date.get("day", 15)
        else:
            birth_year = birth_date.year
            birth_month = birth_date.month
            birth_day = birth_date.day
        
        # For very ancient characters, calculate years directly
        real_years = self.today.year - birth_year
        # Adjust for month/day
        if (self.today.month, self.today.day) < (birth_month, birth_day):
            real_years -= 1
        
        # Applica scaling della specie
        scale = SPECIES_SCALING.get(species.lower(), 1.0)
        
        # Età percepita (come il personaggio la vive)
        perceived_age = real_years * scale
        
        return round(perceived_age, 2)
    
    def calculate_age_at_epoch(self, birth_date, species: str = "umano") -> float:
        """Calcola l'età del personaggio all'epoch dell'universo."""
        if not birth_date:
            return 0.0
        
        if isinstance(birth_date, dict):
            birth_year = birth_date.get("year", 2000)
            birth_month = birth_date.get("month", 6)
            birth_day = birth_date.get("day", 15)
        else:
            birth_year = birth_date.year
            birth_month = birth_date.month
            birth_day = birth_date.day
        
        real_years_at_epoch = self.epoch.year - birth_year
        if (self.epoch.month, self.epoch.day) < (birth_month, birth_day):
            real_years_at_epoch -= 1
        
        scale = SPECIES_SCALING.get(species.lower(), 1.0)
        return round(real_years_at_epoch * scale, 2)
    
    def get_birthday_info(self, birth_date) -> Dict:
        """
        Restituisce informazioni sul prossimo compleanno.
        """
        if not birth_date:
            return {"has_birthday": False}
        
        if isinstance(birth_date, dict):
            b_month = birth_date.get("month", 6)
            b_day = birth_date.get("day", 15)
        else:
            b_month = birth_date.month
            b_day = birth_date.day
        
        today = self.today
        try:
            this_year_birthday = date(today.year, b_month, b_day)
        except ValueError:
            return {"has_birthday": False}
        
        if this_year_birthday < today:
            next_birthday = date(today.year + 1, b_month, b_day)
        else:
            next_birthday = this_year_birthday
        
        days_until = (next_birthday - today).days
        
        if isinstance(birth_date, dict):
            birth_year = birth_date.get("year", 2000)
        else:
            birth_year = birth_date.year
        
        age_at_birthday = next_birthday.year - birth_year
        
        return {
            "has_birthday": True,
            "birth_month": b_month,
            "birth_day": b_day,
            "next_birthday": next_birthday.isoformat(),
            "days_until_birthday": days_until,
            "age_at_next_birthday": age_at_birthday,
            "is_birthday_today": days_until == 0,
        }
    
    def format_age_for_prompt(self, age: float, species: str = "umano") -> str:
        """Formatta l'età per il system prompt."""
        if species.lower() in ("divinità", "entità", "spirito"):
            return f"sei antico quanto il tempo stesso ({int(age)} anni)"
        elif species.lower() in ("elfo", "elfa", "mago", "maga"):
            if age > 1000:
                return f"sei millenario ({int(age)} anni)"
            elif age > 100:
                return f"sei molto longevo ({int(age)} anni)"
            else:
                return f"hai {int(age)} anni"
        else:
            # Umani e creature normali
            years = int(age)
            months = int((age - years) * 12)
            if months > 0:
                return f"hai {years} anni e {months} mesi"
            else:
                return f"hai {years} anni"
    
    def get_character_time_state(self, character: Dict) -> Dict:
        """
        Restituisce lo stato temporale completo di un personaggio.
        """
        birth_date_raw = character.get("birth_date")
        species = character.get("species", "umano")
        
        if not birth_date_raw:
            return {
                "has_birth_date": False,
                "static_age": character.get("age", 0),
                "species": species,
                "can_age": False,
            }
        
        # Parse birth_date - can be ISO string or dict
        if isinstance(birth_date_raw, dict):
            birth_date = birth_date_raw  # Already a dict
        elif isinstance(birth_date_raw, str):
            try:
                # Try ISO format first
                parts = birth_date_raw.split("-")
                year = int(parts[0])
                month = int(parts[1]) if len(parts) > 1 else 6
                day = int(parts[2]) if len(parts) > 2 else 15
                if year < 1:
                    birth_date = {"year": year, "month": month, "day": day}
                else:
                    birth_date = date(year, month, day)
            except (ValueError, IndexError):
                birth_date = None
        else:
            birth_date = None
        
        if not birth_date:
            return {
                "has_birth_date": False,
                "static_age": character.get("age", 0),
                "species": species,
                "can_age": False,
            }
        
        current_age = self.calculate_age(birth_date, species)
        birthday_info = self.get_birthday_info(birth_date)
        age_at_epoch = self.calculate_age_at_epoch(birth_date, species)
        
        scale = SPECIES_SCALING.get(species.lower(), 1.0)
        can_age = scale > 0
        
        # Birth month/day for birthday tracking
        if isinstance(birth_date, dict):
            b_month = birth_date.get("month", 6)
            b_day = birth_date.get("day", 15)
        else:
            b_month = birth_date.month
            b_day = birth_date.day
        
        return {
            "has_birth_date": True,
            "birth_date": birth_date_raw,
            "birth_month": b_month,
            "birth_day": b_day,
            "species": species,
            "current_age": current_age,
            "age_at_epoch": age_at_epoch,
            "age_display": self.format_age_for_prompt(current_age, species),
            "birthday": birthday_info,
            "can_age": can_age,
            "aging_scale": scale,
        }


def get_time_engine() -> TimeEngine:
    """Factory function per ottenere un'istanza del TimeEngine."""
    return TimeEngine()


def calculate_character_age_static(character: Dict) -> int:
    """
    Calcola l'età statica (compatibilità con codice esistente).
    Usa l'età del personaggio se non ha birth_date.
    """
    engine = TimeEngine()
    state = engine.get_character_time_state(character)
    
    if state["has_birth_date"]:
        return int(state["current_age"])
    return character.get("age", 0)


def sync_character_age(character: Dict) -> Dict:
    """
    Sincronizza il campo 'age' del personaggio con l'età calcolata.
    Aggiorna anche il system_prompt se necessario.
    """
    engine = TimeEngine()
    state = engine.get_character_time_state(character)
    
    if state["has_birth_date"]:
        character["age"] = int(state["current_age"])
        character["_age_display"] = state["age_display"]
        character["_birthday_info"] = state["birthday"]
    
    return character
