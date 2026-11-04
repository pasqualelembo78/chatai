#!/usr/bin/env python3
"""Verifica che le correzioni linguistiche siano davvero attive.

Ogni caso è una frase sbagliata presa dalla realtà (trascrizioni dei test) con:
  - quello che DEVE comparire dopo la correzione
  - quello che NON deve più comparire
Se un caso migliora il testo ma non rispetta le attese, conta come fallito: qui non
si guarda "se sembra meglio", si guarda se la regola scatta.

Uso:
    python3 verifica_correzioni.py           # tutti i casi
    python3 verifica_correzioni.py --dettagli # mostra anche i testi corretti

Esce con codice 1 se c'è almeno un fallimento: si può usare come controllo prima
di un commit o dopo ogni modifica al dizionario.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))
from language import correggi  # noqa: E402

# (frase sbagliata, deve contenere, non deve contenere, perché)
CASI = [
    ("Veni, ti aiuterò a rilassarti", "Vieni", "Veni", "refuso"),
    ("ho leggito per un po'", "ho letto", "leggito", "participio sbagliato"),
    ("metti le mani su mine", "sulle mie", "su mine", "possessivo"),
    ("mi sei apparito con un taglio", "apparso", "apparito", "participio"),
    ("Tiro fuori uno strappacapelli", "un cerotto", "strappacapelli", "oggetto inventato"),
    ("ti lego al libro del letto", "bordo del letto", "libro del letto", "libro/bordo"),
    ("Tiro le lenze di cuoio", "cinghie", "lenze", "lenza è da pesca"),
    ("i nostri bocchi non sono distanti", "bocche", "bocchi", "parola inesistente"),
    ("le dita attorno alle mie ciate", "chiappe", "ciate", "parola inesistente"),
    ("Prendo la termoadegliata", "il termometro", "termoadegliata", "parola inventata"),
    ("C'è una bella bar quartiere", "un bel bar", "una bella bar", "accordo"),
    ("una trattoria attorno l'angolo", "dietro l'angolo", "attorno l'angolo", "calco"),
    ("mi fa sensibile", "intenerisce", "fa sensibile", "calco"),
    ("può far sentire a suo agio", "mettere a suo agio", "far sentire a suo agio", "collocazione"),
    ("mi siedo sulla tua destra", "alla tua destra", "sulla tua destra", "preposizione"),
    ("abbiamo inalato il tuo profumo", "annusato", "inalato", "inalare/annusare"),
    ("Signor.? come stai", "signore,", "Signor.?", "puntatura"),
    ("ti bacchio forte", "ti bacio", "bacchio", "verbo"),
    ("Sono legato con un coro", "una corda", "un coro", "coro/corda"),
    ("mi tocca il culo!", "mi tocco", "mi tocca il culo", "transitivo"),
    ("ti frego la mano", "ti sfioro", "ti frego", "verbo"),
    ("ti bisogno", "ti bacio", "ti bisogno", "sostantivo usato come verbo"),
    ("ti le poso sulle tette", "te le poso", "ti le poso", "pronome doppio"),
    # regole generali, non singole parole
    ("*ti guarda con affetto* e sorride", "Ti guarda", "*", "asterischi"),
    ("il il cazzo", "il cazzo", "il il", "parola doppia"),
    ("Ti incollo addosso addosso", "Ti incollo addosso", "addosso addosso", "avverbio ripetuto"),
    ("la tua fronte, la tua fronte che si abbassa", "la tua fronte che si abbassa",
     "la tua fronte, la tua fronte", "clausola ripetuta"),
    ("Ecco l'ora: 22.15. Poi", "22:15", "22.15", "orario con la virgola"),
    ("Ti chiami Paolo. .", "Paolo.", ". .", "punteggiatura orfana"),
    ("guardami in faccia , ti sfioro", "faccia,", "faccia ,", "spazio prima della virgola"),
    ("una atmosfera intima", "un'atmosfera", "una atmosfera", "apostrofo"),
    ("voglio che mi segui", "mi segua", "mi segui", "congiuntivo"),
    ("Mi dispiace, ma non posso continuare questa conversazione.", "", "conversazione",
     "frase fatta cancellata"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dettagli", action="store_true", help="mostra anche il testo corretto")
    args = ap.parse_args()

    falliti = 0
    for sbagliato, atteso, vietato, perche in CASI:
        uscita = correggi(sbagliato) or ""
        ok_atteso = atteso.lower() in uscita.lower() if atteso else True
        ok_vietato = vietato.lower() not in uscita.lower() if vietato else True
        esito = "OK  " if (ok_atteso and ok_vietato) else "FAIL"
        if esito == "FAIL":
            falliti += 1
        print(f"{esito} [{perche}]")
        print(f"     prima:  {sbagliato}")
        if args.dettagli or esito == "FAIL":
            print(f"     dopo:   {uscita!r}")
            if not ok_atteso:
                print(f"     manca:  {atteso!r}")
            if not ok_vietato:
                print(f"     resta:  {vietato!r}")

    print(f"\n{len(CASI) - falliti}/{len(CASI)} casi corretti.")
    if falliti:
        print("ATTENZIONE: qualcuno non scatta, il dizionario o le regole vanno sistemati.")
        sys.exit(1)


if __name__ == "__main__":
    main()
