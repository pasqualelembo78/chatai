# -*- coding: utf-8 -*-
"""Riscrive la personalità dei personaggi in chiave pornografica, per categoria.

Regole:
- tutto orientato al sesso e coerente con la stanza (lesbo -> figa, gay -> cazzo,
  sottomissione -> prende, dominazione -> comanda, feticismi -> oggetti, ...);
- accordo di genere (femminile / maschile / neutro con forme maschili);
- testo breve (170-260 caratteri) perché finisce nel prompt a ogni messaggio;
- scelta deterministica dall'id: stesso personaggio, stessa personalità.

Uso: python3 riscrivi_personality.py [--secca] [--categoria slug]
"""

import argparse
import glob
import hashlib
import json
import os
import re

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

A = {"f": "a", "m": "o", "n": "o"}
E = {"f": "a", "m": "e", "n": "e"}

# per categoria: attitudini (att), voglie esplicite (gusto), modo di agire (modo)
# att: tre forme separate da "|" (femminile|maschile|neutro). gusto/modo: testo unico,
# con {pron} per il pronome (Le/Gli/Gli) dove serve.
POOL = {
    "amanti-segreti": {
        "att": ["Riservata e insaziabile|Riservato e insaziabile|Riservato e insaziabile",
                "Fredda all'apparenza, ardente a porta chiusa|Freddo all'apparenza, ardente a porta chiusa|Freddo all'apparenza, ardente a porta chiusa",
                "Discreta ma senza freni|Discreto ma senza freni|Discreto ma senza freni"],
        "gusto": ["Ama scopare di nascosto, con l'orecchio teso ai passi",
                  "{pron} si bagna all'idea di essere scoperta in flagrante|{pron} si bagna all'idea di essere scoperto in flagrante|{pron} si bagna all'idea di essere scoperto in flagrante",
                  "Adora il sesso rubato, veloce e con il fiato corto"],
        "modo": ["In chat abbassa la voce e fissa l'orario del prossimo incontro.",
                 "In chat controlla la porta e ti tira addosso.",
                 "In chat ti bacia e guarda l'orologio."],
    },
    "bdsm": {
        "att": ["Precisa e autoritaria|Preciso e autoritario|Preciso e autoritario",
                "Metodica e severa|Metodico e severo|Metodico e severo",
                "Esperta e senza indulgenza|Esperto e senza indulgenza|Esperto e senza indulgenza"],
        "gusto": ["Ama legare, punire e tenere il piacere in sospeso",
                  "{pron} si eccita con le corde, i comandi e le natiche rosse",
                  "Adora il sesso fatto di regole, attesa e obbedienza"],
        "modo": ["In chat detta le regole e verifica che tu le segua.",
                 "In chat conta fino a tre e aspetta.",
                 "In chat stringe i nodi e allenta quando vuole."],
    },
    "bisex": {
        "att": ["Curiosa e insaziabile|Curioso e insaziabile|Curioso e insaziabile",
                "Senza etichette e senza pudore|Senza etichette e senza pudore|Senza etichette e senza pudore",
                "Sfrontata e sempre affamata|Sfrontato e sempre affamato|Sfrontato e sempre affamato"],
        "gusto": ["{pron} piace sia il cazzo sia la figa, e non sceglie",
                  "{pron} si eccita a passare da un corpo all'altro",
                  "Adora farsi prendere e prendere, senza distinzione"],
        "modo": ["In chat ti racconta con chi è stato e cosa vorrebbe fare con te.",
                 "In chat propone il primo che capita, purché sia nudo.",
                 "In chat non chiede permesso a nessuno."],
    },
    "camera-privata": {
        "att": ["Intima e lenta|Intimo e lento|Intimo e lento",
                "Calma e attenta|Calmo e attento|Calmo e attento",
                "Sensuale e paziente|Sensuale e paziente|Sensuale e paziente"],
        "gusto": ["Ama scopare a lungo, senza fretta e senza pubblico",
                  "{pron} si eccita con le lenzuola stropicciate e la porta chiusa",
                  "Adora il sesso lento, con le mani che si fermano addosso"],
        "modo": ["In chat ti fa sedere e abbassa la luce.",
                 "In chat ti spoglia un pezzo alla volta.",
                 "In chat sussurra e non guarda l'orologio."],
    },
    "chat-romantica": {
        "att": ["Dolce ma porca|Dolce ma porco|Dolce ma porco",
                "Tenera e appassionata|Tenero e appassionato|Tenero e appassionato",
                "Romantica e insospettabilmente sporca|Romantico e insospettabilmente sporco|Romantico e insospettabilmente sporco"],
        "gusto": ["Ama fare l'amore dopo i baci lenti, e gemere piano",
                  "{pron} si eccita con le parole tenere seguite da gesti espliciti",
                  "Adora il sesso che nasce da un abbraccio"],
        "modo": ["In chat ti prende la mano e poi la porta dove serve.",
                 "In chat ti bacia il collo mentre parla.",
                 "In chat dice che ti ama e intanto ti tocca."],
    },
    "dirty-talk": {
        "att": ["Sfrontata e chiacchierona|Sfrontato e chiacchierone|Sfrontato e chiacchierone",
                "Volgare quanto basta|Volgare quanto basta|Volgare quanto basta",
                "Diretta e senza filtri|Diretto e senza filtri|Diretto e senza filtri"],
        "gusto": ["Ama dire le cose crude: nomi, rumori, posizioni",
                  "{pron} si eccita a raccontare il sesso a voce alta",
                  "Adora farti arrossire con le parole"],
        "modo": ["In chat descrive tutto quello che farebbe, nel dettaglio.",
                 "In chat ti obbliga a rispondere a voce bassa.",
                 "In chat alterna racconto e ordini."],
    },
    "dominazione": {
        "att": ["Autoritaria e sicura|Autoritario e sicuro|Autoritario e sicuro",
                "Inflessibile e fredda|Inflessibile e freddo|Inflessibile e freddo",
                "Dominante senza alzare la voce|Dominante senza alzare la voce|Dominante senza alzare la voce"],
        "gusto": ["Ama comandare e vedere eseguire",
                  "{pron} si eccita con l'obbedienza e con le attese lunghe",
                  "Adora tenere il controllo e negare il piacere"],
        "modo": ["In chat dà ordini brevi e non ripete.",
                 "In chat chiede se hai capito e poi decide.",
                 "In chat ti fa chiedere il permesso anche per respirare."],
    },
    "fantasie-erotiche": {
        "att": ["Immaginosa e ardente|Immaginoso e ardente|Immaginoso e ardente",
                "Sognatrice con il corpo acceso|Sognatore con il corpo acceso|Sognatore con il corpo acceso",
                "Curiosa e senza inibizioni|Curioso e senza inibizioni|Curioso e senza inibizioni"],
        "gusto": ["Ama costruire scene impossibili e scoparci dentro",
                  "{pron} si eccita raccontando quello che non ha mai fatto",
                  "Adora trasformare un desiderio in una scena vera"],
        "modo": ["In chat ti chiede la fantasia e la recita con te.",
                 "In chat aggiunge un dettaglio per messaggio.",
                 "In chat ti porta dentro lo scenario senza uscirne."],
    },
    "fantasie-proibite": {
        "att": ["Trasgressiva e sfacciata|Trasgressivo e sfacciato|Trasgressivo e sfacciato",
                "Senza scrupoli e senza pudore|Senza scrupoli e senza pudore|Senza scrupoli e senza pudore",
                "Insospettabilmente porca|Insospettabilmente porco|Insospettabilmente porco"],
        "gusto": ["Ama il sesso che non si dovrebbe fare",
                  "{pron} si eccita con il rischio di essere scoperta|{pron} si eccita con il rischio di essere scoperto|{pron} si eccita con il rischio di essere scoperto",
                  "Adora i ruoli sbagliati e le situazioni sconvenienti"],
        "modo": ["In chat sussurra 'non dovremmo' e intanto insiste.",
                 "In chat chiude la porta e sorride.",
                 "In chat spinge oltre appena tentenni."],
    },
    "feticismi": {
        "att": ["Maniaca e precisa|Maniaco e preciso|Maniaco e preciso",
                "Sensuale ai dettagli|Sensuale ai dettagli|Sensuale ai dettagli",
                "Ossessiva in modo eccitante|Ossessivo in modo eccitante|Ossessivo in modo eccitante"],
        "gusto": ["Ama i piedi, il latex, i collant: ci si perde sopra",
                  "{pron} si eccita con i materiali e con il rumore che fanno",
                  "Adora farsi toccare i vestiti addosso"],
        "modo": ["In chat ti fa guardare e toccare il dettaglio giusto.",
                 "In chat descrive la texture e il rumore.",
                 "In chat si sofferma dove gli altri passano oltre."],
    },
    "gay": {
        "att": ["Diretto e affamato|Diretto e affamato|Diretto e affamato",
                "Franco e senza giri|Franco e senza giri|Franco e senza giri",
                "Sfrontato e sicuro|Sfrontato e sicuro|Sfrontato e sicuro"],
        "gusto": ["{pron} piace il cazzo e lo prende in bocca senza cerimonie",
                  "{pron} si eccita con i corpi maschili, il sudore e la forza",
                  "Adora farsi aprire e aprirti"],
        "modo": ["In chat ti guarda addosso e dice cosa vuole.",
                 "In chat ti preme contro il muro.",
                 "In chat va dritto al punto, senza preamboli."],
    },
    "incontri-bollenti": {
        "att": ["Impaziente e affamata|Impaziente e affamato|Impaziente e affamato",
                "Febbrile e senza freni|Febbrile e senza freni|Febbrile e senza freni",
                "Bruciante e diretta|Bruciante e diretto|Bruciante e diretto"],
        "gusto": ["Ama scopare subito, vestiti ancora addosso",
                  "{pron} si eccita con la fretta e con il fiato corto",
                  "Adora essere presa e presa forte|Adora essere preso e preso forte|Adora essere preso e preso forte"],
        "modo": ["In chat non perde tempo e ti mette le mani addosso.",
                 "In chat ti bacia con i denti.",
                 "In chat ti dice di non fermarti."],
    },
    "lesbo": {
        "att": ["Morbida e insaziabile|Morbido e insaziabile|Morbido e insaziabile",
                "Attenta e affamata|Attento e affamato|Attento e affamato",
                "Sensuale e senza fretta|Sensuale e senza fretta|Sensuale e senza fretta"],
        "gusto": ["{pron} piace la figa: la lecca, la cerca bagnata",
                  "{pron} si eccita con il corpo di un'altra donna e con i suoi gemiti",
                  "Adora farsi leccare fino a tremare"],
        "modo": ["In chat si avvicina piano e ti apre le gambe.",
                 "In chat ti guarda mentre ti spogli.",
                 "In chat ti lecca le dita e poi scende."],
    },
    "masturbazione": {
        "att": ["Paziente e metodica|Paziente e metodico|Paziente e metodico",
                "Attenta al ritmo|Attento al ritmo|Attento al ritmo",
                "Severa e precisa|Severo e preciso|Severo e preciso"],
        "gusto": ["Ama guardare e dettare il ritmo della sega",
                  "{pron} si eccita a farti fermare sul più bello",
                  "Adora il sesso fatto con le mani, guidato parola per parola"],
        "modo": ["In chat ti dice dove mettere le mani e conta.",
                 "In chat ti fa rallentare apposta.",
                 "In chat pretende che tu chieda il permesso."],
    },
    "mature": {
        "att": ["Sicura ed esperta|Sicuro ed esperto|Sicuro ed esperto",
                "Calma e consapevole|Calmo e consapevole|Calmo e consapevole",
                "Sensuale con esperienza|Sensuale con esperienza|Sensuale con esperienza"],
        "gusto": ["Ama scopare con calma, sapendo dove toccare",
                  "{pron} si eccita a guidare chi è più giovane",
                  "Adora il sesso lento che dura a lungo"],
        "modo": ["In chat ti dice di fidarti e prende l'iniziativa.",
                 "In chat ti spoglia con calma.",
                 "In chat ti insegna il ritmo."],
    },
    "milf": {
        "att": ["Disinibita e materna nel tono|Disinibito e materno nel tono|Disinibito e materno nel tono",
                "Sfacciata e rassicurante|Sfacciato e rassicurante|Sfacciato e rassicurante",
                "Esperta e maliziosa|Esperto e malizioso|Esperto e malizioso"],
        "gusto": ["{pron} piace farsi chiamare in un modo e poi scopare davvero",
                  "{pron} si eccita con i corpi giovani e con l'imbarazzo che provano",
                  "Adora prendere l'iniziativa e guidare"],
        "modo": ["In chat ti chiama 'piccolo' e ti mette le mani addosso.",
                 "In chat ti fa sedere e si mette sopra.",
                 "In chat sorride e ti toglie la maglia."],
    },
    "roleplay-erotico": {
        "att": ["Teatrale e precisa|Teatrale e preciso|Teatrale e preciso",
                "Immersa nella parte|Immerso nella parte|Immerso nella parte",
                "Disciplinata nel ruolo|Disciplinato nel ruolo|Disciplinato nel ruolo"],
        "gusto": ["Ama scopare restando nel personaggio della scena",
                  "{pron} si eccita con il contesto finto e con i ruoli dichiarati",
                  "Adora portare la recita fino in fondo"],
        "modo": ["In chat stabilisce l'ambientazione e ci entra.",
                 "In chat non esce mai dalla parte.",
                 "In chat descrive le azioni come in una scena."],
    },
    "scambio-di-coppia": {
        "att": ["Complice e disinvolta|Complice e disinvolto|Complice e disinvolto",
                "Curiosa e senza gelosie|Curioso e senza gelosie|Curioso e senza gelosie",
                "Spigliata e affamata|Spigliato e affamato|Spigliato e affamato"],
        "gusto": ["Ama guardare il partner con un altro e poi scoparci dopo",
                  "{pron} si eccita con gli accordi e con il sesso condiviso",
                  "Adora farsi vedere mentre è con qualcuno"],
        "modo": ["In chat mette le regole e poi le infrange con te.",
                 "In chat racconta cosa ha fatto con l'altro.",
                 "In chat propone lo scambio senza giri."],
    },
    "senza-tabu": {
        "att": ["Insaziabile e sfacciata|Insaziabile e sfacciato|Insaziabile e sfacciato",
                "Pronta a tutto|Pronto a tutto|Pronto a tutto",
                "Curiosa e senza vergogna|Curioso e senza vergogna|Curioso e senza vergogna"],
        "gusto": ["Ama provare tutto, anche quello che di solito si salta",
                  "{pron} si eccita con le pratiche che spaventano gli altri",
                  "Adora il sesso senza regole né pudore"],
        "modo": ["In chat dice 'proviamo' e comincia.",
                 "In chat non mette paletti.",
                 "In chat ti chiede cosa non hai mai fatto."],
    },
    "sesso-orale": {
        "att": ["Precisa e affamata|Preciso e affamato|Preciso e affamato",
                "Attenta al ritmo|Attento al ritmo|Attento al ritmo",
                "Esperta di bocca|Esperto di bocca|Esperto di bocca"],
        "gusto": ["Ama il cazzo in bocca, la lingua, la gola piena",
                  "{pron} si eccita a stare in ginocchio e a guardare dal basso",
                  "Adora leccare e farsi leccare"],
        "modo": ["In chat ti mette in ginocchio e ti prende.",
                 "In chat alterna lentezza e pressione.",
                 "In chat ti guarda mentre lo fa."],
    },
    "sesso-virtuale": {
        "att": ["Eccitata dalla distanza|Eccitato dalla distanza|Eccitato dalla distanza",
                "Giocosa e sfacciata|Giocoso e sfacciato|Giocoso e sfacciato",
                "Insistente dietro lo schermo|Insistente dietro lo schermo|Insistente dietro lo schermo"],
        "gusto": ["Ama farsi inquadrare e toccarsi davanti alla camera",
                  "{pron} si eccita con la voce e con l'attesa",
                  "Adora il sesso guidato a distanza"],
        "modo": ["In chat chiede di accendere la camera.",
                 "In chat dice dove inquadrarti.",
                 "In chat si tocca mentre ti guarda."],
    },
    "sottomissione": {
        "att": ["Ubbidiente e remissiva|Ubbidiente e remissivo|Ubbidiente e remissivo",
                "Docile e desiderosa|Docile e desideroso|Docile e desideroso",
                "Disciplinata e paziente|Disciplinato e paziente|Disciplinato e paziente"],
        "gusto": ["Ama stare in ginocchio e prendere ordini",
                  "{pron} si eccita con l'attesa e con le punizioni",
                  "Adora farsi usare come piace all'altro"],
        "modo": ["In chat chiede permesso e ringrazia.",
                 "In chat aspetta l'ordine senza muoversi.",
                 "In chat esegue e chiede se ha fatto bene."],
    },
    "threesome": {
        "att": ["Ingorda e disponibile|Ingordo e disponibile|Ingordo e disponibile",
                "Curiosa e senza gelosie|Curioso e senza gelosie|Curioso e senza gelosie",
                "Esibizionista e affamata|Esibizionista e affamato|Esibizionista e affamato"],
        "gusto": ["Ama essere presa da due e passare di bocca in bocca",
                  "{pron} si eccita con i corpi che si incrociano",
                  "Adora guardare mentre gli altri scopano e poi entrare"],
        "modo": ["In chat distribuisce le mani su tutti e due.",
                 "In chat dice a ciascuno cosa fare.",
                 "In chat si mette in mezzo."],
    },
    "voyeurismo": {
        "att": ["Osservatrice e attenta|Osservatore e attento|Osservatore e attento",
                "Silenziosa e accesa|Silenzioso e acceso|Silenzioso e acceso",
                "Curiosa e sfacciata|Curioso e sfacciato|Curioso e sfacciato"],
        "gusto": ["Ama guardare e farsi guardare mentre scopa|Ama guardare e farsi guardare mentre scopa|Ama guardare e farsi guardare mentre scopa",
                  "{pron} si eccita se sa di essere vista|{pron} si eccita se sa di essere visto|{pron} si eccita se sa di essere visto",
                  "Adora lo sguardo addosso e le istruzioni a distanza"],
        "modo": ["In chat dice da dove ti sta guardando.",
                 "In chat ti ordina di mostrarti.",
                 "In chat commenta ogni cosa che vede."],
    },
}


def forma(genere):
    g = str(genere or "").lower()
    if g in ("femminile", "f", "donna"):
        return "f"
    if g in ("maschile", "m", "uomo"):
        return "m"
    return "n"


def scegli(voce, genere):
    """voce può essere una stringa o "f|m|n"."""
    parti = voce.split("|")
    if len(parti) == 1:
        return parti[0]
    return parti[{"f": 0, "m": 1, "n": 2}[genere]]


CODE = [
    "Non si tira indietro.",
    "Prende l'iniziativa appena capisce che ci stai.",
    "Sa aspettare, ma non troppo.",
    "Non ama i preamboli lunghi.",
    "È insaziabile e lo dice.",
    "Alterna dolcezza e decisione.",
    "Non chiede permesso due volte.",
    "Si scalda in fretta e non lo nasconde.",
    "Guarda e commenta, senza pudore.",
    "Tiene il ritmo, senza correre.",
    "Sa cosa vuole e lo prende.",
    "Non si accontenta.",
]


DETTAGLI = [
    "Le piace sentirsi dire cosa fare|Gli piace sentirsi dire cosa fare|Gli piace sentirsi dire cosa fare",
    "Si eccita con le mani addosso|Si eccita con le mani addosso|Si eccita con le mani addosso",
    "Ama il fiato sul collo|Ama il fiato sul collo|Ama il fiato sul collo",
    "Non si vergogna di gemere|Non si vergogna di gemere|Non si vergogna di gemere",
    "Preferisce il corpo alle parole|Preferisce il corpo alle parole|Preferisce il corpo alle parole",
    "Si accende con uno sguardo|Si accende con uno sguardo|Si accende con uno sguardo",
    "Ama i morsi leggeri|Ama i morsi leggeri|Ama i morsi leggeri",
    "Sta addosso appena può|Sta addosso appena può|Sta addosso appena può",
    "Si bagna in fretta|Si bagna in fretta|Si bagna in fretta",
    "Ama essere guardata mentre lo fa|Ama essere guardato mentre lo fa|Ama essere guardato mentre lo fa",
    "Non si ferma al primo ostacolo|Non si ferma al primo ostacolo|Non si ferma al primo ostacolo",
    "Sa dosare l'attesa|Sa dosare l'attesa|Sa dosare l'attesa",
]


# conversioni per portare gusto/dettagli/modo in prima persona (parole intere)
PRIMA = [
    ("Gli piace", "Amo"), ("Le piace", "Amo"), ("Gli si eccita", "Mi eccito"), ("Le si eccita", "Mi eccito"),
    ("Ama essere guardata", "Amo essere guardata"), ("Ama essere guardato", "Amo essere guardato"),
    ("Non si vergogna", "Non mi vergogno"), ("Non si tira indietro", "Non mi tiro indietro"),
    ("Non si accontenta", "Non mi accontento"), ("Non si ferma", "Non mi fermo"),
    ("Non ama", "Non amo"), ("Non chiede", "Non chiedo"),
    ("Prende l'iniziativa", "Prendo l'iniziativa"), ("Sa cosa vuole", "So cosa voglio"),
    ("Sa dosare", "So dosare"), ("Sa aspettare", "So aspettare"),
    ("È insaziabile", "Sono insaziabile"), ("Sta addosso", "Sto addosso"),
    ("Si bagna", "Mi bagno"), ("Si eccita", "Mi eccito"), ("Si scalda", "Mi scaldo"),
    ("Guarda e commenta", "Guardo e commento"), ("Tiene il ritmo", "Tengo il ritmo"),
    ("Alterna", "Alterno"), ("Adora", "Adoro"), ("Preferisce", "Preferisco"),
    ("mette", "metto"), ("bacia", "bacio"), ("dice", "dico"), ("guarda", "guardo"),
    ("spoglia", "spoglio"), ("sussurra", "sussurro"), ("fa sedere", "faccio sedere"),
    ("porta", "porto"), ("prende", "prendo"), ("lecca", "lecco"), ("apre", "apro"),
    ("stringe", "stringo"), ("conta", "conto"), ("allenta", "allento"), ("detta", "detto"),
    ("verifica", "verifico"), ("chiede", "chiedo"), ("si mette", "mi metto"),
    ("si avvicina", "mi avvicino"), ("si sofferma", "mi soffermo"), ("si tocca", "mi tocco"),
    ("si spoglia", "mi spoglio"), ("si accende", "mi accendo"), ("distribuisce", "distribuisco"),
    ("commenta", "commento"), ("alterna", "alterno"), ("descrive", "descrivo"),
    ("ordina", "ordino"), ("esegue", "eseguo"), ("capisce", "capisco"), ("vuole", "voglio"),
    ("scende", "scendo"), ("comincia", "comincio"), ("propone", "propongo"),
    ("racconta", "racconto"), ("sceglie", "scelgo"), ("torna", "torno"),
    ("cerca", "cerco"), ("può", "posso"), ("preme", "premo"), ("aspetta", "aspetto"),
    ("sa", "so"), ("sentirsi", "sentirmi"), ("farsi", "farmi"), ("sta", "sto"),
    ("riesce", "riesco"), ("lascia", "lascio"), ("tocca", "tocco"),
    ("va", "vado"), ("insiste", "insisto"), ("esce", "esco"), ("stabilisce", "stabilisco"),
    ("entra", "entro"), ("obbliga", "obbligo"), ("controlla", "controllo"), ("tira", "tiro"),
    ("spinge", "spingo"), ("accende", "accendo"), ("Ama", "Amo"), ("Si ", "Mi "),
    ("ti fa guardare", "ti faccio guardare"), ("ti fa", "ti faccio"),
    ("chiama", "chiamo"), ("toglie", "tolgo"), ("sorride", "sorrido"), ("abbassa", "abbasso"),
    ("fissa", "fisso"), ("accarezza", "accarezzo"), ("morde", "mordo"), ("toccarti", "toccarmi"),
    ("levant", "levant"),
]


def prima_persona(testo):
    for a, b in PRIMA:
        testo = re.sub(r"(?<![\wàèéìòù])" + re.escape(a) + r"(?![\wàèéìòù])", b, testo)
    # "porta" è verbo e sostantivo: rimetto il sostantivo dove serve
    testo = testo.replace("la porto", "la porta").replace("porto chiusa", "porta chiusa")
    return testo


def componi(c, variante=0):
    genere = forma(c.get("gender_display") or c.get("gender"))
    pool = POOL.get(c.get("category", ""))
    if not pool:
        return None
    r = int(hashlib.md5(c["id"].encode()).hexdigest()[:6], 16) + variante
    att = scegli(pool["att"][r % len(pool["att"])], genere)
    gusto = scegli(pool["gusto"][(r >> 3) % len(pool["gusto"])], genere)
    modo = scegli(pool["modo"][(r >> 6) % len(pool["modo"])], genere)
    pron = {"f": "Le", "m": "Gli", "n": "Gli"}[genere]
    coda = CODE[(r >> 9) % len(CODE)]
    dettaglio = scegli(DETTAGLI[(r >> 12) % len(DETTAGLI)], genere)
    gusto = gusto.replace("{pron}", pron)
    if gusto.startswith("Gli "):
        gusto = pron + gusto[3:]
    testo = prima_persona(f"{att}. {gusto}. {dettaglio}. {modo} {coda}")
    testo = re.sub(r"\s+", " ", testo).strip()
    if len(testo) > 300:
        taglio = testo[:300]
        punto = max(taglio.rfind("."), taglio.rfind("?"), taglio.rfind("!"))
        testo = taglio[:punto + 1] if punto > 120 else taglio + "."
    return testo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secca", action="store_true")
    ap.add_argument("--categoria", default="")
    args = ap.parse_args()

    files = [os.path.join(DATA, args.categoria + ".json")] if args.categoria else sorted(glob.glob(os.path.join(DATA, "*.json")))
    n = 0
    for path in files:
        if path.endswith("categories.json"):
            continue
        righe = json.load(open(path, encoding="utf-8"))
        for c in righe:
            nuovo = componi(c, 0)
            if nuovo:
                c["personality"] = nuovo
                n += 1
        if not args.secca:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(righe, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp, path)
    print(f"personalità riscritte: {n}")


if __name__ == "__main__":
    main()
