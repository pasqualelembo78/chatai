# -*- coding: utf-8 -*-
"""Sostituisce i nomi reali/protetti con nomi italiani inventati.

4982 personaggi su 5072 arrivano da HuggingFace: sono personaggi di videogiochi,
cartoni, fumetti, serie TV, sportivi, storici (Axl Rose, Arale Norimaki, Thomas
Jefferson...). Qui ognuno riceve un nome e un cognome inventati, coerenti col
genere, e una identità riscritta senza titoli di opere protette.

Il nome vecchio si conserva in `old_name` e viene usato per sostituirlo anche
nei testi che lo citano.

Uso:
    python3 rename_characters.py [--dry-run] [--tutte]
"""

import glob
import hashlib
import json
import os
import random
import re
import sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

NOMI_F = [
    "Adele", "Agnese", "Alba", "Alessia", "Alma", "Amelia", "Arianna", "Aurora", "Beatrice",
    "Berenice", "Bianca", "Camilla", "Carola", "Celeste", "Chiara", "Clarissa", "Corinna",
    "Dalia", "Delia", "Dora", "Elena", "Eleonora", "Elisa", "Emma", "Erika", "Ester", "Eva",
    "Fabiana", "Federica", "Fiamma", "Filomena", "Flavia", "Gaia", "Gemma", "Gilda", "Gioia",
    "Giulia", "Greta", "Ida", "Ilaria", "Irene", "Iris", "Isotta", "Lara", "Laura", "Leda",
    "Leila", "Lia", "Livia", "Lorena", "Luana", "Lucia", "Maddalena", "Mara", "Marilena",
    "Marta", "Melania", "Michela", "Mila", "Mirella", "Nadia", "Nerina", "Noemi", "Nora",
    "Olga", "Ortensia", "Paola", "Perla", "Raffaella", "Renata", "Rita", "Rosa", "Rosalba",
    "Sabrina", "Sara", "Selene", "Serena", "Silvia", "Siria", "Sonia", "Stella", "Susanna",
    "Teresa", "Tiziana", "Valeria", "Vera", "Veronica", "Viola", "Vittoria", "Zelda", "Zoe",
]

NOMI_M = [
    "Achille", "Adamo", "Alberto", "Alessio", "Alfio", "Amedeo", "Andrea", "Angelo", "Anselmo",
    "Antonio", "Araldo", "Arduino", "Arialdo", "Armando", "Arturo", "Augusto", "Aurelio",
    "Baldassarre", "Bartolo", "Basilio", "Beniamino", "Bernardo", "Bruno", "Calogero", "Carmelo",
    "Cesare", "Ciro", "Corrado", "Costanzo", "Daniele", "Dario", "Dino", "Domenico", "Dorian",
    "Edmondo", "Edoardo", "Elias", "Elio", "Emanuele", "Emilio", "Ennio", "Enrico", "Ermanno",
    "Fabio", "Fabrizio", "Federico", "Filippo", "Fiorenzo", "Flavio", "Fulvio", "Gabriele",
    "Gaetano", "Gennaro", "Gerardo", "Giacomo", "Gianni", "Gilberto", "Gino", "Giorgio",
    "Giovanni", "Giulio", "Goffredo", "Graziadio", "Guido", "Gustavo", "Iacopo", "Ignazio",
    "Ivo", "Lamberto", "Lauro", "Leandro", "Lino", "Lorenzo", "Luca", "Luciano", "Manfredi",
    "Marcello", "Mariano", "Mario", "Martino", "Massimo", "Matteo", "Mauro", "Michele",
    "Mirko", "Nando", "Narciso", "Nereo", "Nevio", "Nicola", "Norberto", "Orazio", "Orlando",
    "Osvaldo", "Ottavio", "Pierluigi", "Pietro", "Primo", "Quirino", "Raffaele", "Remo",
    "Renzo", "Riccardo", "Roberto", "Rocco", "Rodolfo", "Ruggero", "Salvo", "Samuele", "Sandro",
    "Saverio", "Sebastiano", "Sergio", "Silvio", "Simone", "Stefano", "Tancredi", "Teodoro",
    "Tiziano", "Tommaso", "Ubaldo", "Ugo", "Valerio", "Vittorio", "Walter", "Zeno",
]

NOMI_N = [
    "Adri", "Alen", "Ari", "Aster", "Atena", "Bene", "Cale", "Dani", "Dorian", "Eli", "Elio",
    "Ely", "Enea", "Etere", "Falco", "Fiamma", "Gio", "Giule", "Ilar", "Indra", "Iris", "Kim",
    "Lauro", "Lian", "Loren", "Luan", "Madi", "Marlo", "Michele", "Nadir", "Nerio", "Nino",
    "Noa", "Ondina", "Ori", "Reno", "Riva", "Rober", "Rudi", "Sami", "Sasha", "Sole", "Tara",
    "Teti", "Toni", "Ugo", "Vale", "Vani", "Vela", "Zeno",
]

RADICI = [
    "Albar", "Alber", "Alt", "Amad", "Arqu", "Band", "Barb", "Bast", "Belf", "Bern", "Bianc",
    "Bord", "Bram", "Brun", "Calc", "Cald", "Camp", "Cant", "Cap", "Carb", "Carl", "Carr",
    "Cast", "Cer", "Chiar", "Cim", "Cipr", "Clar", "Col", "Cont", "Corb", "Cord", "Corn",
    "Cort", "Crist", "Dalm", "Dant", "Dard", "Del", "Dent", "Diam", "Dolf", "Don", "Dorig",
    "Fabb", "Falc", "Fant", "Farin", "Ferr", "Fiamm", "Fior", "Foll", "Font", "Forl", "Franc",
    "Fum", "Gall", "Gar", "Gatt", "Ghir", "Gianc", "Giorg", "Giul", "Gor", "Gran", "Grass",
    "Grav", "Gris", "Guer", "Guid", "Lamb", "Lanc", "Lant", "Laur", "Len", "Lent", "Leon",
    "Lomb", "Lorenz", "Lucc", "Lun", "Macc", "Magr", "Mald", "Malv", "Manfr", "Mant", "Marc",
    "Marr", "Mazz", "Mel", "Merl", "Montal", "Mor", "Mosc", "Nann", "Nard", "Nast", "Ner",
    "Nicol", "Nov", "Ort", "Osti", "Pagl", "Pal", "Pand", "Panz", "Paol", "Pasq", "Pell",
    "Perr", "Pes", "Petr", "Pian", "Picc", "Pier", "Pini", "Pis", "Pogg", "Pol", "Port",
    "Priv", "Quar", "Rag", "Ramb", "Rast", "Ric", "Rinal", "Rizz", "Roc", "Rom", "Ros", "Ross",
    "Rov", "Ruff", "Sabb", "Salv", "Samp", "Sant", "Sard", "Sart", "Sav", "Scal", "Scar",
    "Ser", "Serr", "Silv", "Sor", "Spad", "Spall", "Sper", "Stab", "Stell", "Stort", "Tad",
    "Tagl", "Talam", "Tamb", "Tard", "Tass", "Tell", "Tess", "Tomb", "Torr", "Tosc", "Trav",
    "Tre", "Trec", "Ubal", "Vald", "Vall", "Van", "Vanz", "Vasc", "Vent", "Ver", "Verg",
    "Vern", "Vesc", "Vett", "Vian", "Vig", "Vill", "Vin", "Viol", "Vir", "Vis", "Vitt",
    "Zacc", "Zamp", "Zan", "Zav", "Zerb", "Zoll", "Zor",
]

DESINENZE = ["ali", "ani", "ardi", "elli", "etti", "ini", "oni", "ucci", "azzi", "aro",
             "iero", "oni", "eschi", "otti", "andi", "enti", "oldi", "urri", "agni", "occhi"]


def genera_nome(ident, genere, occupati):
    """Nome + cognome deterministici dall'id, coerenti col genere, unici."""
    for tentativo in range(60):
        seme = int(hashlib.md5(f"{ident}:{tentativo}".encode()).hexdigest()[:8], 16)
        rnd = random.Random(seme)
        if genere == "femminile":
            nome = rnd.choice(NOMI_F)
        elif genere == "maschile":
            nome = rnd.choice(NOMI_M)
        else:
            nome = rnd.choice(NOMI_N)
        cognome = rnd.choice(RADICI) + rnd.choice(DESINENZE)
        completo = f"{nome} {cognome}"
        if completo.lower() not in occupati:
            occupati.add(completo.lower())
            return nome, cognome
    return None, None


def essenza_nuova(c, nome, cognome):
    """Identità italiana senza titoli di opere protette."""
    eta = c.get("age")
    mestiere = (c.get("job") or "").strip()
    ruolo = (c.get("role") or "personaggio").strip()
    pezzi = [f"{nome} {cognome}"]
    if eta:
        pezzi[0] += f", {eta} anni"
    if mestiere:
        pezzi[0] += f", di mestiere {mestiere[:1].lower() + mestiere[1:]}"
    elif ruolo:
        pezzi[0] += f", {ruolo}"
    frase = pezzi[0] + "."
    person = re.sub(r"\s+", " ", str(c.get("personality") or "")).strip()
    if person:
        frase += " " + person[:220]
    return frase


def rinomina(c, occupati):
    vecchio = c.get("name") or ""
    genere = (c.get("gender_display") or "").lower()
    nome, cognome = genera_nome(c["id"], genere, occupati)
    if not nome:
        return False
    c["old_name"] = vecchio
    c["name"] = nome
    c["full_name"] = f"{nome} {cognome}"
    c["surname"] = cognome
    c["essence"] = essenza_nuova(c, nome, cognome)
    desc = c.get("description") or ""
    c["description"] = desc.replace(vecchio, nome, 1) if vecchio and vecchio in desc else re.sub(r"^[^—,]+", nome, desc, count=1)
    c["personality"] = re.sub(r"^" + re.escape(vecchio), nome, c.get("personality") or "", count=1)
    c["renamed"] = 1
    return True


def main():
    dry = "--dry-run" in sys.argv
    occupati = set()
    totale = 0
    if "--tutte" in sys.argv:
        files = [p for p in sorted(glob.glob(os.path.join(DATA, "*.json"))) if not p.endswith("categories.json")]
    else:
        files = [os.path.join(DATA, "amanti-segreti.json")]

    for path in files:
        righe = json.load(open(path, encoding="utf-8"))
        for c in righe:
            if c.get("renamed") and "--forza" not in sys.argv:
                occupati.add((c.get("full_name") or "").lower())
                continue
            if rinomina(c, occupati):
                totale += 1
        if not dry:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(righe, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp, path)
        print(f"{os.path.basename(path)}: rinominati {len(righe)}")

    print(f"{'DRY RUN' if dry else 'FATTO'}: {totale} personaggi rinominati, {len(occupati)} nomi unici")


if __name__ == "__main__":
    main()
