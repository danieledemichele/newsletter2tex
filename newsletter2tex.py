#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
newsletter2tex — converte la Newsletter Ubuntu-it dal formato wiki (MoinMoin)
al file LaTeX per l'edizione PDF.

Uso:
  newsletter2tex.py                      scarica l'ultimo numero dal wiki e lo converte
  newsletter2tex.py -n 2026.031          scarica e converte un numero preciso
  newsletter2tex.py -f vecchio.txt       converte un file .txt già salvato
  newsletter2tex.py --gui                apre l'interfaccia grafica
  aggiungi --pdf per compilare anche il PDF con pdflatex

I file vengono salvati in una sottocartella col numero dell'uscita
(es. .../2026/031/). Ogni conversione produce, accanto al .tex, un file
"Newsletter Ubuntu-it NNN.AAAA.conversione.log" con tutto ciò che va controllato.

Solo libreria standard di Python 3 (nessuna dipendenza da installare).

Design: Daniele De Michele
https://github.com/danieledemichele/newsletter2tex

Copyright (C) 2026 Daniele De Michele

Questo programma è software libero: puoi ridistribuirlo e/o modificarlo secondo
i termini della GNU General Public License pubblicata dalla Free Software
Foundation, versione 3 della licenza o (a tua scelta) qualsiasi versione successiva.
Questo programma è distribuito nella speranza che sia utile, ma SENZA ALCUNA
GARANZIA. Vedi il file LICENSE per i dettagli.
"""

import argparse
import base64
import json
import logging
import logging.handlers
import platform
import threading
import traceback
import datetime as dt
import os
import re
import shutil
import struct
import socket
import subprocess
import sys
import zlib
import time
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# CONFIGURAZIONE — modifica qui se cambia qualcosa
# ---------------------------------------------------------------------------

WIKI_IT = "https://wiki.ubuntu-it.org"
PAGINA_NEWSLETTER = "NewsletterItaliana"          # NewsletterItaliana/2026.031
PAGINA_ARCHIVIO = "NewsletterItaliana/Archivio"

# Valori predefiniti. Ogni utente può cambiarli dalla GUI (Impostazioni):
# vengono salvati in ~/.config/newsletter2tex/config.json e letti anche da terminale.
CONFIG_PREDEFINITA = {
    # Cartella dell'anno: {anno} viene sostituito con l'anno del numero.
    # Qui stanno le immagini; .tex/.pdf/.txt/log vanno nella sottocartella NNN/.
    # Vuota finché l'utente non la sceglie (Sfoglia… nella finestra, -o da terminale).
    "cartella_lavoro": "",
    "a_cura_di": "Daniele De Michele",                       # colophon
    "realizzato_pdf": [["dd3my", "Daniele De Michele"]],    # "Ha realizzato il pdf"
    # Usati solo se il .txt non contiene "Ha inoltre collaborato all'edizione:"
    "edizione_predefinita": [],
    "tema": "",                                             # "chiaro", "scuro" o "" = come Ubuntu
    "notifiche": True,                                      # avviso dei nuovi numeri (lunedì sera/martedì)
    "aggiornamenti_automatici": True,                       # aggiornamento da GitHub all'avvio
    # Pagina del wiki a cui si allega il PDF ({anno}, {numero} a tre cifre)
    "pagina_allegati": "NewsletterItaliana/{anno}.{numero}",
}
CONFIG_FILE = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                           "newsletter2tex", "config.json")


def carica_config():
    cfg = json.loads(json.dumps(CONFIG_PREDEFINITA))
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            salvata = json.load(f)
        cfg.update({k: v for k, v in salvata.items() if k in cfg})
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as e:
        print(f"Attenzione: impossibile leggere {CONFIG_FILE} ({e}), uso i valori predefiniti",
              file=sys.stderr)
    return cfg


def salva_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# ICONA DEL PROGRAMMA "Monogramma" (disegno originale, palette Ubuntu): (PNG 256px, PNG 64px)
# ---------------------------------------------------------------------------

ICONA = (
        ("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"),
        ("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"
         "QQAAAABJRU5ErkJggg=="),
)

PERCORSO_ICONA = os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps/newsletter2tex.png")


def icona_png(grande=True):
    return base64.b64decode(ICONA[0] if grande else ICONA[1])


def png_rgba(larghezza, altezza, pixel):
    """PNG a 8 bit RGBA da una sequenza di byte riga per riga (solo libreria standard)."""
    riga = larghezza * 4
    grezzo = b"".join(b"\x00" + bytes(pixel[y * riga:(y + 1) * riga]) for y in range(altezza))

    def blocco(tipo, dati):
        return (struct.pack(">I", len(dati)) + tipo + dati
                + struct.pack(">I", zlib.crc32(tipo + dati) & 0xFFFFFFFF))
    return (b"\x89PNG\r\n\x1a\n" + blocco(b"IHDR", struct.pack(">IIBBBBB", larghezza, altezza, 8, 6, 0, 0, 0))
            + blocco(b"IDAT", zlib.compress(grezzo, 9)) + blocco(b"IEND", b""))


def esporta_icona(percorso=PERCORSO_ICONA):
    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    with open(percorso, "wb") as f:
        f.write(icona_png())
    return percorso


# Immagini richieste dal template (cercate in ./, ./Immagini/, ../, ../Immagini/)
IMMAGINI = ["newlogo1.png", "newlogo2.png", "Facebook.png",
            "Twitter.png", "YouTube.png", "Telegram.png"]

# Prefissi interwiki → URL base
INTERWIKI = {
    "ubuntu": "https://wiki.ubuntu.com/",
    "ubuntuwiki": "https://wiki.ubuntu.com/",
    "wikipedia": "https://en.wikipedia.org/wiki/",
    "wikipediait": "https://it.wikipedia.org/wiki/",
    "launchpad": "https://launchpad.net/",
}

USER_AGENT = "newsletter2tex/1.0 (Python urllib; uso personale per Newsletter Ubuntu-it)"

MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]


# ---------------------------------------------------------------------------
# LOG
# ---------------------------------------------------------------------------

VERSIONE = "2.0.0"
DESIGN = "Daniele De Michele"

LIVELLI = ("ERRORE", "AVVISO", "REFUSO", "INFO")
DESCRIZIONE_LIVELLI = {
    "ERRORE": "impedisce una conversione corretta: va sistemato",
    "AVVISO": "markup sospetto o non riconosciuto: controllare il risultato",
    "REFUSO": "possibile errore di battitura nel testo",
    "INFO": "solo informativo",
}


class Log:
    def __init__(self):
        self.voci = []      # (livello, riga, messaggio)
        self.sorgente = {}  # numero riga -> testo originale (per gli estratti)

    def _add(self, livello, riga, msg):
        voce = (livello, riga, msg)
        if voce not in self.voci:
            self.voci.append(voce)

    def info(self, msg, riga=None):
        self._add("INFO", riga, msg)

    def avviso(self, msg, riga=None):
        self._add("AVVISO", riga, msg)

    def refuso(self, msg, riga=None):
        self._add("REFUSO", riga, msg)

    def errore(self, msg, riga=None):
        self._add("ERRORE", riga, msg)

    def conta(self, livello):
        return sum(1 for v in self.voci if v[0] == livello)

    def estratto(self, riga, larghezza=110):
        t = self.sorgente.get(riga, "").strip()
        return t if len(t) <= larghezza else t[:larghezza - 1] + "…"

    def da_controllare(self):
        "Voci non informative, in ordine di riga (quelle senza riga in fondo)."
        voci = [v for v in self.voci if v[0] != "INFO"]
        return sorted(voci, key=lambda v: (v[1] is None, v[1] or 0, LIVELLI.index(v[0])))

    def riepilogo(self):
        return ", ".join(f"{self.conta(l)} {n}" for l, n in
                         (("ERRORE", "errori"), ("AVVISO", "avvisi"), ("REFUSO", "refusi")))

    def scrivi(self, percorso, intestazione):
        with open(percorso, "w", encoding="utf-8") as f:
            f.write(intestazione.rstrip() + "\n")
            f.write("=" * 78 + "\n")
            f.write(f"Riepilogo: {self.riepilogo()}\n")
            for l in LIVELLI:
                f.write(f"  {l:<7} {DESCRIZIONE_LIVELLI[l]}\n")
            f.write("=" * 78 + "\n\n")
            voci = self.da_controllare()
            if voci:
                f.write("DA CONTROLLARE (in ordine di riga del .txt)\n")
                f.write("-" * 78 + "\n")
                ultima = object()
                for livello, riga, msg in voci:
                    if riga != ultima and riga is not None:
                        f.write(f"\nRiga {riga}:  {self.estratto(riga)}\n")
                    elif riga is None and ultima is not None:
                        f.write("\nGenerale:\n")
                    ultima = riga
                    f.write(f"   [{livello}] {msg}\n")
                f.write("\n")
            else:
                f.write("Nessun problema trovato.\n\n")
            info = [v for v in self.voci if v[0] == "INFO"]
            if info:
                f.write("INFORMAZIONI\n" + "-" * 78 + "\n")
                for _, riga, msg in sorted(info, key=lambda v: (v[1] is None, v[1] or 0)):
                    f.write((f"   riga {riga:<4} " if riga else "   ") + msg + "\n")


# ---------------------------------------------------------------------------
# DOWNLOAD DAL WIKI
# ---------------------------------------------------------------------------

class WikiBloccato(Exception):
    pass


TIMEOUT_RETE = 20          # secondi senza risposta prima di considerare la richiesta persa
SCADENZA_DOWNLOAD = 60     # durata massima di un download, anche se i dati arrivano a rilento


def _e_timeout(e):
    return isinstance(e, (socket.timeout, TimeoutError)) or isinstance(
        getattr(e, "reason", None), (socket.timeout, TimeoutError))


def scarica_raw(pagina, tentativi=2):
    """Restituisce il testo grezzo di una pagina, None se non esiste.
    Non resta mai appeso: oltre SCADENZA_DOWNLOAD secondi rinuncia con un errore chiaro."""
    url = f"{WIKI_IT}/{pagina}?action=raw"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for tentativo in range(1, tentativi + 1):
        inizio = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_RETE) as r:
                parti = []
                while True:
                    if time.monotonic() - inizio > SCADENZA_DOWNLOAD:
                        raise socket.timeout("download troppo lento")
                    blocco = r.read(65536)
                    if not blocco:
                        break
                    parti.append(blocco)
            testo = b"".join(parti).decode("utf-8", errors="replace")
            break
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code in (401, 403, 429, 503):
                registro.warning("Il wiki ha rifiutato %s (HTTP %s)", pagina, e.code)
                raise WikiBloccato(f"HTTP {e.code} su {url}")
            raise
        except (OSError, urllib.error.URLError) as e:
            if not _e_timeout(e):
                raise
            registro.warning("Il wiki non risponde (%s, tentativo %d di %d)", pagina, tentativo, tentativi)
            if tentativo == tentativi:
                raise RuntimeError(f"Il wiki non risponde: {pagina} non è arrivata dopo {tentativi} "
                                   f"tentativi. Riprova tra qualche minuto oppure usa «File .txt».")
    inizio = testo.lstrip()[:600].lower()
    if inizio.startswith("<!doctype") or inizio.startswith("<html"):
        if "anubis" in testo.lower() or "oh noes" in testo.lower() or "not a bot" in testo.lower():
            registro.warning("Protezione anti-bot del wiki su %s", pagina)
            raise WikiBloccato(f"protezione anti-bot del wiki su {url}")
        return None   # pagina HTML generica: la trattiamo come inesistente
    return testo


def e_un_numero(testo):
    return bool(testo) and ("Questo è il numero" in testo or re.search(r"^=\s.+\s=\s*$", testo, re.M))


def esiste(anno, num, cache):
    chiave = (anno, num)
    if chiave not in cache:
        t = scarica_raw(f"{PAGINA_NEWSLETTER}/{anno}.{num:03d}")
        cache[chiave] = t if e_un_numero(t) else None
    return cache[chiave] is not None


def trova_ultimo_numero(log):
    """Trova l'ultimo numero pubblicato sul wiki. Ritorna (anno, numero, testo)."""
    cache = {}
    anno_corrente = dt.date.today().year
    anno, num = None, None

    # 1) pagina Archivio
    try:
        arch = scarica_raw(PAGINA_ARCHIVIO)
    except WikiBloccato:
        raise
    except Exception as e:  # rete ecc.
        arch = None
        log.avviso(f"Impossibile leggere l'Archivio ({e}); uso la ricerca diretta.")
    if arch:
        trovati = [(int(a), int(n)) for a, n in
                   re.findall(rf"{PAGINA_NEWSLETTER}/(\d{{4}})\.(\d{{3}})", arch)]
        if trovati:
            anno, num = max(trovati)
            log.info(f"Archivio: numero più recente elencato {anno}.{num:03d}")

    # 2) se l'archivio è indietro (o assente) si cerca nell'anno corrente
    if anno is None or anno < anno_corrente:
        if esiste(anno_corrente, 1, cache):
            anno, num = anno_corrente, 1
    if anno is None:
        raise RuntimeError("Non riesco a determinare l'ultimo numero: usa -n AAAA.NNN o -f file.txt")

    # 3) ricerca in avanti (l'archivio viene aggiornato dopo l'uscita):
    #    salto esponenziale + ricerca binaria sulle pagine esistenti
    if not esiste(anno, num, cache):
        # numero dell'archivio non trovato: cerco all'indietro
        while num > 1 and not esiste(anno, num, cache):
            num -= 1
    passo = 1
    while esiste(anno, num + passo, cache):
        num += passo
        passo *= 2
    basso, alto = num, num + passo        # basso esiste, alto no
    while alto - basso > 1:
        medio = (basso + alto) // 2
        if esiste(anno, medio, cache):
            basso = medio
        else:
            alto = medio
    num = basso
    testo = cache.get((anno, num)) or scarica_raw(f"{PAGINA_NEWSLETTER}/{anno}.{num:03d}")
    trova_ultimo_numero.cache = cache     # i testi già scaricati si riusano per la conversione
    return anno, num, testo


# ---------------------------------------------------------------------------
# STATISTICHE DEI BUG (Launchpad)
# ---------------------------------------------------------------------------

LAUNCHPAD_API = "https://api.launchpad.net/devel/ubuntu"
STATI_APERTI = ("New", "Incomplete", "Confirmed", "Triaged", "In Progress", "Fix Committed")
VOCI_STATISTICHE = (("aperti", "Aperti"), ("critici", "Critici"), ("nuovi", "Nuovi"))
RE_STATISTICA = re.compile(r"^\s*\*\s*(Aperti|Critici|Nuovi)\s*:\s*([\d.]+)\s*,\s*'*\s*([+\-−–]?\s*[\d.]+)\s*'*",
                           re.I | re.M)


def _intero(testo):
    return int(testo.replace(".", "").replace(" ", "").replace("−", "-").replace("–", "-"))


def leggi_statistiche(testo):
    """Valori della sezione 'Bug riportati' di un numero: {'aperti': (valore, differenza), ...}"""
    stat = {}
    for nome, valore, diff in RE_STATISTICA.findall(testo or ""):
        stat[nome.lower()] = (_intero(valore), _intero(diff))
    return stat


def conteggio_launchpad(parametri, timeout=90, tentativi=2):
    """Numero di bug task di Ubuntu che soddisfano i parametri di searchTasks."""
    url = (LAUNCHPAD_API + "?ws.op=searchTasks&ws.show=total_size&"
           + urllib.parse.urlencode(parametri, doseq=True))
    ultimo = None
    for _ in range(tentativi):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return int(r.read().decode().strip().strip('"'))
        except (OSError, ValueError, urllib.error.URLError) as e:
            ultimo = e
    raise RuntimeError(f"Launchpad non risponde ({getattr(ultimo, 'reason', ultimo)})")


def statistiche_launchpad(avanzamento=lambda m: None):
    """Aperti, critici e nuovi da Launchpad. Il totale degli aperti è una richiesta
    pesante: se va in timeout si sommano i singoli stati aperti."""
    avanzamento("Bug critici…")
    critici = conteggio_launchpad({"importance": "Critical"})
    avanzamento("Bug nuovi…")
    nuovi = conteggio_launchpad({"status": "New"})
    avanzamento("Bug aperti (può richiedere un minuto)…")
    try:
        aperti = conteggio_launchpad({}, timeout=120, tentativi=1)
    except RuntimeError:
        aperti = nuovi
        for stato in STATI_APERTI[1:]:
            avanzamento(f"Bug aperti: stato «{stato}»…")
            aperti += conteggio_launchpad({"status": stato}, timeout=120)
    return {"aperti": aperti, "critici": critici, "nuovi": nuovi}


def formatta_differenza(d):
    return f"+{d}" if d > 0 else ("−" + str(-d) if d < 0 else "0")


def blocco_statistiche(valori, precedenti=None):
    """Righe wiki pronte da incollare nella sezione 'Bug riportati'."""
    righe = []
    for chiave, nome in VOCI_STATISTICHE:
        v = valori[chiave]
        d = v - precedenti[chiave] if precedenti and chiave in precedenti else None
        diff = formatta_differenza(d) if d is not None else "???"
        q = "'" * 3
        righe.append(f" * {nome}: {v}, {q}{diff}{q} rispetto alla scorsa settimana.")
    return "\n".join(righe)


def controlla_statistiche(testo, precedente, num_precedente, log):
    """Controlla che le differenze scritte nel .txt tornino con il numero precedente."""
    attuali = leggi_statistiche(testo)
    if not attuali:
        log.avviso("Statistiche dei bug non trovate (righe « * Aperti: valore, differenza …»)")
        return
    for chiave, nome in VOCI_STATISTICHE:
        if chiave not in attuali:
            log.avviso(f"Statistiche dei bug: manca la riga «{nome}»")
    if not precedente:
        log.info("Statistiche dei bug: numero precedente non disponibile, differenze non verificate")
        return
    prec = leggi_statistiche(precedente)
    if not prec:
        log.info(f"Statistiche dei bug: nel numero {num_precedente} non ci sono valori da confrontare")
        return
    if all(attuali.get(k, (None,))[0] == prec.get(k, (None,))[0] for k, _ in VOCI_STATISTICHE):
        log.avviso(f"Statistiche dei bug identiche al numero {num_precedente}: forse non sono state aggiornate")
    for chiave, nome in VOCI_STATISTICHE:
        if chiave in attuali and chiave in prec:
            valore, scritta = attuali[chiave]
            attesa = valore - prec[chiave][0]
            if attesa != scritta:
                log.errore(f"Statistiche dei bug, «{nome}»: scritto {formatta_differenza(scritta)}, ma "
                           f"{valore} − {prec[chiave][0]} (numero {num_precedente}) = "
                           f"{formatta_differenza(attesa)}")
    log.info("Statistiche dei bug confrontate con il numero " + num_precedente)


def testo_numero_precedente(cfg, anno, num):
    """Testo del numero precedente: prima dalla copia locale, poi dal wiki."""
    if num <= 1:
        return None, None
    prec = num - 1
    etichetta = f"{anno}.{prec:03d}"
    tex = percorso_tex(cfg, anno, prec)
    locale = tex and os.path.join(os.path.dirname(tex), f"NewsletterItaliana_{etichetta}.txt")
    if locale and os.path.exists(locale):
        with open(locale, encoding="utf-8", errors="replace") as f:
            return f.read(), etichetta
    try:
        testo = scarica_raw(f"{PAGINA_NEWSLETTER}/{etichetta}")
        return (testo if e_un_numero(testo) else None), etichetta
    except Exception:
        return None, etichetta


def cartella_anno(cfg, anno):
    """Cartella dell'anno dalle impostazioni; stringa vuota se l'utente non l'ha ancora scelta."""
    base = (cfg.get("cartella_lavoro") or "").strip()
    return os.path.expanduser(base.replace("{anno}", str(anno))) if base else ""


def quando(momento, oggi=None):
    """«alle 09:50», «ieri alle 09:50» o «il 03/10 alle 09:50»."""
    oggi = oggi or dt.date.today()
    ora = momento.strftime("%H:%M")
    if momento.date() == oggi:
        return f"alle {ora}"
    if momento.date() == oggi - dt.timedelta(days=1):
        return f"ieri alle {ora}"
    return f"il {momento.strftime('%d/%m')} alle {ora}"


def riferimento_statistiche(cfg, anno=None):
    """Valori del numero più recente convertito in locale: ({chiave: valore}, 'AAAA.NNN')."""
    anno = anno or dt.date.today().year
    for a in (anno, anno - 1):
        cartella = cartella_anno(cfg, a)
        if not cartella:
            return None
        try:
            numeri = sorted((int(n) for n in os.listdir(cartella) if re.fullmatch(r"\d{3}", n)), reverse=True)
        except OSError:
            continue
        for n in numeri:
            txt = os.path.join(cartella, f"{n:03d}", f"NewsletterItaliana_{a}.{n:03d}.txt")
            if os.path.exists(txt):
                with open(txt, encoding="utf-8", errors="replace") as f:
                    stat = leggi_statistiche(f.read())
                if stat:
                    return {k: v[0] for k, v in stat.items()}, f"{a}.{n:03d}"
    return None


def percorso_tex(cfg, anno, num):
    cartella = cartella_anno(cfg, anno)
    if not cartella:
        return None
    return os.path.join(cartella, f"{num:03d}", f"Newsletter Ubuntu-it {num:03d}.{anno}.tex")


TITOLI_DI_SERVIZIO = ("aggiornamenti di sicurezza", "bug riportati", "statistiche del gruppo",
                      "licenza adottata", "uscite settimanali")


def anteprima(testo):
    """Settimana e titoli degli articoli di un numero, per il popup."""
    info = {"settimana": "", "articoli": []}
    m = re.search(r"da\s*'*\s*(\w+\s+\d{1,2}\s+\w+)\s*'*\s*a\s*'*\s*(\w+\s+\d{1,2}\s+\w+)", testo or "")
    if m:
        info["settimana"] = f"da {m.group(1)} a {m.group(2)}"
    for t in re.findall(r"^==\s+([^=].*?)\s+==\s*$", testo or "", re.M):
        if not any(x in t.lower() for x in TITOLI_DI_SERVIZIO):
            info["articoli"].append(re.sub(r"'{2,}", "", t))
    return info


RE_FILE_NUMERO = re.compile(r"(\d{3})\.(\d{4})\.(tex|pdf)$", re.I)


def numeri_convertiti(cfg, anno):
    """Numeri dell'anno che hanno già un .tex o un .pdf nella cartella dell'anno, anche se creati
    a mano prima di usare il programma (es. «Newsletter Ubuntu-it 029.2026.pdf» in qualsiasi
    sottocartella fino a due livelli)."""
    cartella = cartella_anno(cfg, anno)
    trovati = set()
    if not cartella or not os.path.isdir(cartella):
        return trovati
    base = cartella.rstrip(os.sep).count(os.sep)
    for radice, cartelle, files in os.walk(cartella):
        if radice.count(os.sep) - base >= 2:
            cartelle[:] = []
        for f in files:
            m = RE_FILE_NUMERO.search(f)
            if m and int(m.group(2)) == anno:
                trovati.add(int(m.group(1)))
    return trovati


def controlla_novita(cfg, log=None):
    """Ultimo numero sul wiki e numeri recenti non ancora convertiti in locale."""
    log = log or Log()
    anno, num, testo = trova_ultimo_numero(log)
    fatti = numeri_convertiti(cfg, anno)
    mancanti = []
    if num not in fatti:
        mancanti.append(num)
        if fatti:   # proponiamo i numeri arretrati solo fino all'ultimo già convertito
            n = num - 1
            while n >= 1 and n not in fatti and len(mancanti) < 6:
                mancanti.append(n)
                n -= 1
    testi = {n: t for (a, n), t in getattr(trova_ultimo_numero, "cache", {}).items()
             if a == anno and t}
    testi[num] = testo
    return {"anno": anno, "numero": num, "testo": testo, "testi": testi,
            "convertito": num in fatti, "mancanti": mancanti, "anteprima": anteprima(testo),
            "url": f"{WIKI_IT}/{PAGINA_NEWSLETTER}/{anno}.{num:03d}"}


# ---------------------------------------------------------------------------
# CONVERSIONE INLINE
# ---------------------------------------------------------------------------

SPECIALI = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
    "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}
RE_SPECIALI = re.compile(r"[\\&%$#_{}~^]")

UNICODE = {
    "\u2212": "-",            # segno meno
    "\u2026": r"\dots{}",
    "\u00a0": "~",            # spazio non separabile
    "\u2192": r"$\rightarrow$", "\u2190": r"$\leftarrow$",
    "\u21d2": r"$\Rightarrow$", "\u00d7": r"$\times$",
    "\u2264": r"$\leq$", "\u2265": r"$\geq$", "\u2248": r"$\approx$",
    "\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "",
}
# caratteri non ASCII che pdflatex (utf8 + T1) gestisce senza problemi
SICURI = set("àèéìíòóùúÀÈÉÌÒÙçÇñÑäëïöüÄËÏÖÜâêîôûÂÊÎÔÛßøØåÅæÆœŒãõÃÕšžŠŽčćČĆłŁ"
             "‘’“”«»–—€°ºª•§¶©®·¡¿´¨¸")

PH = "\x00{}\x00"   # segnaposto per pezzi già convertiti
RE_PH = re.compile(r"\x00(\d+)\x00")


def escape(testo):
    testo = RE_SPECIALI.sub(lambda m: SPECIALI[m.group()], testo)
    for k, v in UNICODE.items():
        testo = testo.replace(k, v)
    return testo


def escape_url(url):
    return url.replace("%", r"\%").replace("#", r"\#")


REFUSI_PAROLE = {
    "perchè": "perché", "poichè": "poiché", "affinchè": "affinché", "benchè": "benché",
    "finchè": "finché", "giacchè": "giacché", "sicchè": "sicché", "nè": "né", "pò": "po'",
    "qual'è": "qual è", "qual'era": "qual era", "propio": "proprio",
    "daccordo": "d'accordo", "avvolte": "a volte", "qualcun'altro": "qualcun altro",
}


def controlla_refusi(testo, nr, log):
    "Cerca refusi comuni in una riga di testo wiki."
    t = re.sub(r"\[\[.*?\]\]", "X", testo)          # il contenuto dei link non si controlla
    t = re.sub(r"\{\{\{.*?\}\}\}", "X", t)
    t = re.sub(r"https?://\S+", "X", t)
    t = re.sub(r"'{2,}|\*\*", "", t)                   # grassetto/corsivo
    corpo = t.strip()
    def intorno(m, n=14):
        return "…" + corpo[max(0, m.start() - n):m.end() + n].replace("\n", " ") + "…"
    for m in re.finditer(r"\S {2,}\S", corpo):
        log.refuso(f"Doppio spazio: «{intorno(m)}»", nr)
    for m in re.finditer(r"(?<=\w) +([,;:.])(?=\s|$)", corpo):
        log.refuso(f"Spazio prima di «{m.group(1)}»: «{intorno(m)}»", nr)
    for m in re.finditer(r"(?<=[a-zà-ù])([,;])(?=[A-Za-zÀ-ù])", corpo):
        log.refuso(f"Manca lo spazio dopo «{m.group(1)}»: «{intorno(m)}»", nr)
    for m in re.finditer(r"(?<=[a-zà-ù]{2})\.(?=[A-ZÀ-Ù][a-zà-ù])", corpo):
        log.refuso("Manca lo spazio dopo il punto: «…"
                   + corpo[max(0, m.start() - 12):m.end() + 12] + "…»", nr)
    if corpo.count("(") != corpo.count(")"):
        log.refuso(f"Parentesi tonde non bilanciate ({corpo.count('(')} aperte, "
                   f"{corpo.count(')')} chiuse)", nr)
    if corpo.count('"') % 2:
        log.refuso('Virgolette " in numero dispari (una non chiusa?)', nr)
    for m in re.finditer(r"\b(\w{2,})\s+\1\b", corpo, re.I):
        if not m.group(1).isdigit():
            log.refuso(f"Parola ripetuta: «{m.group(0)}»", nr)
    basso = " " + corpo.lower() + " "
    for sbagliata, giusta in REFUSI_PAROLE.items():
        if re.search(r"(?<![\wà-ù'])" + re.escape(sbagliata) + r"(?![\wà-ù])", basso):
            log.refuso(f"«{sbagliata}» → «{giusta}»", nr)
    m = re.search(r"\b[A-Za-zÀ-ù]+' [aeiouAEIOUèéàìòù]\w*", corpo)
    if m:
        log.refuso(f"Spazio dopo l'apostrofo: «{m.group(0)}»", nr)


RE_MARKUP_RESIDUO = re.compile(r"\[\[|\]\]|\{\{|\}\}|<<|>>|~-|-~|~\+|\+~|\^\^|,,\S|`")


class Inline:
    """Converte il markup inline di una riga MoinMoin in LaTeX."""

    def __init__(self, log, pagina_corrente):
        self.log = log
        self.pagina = pagina_corrente

    # --- link -------------------------------------------------------------
    def url_da_destinazione(self, dest, riga):
        dest = dest.strip()
        if re.match(r"^(https?|ftp|mailto|irc|ircs):", dest, re.I):
            return dest
        if dest.startswith("#"):
            return f"{WIKI_IT}/{self.pagina}{dest}"
        if dest.startswith("/"):
            self.log.avviso(f"Link a sottopagina relativa '{dest}': risolto rispetto a {self.pagina}", riga)
            dest = self.pagina + dest
        elif dest.startswith("../"):
            self.log.avviso(f"Link relativo '{dest}': controllare l'URL generato", riga)
            dest = dest[3:]
        m = re.match(r"^([A-Za-z]+):(?!//)(.+)$", dest)
        if m:
            prefisso = m.group(1).lower()
            if prefisso in INTERWIKI:
                return INTERWIKI[prefisso] + urllib.parse.quote(m.group(2), safe="/#:.-_()+")
            self.log.avviso(f"Prefisso interwiki sconosciuto '{m.group(1)}:' — trattato come pagina del wiki italiano", riga)
        return f"{WIKI_IT}/" + urllib.parse.quote(dest, safe="/#:.-_()+")

    def href(self, url, testo_latex):
        return r"$\href{" + escape_url(url) + "}{\\textsl{" + testo_latex + "}}$"

    def link(self, interno, riga):
        parti = interno.split("|")
        dest = parti[0].strip()
        testo = parti[1].strip() if len(parti) > 1 else ""
        if len(parti) > 2:
            self.log.info(f"Parametri extra del link ignorati: '|{'|'.join(parti[2:])}'", riga)
        if not dest:
            self.log.errore(f"Link senza destinazione: [[{interno}]]", riga)
            return self.formatta(testo, riga)
        url = self.url_da_destinazione(dest, riga)
        if len(parti) > 1 and not parti[1].strip():
            self.log.avviso(f"Link con '|' ma testo vuoto: [[{interno}]]", riga)
        if not testo:
            if re.match(r"^[a-z]+://", dest, re.I):
                self.log.avviso(f"Link senza testo: nel PDF comparirà l'URL intero ({dest})", riga)
            else:
                self.log.info(f"Link interno senza testo: mostro il nome della pagina ({dest})", riga)
            testo = dest
        if " " in dest and re.match(r"^[a-z]+://", dest, re.I):
            self.log.avviso(f"URL con spazi: «{dest}» (manca la '|' tra indirizzo e testo?)", riga)
        return self.href(url, self.formatta(testo, riga))

    # --- formattazione ----------------------------------------------------
    def formatta(self, testo, riga, originale=None):
        "Escape + grassetto/corsivo, senza estrarre link."
        mostra = (originale or testo)[:90]
        testo = re.sub(r"(?<![^\s(\[\"'/])!(?=[A-Z])", "", testo)   # !CamelCase → CamelCase
        # markup con ^ e ~, da gestire prima dell'escape (che li trasforma)
        if re.search(r"~-.+?-~|~\+.+?\+~", testo):
            self.log.avviso("Testo piccolo/grande ~- -~ / ~+ +~ reso come testo normale", riga)
            testo = re.sub(r"~-(.+?)-~|~\+(.+?)\+~", lambda m: m.group(1) or m.group(2), testo)
        if re.search(r"--\(.+?\)--", testo):
            self.log.avviso("Testo barrato --( )-- reso come testo normale", riga)
            testo = re.sub(r"--\(\s*(.+?)\s*\)--", r"\1", testo)
        testo = re.sub(r"\^([^\s^][^^]*?)\^", "\ue000\\1\ue001", testo)
        # markup non riconosciuto (controllato sul testo prima dell'escape)
        controllo = re.sub(r",,\S.*?,,|`.+?`", "", testo)
        residuo = RE_MARKUP_RESIDUO.findall(controllo)
        if residuo:
            self.log.avviso("Markup wiki non riconosciuto, rimasto nel testo così com'è: "
                            + " ".join(f"«{x}»" for x in sorted(set(residuo))), riga)
        testo = escape(testo)
        testo = testo.replace("\ue000", "\\textsuperscript{").replace("\ue001", "}")
        testo = re.sub(r"'''''(.+?)'''''", r"\\textbf{\\textit{\1}}", testo)
        testo = re.sub(r"'''(.+?)'''", r"\\textbf{\1}", testo)
        testo = re.sub(r"''(.+?)''", r"\\textit{\1}", testo)
        testo = re.sub(r"\*\*(.+?)\*\*", r"\\textit{\1}", testo)
        testo = re.sub(r"__(.+?)__", r"\\underline{\1}", testo)
        testo = re.sub(r",,(\S.*?),,", r"\\textsubscript{\1}", testo)
        testo = re.sub(r"`(.+?)`", r"\\texttt{\1}", testo)
        if "'''" in testo or re.search(r"(?<!')''(?!')", testo):
            self.log.avviso(f"Apici di grassetto/corsivo non chiusi: «{mostra}»", riga)
        if "**" in testo:
            self.log.avviso(f"Asterischi ** non chiusi: «{mostra}»", riga)
        return testo

    def converti(self, riga_txt, riga):
        pezzi = []

        def salva(latex):
            pezzi.append(latex)
            return PH.format(len(pezzi) - 1)

        t = riga_txt
        # macro <<...>>
        t = re.sub(r"<<BR>>", lambda m: salva(r"\\"), t, flags=re.I)

        def macro(m):
            self.log.avviso(f"Macro wiki ignorata: {m.group(0)}", riga)
            return ""
        t = re.sub(r"<<.*?>>", macro, t)
        # codice {{{ }}}
        t = re.sub(r"\{\{\{(.*?)\}\}\}", lambda m: salva(r"\textsl{" + escape(m.group(1)) + "}"), t)
        # immagini/allegati {{...}}
        def allegato(m):
            self.log.avviso(f"Immagine/allegato non convertito: {m.group(0)}", riga)
            return ""
        t = re.sub(r"\{\{.*?\}\}", allegato, t)
        # link [[...]]
        t = re.sub(r"\[\[(.+?)\]\]", lambda m: salva(self.link(m.group(1), riga)), t)
        if "[[" in t or "]]" in t:
            self.log.errore(f"Parentesi di link non bilanciate: «{riga_txt[:90]}»", riga)
        # URL nudi
        def url_nudo(m):
            url = m.group(0)
            coda = ""
            while url and url[-1] in ".,;:)!?'\"":
                coda = url[-1] + coda
                url = url[:-1]
            self.log.info(f"URL senza parentesi convertito in link: {url}", riga)
            return salva(self.href(url, escape(url))) + coda
        t = re.sub(r"(?<![\w/])(https?://[^\s\x00]+)", url_nudo, t)

        # emoji e simboli che pdflatex non sa comporre
        def emoji(m):
            self.log.avviso(f"Emoji/simbolo rimosso: {m.group(0)} (U+{ord(m.group(0)[0]):04X})", riga)
            return ""
        t = re.sub(r"[\U00010000-\U0010FFFF\u2600-\u27BF\uFE0F]", emoji, t)
        t = self.formatta(t, riga, riga_txt)
        # ripristino segnaposto (anche annidati)
        while RE_PH.search(t):
            t = RE_PH.sub(lambda m: pezzi[int(m.group(1))], t)
        return t


# ---------------------------------------------------------------------------
# PARSING A BLOCCHI
# ---------------------------------------------------------------------------

RE_TITOLO = re.compile(r"^(={1,5})\s+([^=\s].*?)\s+\1\s*$")
RE_ELEMENTO = re.compile(r"^(\s+)(\*|\d+\.|[a-zA-Z]\.|[iI]\.)\s+(.*)$")
RE_FONTE = re.compile(r"^\s*''\s*Font[ei]\s*''\s*:?\s*(.*)$", re.I)


def controlla_struttura(righe, log):
    "Righe che sembrano markup ma non vengono riconosciute."
    for nr, r in righe:
        s = r.rstrip()
        if s.startswith("=") and not RE_TITOLO.match(s):
            log.errore("Titolo non riconosciuto: i segni '=' all'inizio e alla fine devono essere "
                       "uguali e separati da spazi (es. '== Titolo ==')", nr)
        elif re.match(r"^(\*|\d+\.)\s+\S", s):
            log.avviso("Sembra un elemento di lista ma manca lo spazio iniziale (' * '): "
                       "finisce attaccato al paragrafo precedente", nr)
        elif re.match(r"^\s+-\s+\S", s):
            log.avviso("Elemento con trattino ' - ': nel wiki le liste usano ' * '", nr)
        elif re.match(r"^\s*'{2,3}\s*Font[ei]\s*'{2,3}", s, re.I) and not RE_FONTE.match(s):
            log.avviso("Riga 'Fonte' scritta in modo non standard: usare ''Fonte'': [[url | sito]]", nr)
        elif re.match(r"^\s*Font[ei]\s*:", s, re.I):
            log.avviso("Riga 'Fonte' senza corsivo: usare ''Fonte'': [[url | sito]] "
                       "(altrimenti non viene raggruppata)", nr)


def leggi_blocchi(righe, inline, log):
    """righe: lista di (numero_riga, testo). Ritorna la lista dei blocchi."""
    blocchi = []
    i = 0
    n = len(righe)
    while i < n:
        nr, r = righe[i]
        s = r.rstrip()
        if not s.strip():
            i += 1
            continue
        if s.startswith("##"):
            i += 1
            continue
        if s.startswith("#"):
            log.avviso(f"Istruzione wiki ignorata: «{s.strip()[:60]}»", nr)
            i += 1
            continue

        if re.match(r"^-{4,}\s*$", s):
            i += 1
            continue
        if re.match(r"^\s*(Category\w+\s*)+$", s):
            i += 1
            continue
        if s.lstrip().startswith("||"):
            log.avviso(f"Tabella wiki ignorata: «{s.strip()[:70]}»", nr)
            i += 1
            continue
        m = RE_TITOLO.match(s)
        if m:
            blocchi.append({"tipo": "titolo", "livello": len(m.group(1)),
                            "testo": m.group(2), "riga": nr})
            controlla_refusi(m.group(2), nr, log)
            i += 1
            continue
        m = RE_FONTE.match(s)
        if m:
            fonti = blocchi[-1] if blocchi and blocchi[-1]["tipo"] == "fonti" else None
            if fonti is None:
                fonti = {"tipo": "fonti", "voci": [], "riga": nr}
                blocchi.append(fonti)
            resto = m.group(1).strip()
            link = re.findall(r"\[\[.+?\]\]", resto)
            if link:
                fonti["voci"].extend((l, nr) for l in link)
                avanzo = re.sub(r"\[\[.+?\]\]", "", resto).strip(" ,;-")
                if avanzo:
                    log.avviso(f"Testo extra nella riga Fonte ignorato: «{avanzo}»", nr)
            elif resto:
                fonti["voci"].append((resto, nr))
                log.avviso(f"Fonte senza link: «{resto}»", nr)
            else:
                log.errore("Riga 'Fonte' vuota", nr)
            i += 1
            continue
        if RE_ELEMENTO.match(s):
            elementi = []   # (profondità, marcatore, testo, riga)
            while i < n:
                nr2, r2 = righe[i]
                s2 = r2.rstrip()
                me = RE_ELEMENTO.match(s2)
                if me:
                    elementi.append([len(me.group(1)), me.group(2), me.group(3), nr2])
                    controlla_refusi(me.group(3), nr2, log)
                    i += 1
                    continue
                if not s2.strip():
                    # riga vuota: la lista continua solo se il prossimo non vuoto è un elemento
                    j = i
                    while j < n and not righe[j][1].strip():
                        j += 1
                    if j < n and RE_ELEMENTO.match(righe[j][1].rstrip()):
                        i = j
                        continue
                    break
                if s2.startswith(" ") and elementi and not s2.lstrip().startswith("||"):
                    elementi[-1][2] += " " + s2.strip()   # continuazione
                    i += 1
                    continue
                break
            blocchi.append({"tipo": "lista", "elementi": elementi, "riga": nr})
            continue
        # paragrafo
        par = []
        while i < n:
            nr2, r2 = righe[i]
            s2 = r2.rstrip()
            if (not s2.strip() or RE_TITOLO.match(s2) or RE_FONTE.match(s2)
                    or RE_ELEMENTO.match(s2) or s2.startswith("##")
                    or re.match(r"^-{4,}\s*$", s2) or s2.lstrip().startswith("||")):
                break
            par.append((nr2, s2.strip()))
            controlla_refusi(s2, nr2, log)
            i += 1
        blocchi.append({"tipo": "paragrafo", "righe": par, "riga": nr})
    return blocchi


def raggruppa_sviluppatori(blocchi):
    """Nella sezione 'Statistiche del gruppo sviluppo' unisce (=== Nome ===, lista)."""
    out = []
    in_sviluppo = False
    for b in blocchi:
        if b["tipo"] == "titolo" and b["livello"] <= 2:
            in_sviluppo = "sviluppo" in b["testo"].lower() and "statistiche" in b["testo"].lower()
        if in_sviluppo and b["tipo"] == "titolo" and b["livello"] == 3:
            gruppo = out[-1] if out and out[-1]["tipo"] == "sviluppatori" else None
            if gruppo is None:
                gruppo = {"tipo": "sviluppatori", "voci": [], "riga": b["riga"]}
                out.append(gruppo)
            gruppo["voci"].append({"nome": b["testo"], "riga": b["riga"], "lista": None})
            continue
        if (in_sviluppo and b["tipo"] == "lista" and out and out[-1]["tipo"] == "sviluppatori"
                and out[-1]["voci"][-1]["lista"] is None):
            out[-1]["voci"][-1]["lista"] = b
            continue
        out.append(b)
    return out


# ---------------------------------------------------------------------------
# RENDERING LATEX
# ---------------------------------------------------------------------------

def render_lista(elementi, inline, log):
    """Lista annidata in base al rientro."""
    righe = []
    pila = []   # (rientro, ambiente)

    def ambiente(marc):
        return "itemize" if marc == "*" else "enumerate"

    for rientro, marc, testo, nr in elementi:
        while pila and rientro < pila[-1][0]:
            righe.append(f"\\end{{{pila.pop()[1]}}}")
        if not pila or rientro > pila[-1][0]:
            env = ambiente(marc)
            righe.append(f"\\begin{{{env}}}")
            pila.append((rientro, env))
        corpo = inline.converti(testo, nr)
        if corpo.startswith("["):
            corpo = "{" + corpo.split("]", 1)[0] + "]}" + corpo.split("]", 1)[1]
        if not corpo.strip():
            log.avviso("Elemento di lista vuoto", nr)
        righe.append(f"\\item {corpo}")
    while pila:
        righe.append(f"\\end{{{pila.pop()[1]}}}")
    return "\n".join(righe)


def render_blocchi(blocchi, inline, log):
    out = []
    for k, b in enumerate(blocchi):
        t = b["tipo"]
        if t == "titolo":
            comando = {1: "section", 2: "subsection", 3: "subsubsection"}.get(b["livello"], "paragraph")
            if b["livello"] > 3:
                log.avviso(f"Titolo di livello {b['livello']} reso come \\paragraph", b["riga"])
            if out:
                out.append("")
            out.append(f"\\{comando}{{{inline.converti(b['testo'], b['riga'])}}}")
        elif t == "paragrafo":
            testo = "\n".join(inline.converti(r, nr) for nr, r in b["righe"])
            out.append(testo)
            out.append("")
        elif t == "lista":
            out.append("")
            out.append(render_lista(b["elementi"], inline, log))
            out.append("")
        elif t == "fonti":
            link = []
            for v, nr in b["voci"]:
                link.append(inline.converti(v, nr))
            prec = blocchi[k - 1]["tipo"] if k > 0 else None
            if prec == "paragrafo":
                while out and out[-1] == "":
                    out.pop()
                out[-1] = out[-1] + "\\\\\n\\\\"
            out.append("\\textit{Fonte}:\\\\")
            out.append("\\\\\n".join(link))
            out.append("")
        elif t == "sviluppatori":
            out.append("\\begin{itemize}")
            for v in b["voci"]:
                out.append(f"\\item \\textit{{{inline.converti(v['nome'], v['riga'])}}}:")
                if v["lista"]:
                    out.append(render_lista(v["lista"]["elementi"], inline, log))
                else:
                    log.avviso(f"Sviluppatore '{v['nome']}' senza pacchetti elencati", v["riga"])
            out.append("\\end{itemize}")
            out.append("")
    # compatta righe vuote multiple
    testo = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", testo).strip() + "\n"


# ---------------------------------------------------------------------------
# DATI DEL NUMERO
# ---------------------------------------------------------------------------

def mese_numero(nome):
    nome = nome.lower().strip()
    return MESI.index(nome) + 1 if nome in MESI else None


def leggi_intestazione(testo, nome_file, log):
    dati = {}
    m = re.search(r"Questo è il numero\s*'*\s*(\d+)\s*'*\s*del\s*'*\s*(\d{4})", testo)
    if m:
        dati["numero"], dati["anno"] = int(m.group(1)), int(m.group(2))
    mf = re.search(r"(\d{4})[._](\d{3})", nome_file or "")
    if mf:
        anno_f, num_f = int(mf.group(1)), int(mf.group(2))
        if not m:
            dati["numero"], dati["anno"] = num_f, anno_f
            log.avviso(f"Numero/anno non trovati nel testo: ricavati dal nome del file ({anno_f}.{num_f:03d})")
        elif (anno_f, num_f) != (dati["anno"], dati["numero"]):
            log.avviso(f"Il nome del file indica {anno_f}.{num_f:03d} ma il testo dice "
                           f"{dati['anno']}.{dati['numero']:03d}: uso il testo")
    if "numero" not in dati:
        raise RuntimeError("Impossibile ricavare numero e anno della newsletter "
                           "(manca la frase 'Questo è il numero ... del ...').")

    md = re.search(r"da\s*'*\s*(\w+)\s+(\d{1,2})\s+(\w+)\s*'*\s*a\s*'*\s*(\w+)\s+(\d{1,2})\s+(\w+)", testo)
    if not md:
        raise RuntimeError("Impossibile leggere le date della settimana "
                           "('dalla settimana che va da lunedì X mese a domenica Y mese').")
    g1, d1, m1, g2, d2, m2 = md.groups()
    mese1, mese2 = mese_numero(m1), mese_numero(m2)
    if not mese1 or not mese2:
        raise RuntimeError(f"Mese non riconosciuto nelle date: '{m1}' / '{m2}'")
    anno = dati["anno"]
    # anno della domenica (settimana a cavallo dell'anno)
    if mese2 < mese1:          # dicembre → gennaio
        anno_dom = anno if dati["numero"] <= 5 else anno + 1
        anno_lun = anno_dom - 1
    else:
        anno_dom = anno_lun = anno
        if mese1 == 1 and dati["numero"] >= 50:
            anno_dom = anno_lun = anno + 1
    try:
        lun = dt.date(anno_lun, mese1, int(d1))
        dom = dt.date(anno_dom, mese2, int(d2))
        if lun.weekday() != 0:
            log.avviso(f"Il {d1} {m1} {anno_lun} non è un lunedì ({GIORNI[lun.weekday()]})")
        if dom.weekday() != 6:
            log.avviso(f"Il {d2} {m2} {anno_dom} non è una domenica ({GIORNI[dom.weekday()]})")
        if (dom - lun).days != 6:
            log.avviso(f"Tra le due date ci sono {(dom - lun).days} giorni invece di 6")
    except ValueError as e:
        log.errore(f"Data non valida: {e}")
    dati.update({
        "giorno1": g1.lower(), "data1": int(d1), "mese1": m1.lower(),
        "giorno2": g2.lower(), "data2": int(d2), "mese2": m2.lower(),
        "mese_testata": m2.capitalize(), "anno_testata": anno_dom,
    })
    return dati


RE_UTENTE = re.compile(r"^\[\[\s*([^|\]]+?)\s*(?:\|\s*([^\]]+?)\s*)?\]\]$")


def leggi_crediti(righe, log):
    """Elenchi della sezione 'Commenti e informazioni':
    redazione degli articoli, collaborato all'edizione, realizzato il pdf.
    Ritorna un dizionario {gruppo: [(utente, nome), ...]} (solo i gruppi trovati)."""
    gruppi = {}
    attivo = None
    for nr, r in righe:
        s = r.rstrip()
        basso = s.lower()
        if "partecipato alla redazione" in basso:
            attivo = "redazione"
        elif "collaborat" in basso and "edizione" in basso:
            attivo = "edizione"
        elif "realizzat" in basso and "pdf" in basso:
            attivo = "pdf"
        elif RE_TITOLO.match(s):
            attivo = None
            continue
        else:
            me = RE_ELEMENTO.match(s)
            if attivo and me:
                voce = me.group(3).strip()
                mu = RE_UTENTE.match(voce)
                if mu:
                    utente = mu.group(1).strip()
                    nome = (mu.group(2) or utente).strip()
                else:
                    utente, nome = None, re.sub(r"'{2,}", "", voce)
                    log.avviso(f"Nome senza link alla pagina utente: «{voce}»", nr)
                gruppi.setdefault(attivo, []).append((utente, nome))
            elif attivo and s.strip() and not me:
                attivo = None
            continue
        gruppi.setdefault(attivo, [])
    return gruppi


# ---------------------------------------------------------------------------
# TEMPLATE
# ---------------------------------------------------------------------------

PREAMBOLO = r"""\documentclass[a4paper,twoside]{article}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[italian]{babel}

\usepackage{graphicx}
\graphicspath{{./}{./Immagini/}{../}{../Immagini/}}
\usepackage{wrapfig}
\usepackage[labelformat=empty]{subfig}

\usepackage{emptypage}
\usepackage{amsmath}
\usepackage{amsthm}
\usepackage{siunitx}
\usepackage{booktabs}
\usepackage{bm}
\usepackage{hyperref}
\hypersetup{
			colorlinks=true,
			linkcolor=blue,
			anchorcolor=magenta,
			citecolor=blue,
			urlcolor=blue,
}
\usepackage[hypertext]{cdpaddon}
\usepackage[dvipsnames]{xcolor}
	\definecolor{ubuntuarancio}{RGB}{233, 84, 32}
	\definecolor{Mycolor2}{HTML}{E95420}

\usepackage{fancyhdr}
	\pagestyle{fancy}
	\fancyhead{}
	\fancyhead[RO,LE]{\textit{Newsletter Ubuntu-it N.<<NUM3>>, <<MESE>> <<ANNO_TESTATA>>}}
	\renewcommand{\headrulewidth}{0.4pt}
	\renewcommand{\footrulewidth}{0.4pt}

\begin{document}

\begin{titlepage}
\parbox{0.33\textwidth}{%
	\smash{\textcolor{ubuntuarancio}{\rule[-\textheight]{15pt}{\textheight}}}\hfill
\parbox[b][\textheight]{0.95\textwidth}{\centering
		\includegraphics[width=0.8\textwidth]{newlogo1.png}
		\vspace{1\baselineskip}

		\textbf{\Huge Newsletter Ubuntu-it}\vspace{0.5\baselineskip}

		\textbf{\Large Numero <<NUM3>> - Anno <<ANNO>>}\vspace{0.5\baselineskip}

		\textit{\large Gruppo Social Media}

		\vspace{\stretch{1}}
		\url{https://wiki.ubuntu-it.org/GruppoPromozione/}\vspace{\baselineskip}
		\makebox[\linewidth]{<<ANNO>>}
}}
\end{titlepage}
\clearpage
\hfill
\vfill
\pdfbookmark[0]{Colophon}{colophon}
\thispagestyle{empty}
\section*{Licenza}
Il presente documento e il suo contenuto è distribuito con licenza \textbf{Creative Commons 4.0 di tipo “Attribuzione - Condividi allo stesso modo”}. È possibile riprodurre, distribuire, comunicare al pubblico, esporre al pubblico, rappresentare, eseguire o recitare il presente documento alle seguenti condizioni:

\begin{itemize}
\item \textbf{Attribuzione} - Devi riconoscere una menzione di paternità adeguata, fornire un link alla licenza e indicare se sono state effettuate delle modifiche. Puoi fare ciò in qualsiasi maniera ragionevole possibile, ma non con modalità tali da suggerire che il licenziante avalli te o il tuo utilizzo del materiale.
\item \textbf{Stessa Licenza} - Se remixi, trasformi il materiale o ti basi su di esso, devi distribuire i tuoi contributi con la stessa licenza del materiale originario.
\item \textbf{Divieto di restrizioni aggiuntive} - Non puoi applicare termini legali o misure tecnologiche che impongano ad altri soggetti dei vincoli giuridici su quanto la licenza consente loro di fare.
\end{itemize}

Un riassunto in italiano della licenza è presente a questa $\href{https://creativecommons.org/licenses/by-sa/4.0/it/}{\textsl{pagina}}$. Per maggiori informazioni:

\begin{center}
$\href{http://www.creativecommons.org}{\texttt{http://www.creativecommons.org}}$
\end{center}

Questo documento è stato composto interamente dall'autore con \LaTeX. Per maggiori informazioni, o segnalazioni:

\begin{flushleft}
$\href{http://liste.ubuntu-it.org/cgi-bin/mailman/listinfo/newsletter-italiana}{\textsl{Mailing List Newsletter-italiana}}$: iscriviti per
ricevere la Newsletter Italiana di Ubuntu!;\\
$\href{http://liste.ubuntu-it.org/cgi-bin/mailman/listinfo/newsletter-ubuntu}{\textsl{Mailing List Newsletter-Ubuntu}}$: la redazione della newsletter italiana. Se vuoi collaborare alla realizzazione della newsletter, questo è lo strumento giusto con cui contattarci.\\
\textbf{Canale IRC}: $\href{https://chat.ubuntu-it.org/#ubuntu-it-promo}{\textsl{$\#$ubuntu-it-promo}}$
\end{flushleft}

\begin{flushright}
A cura di:\\
\textbf{<<A_CURA_DI>>}
\end{flushright}

\clearpage
\thispagestyle{empty}
\begin{figure}[!h]
\centering
\includegraphics[width=0.2\textwidth]{newlogo2.png}
\end{figure}
\begin{center}
\textbf{\Huge Newsletter Ubuntu-it}\vspace{\baselineskip}
\end{center}
\tableofcontents

\cleardoublepage

\begin{figure}[!h]
\centering
\includegraphics[width=0.7\textwidth]{newlogo1.png}
\end{figure}
\vspace{0.30cm}
Questo è il numero \textbf{<<NUM>>} del \textbf{<<ANNO>>} della Newsletter di Ubuntu-it, riferito alla settimana che va da \textbf{<<GIORNO1>> <<DATA1>> <<MESE1>>} a \textbf{<<GIORNO2>> <<DATA2>> <<MESE2>>}. Per qualsiasi commento, critica o lode, contattaci attraverso la $\href{http://liste.ubuntu-it.org/cgi-bin/mailman/listinfo/facciamo-promozione}{\textsl{mailing list}}$ del $\href{https://wiki.ubuntu-it.org/GruppoPromozione}{\textsl{gruppo promozione}}$.

"""

CHIUSURA = r"""
\section{Commenti e informazioni}
La tua newsletter preferita è scritta grazie al contributo libero e volontario della $\href{https://wiki.ubuntu-it.org/GruppoPromozione/SocialMedia/Crediti}{\textsl{comunità ubuntu-it}}$. In questo numero hanno partecipato alla redazione degli articoli:

\begin{itemize}
<<AUTORI>>
\end{itemize}
<<EDIZIONE>>
Ha realizzato il pdf:

\begin{itemize}
<<PDF>>
\end{itemize}

\section{Scrivi per la newsletter}
La \textbf{Newsletter Ubuntu-it} ha lo scopo di tenere aggiornati tutti gli utenti \textbf{Ubuntu} e, più in generale, le persone appassionate del mondo open-source. Viene resa disponibile gratuitamente con cadenza settimanale ogni Lunedì, ed è aperta al contributo di tutti gli utenti che vogliono partecipare con un proprio articolo. L’autore dell’articolo troverà tutte le raccomandazioni e istruzioni dettagliate all’interno della pagina $\href{https://wiki.ubuntu-it.org/GruppoPromozione/SocialMedia/Newsletter/LineeGuida}{\textsl{Linee Guida}}$, dove inoltre sono messi a disposizione per tutti gli utenti una serie di indirizzi web che offrono notizie riguardanti le principali novità su Ubuntu e sulla comunità internazionale, tutte le informazioni sulle attività della comunità italiana, le notizie sul software libero dall’Italia e dal mondo. Per chiunque fosse interessato a collaborare con la newsletter Ubuntu-it a titolo di redattore o grafico, può scrivere alla $\href{http://liste.ubuntu-it.org/cgi-bin/mailman/listinfo/facciamo-promozione}{\textsl{mailing list}}$ del $\href{http://wiki.ubuntu-it.org/GruppoPromozione}{\textsl{gruppo promozione}}$ oppure sul canale IRC: $\href{https://chat.ubuntu-it.org/#ubuntu-it-promo}{\textsl{$\#$ubuntu-it-promo}}$. Fornire il tuo contributo a questa iniziativa come membro, e non solo come semplice utente, è un presupposto fondamentale per aiutare la diffusione di Ubuntu anche nel nostro paese. Per rimanere in contatto con noi, puoi seguirci su:

\begin{figure}[!h]
\centering
\subfloat[][\emph{$\href{https://www.facebook.com/ubuntu.it}{\textsl{Facebook}}$}]
	{\includegraphics[width=.12\textwidth]{Facebook.png}} \qquad
\subfloat[][\emph{$\href{https://twitter.com/ubuntuit}{\textsl{Twitter}}$}]
	{\includegraphics[width=.15\textwidth]{Twitter.png}} \qquad
\subfloat[][\emph{$\href{https://youtube.com/ubuntuitpromozione}{\textsl{YouTube}}$}]
	{\includegraphics[width=.15\textwidth]{YouTube.png}} \qquad
\subfloat[][\emph{$\href{https://telegram.me/ubuntuit}{\textsl{Telegram}}$}]
	{\includegraphics[width=.12\textwidth]{Telegram.png}} \qquad
\end{figure}

\begin{flushright}
"Noi siamo ciò che siamo per\\
merito di ciò che siamo tutti"
\end{flushright}

\clearpage
\thispagestyle{empty}
\begin{center}
Questa newsletter è stata prodotta dal\\
Gruppo Social Media usando esclusivamente\\
software libero.
\end{center}

\end{document}
"""


def item_persona(utente, nome):
    if not utente:
        return r"\item \textsl{" + escape(nome) + "}"
    if not re.match(r"^https?://", utente):
        utente = f"{WIKI_IT}/" + urllib.parse.quote(utente, safe="/")
    return r"\item $\href{" + escape_url(utente) + "}{\\textsl{" + escape(nome) + "}}$"


def blocco_persone(persone):
    return "\n".join(item_persona(u, n) for u, n in persone)


# ---------------------------------------------------------------------------
# CONVERSIONE COMPLETA
# ---------------------------------------------------------------------------

def converti(testo, nome_file, log, cfg=None, edizione=None, precedente=None):
    cfg = cfg or carica_config()
    testo = testo.replace("\r\n", "\n").replace("\r", "\n")
    dati = leggi_intestazione(testo, nome_file, log)
    pagina = f"{PAGINA_NEWSLETTER}/{dati['anno']}.{dati['numero']:03d}"
    inline = Inline(log, pagina)

    righe = list(enumerate(testo.split("\n"), start=1))
    log.sorgente = dict(righe)

    # corpo: dal primo titolo "= ... =" fino a "= Commenti e informazioni ="
    inizio = fine = None
    for idx, (nr, r) in enumerate(righe):
        m = RE_TITOLO.match(r.rstrip())
        if m and len(m.group(1)) == 1:
            if inizio is None and "commenti" not in m.group(2).lower():
                inizio = idx
            if "commenti e informazioni" in m.group(2).lower():
                fine = idx
                break
    if inizio is None:
        raise RuntimeError("Nessuna sezione '= Titolo =' trovata nel testo.")
    if fine is None:
        log.errore("Sezione '= Commenti e informazioni =' non trovata: converto fino alla fine del file")
        fine = len(righe)

    controlla_struttura(righe[inizio:fine], log)
    blocchi = leggi_blocchi(righe[inizio:fine], inline, log)
    blocchi = raggruppa_sviluppatori(blocchi)

    sezioni = [b["testo"] for b in blocchi if b["tipo"] == "titolo" and b["livello"] == 1]
    articoli = [b for b in blocchi if b["tipo"] == "titolo" and b["livello"] == 2]
    for k, b in enumerate(blocchi):
        if b["tipo"] == "titolo" and b["livello"] == 2:
            nome = b["testo"].lower()
            if any(x in nome for x in ("aggiornamenti di sicurezza", "bug riportati",
                                        "statistiche del gruppo", "full circle")):
                continue
            # cerca le fonti prima del prossimo titolo
            ha_fonte = False
            for b2 in blocchi[k + 1:]:
                if b2["tipo"] == "titolo":
                    break
                if b2["tipo"] == "fonti":
                    ha_fonte = True
            vuota = k + 1 >= len(blocchi) or blocchi[k + 1]["tipo"] == "titolo"
            if not ha_fonte and not vuota:
                log.avviso(f"Articolo senza 'Fonte': «{b['testo']}»", b["riga"])
    for k, b in enumerate(blocchi):
        if b["tipo"] == "titolo":
            seguente = blocchi[k + 1] if k + 1 < len(blocchi) else None
            if seguente is None or (seguente["tipo"] == "titolo" and seguente["livello"] <= b["livello"]):
                log.avviso(f"Sezione vuota: «{b['testo']}»", b["riga"])
        if b["tipo"] == "fonti":
            visti = {}
            for v, nr in b["voci"]:
                url = re.sub(r"^\[\[\s*|\s*(\|.*)?\]\]$", "", v)
                if url in visti:
                    log.avviso(f"Fonte ripetuta (già alla riga {visti[url]}): {url}", nr)
                visti.setdefault(url, nr)
    corpo = render_blocchi(blocchi, inline, log)
    if precedente is not None:
        controlla_statistiche(testo, precedente[0], precedente[1], log)

    crediti = leggi_crediti(righe[fine:], log)
    autori = crediti.get("redazione", [])
    if not autori:
        log.errore("Nessun autore trovato in 'In questo numero hanno partecipato alla redazione degli articoli'")
    if edizione:
        log.info("Collaboratori all'edizione presi dalle opzioni (ignorando il .txt)")
    elif "edizione" in crediti:
        edizione = crediti["edizione"]
        if not edizione:
            log.avviso("Trovato 'Ha inoltre collaborato all'edizione:' ma senza nomi: sezione omessa")
    else:
        edizione = [tuple(x) for x in cfg["edizione_predefinita"]]
        log.info("Nel .txt manca 'Ha inoltre collaborato all'edizione:' — "
                 + ("uso i collaboratori predefiniti delle impostazioni" if edizione else "sezione omessa"))
    pdf = crediti.get("pdf") or [tuple(x) for x in cfg["realizzato_pdf"]]

    blocco_edizione = ""
    if edizione:
        blocco_edizione = ("\nHa inoltre collaborato all'edizione:\n\n\\begin{itemize}\n"
                           + blocco_persone(edizione) + "\n\\end{itemize}\n")

    sost = {
        "<<NUM3>>": f"{dati['numero']:03d}", "<<NUM>>": str(dati["numero"]),
        "<<ANNO>>": str(dati["anno"]), "<<MESE>>": dati["mese_testata"],
        "<<ANNO_TESTATA>>": str(dati["anno_testata"]),
        "<<GIORNO1>>": dati["giorno1"], "<<DATA1>>": str(dati["data1"]),
        "<<MESE1>>": dati["mese1"].capitalize(),
        "<<GIORNO2>>": dati["giorno2"], "<<DATA2>>": str(dati["data2"]),
        "<<MESE2>>": dati["mese2"].capitalize(),
        "<<A_CURA_DI>>": escape(cfg["a_cura_di"]),
        "<<AUTORI>>": blocco_persone(autori),
        "<<EDIZIONE>>": blocco_edizione,
        "<<PDF>>": blocco_persone(pdf),
    }
    tex = PREAMBOLO + corpo + CHIUSURA
    for k, v in sost.items():
        tex = tex.replace(k, v)

    # controllo caratteri potenzialmente problematici
    for nr, riga in enumerate(tex.split("\n"), start=1):
        strani = sorted({c for c in riga if ord(c) > 127 and c not in SICURI})
        if strani:
            log.avviso("Caratteri Unicode che pdflatex potrebbe non gestire nel .tex "
                       f"(riga {nr} del .tex): {' '.join(f'{c!r} U+{ord(c):04X}' for c in strani)}")

    log.info(f"Numero {dati['numero']:03d}/{dati['anno']}, settimana {dati['giorno1']} {dati['data1']} "
             f"{dati['mese1']} – {dati['giorno2']} {dati['data2']} {dati['mese2']}, "
             f"testata: {dati['mese_testata']} {dati['anno_testata']}")
    log.info(f"Sezioni: {', '.join(sezioni)}")
    log.info(f"Sottosezioni/articoli: {len(articoli)}")
    log.info("Redazione: " + ", ".join(n for _, n in autori))
    log.info("Collaborato all'edizione: " + (", ".join(n for _, n in edizione) or "—"))
    log.info("Realizzato il pdf: " + ", ".join(n for _, n in pdf))
    return tex, dati


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

def trova_immagini(cartella, log):
    mancanti = []
    for img in IMMAGINI:
        posti = [os.path.join(cartella, img), os.path.join(cartella, "Immagini", img),
                 os.path.join(cartella, "..", img), os.path.join(cartella, "..", "Immagini", img)]
        if not any(os.path.exists(p) for p in posti):
            mancanti.append(img)
    if mancanti:
        log.avviso(f"Immagini non trovate in {cartella} (né nella cartella dell'anno o in Immagini/): "
                   f"{', '.join(mancanti)}")


def compila_pdf(percorso_tex, log):
    if not shutil.which("pdflatex"):
        log.errore("pdflatex non trovato: installa texlive (sudo apt install texlive-latex-extra texlive-science texlive-lang-italian)")
        return None
    cartella, nome = os.path.split(percorso_tex)
    base = os.path.splitext(nome)[0]
    env = dict(os.environ)
    env["TEXINPUTS"] = f".:./Immagini//:..:../Immagini//:{env.get('TEXINPUTS', '')}"
    for passata in (1, 2):   # due passate per l'indice
        r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", nome],
                           cwd=cartella or ".", env=env, capture_output=True,
                           text=True, errors="replace")
        if r.returncode != 0:
            break
    log_tex = os.path.join(cartella, base + ".log")
    errori, avvisi = [], 0
    if os.path.exists(log_tex):
        with open(log_tex, encoding="utf-8", errors="replace") as f:
            righe = f.read().split("\n")
        for i, l in enumerate(righe):
            if l.startswith("!"):
                contesto = " ".join(" ".join(righe[i:i + 3]).split())
                errori.append(contesto)
            elif "Warning" in l and "Font" not in l:
                avvisi += 1
        overfull = sum(1 for l in righe if l.startswith("Overfull"))
        if overfull:
            log.info(f"pdflatex: {overfull} righe 'Overfull hbox' (testo che sborda, di solito URL lunghi)")
        if avvisi:
            log.info(f"pdflatex: {avvisi} avvisi LaTeX (vedi {base}.log)")
    for e in errori:
        log.errore(f"pdflatex: {e}")
    for ext in (".aux", ".toc", ".out"):
        p = os.path.join(cartella, base + ext)
        if os.path.exists(p):
            os.remove(p)
    pdf = os.path.join(cartella, base + ".pdf")
    if r.returncode == 0 and os.path.exists(pdf):
        return pdf
    log.errore("Compilazione PDF fallita: controlla gli errori sopra e il file " + base + ".log")
    return None


# ---------------------------------------------------------------------------
# ESECUZIONE (condivisa da terminale e GUI)
# ---------------------------------------------------------------------------

class Errore(Exception):
    pass


def cartella_output(dati, scelta, cfg, log):
    """<cartella dell'anno>/<NNN>/ — la cartella dell'anno è quella delle immagini."""
    if scelta:
        anno_dir = os.path.abspath(os.path.expanduser(scelta.replace("{anno}", str(dati["anno"]))))
    else:
        anno_dir = cartella_anno(cfg, dati["anno"])
        if not anno_dir:
            raise Errore("Nessuna cartella di destinazione: sceglila con «Sfoglia…» nella finestra "
                         "oppure, da terminale, indicala con -o CARTELLA (es. -o \"~/Newsletter/{anno}\").")
        if not os.path.isdir(anno_dir):
            ripiego = os.path.expanduser(f"~/Newsletter Ubuntu-it/{dati['anno']}")
            log.avviso(f"Cartella {anno_dir} inesistente: salvo in {ripiego} "
                       "(cambia la cartella nelle impostazioni)")
            anno_dir = ripiego
    cartella = os.path.join(anno_dir, f"{dati['numero']:03d}")
    os.makedirs(cartella, exist_ok=True)
    return cartella


def leggi_persone(valori):
    """['utente:Nome', ...] oppure 'utente:Nome; utente:Nome' → [(utente, nome)]"""
    if isinstance(valori, str):
        valori = [v for v in valori.split(";")]
    out = []
    for v in valori or []:
        v = v.strip()
        if not v:
            continue
        if ":" not in v:
            raise Errore(f"Formato atteso utente:Nome Cognome, ricevuto '{v}'")
        u, n = v.split(":", 1)
        out.append((u.strip(), n.strip()))
    return out


def esegui(file=None, numero=None, output=None, pdf=False, salva_txt=True,
           edizione=None, cfg=None, avanzamento=print, pronto=None, verifica_statistiche=True,
           copia_txt=False):
    """Scarica/legge, converte, salva e (opzionale) compila.
    Ritorna un dizionario con percorsi, log e codice (0 ok, 1 errori nel log)."""
    cfg = cfg or carica_config()
    log = Log()
    if file:
        percorso = os.path.expanduser(file)
        with open(percorso, encoding="utf-8", errors="replace") as f:
            testo = f.read()
        nome_file = os.path.basename(percorso)
        origine = f"file locale {os.path.abspath(percorso)}"
        scaricato = False
        if copia_txt:       # testo salvato dal browser: lo archiviamo con il nome standard
            mi = re.search(r"Questo è il numero\s*'*\s*(\d+)\s*'*\s*del\s*'*\s*(\d{4})", testo)
            if mi:
                nome_file = f"NewsletterItaliana_{mi.group(2)}.{int(mi.group(1)):03d}.txt"
    else:
        if pronto:
            anno, num, testo = pronto
            avanzamento(f"Uso il testo già scaricato di {anno}.{num:03d}")
        elif numero:
            m = re.match(r"^(\d{4})[./_-]?(\d{1,3})$", numero.strip())
            if not m:
                raise Errore("Formato numero non valido: usa AAAA.NNN, es. 2026.031")
            anno, num = int(m.group(1)), int(m.group(2))
            avanzamento(f"Scarico {PAGINA_NEWSLETTER}/{anno}.{num:03d} ...")
            testo = scarica_raw(f"{PAGINA_NEWSLETTER}/{anno}.{num:03d}")
            if not e_un_numero(testo):
                raise Errore(f"La pagina {PAGINA_NEWSLETTER}/{anno}.{num:03d} non esiste o è vuota.")
        else:
            avanzamento("Cerco l'ultimo numero sul wiki ...")
            anno, num, testo = trova_ultimo_numero(log)
            avanzamento(f"Ultimo numero trovato: {anno}.{num:03d}")
        nome_file = f"NewsletterItaliana_{anno}.{num:03d}.txt"
        origine = f"{WIKI_IT}/{PAGINA_NEWSLETTER}/{anno}.{num:03d}"
        scaricato = True

    avanzamento("Converto in LaTeX ...")
    mi = re.search(r"Questo è il numero\s*'*\s*(\d+)\s*'*\s*del\s*'*\s*(\d{4})", testo)
    precedente = None
    if mi and verifica_statistiche:
        prec_testo, prec_num = testo_numero_precedente(cfg, int(mi.group(2)), int(mi.group(1)))
        precedente = (prec_testo, prec_num or "precedente")
    tex, dati = converti(testo, nome_file, log, cfg, edizione or None, precedente)
    cartella = cartella_output(dati, output, cfg, log)
    base = f"Newsletter Ubuntu-it {dati['numero']:03d}.{dati['anno']}"
    percorso_tex = os.path.join(cartella, base + ".tex")
    with open(percorso_tex, "w", encoding="utf-8") as f:
        f.write(tex)
    if (scaricato or copia_txt) and salva_txt:
        with open(os.path.join(cartella, nome_file), "w", encoding="utf-8") as f:
            f.write(testo)
    trova_immagini(cartella, log)
    avanzamento(f"Creato: {percorso_tex}")

    percorso_pdf = None
    if pdf:
        avanzamento("Compilo il PDF (due passate) ...")
        percorso_pdf = compila_pdf(percorso_tex, log)
        if percorso_pdf:
            avanzamento(f"Creato: {percorso_pdf}")

    registro.info("Convertito %s.%03d → %s (%s)%s", dati["anno"], dati["numero"], percorso_tex, log.riepilogo(),
                  " · PDF creato" if percorso_pdf else (" · PDF NON creato" if pdf else ""))
    for livello, _, msg in log.voci:
        if livello == "ERRORE" and msg.startswith(("pdflatex", "Compilazione PDF")):
            registro.error("%s.%03d: %s", dati["anno"], dati["numero"], msg)
    percorso_log = os.path.join(cartella, base + ".conversione.log")
    log.scrivi(percorso_log,
               f"Conversione Newsletter Ubuntu-it {dati['numero']:03d}.{dati['anno']}\n"
               f"Data: {dt.datetime.now():%d/%m/%Y %H:%M}\n"
               f"Origine: {origine}\n"
               f"Output: {percorso_tex}")
    avanzamento(f"Log:    {percorso_log}  ({log.riepilogo()})")
    return {"codice": 1 if log.conta("ERRORE") else 0, "cartella": cartella,
            "tex": percorso_tex, "pdf": percorso_pdf, "log": percorso_log,
            "voci": log.voci, "dati": dati, "log_obj": log}


MSG_BLOCCATO = ("Il wiki ha rifiutato il download automatico ({e}).\n\n"
                "Apri nel browser " + WIKI_IT + "/" + PAGINA_NEWSLETTER + "/AAAA.NNN?action=raw,\n"
                "salva la pagina come .txt e convertila come file locale.")


# ---------------------------------------------------------------------------
# GUI (tkinter)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# LOG DI SISTEMA
# ---------------------------------------------------------------------------
# Ogni avvio scrive in ~/.local/state/newsletter2tex/newsletter2tex.log cosa succede e,
# soprattutto, ogni errore con i dettagli tecnici. Il file ruota da solo (4 file da 1 MB).

registro = logging.getLogger("newsletter2tex")
registro.addHandler(logging.NullHandler())


def file_log_sistema():
    cartella = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
                            "newsletter2tex")
    return os.path.join(cartella, "newsletter2tex.log")


def avvia_registro(modalita):
    "Apre il log di sistema e registra le informazioni sull'avvio. Non fallisce mai."
    if any(isinstance(h, logging.FileHandler) for h in registro.handlers):
        return file_log_sistema()
    percorso = file_log_sistema()
    try:
        os.makedirs(os.path.dirname(percorso), exist_ok=True)
        gestore = logging.handlers.RotatingFileHandler(percorso, maxBytes=1_000_000, backupCount=3,
                                                       encoding="utf-8")
    except OSError:
        return None
    gestore.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s %(message)s", "%Y-%m-%d %H:%M:%S"))
    registro.addHandler(gestore)
    registro.setLevel(logging.INFO)
    registro.info("=" * 70)
    registro.info("Avvio di newsletter2tex %s (%s)", VERSIONE, modalita)
    registro.info("Python %s · %s", platform.python_version(), platform.platform())
    registro.info("Programma: %s%s", os.path.realpath(sys.argv[0]),
                  " (copia installata)" if programma_installato() else "")
    try:
        cfg = carica_config()
        registro.info("Impostazioni: cartella %s · tema %s · avvisi %s · aggiornamenti automatici %s",
                      cfg.get("cartella_lavoro"), cfg.get("tema") or "come Ubuntu",
                      "sì" if cfg.get("notifiche", True) else "no",
                      "sì" if cfg.get("aggiornamenti_automatici", True) else "no")
    except Exception:
        registro.exception("Impostazioni illeggibili")

    gancio_originale = sys.excepthook

    def gancio(tipo, valore, tb):
        if not issubclass(tipo, KeyboardInterrupt):
            registro.critical("Errore non gestito:\n%s", "".join(traceback.format_exception(tipo, valore, tb)))
        gancio_originale(tipo, valore, tb)
    sys.excepthook = gancio

    if hasattr(threading, "excepthook"):
        def gancio_thread(argomenti):
            registro.critical("Errore non gestito nel thread %s:\n%s", getattr(argomenti.thread, "name", "?"),
                              "".join(traceback.format_exception(argomenti.exc_type, argomenti.exc_value,
                                                                 argomenti.exc_traceback)))
        threading.excepthook = gancio_thread
    return percorso


def coda_log_sistema(righe=40):
    try:
        with open(file_log_sistema(), encoding="utf-8", errors="replace") as f:
            return f.readlines()[-righe:]
    except OSError:
        return []


# ---------------------------------------------------------------------------
# AGGIORNAMENTI DA GITHUB
# ---------------------------------------------------------------------------

URL_REPO = "https://github.com/danieledemichele/newsletter2tex"
URL_SCRIPT = "https://raw.githubusercontent.com/danieledemichele/newsletter2tex/main/newsletter2tex.py"
PERCORSO_INSTALLATO = os.path.expanduser("~/.local/bin/newsletter2tex")


def versione_tupla(v):
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


def _scarica_url(url, limite=None, timeout=20):
    intestazioni = {"User-Agent": USER_AGENT, "Cache-Control": "no-cache"}
    if limite:
        intestazioni["Range"] = f"bytes=0-{limite - 1}"
    req = urllib.request.Request(url, headers=intestazioni)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limite) if limite else r.read()


def versione_remota():
    "Versione pubblicata su GitHub (legge solo l'inizio del file)."
    testo = _scarica_url(URL_SCRIPT, limite=65536).decode("utf-8", errors="replace")
    m = re.search(r'^VERSIONE = "([\d.]+)"', testo, re.M)
    return m.group(1) if m else None


def programma_installato():
    "True se è in esecuzione la copia installata da installa.sh (l'unica che si aggiorna da sola)."
    try:
        return os.path.realpath(sys.argv[0]) == os.path.realpath(PERCORSO_INSTALLATO)
    except OSError:
        return False


def aggiorna_programma(destinazione=PERCORSO_INSTALLATO):
    """Scarica da GitHub la versione più recente e sostituisce la copia installata.
    Il file viene verificato prima di sostituire quello vecchio. Ritorna la nuova versione,
    oppure None se quella installata è già la più recente."""
    codice = _scarica_url(URL_SCRIPT, timeout=60)
    testo = codice.decode("utf-8")
    m = re.search(r'^VERSIONE = "([\d.]+)"', testo, re.M)
    if not m or "def avvia_gui" not in testo or "def converti(" not in testo:
        raise RuntimeError("Il file scaricato da GitHub non sembra newsletter2tex: aggiornamento annullato")
    try:
        compile(testo, destinazione, "exec")
    except SyntaxError as e:
        raise RuntimeError(f"Il file scaricato contiene un errore ({e}): aggiornamento annullato")
    if versione_tupla(m.group(1)) <= versione_tupla(VERSIONE):
        return None
    registro.info("Aggiornamento: installo la versione %s in %s", m.group(1), destinazione)
    temporaneo = destinazione + ".nuovo"
    with open(temporaneo, "wb") as f:
        f.write(codice)
    os.chmod(temporaneo, 0o755)
    os.replace(temporaneo, destinazione)      # sostituzione atomica: mai un file a metà
    return m.group(1)


# ---------------------------------------------------------------------------
# BLOCCO ANTI-BOT: pagina nel browser, testo salvato in Scaricati
# ---------------------------------------------------------------------------

def cartelle_utente():
    "Cartelle XDG dell'utente (Scrivania, Documenti, Scaricati…) da ~/.config/user-dirs.dirs."
    trovate = {}
    casa = os.path.expanduser("~")
    try:
        with open(os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(casa, ".config")),
                               "user-dirs.dirs"), encoding="utf-8") as f:
            for riga in f:
                m = re.match(r'XDG_(\w+)_DIR="(.+)"', riga.strip())
                if m:
                    trovate[m.group(1)] = m.group(2).replace("$HOME", casa)
    except OSError:
        pass
    return trovate


def cartella_scaricati():
    casa = os.path.expanduser("~")
    for p in (cartelle_utente().get("DOWNLOAD"), os.path.join(casa, "Scaricati"),
              os.path.join(casa, "Downloads")):
        if p and os.path.isdir(p):
            return p
    return casa


def url_raw(anno, num):
    return f"{WIKI_IT}/{PAGINA_NEWSLETTER}/{anno}.{num:03d}?action=raw"


def url_allegati(cfg, anno, num):
    """Pagina «Allegati» del wiki dove caricare il PDF del numero."""
    pagina = (cfg.get("pagina_allegati") or CONFIG_PREDEFINITA["pagina_allegati"]).format(
        anno=anno, numero=f"{num:03d}")
    return f"{WIKI_IT}/{urllib.parse.quote(pagina)}?action=AttachFile"


def mostra_nella_cartella(percorso):
    """Apre il gestore file con il file già selezionato (Nautilus), altrimenti la cartella."""
    for comando in (["nautilus", "--select", percorso],
                    ["dbus-send", "--session", "--dest=org.freedesktop.FileManager1", "--type=method_call",
                     "/org/freedesktop/FileManager1", "org.freedesktop.FileManager1.ShowItems",
                     "array:string:file://" + urllib.parse.quote(percorso), "string:"]):
        if shutil.which(comando[0]):
            try:
                subprocess.Popen(comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except OSError:
                pass
    apri_nel_browser(os.path.dirname(percorso))


def apri_nel_browser(url):
    try:
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        import webbrowser
        webbrowser.open(url)


def cerca_txt_salvato(cartella, dopo, anno=None, num=None):
    """Il testo della newsletter salvato nella cartella dopo l'istante 'dopo' (il browser può
    chiamarlo «2026.031», «2026.031.txt», «NewsletterItaliana_2026.031.txt»…). Se anno e num
    sono indicati, deve essere proprio quel numero."""
    try:
        voci = sorted(os.scandir(cartella), key=lambda v: v.stat().st_mtime, reverse=True)
    except OSError:
        return None
    for v in voci:
        nome = v.name.lower()
        if not v.is_file() or nome.endswith((".part", ".crdownload", ".tmp", ".download")):
            continue
        st = v.stat()
        if st.st_mtime < dopo - 2:
            break                                   # i successivi sono più vecchi
        if st.st_size == 0 or st.st_size > 5 * 1024 * 1024:
            continue
        try:
            with open(v.path, encoding="utf-8", errors="replace") as f:
                testo = f.read()
        except OSError:
            continue
        if not e_un_numero(testo):
            continue
        if anno and num:
            m = re.search(r"Questo è il numero\s*'*\s*(\d+)\s*'*\s*del\s*'*\s*(\d{4})", testo)
            if not m or (int(m.group(2)), int(m.group(1))) != (anno, num):
                continue
        return v.path
    return None


# ---------------------------------------------------------------------------
# AVVISO DEI NUOVI NUMERI (timer di systemd + notifica desktop)
# ---------------------------------------------------------------------------

NOME_UNITA = "newsletter2tex-controllo"
# il nuovo numero esce di solito tra il lunedì notte e il martedì
ORARI_CONTROLLO = ("Mon 21:30", "Tue 08:15", "Tue 13:15", "Tue 19:15", "Wed 09:15")


def cartella_systemd():
    return os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                        "systemd", "user")


def testo_unita(script=PERCORSO_INSTALLATO):
    servizio = ("[Unit]\nDescription=Newsletter Ubuntu-it: controllo dei nuovi numeri\n"
                "After=network-online.target\n\n[Service]\nType=oneshot\n"
                f"ExecStart=/usr/bin/env python3 {script} --notifica\nTimeoutStartSec=4h\n")
    timer = ("[Unit]\nDescription=Newsletter Ubuntu-it: controllo il lunedì sera e il martedì\n\n[Timer]\n"
             + "".join(f"OnCalendar={o}\n" for o in ORARI_CONTROLLO)
             + "Persistent=true\nRandomizedDelaySec=10min\n\n[Install]\nWantedBy=timers.target\n")
    return servizio, timer


def _systemctl(*argomenti):
    r = subprocess.run(["systemctl", "--user", *argomenti], capture_output=True, text=True, timeout=30)
    return r.returncode, (r.stderr or r.stdout).strip()


def imposta_notifiche(attive, script=PERCORSO_INSTALLATO):
    "Attiva o disattiva il controllo automatico dei nuovi numeri. Ritorna un messaggio."
    if not shutil.which("systemctl"):
        raise RuntimeError("systemd non è disponibile: avviso dei nuovi numeri non attivabile")
    cartella = cartella_systemd()
    servizio_p = os.path.join(cartella, NOME_UNITA + ".service")
    timer_p = os.path.join(cartella, NOME_UNITA + ".timer")
    if attive:
        os.makedirs(cartella, exist_ok=True)
        servizio, timer = testo_unita(script)
        for percorso, testo in ((servizio_p, servizio), (timer_p, timer)):
            with open(percorso, "w", encoding="utf-8") as f:
                f.write(testo)
        _systemctl("daemon-reload")
        _systemctl("enable", NOME_UNITA + ".timer")
        collegamento = os.path.join(cartella, "timers.target.wants", NOME_UNITA + ".timer")
        if not os.path.exists(collegamento):
            raise RuntimeError("systemctl non ha abilitato il controllo automatico")
        codice, _ = _systemctl("start", NOME_UNITA + ".timer")
        if codice:      # es. installazione da SSH, senza sessione: partirà al prossimo accesso
            return "Avviso dei nuovi numeri abilitato: sarà attivo dal prossimo accesso al desktop"
        registro.info("Avviso dei nuovi numeri attivato")
        return "Avviso dei nuovi numeri attivo: controllo il lunedì sera e il martedì"
    registro.info("Avviso dei nuovi numeri disattivato")
    _systemctl("disable", "--now", NOME_UNITA + ".timer")
    for percorso in (servizio_p, timer_p):
        if os.path.exists(percorso):
            os.remove(percorso)
    _systemctl("daemon-reload")
    return "Avviso dei nuovi numeri disattivato"


def notifiche_attive():
    if not shutil.which("systemctl"):
        return False
    try:
        return _systemctl("is-enabled", NOME_UNITA + ".timer")[1] == "enabled"
    except (OSError, subprocess.SubprocessError):
        return False


def invia_notifica(titolo, testo, azione=None):
    "Notifica desktop; con azione restituisce 'apri' se l'utente la sceglie."
    if not shutil.which("notify-send"):
        return None
    icona = PERCORSO_ICONA if os.path.exists(PERCORSO_ICONA) else "newsletter2tex"
    base = ["notify-send", "-a", "Newsletter Ubuntu-it", "-i", icona, titolo, testo]
    if azione:
        try:
            r = subprocess.run(base + ["-A", f"apri={azione}"], capture_output=True, text=True, timeout=4 * 3600)
            if r.returncode == 0:
                return r.stdout.strip() or None
        except subprocess.TimeoutExpired:
            return None
        # notify-send senza supporto per le azioni (Ubuntu 22.04): notifica semplice
    subprocess.run(base, capture_output=True, timeout=30)
    return None


def file_notificati():
    return os.path.join(os.path.dirname(CONFIG_FILE), "notificati.json")


def notifica_nuovi_numeri():
    """Eseguito dal timer: se c'è un numero nuovo non ancora convertito e non ancora
    segnalato, manda una notifica (una sola volta per numero)."""
    cfg = carica_config()
    try:
        n = controlla_novita(cfg)
    except Exception as e:
        registro.warning("Controllo programmato: wiki non raggiungibile (%s)", e)
        return False                       # si riproverà al prossimo orario
    registro.info("Controllo programmato: ultimo numero %s.%03d, da convertire %s", n.get("anno"),
                  n.get("numero") or 0, n.get("mancanti") or "nessuno")
    if not n["mancanti"]:
        return False
    chiave = f"{n['anno']}.{n['numero']:03d}"
    try:
        with open(file_notificati(), encoding="utf-8") as f:
            notificati = json.load(f)
    except (OSError, ValueError):
        notificati = []
    if chiave in notificati:
        return False
    notificati = (notificati + [chiave])[-30:]
    os.makedirs(os.path.dirname(file_notificati()), exist_ok=True)
    with open(file_notificati(), "w", encoding="utf-8") as f:
        json.dump(notificati, f)
    articoli = len(n["anteprima"]["articoli"])
    testo = (f"{n['anteprima']['settimana'].capitalize()} · {articoli} articoli.\n"
             "Apri Newsletter Ubuntu-it per convertirlo.")
    registro.info("Notifica inviata per il numero %s", chiave)
    scelta = invia_notifica(f"È uscito il numero {n['numero']:03d}/{n['anno']}", testo, azione="Apri")
    if scelta == "apri":
        subprocess.Popen([sys.executable, os.path.realpath(sys.argv[0]), "--gui"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


PALETTE = {
    "chiaro": {
        "SFONDO": "#F2F0EE", "LATERALE": "#EAE6E2", "SCHEDA": "#FFFFFF", "BORDO": "#E2DDD8",
        "BORDO_FORTE": "#CFC8C2", "TESTO": "#2B2B2B", "TENUE": "#7A746F", "GRIGIO_CALDO": "#AEA79F",
        "ARANCIO_HOVER": "#C7441A", "ARANCIO_TENUE": "#FBE3D9", "ARANCIO_SPENTO": "#F3B59E",
        "PRIMARIO_SPENTO_TESTO": "#FFFFFF",
        "HOVER": "#F7F3F0", "PIATTO_HOVER": "#E4DED9", "DISABILITATO": "#C2BBB5",
        "TRACCIA": "#E6E0DB", "INTERRUTTORE_OFF": "#D6D0CB", "SEGMENTATO": "#ECE7E3",
        "RIGA_PARI": "#FBFAF9", "CONSOLE": "#2C001E",
        "ROSSO": "#E5484D", "ROSSO_TENUE": "#FDE7E7", "AMBRA": "#F5A524", "AMBRA_TESTO": "#9A6100",
        "AMBRA_TENUE": "#FEF2DC", "VERDE": "#3FB950", "VERDE_TESTO": "#1F7A31", "VERDE_TENUE": "#E3F6E6",
        "REFUSO_TESTO": "#77216F", "REFUSO_TENUE": "#F3E6F1",
    },
    "scuro": {
        "SFONDO": "#1A1418", "LATERALE": "#1F181D", "SCHEDA": "#251D23", "BORDO": "#382C34",
        "BORDO_FORTE": "#4D3F48", "TESTO": "#EEE8EC", "TENUE": "#A79AA3", "GRIGIO_CALDO": "#7C6F78",
        "ARANCIO_HOVER": "#F26B3A", "ARANCIO_TENUE": "#4B2617", "ARANCIO_SPENTO": "#3F2620",
        "PRIMARIO_SPENTO_TESTO": "#8E7A72",
        "HOVER": "#2E242B", "PIATTO_HOVER": "#3A2E36", "DISABILITATO": "#6A5E66",
        "TRACCIA": "#3A2E36", "INTERRUTTORE_OFF": "#4D3F48", "SEGMENTATO": "#2E242B",
        "RIGA_PARI": "#2A2128", "CONSOLE": "#130C11",
        "ROSSO": "#FF6B70", "ROSSO_TENUE": "#4A1C20", "AMBRA": "#F5A524", "AMBRA_TESTO": "#FFC266",
        "AMBRA_TENUE": "#45330F", "VERDE": "#3FB950", "VERDE_TESTO": "#7EE787", "VERDE_TENUE": "#173A1F",
        "REFUSO_TESTO": "#E59AD8", "REFUSO_TENUE": "#3D1D39",
    },
}


def tema_di_sistema():
    # "scuro" se Ubuntu/GNOME usa lo stile scuro, altrimenti "chiaro"
    for chiave in ("color-scheme", "gtk-theme"):
        try:
            r = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", chiave],
                               capture_output=True, text=True, timeout=3)
            if "dark" in r.stdout.lower():
                return "scuro"
        except (OSError, subprocess.SubprocessError):
            break
    return "chiaro"


def miniatura_pdf(pdf, larghezza=104):
    # Copertina del PDF in PNG (con pdftoppm di poppler-utils) e numero di pagine
    if not (pdf and os.path.exists(pdf) and shutil.which("pdftoppm")):
        return None
    cache = os.path.join(os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "newsletter2tex")
    os.makedirs(cache, exist_ok=True)
    base = os.path.join(cache, "copertina")
    try:
        subprocess.run(["pdftoppm", "-png", "-singlefile", "-f", "1", "-l", "1",
                        "-scale-to-x", str(larghezza), "-scale-to-y", "-1", pdf, base],
                       capture_output=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    pagine = None
    if shutil.which("pdfinfo"):
        try:
            info = subprocess.run(["pdfinfo", pdf], capture_output=True, text=True, timeout=15).stdout
            m = re.search(r"^Pages:\s+(\d+)", info, re.M)
            pagine = int(m.group(1)) if m else None
        except (OSError, subprocess.SubprocessError):
            pass
    return {"png": base + ".png", "pagine": pagine, "dimensione": os.path.getsize(pdf)}


def avvia_gui(prova=None):
    try:
        import tkinter as tk
    except ImportError:
        sys.exit("Per l'interfaccia grafica serve tkinter:  sudo apt install python3-tk")
    # className: la dock/barra delle applicazioni associa la finestra al lanciatore
    root = tk.Tk(className="newsletter2tex")
    root.title("Newsletter Ubuntu-it")
    root.minsize(1000, 600)
    root.geometry(f"1100x{min(800, root.winfo_screenheight() - 80)}")
    root._icone = [tk.PhotoImage(data=base64.b64encode(icona_png(g)).decode()) for g in (True, False)]
    root.iconphoto(True, *root._icone)
    registro.info("Interfaccia grafica: Tk %s, schermo %sx%s", root.tk.call("info", "patchlevel"),
                  root.winfo_screenwidth(), root.winfo_screenheight())

    def errore_interfaccia(tipo, valore, tb):
        # ogni errore nell'interfaccia finisce nel log di sistema (oltre che nel terminale)
        registro.error("Errore nell'interfaccia:\n%s", "".join(traceback.format_exception(tipo, valore, tb)))
        traceback.print_exception(tipo, valore, tb)
    root.report_callback_exception = errore_interfaccia

    def chiudi():
        registro.info("Chiusura della finestra")
        root.destroy()
    root.protocol("WM_DELETE_WINDOW", chiudi)
    _finestra(root, prova, None)
    root.mainloop()


def _finestra(root, prova=None, stato=None):
    # Costruisce (o ricostruisce, al cambio di tema) il contenuto della finestra
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import ttk, messagebox
    import queue
    import threading

    for w in root.winfo_children():
        if not getattr(w, "_velo", False):
            w.destroy()
    for evento in ("<Button-4>", "<Button-5>", "<MouseWheel>"):
        root.unbind_all(evento)

    stato = stato or {}
    cfg = carica_config()
    root_generazione = root.__dict__.setdefault("_generazione", [0])
    root_generazione[0] += 1
    generazione = root_generazione[0]
    tema = stato.get("tema") or cfg.get("tema") or tema_di_sistema()
    if tema not in PALETTE:
        tema = "chiaro"
    P = PALETTE[tema]

    # --- palette Ubuntu -----------------------------------------------------
    ARANCIO = "#E95420"
    ARANCIO_HOVER = P["ARANCIO_HOVER"]
    ARANCIO_TENUE = P["ARANCIO_TENUE"]
    ARANCIO_SPENTO = P["ARANCIO_SPENTO"]
    MELANZANA_SCURA = "#2C001E"
    MELANZANA = "#5E2750"
    MELANZANA_VIVA = "#77216F"
    SFONDO = P["SFONDO"]
    LATERALE = P["LATERALE"]
    SCHEDA = P["SCHEDA"]
    BORDO = P["BORDO"]
    BORDO_FORTE = P["BORDO_FORTE"]
    TESTO = P["TESTO"]
    TENUE = P["TENUE"]
    GRIGIO_CALDO = P["GRIGIO_CALDO"]
    HOVER, PIATTO_HOVER, DISABILITATO = P["HOVER"], P["PIATTO_HOVER"], P["DISABILITATO"]
    TRACCIA, INTERRUTTORE_OFF, SEGMENTATO = P["TRACCIA"], P["INTERRUTTORE_OFF"], P["SEGMENTATO"]
    RIGA_PARI, CONSOLE = P["RIGA_PARI"], P["CONSOLE"]
    CONSOLE_TESTO = "#F1E6EE"
    CONSOLE_TENUE = "#B9A3B4"
    ROSSO, ROSSO_TENUE = P["ROSSO"], P["ROSSO_TENUE"]
    AMBRA, AMBRA_TESTO, AMBRA_TENUE = P["AMBRA"], P["AMBRA_TESTO"], P["AMBRA_TENUE"]
    VERDE, VERDE_TESTO, VERDE_TENUE = P["VERDE"], P["VERDE_TESTO"], P["VERDE_TENUE"]
    REFUSO_TESTO, REFUSO_TENUE = P["REFUSO_TESTO"], P["REFUSO_TENUE"]

    import math
    casa = os.path.expanduser("~")
    root.configure(bg=SFONDO)

    immagini = {}   # riferimenti alle PhotoImage (altrimenti il garbage collector le cancella)

    def immagine_icona(grande):
        if grande not in immagini:
            immagini[grande] = tk.PhotoImage(data=base64.b64encode(icona_png(grande)).decode())
        return immagini[grande]


    famiglie = {f.lower(): f for f in tkfont.families(root)}
    sans = next((famiglie[f.lower()] for f in ("Ubuntu", "Ubuntu Sans", "Cantarell", "Noto Sans", "DejaVu Sans")
                 if f.lower() in famiglie), "TkDefaultFont")
    mono = next((famiglie[f.lower()] for f in ("Ubuntu Mono", "Ubuntu Sans Mono", "DejaVu Sans Mono",
                                               "Noto Mono") if f.lower() in famiglie), "TkFixedFont")
    F = {
        "titolo": tkfont.Font(family=sans, size=17, weight="bold"),
        "sottotitolo": tkfont.Font(family=sans, size=10),
        "scheda": tkfont.Font(family=sans, size=11, weight="bold"),
        "testo": tkfont.Font(family=sans, size=10),
        "piccolo": tkfont.Font(family=sans, size=9),
        "piccolo_b": tkfont.Font(family=sans, size=9, weight="bold"),
        "bottone": tkfont.Font(family=sans, size=10, weight="bold"),
        "grande": tkfont.Font(family=sans, size=11, weight="bold"),
        "enorme": tkfont.Font(family=sans, size=20, weight="bold"),
        "numero": tkfont.Font(family=sans, size=22, weight="bold"),
        "mono": tkfont.Font(family=mono, size=9),
        "mono_b": tkfont.Font(family=mono, size=9, weight="bold"),
    }
    root.option_add("*Font", F["testo"])

    stile = ttk.Style(root)
    if "clam" in stile.theme_names():
        stile.theme_use("clam")
    stile.configure("Esplora.Treeview", background=SCHEDA, fieldbackground=SCHEDA, foreground=TESTO,
                    rowheight=30, borderwidth=0, relief="flat", font=F["testo"])
    stile.map("Esplora.Treeview", background=[("selected", ARANCIO_TENUE)],
              foreground=[("selected", TESTO)])
    stile.configure("Esplora.Treeview.Heading", background=SCHEDA, foreground=TENUE, relief="flat",
                    borderwidth=0, font=F["piccolo_b"], padding=(8, 6))
    stile.map("Esplora.Treeview.Heading", background=[("active", HOVER)])
    stile.layout("Esplora.Treeview", [("Esplora.Treeview.treearea", {"sticky": "nswe"})])

    class Suggerimento:
        # Piccola etichetta che compare al passaggio del mouse
        def __init__(self):
            self.top = None

        def mostra(self, testo, x, y):
            self.nascondi()
            self.top = tk.Toplevel(root)
            self.top.wm_overrideredirect(True)
            tk.Label(self.top, text=testo, bg="#1F161C", fg="#F1E6EE", font=F["piccolo"],
                     padx=9, pady=5).pack()
            self.top.wm_geometry(f"+{x}+{y}")

        def nascondi(self):
            if self.top:
                self.top.destroy()
                self.top = None

    suggerimento = Suggerimento()

    def con_suggerimento(widget, testo):
        widget.bind("<Enter>", lambda e: suggerimento.mostra(
            testo() if callable(testo) else testo, e.x_root + 12, e.y_root + 18), add="+")
        widget.bind("<Leave>", lambda e: suggerimento.nascondi(), add="+")

    # --- forme con antialiasing ----------------------------------------------
    # Il Canvas di Tk su Linux disegna cerchi, curve e linee spesse senza antialiasing: i bordi
    # restano a scalette. Le parti curve si generano quindi come piccole immagini PNG con
    # trasparenza (4×4 campioni per pixel), tenute in memoria e riusate; i tratti dritti restano
    # rettangoli del Canvas, che sono già nitidi.
    forme = {}
    colori_rgb = {}

    def rgb(colore):
        if colore not in colori_rgb:
            r, g, b = root.winfo_rgb(colore)
            colori_rgb[colore] = (r >> 8, g >> 8, b >> 8)
        return colori_rgb[colore]

    def immagine_liscia(chiave, larghezza, altezza, strati):
        """strati: [(colore o None, dentro(x, y))]; vince l'ultimo strato che contiene il punto,
        None lo rende trasparente (per i ritagli, come la luna)."""
        if chiave in forme:
            return forme[chiave]
        campioni = [(i + 0.5) / 4 for i in range(4)]
        strati = [(rgb(col) if col else None, dentro) for col, dentro in reversed(strati)]
        pixel = bytearray(larghezza * altezza * 4)
        for y in range(altezza):
            for x in range(larghezza):
                rs = gs = bs = n = 0
                for sy in campioni:
                    for sx in campioni:
                        for col, dentro in strati:
                            if dentro(x + sx, y + sy):
                                if col:
                                    rs += col[0]
                                    gs += col[1]
                                    bs += col[2]
                                    n += 1
                                break
                if n:
                    i = (y * larghezza + x) * 4
                    pixel[i:i + 4] = bytes((rs // n, gs // n, bs // n, (255 * n + 8) // 16))
        forme[chiave] = tk.PhotoImage(data=base64.b64encode(png_rgba(larghezza, altezza, pixel)).decode())
        return forme[chiave]

    def angolo(r, fill, outline, quale, w=1):
        cx = r if quale[1] == "w" else 0
        cy = r if quale[0] == "n" else 0
        esterno = lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r
        interno = lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= max(0, r - w) ** 2
        if outline:
            strati = [(outline, esterno), (fill or None, interno)]
        else:
            strati = [(fill, esterno)]
        return immagine_liscia(("angolo", r, fill, outline, quale, w), r, r, strati)

    def rettangolo_arrotondato(c, x1, y1, x2, y2, r, fill="", outline="", tags=(), width=1):
        X1, Y1, X2, Y2 = (int(round(v)) for v in (x1, y1, x2, y2))
        if X2 <= X1 or Y2 <= Y1:
            return
        R = int(round(max(0, min(r, (X2 - X1) / 2, (Y2 - Y1) / 2))))
        t = {"tags": tags} if tags else {}
        if fill:
            c.create_rectangle(X1 + R, Y1, X2 - R, Y2, fill=fill, outline="", **t)
            if Y2 - Y1 > 2 * R:
                c.create_rectangle(X1, Y1 + R, X1 + R, Y2 - R, fill=fill, outline="", **t)
                c.create_rectangle(X2 - R, Y1 + R, X2, Y2 - R, fill=fill, outline="", **t)
        if outline:
            w = max(1, int(round(width)))
            for a, b, cc, d in ((X1 + R, Y1, X2 - R, Y1 + w), (X1 + R, Y2 - w, X2 - R, Y2),
                                (X1, Y1 + R, X1 + w, Y2 - R), (X2 - w, Y1 + R, X2, Y2 - R)):
                if cc > a and d > b:
                    c.create_rectangle(a, b, cc, d, fill=outline, outline="", **t)
        if R > 0 and (fill or outline):
            for quale, x, y in (("nw", X1, Y1), ("ne", X2 - R, Y1), ("sw", X1, Y2 - R), ("se", X2 - R, Y2 - R)):
                c.create_image(x, y, image=angolo(R, fill, outline, quale, max(1, int(round(width)))),
                               anchor="nw", **t)

    def disco(c, cx, cy, r, fill, ritaglio=None, tags=()):
        """Cerchio pieno; ritaglio=(dx, dy, r2) toglie un secondo cerchio (falce di luna)."""
        n = int(math.ceil(r)) + 1
        strati = [(fill, lambda x, y: (x - n) ** 2 + (y - n) ** 2 <= r * r)]
        if ritaglio:
            dx, dy, r2 = ritaglio
            strati.append((None, lambda x, y: (x - n - dx) ** 2 + (y - n - dy) ** 2 <= r2 * r2))
        img = immagine_liscia(("disco", r, fill, ritaglio), 2 * n, 2 * n, strati)
        return c.create_image(round(cx), round(cy), image=img, anchor="center", **({"tags": tags} if tags else {}))

    def linea(c, punti, spessore, colore, tags=()):
        """Spezzata con estremi arrotondati."""
        m = spessore / 2 + 1
        x0, y0 = math.floor(min(punti[0::2]) - m), math.floor(min(punti[1::2]) - m)
        larghezza = math.ceil(max(punti[0::2]) + m) - x0
        altezza = math.ceil(max(punti[1::2]) + m) - y0
        rel = [round(v - (x0 if i % 2 == 0 else y0), 3) for i, v in enumerate(punti)]
        segmenti = [rel[i:i + 4] for i in range(0, len(rel) - 2, 2)]
        r2 = (spessore / 2) ** 2

        def dentro(x, y):
            for ax, ay, bx, by in segmenti:
                dx, dy = bx - ax, by - ay
                lung = dx * dx + dy * dy
                k = 0 if not lung else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / lung))
                ex, ey = ax + k * dx - x, ay + k * dy - y
                if ex * ex + ey * ey <= r2:
                    return True
            return False
        img = immagine_liscia(("linea", tuple(rel), spessore, colore), larghezza, altezza, [(colore, dentro)])
        return c.create_image(x0, y0, image=img, anchor="nw", **({"tags": tags} if tags else {}))

    def fascia(c, larghezza, altezza, colore1, colore2):
        """Sfumatura orizzontale continua (un pixel per colonna, senza bande)."""
        larghezza = max(1, int(larghezza))
        (r1, g1, b1), (r2, g2, b2) = rgb(colore1), rgb(colore2)
        colonne = []
        for i in range(larghezza):
            k = i / max(larghezza - 1, 1)
            colonne.append("#%02x%02x%02x" % (round(r1 + (r2 - r1) * k), round(g1 + (g2 - g1) * k),
                                               round(b1 + (b2 - b1) * k)))
        img = tk.PhotoImage(width=larghezza, height=altezza)
        img.put("{" + " ".join(colonne) + "}", to=(0, 0, larghezza, altezza))
        c._fascia = img                     # una per canvas: sostituisce la precedente
        return c.create_image(0, 0, image=img, anchor="nw")

    # --- componenti -----------------------------------------------------------

    def traccia(widget, variabile, funzione):
        # collega funzione() alle modifiche di variabile finché widget esiste;
        # senza questo, chiudere un popup lasciava tracce verso widget distrutti
        def chiama(*_):
            try:
                if widget.winfo_exists():
                    funzione()
            except tk.TclError:
                pass
        tid = variabile.trace_add("write", chiama)

        def rimuovi(e):
            if e.widget is widget:
                try:
                    variabile.trace_remove("write", tid)
                except (tk.TclError, ValueError):
                    pass
        widget.bind("<Destroy>", rimuovi, add="+")

    class Pannello(tk.Canvas):
        "Contenitore con angoli arrotondati; .interno è il Frame dove mettere i widget."

        def __init__(self, parent, sfondo=None, bordo=None, r=16, padx=18, pady=14, riempi=False):
            super().__init__(parent, bg=parent["bg"], highlightthickness=0, bd=0, height=20, width=20)
            self.sfondo, self.bordo, self.r, self.riempi = sfondo or SCHEDA, bordo or BORDO, r, riempi
            self.inset = max(4, int(r * 0.35))
            self.interno = tk.Frame(self, bg=self.sfondo, padx=max(0, padx - self.inset),
                                    pady=max(0, pady - self.inset))
            self.win = self.create_window(self.inset, self.inset, window=self.interno, anchor="nw")
            self.bind("<Configure>", self._ridisegna)
            if not riempi:
                self.interno.bind("<Configure>", self._adatta)

        def _adatta(self, _=None):
            h = self.interno.winfo_reqheight() + 2 * self.inset
            if int(float(self["height"])) != h:
                self.configure(height=h)

        def _ridisegna(self, e):
            self.delete("fondo")
            rettangolo_arrotondato(self, 1, 1, e.width - 1, e.height - 1, self.r, fill=self.sfondo,
                                   outline=self.bordo, tags="fondo")
            self.tag_lower("fondo")
            self.itemconfigure(self.win, width=max(1, e.width - 2 * self.inset))
            if self.riempi:
                self.itemconfigure(self.win, height=max(1, e.height - 2 * self.inset))

    class Gettone(tk.Canvas):
        "Etichetta a pillola (conteggi di errori, avvisi, refusi); spenta = filtrata."

        def __init__(self, parent, colore, sfondo, comando=None):
            super().__init__(parent, height=24, width=10, bg=parent["bg"], highlightthickness=0,
                             cursor="hand2" if comando else "arrow")
            self.colore, self.sfondo, self.testo, self.acceso = colore, sfondo, "", True
            if comando:
                self.bind("<Button-1>", lambda e: comando())

        def configure_testo(self, testo=None, acceso=None):
            if testo is not None:
                self.testo = testo
            if acceso is not None:
                self.acceso = acceso
            self.delete("all")
            l = F["piccolo_b"].measure(self.testo) + 24
            self.configure(width=l)
            if self.acceso:
                rettangolo_arrotondato(self, 0, 0, l, 24, 12, fill=self.sfondo, outline="")
                colore = self.colore
            else:
                rettangolo_arrotondato(self, 1, 1, l - 1, 23, 11, fill=self["bg"], outline=BORDO_FORTE)
                colore = GRIGIO_CALDO
            self.create_text(l / 2, 12, text=self.testo, fill=colore, font=F["piccolo_b"])

    class Bottone(tk.Canvas):
        """Pulsante arrotondato: tipo 'primario' (arancione), 'secondario' o 'piatto'."""

        def __init__(self, parent, testo, comando=None, tipo="secondario", font=None, alto=36, padx=18,
                     espandi=False):
            self.font = font or F["bottone"]
            larg = self.font.measure(testo) + 2 * padx
            super().__init__(parent, width=larg, height=alto, bg=parent["bg"],
                             highlightthickness=0, bd=0, cursor="hand2")
            self.testo, self.comando, self.tipo = testo, comando, tipo
            self.l, self.a = larg, alto
            self.attivo, self.sopra = True, False
            self.bind("<Enter>", lambda e: self._hover(True))
            self.bind("<Leave>", lambda e: self._hover(False))
            self.bind("<ButtonRelease-1>", self._click)
            if espandi:
                self.bind("<Configure>", self._ridimensiona)
            self._disegna()

        def _ridimensiona(self, e):
            if e.width != self.l:
                self.l = e.width
                self._disegna()

        def _colori(self):
            if self.tipo == "primario":
                if not self.attivo:
                    return ARANCIO_SPENTO, ARANCIO_SPENTO, P["PRIMARIO_SPENTO_TESTO"]
                f = ARANCIO_HOVER if self.sopra else ARANCIO
                return f, f, "white"
            sfondo = self["bg"]
            if self.tipo == "piatto":
                if not self.attivo:
                    return sfondo, sfondo, DISABILITATO
                return ((PIATTO_HOVER if self.sopra else sfondo), (PIATTO_HOVER if self.sopra else sfondo),
                        TESTO)
            if not self.attivo:
                return SCHEDA, BORDO, DISABILITATO
            return (HOVER if self.sopra else SCHEDA), (BORDO_FORTE if self.sopra else BORDO), TESTO

        def _disegna(self):
            self.delete("all")
            riemp, bordo, col = self._colori()
            rettangolo_arrotondato(self, 1, 1, self.l - 1, self.a - 1, min(14, self.a / 2 - 2),
                                   fill=riemp, outline=bordo)
            self.create_text(self.l / 2, self.a / 2, text=self.testo, fill=col, font=self.font)

        def _hover(self, v):
            self.sopra = v
            self.configure(cursor="hand2" if self.attivo else "arrow")
            self._disegna()

        def _click(self, _):
            if self.attivo and self.comando:
                self.comando()

        def stato(self, attivo):
            self.attivo = attivo
            self._disegna()

    class BottoneFreccia(Bottone):
        """Pulsante di navigazione con freccia disegnata (non dipende dai font)."""

        def __init__(self, parent, direzione, comando):
            self.direzione = direzione
            super().__init__(parent, "", comando, tipo="piatto", alto=32, padx=16)

        def _disegna(self):
            self.delete("all")
            riemp, bordo, col = self._colori()
            rettangolo_arrotondato(self, 1, 1, self.l - 1, self.a - 1, 12, fill=riemp, outline=bordo)
            cx, cy, d = self.l / 2, self.a / 2, 5
            punti = {"sx": (cx + 2, cy - d, cx - 3, cy, cx + 2, cy + d),
                     "dx": (cx - 2, cy - d, cx + 3, cy, cx - 2, cy + d),
                     "su": (cx - d, cy + 2, cx, cy - 3, cx + d, cy + 2)}[self.direzione]
            linea(self, punti, 2, col)

    class Interruttore(tk.Frame):
        """Interruttore on/off con etichetta, legato a una BooleanVar."""

        def __init__(self, parent, testo, variabile):
            super().__init__(parent, bg=parent["bg"])
            self.var = variabile
            self.c = tk.Canvas(self, width=40, height=22, bg=parent["bg"], highlightthickness=0,
                               cursor="hand2")
            self.c.pack(side="left")
            et = tk.Label(self, text=testo, bg=parent["bg"], fg=TESTO, font=F["testo"], cursor="hand2")
            et.pack(side="left", padx=(8, 0))
            for w in (self.c, et):
                w.bind("<Button-1>", lambda e: self.var.set(not self.var.get()))
            traccia(self, self.var, self._disegna)
            self._disegna()

        def _disegna(self):
            c = self.c
            c.delete("all")
            on = self.var.get()
            rettangolo_arrotondato(c, 1, 1, 39, 21, 10, fill=ARANCIO if on else INTERRUTTORE_OFF, outline="")
            disco(c, 28 if on else 12, 11, 8, "white")

    class Spunta(tk.Frame):
        """Casella di spunta arrotondata."""

        def __init__(self, parent, testo, variabile, font=None):
            super().__init__(parent, bg=parent["bg"])
            self.var = variabile
            self.c = tk.Canvas(self, width=20, height=20, bg=parent["bg"], highlightthickness=0,
                               cursor="hand2")
            self.c.pack(side="left")
            et = tk.Label(self, text=testo, bg=parent["bg"], fg=TESTO, font=font or F["testo"],
                          cursor="hand2")
            et.pack(side="left", padx=(8, 0))
            for w in (self.c, et):
                w.bind("<Button-1>", lambda e: self.var.set(not self.var.get()))
            traccia(self, self.var, self._disegna)
            self._disegna()

        def _disegna(self):
            c = self.c
            c.delete("all")
            if self.var.get():
                rettangolo_arrotondato(c, 1, 1, 19, 19, 5, fill=ARANCIO, outline="")
                linea(c, (5, 10, 9, 14, 15, 6), 2.5, "white")
            else:
                rettangolo_arrotondato(c, 1, 1, 19, 19, 5, fill=SCHEDA, outline=BORDO_FORTE)

    class Segmentato(tk.Canvas):
        """Selettore a pillole (stile GNOME/Yaru)."""

        def __init__(self, parent, opzioni, variabile):
            self.opzioni, self.var = opzioni, variabile
            self.pad, self.a = 20, 34
            self.larghezze = [F["bottone"].measure(t) + 2 * self.pad for _, t in opzioni]
            super().__init__(parent, width=sum(self.larghezze) + 8, height=self.a + 8,
                             bg=parent["bg"], highlightthickness=0, cursor="hand2")
            self.bind("<Button-1>", self._click)
            traccia(self, self.var, self._disegna)
            self._disegna()

        def _disegna(self):
            self.delete("all")
            rettangolo_arrotondato(self, 1, 1, int(self["width"]) - 1, self.a + 7, 16,
                                   fill=SEGMENTATO, outline="")
            x = 4
            for (valore, testo), l in zip(self.opzioni, self.larghezze):
                scelto = self.var.get() == valore
                if scelto:
                    rettangolo_arrotondato(self, x, 4, x + l, self.a + 4, 13, fill=ARANCIO, outline="")
                self.create_text(x + l / 2, self.a / 2 + 4, text=testo, font=F["bottone"],
                                 fill="white" if scelto else TENUE)
                x += l

        def _click(self, e):
            x = 4
            for (valore, _), l in zip(self.opzioni, self.larghezze):
                if x <= e.x < x + l:
                    self.var.set(valore)
                    return
                x += l

    class Campo(tk.Canvas):
        "Casella di testo arrotondata, con bordo che si accende di arancione."

        def __init__(self, parent, variabile, larghezza=None, segnaposto=None):
            alto = F["testo"].metrics("linespace") + 18
            largo = F["testo"].measure("0") * larghezza + 28 if larghezza else 60
            super().__init__(parent, height=alto, width=largo, bg=parent["bg"], highlightthickness=0,
                             cursor="xterm")
            self.var, self.alto, self.fuoco = variabile, alto, False
            self.e = tk.Entry(self, textvariable=variabile, relief="flat", bd=0, bg=SCHEDA,
                              fg=TESTO, insertbackground=ARANCIO, font=F["testo"],
                              selectbackground=ARANCIO_TENUE, selectforeground=TESTO,
                              highlightthickness=0, width=1)
            self.win = self.create_window(13, alto / 2, window=self.e, anchor="w")
            self.ph = tk.Label(self, text=segnaposto or "", bg=SCHEDA, fg=GRIGIO_CALDO,
                               font=F["testo"], cursor="xterm", bd=0, padx=0, pady=0)
            self.ph.bind("<Button-1>", lambda e: self.e.focus_set())
            self.segnaposto = bool(segnaposto)
            self.e.bind("<FocusIn>", lambda e: self._fuoco(True))
            self.e.bind("<FocusOut>", lambda e: self._fuoco(False))
            self.bind("<Button-1>", lambda e: self.e.focus_set())
            self.bind("<Configure>", lambda e: self._disegna())
            traccia(self, variabile, self._segnaposto)
            self._segnaposto()

        def _fuoco(self, v):
            self.fuoco = v
            self._disegna()

        def _segnaposto(self):
            if self.segnaposto and not self.var.get():
                self.ph.place(x=13, y=self.alto / 2, anchor="w")
            else:
                self.ph.place_forget()

        def _disegna(self):
            self.delete("fondo")
            l = self.winfo_width()
            rettangolo_arrotondato(self, 1, 1, l - 1, self.alto - 1, 11, fill=SCHEDA,
                                   outline=ARANCIO if self.fuoco else BORDO_FORTE if False else BORDO,
                                   width=2 if self.fuoco else 1, tags="fondo")
            self.tag_lower("fondo")
            self.itemconfigure(self.win, width=max(10, l - 26))

    class Avanzamento(tk.Canvas):
        """Barra sottile con segmento che scorre."""

        def __init__(self, parent):
            super().__init__(parent, height=4, bg=parent["bg"], highlightthickness=0)
            self.pos, self.in_corso = 0.0, False
            self.bind("<Configure>", lambda e: self._disegna())

        def _disegna(self, pieno=None):
            self.delete("all")
            l = self.winfo_width()
            rettangolo_arrotondato(self, 0, 0, l, 4, 2, fill=TRACCIA, outline="")
            if pieno is not None:
                rettangolo_arrotondato(self, 0, 0, l, 4, 2, fill=pieno, outline="")
            elif self.in_corso:
                seg = l * 0.28
                x = (self.pos % 1.28 - 0.28) * l
                if min(l, x + seg) - max(0, x) > 4:
                    rettangolo_arrotondato(self, max(0, x), 0, min(l, x + seg), 4, 2, fill=ARANCIO,
                                           outline="")

        def _passo(self):
            if self.in_corso:
                self.pos += 0.02
                self._disegna()
                self.after(16, self._passo)

        def avvia(self):
            if not self.in_corso:
                self.in_corso, self.pos = True, 0.0
                self._passo()

        def ferma(self, colore=None):
            self.in_corso = False
            self._disegna(colore)

    def barra_scorrimento(parent, widget, sfondo, cursore):
        """Barra di scorrimento sottile disegnata, collegata a un Text o Treeview."""
        sb = tk.Canvas(parent, width=12, bg=sfondo, highlightthickness=0)
        pos = [0.0, 1.0]

        def disegna(primo=None, ultimo=None):
            if primo is not None:
                pos[:] = [float(primo), float(ultimo)]
            sb.delete("all")
            if pos[1] - pos[0] >= 0.999:
                return
            a = sb.winfo_height()
            y1, y2 = pos[0] * a, max(pos[1] * a, pos[0] * a + 24)
            rettangolo_arrotondato(sb, 3, y1, 9, y2, 3, fill=cursore, outline="")

        def trascina(e):
            meta = (pos[1] - pos[0]) / 2
            widget.yview_moveto(max(0.0, e.y / max(sb.winfo_height(), 1) - meta))
        sb.bind("<Button-1>", trascina)
        sb.bind("<B1-Motion>", trascina)
        sb.bind("<Configure>", lambda e: disegna())
        widget.configure(yscrollcommand=disegna)
        return sb

    class AreaScorrevole(tk.Frame):
        "Colonna che scorre con la rotella quando il contenuto non entra nella finestra."

        def __init__(self, parent):
            super().__init__(parent, bg=parent["bg"])
            self.c = tk.Canvas(self, bg=parent["bg"], highlightthickness=0, bd=0, yscrollincrement=24)
            self.interno = tk.Frame(self.c, bg=parent["bg"])
            self.win = self.c.create_window(0, 0, window=self.interno, anchor="nw")
            self.sb = barra_scorrimento(self, self.c, parent["bg"], BORDO_FORTE)
            self.c.pack(side="left", fill="both", expand=True)
            self.interno.bind("<Configure>", self._aggiorna)
            self.c.bind("<Configure>", self._aggiorna)
            root.bind_all("<Button-4>", self._rotella, add="+")
            root.bind_all("<Button-5>", self._rotella, add="+")
            root.bind_all("<MouseWheel>", self._rotella, add="+")

        def _aggiorna(self, _=None):
            self.c.itemconfigure(self.win, width=self.c.winfo_width())
            alto = self.interno.winfo_reqheight()
            self.c.configure(scrollregion=(0, 0, self.c.winfo_width(), alto))
            serve = alto > self.c.winfo_height() + 1
            if serve and not self.sb.winfo_ismapped():
                self.sb.pack(side="right", fill="y", padx=(6, 0), before=self.c)
            elif not serve and self.sb.winfo_ismapped():
                self.sb.pack_forget()
                self.c.yview_moveto(0)

        def _rotella(self, e):
            w = root.winfo_containing(e.x_root, e.y_root)
            if w is None or not str(w).startswith(str(self)) or not self.sb.winfo_ismapped():
                return
            passo = -1 if (getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0) else 1
            self.c.yview_scroll(passo * 2, "units")

        def in_fondo(self):
            root.update_idletasks()
            self._aggiorna()
            self.c.yview_moveto(1.0)

    def scheda(parent, titolo, sottotitolo=None, riempi=False):
        cornice = Pannello(parent, r=18, padx=20, pady=16, riempi=riempi)
        interno = cornice.interno
        testa = tk.Frame(interno, bg=SCHEDA)
        testa.pack(fill="x")
        segno = tk.Canvas(testa, width=4, height=18, bg=SCHEDA, highlightthickness=0)
        rettangolo_arrotondato(segno, 0, 0, 4, 18, 2, fill=ARANCIO, outline="")
        segno.pack(side="left", padx=(0, 10))
        tk.Label(testa, text=titolo, bg=SCHEDA, fg=TESTO, font=F["scheda"]).pack(side="left")
        if sottotitolo:
            tk.Label(testa, text=sottotitolo, bg=SCHEDA, fg=TENUE, font=F["piccolo"]).pack(
                side="left", padx=(10, 0))
        corpo = tk.Frame(interno, bg=SCHEDA)
        corpo.pack(fill="both", expand=True, pady=(12, 0))
        return cornice, corpo, testa

    def nota(parent, testo, colore=TENUE, font=None):
        return tk.Label(parent, text=testo, bg=parent["bg"], fg=colore, font=font or F["piccolo"],
                        justify="left", anchor="w")

    def finestra_modale(titolo, larghezza, altezza):
        top = tk.Toplevel(root, bg=SFONDO)
        top.title(titolo)
        top.transient(root)
        top.resizable(True, True)
        root.update_idletasks()
        x = root.winfo_rootx() + max(0, (root.winfo_width() - larghezza) // 2)
        y = root.winfo_rooty() + max(0, (root.winfo_height() - altezza) // 3)
        top.geometry(f"{larghezza}x{altezza}+{x}+{y}")
        top.minsize(min(larghezza, 560), min(altezza, 380))
        top.bind("<Escape>", lambda e: top.destroy())
        return top

    def mostra_modale(top):
        top.wait_visibility()
        top.grab_set()
        top.focus_set()
        root.wait_window(top)

    # --- icone per l'esplora file -------------------------------------------------
    def icona_cartella(colore="#E9763F", scuro="#C9561F"):
        img = tk.PhotoImage(width=22, height=18)
        img.put(scuro, to=(1, 1, 9, 4))
        img.put(scuro, to=(1, 3, 21, 17))
        img.put(colore, to=(1, 5, 21, 17))
        img.put("#F39A6D", to=(1, 5, 21, 6))
        return img

    def icona_file(righe="#AEA79F", accento=None):
        img = tk.PhotoImage(width=18, height=22)
        img.put("#B9B2AC", to=(2, 0, 16, 22))
        img.put("#FFFFFF", to=(3, 1, 15, 21))
        img.put("#D8D2CC", to=(11, 1, 15, 5))
        for i, y in enumerate((7, 10, 13, 16)):
            img.put(accento if (accento and i == 0) else righe, to=(5, y, 13 if i < 3 else 10, y + 1))
        return img

    immagini["cartella"] = icona_cartella()
    immagini["cartella_casa"] = icona_cartella("#8E5B86", "#6A3A62")
    immagini["txt"] = icona_file(accento=ARANCIO)
    immagini["file"] = icona_file("#D0CAC4")

    # --- esplora file ----------------------------------------------------------------
    cartelle_xdg = cartelle_utente

    def posizioni():
        xdg = cartelle_xdg()
        voci = [("Home", casa)]
        for chiave, nome, alternative in (("DESKTOP", "Scrivania", ("Scrivania", "Desktop")),
                                          ("DOCUMENTS", "Documenti", ("Documenti", "Documents")),
                                          ("DOWNLOAD", "Scaricati", ("Scaricati", "Downloads"))):
            p = xdg.get(chiave) or next((os.path.join(casa, a) for a in alternative
                                         if os.path.isdir(os.path.join(casa, a))), None)
            if p and os.path.isdir(p):
                voci.append((nome, p))
        if os.path.isdir(os.path.join(casa, "Dropbox")):
            voci.append(("Dropbox", os.path.join(casa, "Dropbox")))
        lavoro = cartella_anno(cfg, dt.date.today().year)
        base = os.path.dirname(lavoro) if "{anno}" in (cfg.get("cartella_lavoro") or "") else lavoro
        for nome, p in (("Newsletter " + str(dt.date.today().year), lavoro), ("Newsletter", base)):
            if p and os.path.isdir(p) and all(p != v[1] for v in voci):
                voci.append((nome, p))
        return voci

    def esplora(modo="file", titolo="Scegli un file", iniziale=None, estensioni=(".txt",)):
        """Finestra per scegliere un file (modo='file') o una cartella (modo='cartella')."""
        esito = {"percorso": None}
        top = finestra_modale(titolo, 880, 560)
        top.configure(bg=SCHEDA)

        # intestazione
        testa = tk.Frame(top, bg=MELANZANA_SCURA, height=52)
        testa.pack(fill="x")
        tk.Label(testa, text=titolo, bg=MELANZANA_SCURA, fg="white", font=F["grande"]).pack(
            side="left", padx=18, pady=14)
        tk.Frame(top, bg=ARANCIO, height=3).pack(fill="x")

        corpo_e = tk.Frame(top, bg=SCHEDA)
        corpo_e.pack(fill="both", expand=True)

        # barra laterale
        lato = tk.Frame(corpo_e, bg=LATERALE, width=190)
        lato.pack(side="left", fill="y")
        lato.pack_propagate(False)
        tk.Label(lato, text="POSIZIONI", bg=LATERALE, fg=TENUE, font=F["piccolo_b"]).pack(
            anchor="w", padx=18, pady=(16, 6))
        voci_lato = []

        # area principale
        princ = tk.Frame(corpo_e, bg=SCHEDA)
        princ.pack(side="left", fill="both", expand=True)
        nav = tk.Frame(princ, bg=SCHEDA)
        nav.pack(fill="x", padx=14, pady=(12, 8))
        storia = {"indietro": [], "avanti": [], "attuale": None}
        b_ind = BottoneFreccia(nav, "sx", lambda: vai_storia("indietro"))
        b_ava = BottoneFreccia(nav, "dx", lambda: vai_storia("avanti"))
        b_su = BottoneFreccia(nav, "su", lambda: vai(os.path.dirname(storia["attuale"])))
        for b in (b_ind, b_ava, b_su):
            b.pack(side="left", padx=(0, 2))
        briciole = tk.Frame(nav, bg=SCHEDA)
        briciole.pack(side="left", fill="x", expand=True, padx=(10, 10))
        v_percorso = tk.StringVar()
        campo_percorso = Campo(briciole, v_percorso)
        v_filtro = tk.StringVar()
        Campo(nav, v_filtro, larghezza=18, segnaposto="Cerca…").pack(side="right")

        elenco_f = tk.Frame(princ, bg=SCHEDA)
        elenco_f.pack(fill="both", expand=True, padx=(14, 4))
        albero = ttk.Treeview(elenco_f, columns=("mod", "dim"), style="Esplora.Treeview",
                              selectmode="browse")
        albero.heading("#0", text="NOME", anchor="w")
        albero.heading("mod", text="MODIFICATO", anchor="w")
        albero.heading("dim", text="DIMENSIONE", anchor="e")
        albero.column("#0", width=330, minwidth=200, stretch=True)
        albero.column("mod", width=150, minwidth=120, stretch=False, anchor="w")
        albero.column("dim", width=100, minwidth=80, stretch=False, anchor="e")
        albero.tag_configure("pari", background=RIGA_PARI)
        albero.tag_configure("nascosto", foreground=GRIGIO_CALDO)
        albero.pack(side="left", fill="both", expand=True)
        barra_scorrimento(elenco_f, albero, SCHEDA, BORDO_FORTE).pack(side="right", fill="y", pady=4)
        vuoto = tk.Label(elenco_f, text="", bg=SCHEDA, fg=GRIGIO_CALDO, font=F["testo"])

        # piede
        tk.Frame(princ, bg=BORDO, height=1).pack(fill="x", pady=(6, 0))
        piede_e = tk.Frame(princ, bg=SCHEDA)
        piede_e.pack(fill="x", padx=14, pady=12)
        v_nascosti = tk.BooleanVar(value=False)
        v_tutti = tk.BooleanVar(value=False)
        opz_e = tk.Frame(piede_e, bg=SCHEDA)
        opz_e.pack(side="left")
        Spunta(opz_e, "File nascosti", v_nascosti, F["piccolo"]).pack(side="left")
        if modo == "file":
            Spunta(opz_e, "Tutti i tipi di file", v_tutti, F["piccolo"]).pack(side="left", padx=(14, 0))
        v_scelta = tk.StringVar()
        b_ok = Bottone(piede_e, "Apri" if modo == "file" else "Seleziona questa cartella",
                       lambda: conferma(), tipo="primario")
        b_ok.pack(side="right")
        Bottone(piede_e, "Annulla", top.destroy).pack(side="right", padx=(0, 8))
        tk.Label(piede_e, textvariable=v_scelta, bg=SCHEDA, fg=TENUE, font=F["piccolo"],
                 anchor="e").pack(side="right", fill="x", expand=True, padx=12)

        ordine = {"col": "#0", "inverso": False}
        righe = {}

        def formato_data(t):
            d = dt.datetime.fromtimestamp(t)
            oggi = dt.date.today()
            if d.date() == oggi:
                return "oggi, " + d.strftime("%H:%M")
            if d.date() == oggi - dt.timedelta(days=1):
                return "ieri, " + d.strftime("%H:%M")
            return d.strftime("%d/%m/%Y")

        def formato_dim(n):
            for u in ("byte", "kB", "MB", "GB"):
                if n < 1024 or u == "GB":
                    return f"{n:.0f} {u}" if u == "byte" else f"{n:.1f} {u}"
                n /= 1024

        def disegna_briciole():
            for w in briciole.winfo_children():
                if w is not campo_percorso:
                    w.destroy()
            campo_percorso.pack_forget()
            p = storia["attuale"]
            if p == casa or p.startswith(casa + os.sep):
                radice, resto = casa, os.path.relpath(p, casa)
                parti = [("Home", casa)]
            else:
                radice, resto = os.sep, p.lstrip(os.sep)
                parti = [("/", os.sep)]
            acc = radice
            for pezzo in ([] if resto in (".", "") else resto.split(os.sep)):
                acc = os.path.join(acc, pezzo)
                parti.append((pezzo, acc))
            if len(parti) > 5:
                parti = parti[:1] + [("…", None)] + parti[-3:]
            for i, (nome, dest) in enumerate(parti):
                if i:
                    tk.Label(briciole, text="›", bg=SCHEDA, fg=GRIGIO_CALDO, font=F["testo"]).pack(
                        side="left", padx=2)
                ultimo = i == len(parti) - 1
                if ultimo:
                    et = Gettone(briciole, TESTO, ARANCIO_TENUE)
                    et.configure_testo(nome)
                else:
                    et = tk.Label(briciole, text=nome, bg=SCHEDA, fg=TENUE, font=F["piccolo"],
                                  padx=6, pady=4, cursor="hand2" if dest else "arrow")
                et.pack(side="left")
                if dest and not ultimo:
                    et.bind("<Button-1>", lambda e, d=dest: vai(d))
                    et.bind("<Enter>", lambda e, w=et: w.configure(fg=ARANCIO))
                    et.bind("<Leave>", lambda e, w=et: w.configure(fg=TENUE))
            spazio = tk.Label(briciole, text="", bg=SCHEDA, cursor="xterm")
            spazio.pack(side="left", fill="x", expand=True)
            spazio.bind("<Button-1>", lambda e: modifica_percorso())

        def modifica_percorso(_=None):
            for w in briciole.winfo_children():
                if w is not campo_percorso:
                    w.pack_forget()
            v_percorso.set(storia["attuale"])
            campo_percorso.pack(fill="x", expand=True)
            campo_percorso.e.focus_set()
            campo_percorso.e.icursor("end")

        def conferma_percorso(_=None):
            p = os.path.expanduser(v_percorso.get().strip())
            if os.path.isdir(p):
                vai(p)
            elif os.path.isfile(p) and modo == "file":
                esito["percorso"] = p
                top.destroy()
            else:
                v_scelta.set("Percorso non trovato")
                disegna_briciole()
        campo_percorso.e.bind("<Return>", conferma_percorso)
        campo_percorso.e.bind("<Escape>", lambda e: (disegna_briciole(), "break")[1])

        def ricarica(*_):
            albero.delete(*albero.get_children())
            righe.clear()
            p = storia["attuale"]
            try:
                voci = list(os.scandir(p))
            except OSError as e:
                voci = []
                vuoto.configure(text=f"Impossibile aprire la cartella: {e.strerror}")
            filtro = v_filtro.get().strip().lower()
            cartelle, files = [], []
            for v in voci:
                if v.name.startswith(".") and not v_nascosti.get():
                    continue
                if filtro and filtro not in v.name.lower():
                    continue
                try:
                    is_dir = v.is_dir()
                    st = v.stat()
                except OSError:
                    continue
                if is_dir:
                    cartelle.append((v.name, v.path, st.st_mtime, None))
                elif modo == "file" and (v_tutti.get() or v.name.lower().endswith(estensioni)):
                    files.append((v.name, v.path, st.st_mtime, st.st_size))
            chiave = {"#0": lambda x: x[0].lower().lstrip("."), "mod": lambda x: x[2],
                      "dim": lambda x: x[3] or 0}[ordine["col"]]
            inverso = ordine["inverso"]
            cartelle.sort(key=chiave, reverse=inverso)
            files.sort(key=chiave, reverse=inverso)
            for i, (nome, path, mtime, dim) in enumerate(cartelle + files):
                is_dir = dim is None
                if is_dir:
                    img = immagini["cartella_casa"] if path == casa else immagini["cartella"]
                else:
                    img = immagini["txt"] if nome.lower().endswith(".txt") else immagini["file"]
                tag = ["pari"] if i % 2 else []
                if nome.startswith("."):
                    tag.append("nascosto")
                iid = albero.insert("", "end", text="  " + nome, image=img,
                                    values=(formato_data(mtime), "" if is_dir else formato_dim(dim)),
                                    tags=tag)
                righe[iid] = (path, is_dir)
            if not righe:
                if voci or filtro:
                    vuoto.configure(text="Nessun file .txt in questa cartella" if modo == "file"
                                    and not filtro else "Nessun risultato")
                elif not vuoto.cget("text").startswith("Impossibile"):
                    vuoto.configure(text="Cartella vuota")
                vuoto.place(relx=0.5, rely=0.45, anchor="center")
            else:
                vuoto.place_forget()
                vuoto.configure(text="")
            for nome, path, w in voci_lato:
                attivo = os.path.normpath(path) == os.path.normpath(p)
                w.configure(bg=SCHEDA if attivo else LATERALE)
                for c in w.winfo_children():
                    c.configure(bg=(ARANCIO if c.winfo_class() == "Frame" and attivo else
                                    SCHEDA if attivo else LATERALE))
            aggiorna_scelta()
            b_ind.stato(bool(storia["indietro"]))
            b_ava.stato(bool(storia["avanti"]))
            b_su.stato(p != os.sep)

        def vai(p, da_storia=False):
            p = os.path.normpath(p)
            if not os.path.isdir(p):
                return
            if storia["attuale"] and not da_storia and p != storia["attuale"]:
                storia["indietro"].append(storia["attuale"])
                storia["avanti"].clear()
            storia["attuale"] = p
            if v_filtro.get():
                v_filtro.set("")
            disegna_briciole()
            ricarica()
            figli = albero.get_children()
            primo_file = next((i for i in figli if not righe[i][1]), None) if modo == "file" else None
            if primo_file:      # il .txt più recente è già selezionato
                albero.selection_set(primo_file)
                albero.focus(primo_file)
                albero.see(primo_file)
            elif figli:
                albero.focus(figli[0])

        def vai_storia(direzione):
            if storia[direzione]:
                altra = "avanti" if direzione == "indietro" else "indietro"
                storia[altra].append(storia["attuale"])
                vai(storia[direzione].pop(), da_storia=True)

        def selezionato():
            sel = albero.selection()
            return righe.get(sel[0]) if sel else None

        def aggiorna_scelta(_=None):
            s = selezionato()
            if modo == "file":
                if s and not s[1]:
                    v_scelta.set(os.path.basename(s[0]))
                    b_ok.stato(True)
                else:
                    v_scelta.set("Scegli un file .txt" if not v_tutti.get() else "Scegli un file")
                    b_ok.stato(False)
            else:
                dest = s[0] if s and s[1] else storia["attuale"]
                v_scelta.set(dest.replace(casa, "~"))
                b_ok.stato(True)

        def apri_riga(_=None):
            s = selezionato()
            if not s:
                return
            if s[1]:
                vai(s[0])
            elif modo == "file":
                esito["percorso"] = s[0]
                top.destroy()

        def conferma():
            s = selezionato()
            if modo == "file":
                if s and not s[1]:
                    esito["percorso"] = s[0]
                    top.destroy()
            else:
                esito["percorso"] = s[0] if s and s[1] else storia["attuale"]
                top.destroy()

        def ordina(col):
            if ordine["col"] == col:
                ordine["inverso"] = not ordine["inverso"]
            else:
                ordine["col"], ordine["inverso"] = col, col == "mod"
            for c, t in (("#0", "NOME"), ("mod", "MODIFICATO"), ("dim", "DIMENSIONE")):
                freccia = (" ↓" if ordine["inverso"] else " ↑") if c == ordine["col"] else ""
                albero.heading(c, text=t + freccia)
            ricarica()
        for c in ("#0", "mod", "dim"):
            albero.heading(c, command=lambda c=c: ordina(c))

        albero.bind("<<TreeviewSelect>>", aggiorna_scelta)
        albero.bind("<Double-1>", apri_riga)
        albero.bind("<Return>", apri_riga)
        albero.bind("<BackSpace>", lambda e: vai(os.path.dirname(storia["attuale"])))
        top.bind("<Alt-Left>", lambda e: vai_storia("indietro"))
        top.bind("<Alt-Right>", lambda e: vai_storia("avanti"))
        top.bind("<Alt-Up>", lambda e: vai(os.path.dirname(storia["attuale"])))
        top.bind("<Control-l>", modifica_percorso)
        top.bind("<Control-h>", lambda e: v_nascosti.set(not v_nascosti.get()))
        v_filtro.trace_add("write", ricarica)
        v_nascosti.trace_add("write", ricarica)
        v_tutti.trace_add("write", ricarica)

        # voci della barra laterale
        for nome, path in posizioni():
            riga_l = tk.Frame(lato, bg=LATERALE, cursor="hand2")
            riga_l.pack(fill="x")
            tk.Frame(riga_l, bg=LATERALE, width=4).pack(side="left", fill="y")
            et = tk.Label(riga_l, text=nome, bg=LATERALE, fg=TESTO, font=F["testo"], anchor="w",
                          padx=14, pady=7, cursor="hand2")
            et.pack(side="left", fill="x", expand=True)
            for w in (riga_l, et):
                w.bind("<Button-1>", lambda e, p=path: vai(p))
            voci_lato.append((nome, path, riga_l))
        tk.Label(lato, text="Ctrl+L: scrivi un percorso\nCtrl+H: file nascosti\nBackspace: cartella su",
                 bg=LATERALE, fg=GRIGIO_CALDO, font=F["piccolo"], justify="left").pack(
            side="bottom", anchor="w", padx=18, pady=14)

        inizio = os.path.expanduser(iniziale or "")
        if inizio and os.path.isfile(inizio):
            inizio = os.path.dirname(inizio)
        if not inizio or not os.path.isdir(inizio):
            inizio = next((p for n, p in posizioni() if n == "Scaricati"), casa)
        if modo == "file":       # file: i più recenti in alto
            ordine["col"], ordine["inverso"] = "mod", True
            albero.heading("mod", text="MODIFICATO ↓")
        vai(inizio)
        if prova_esplora:
            prova_esplora(top)
        mostra_modale(top)
        return esito["percorso"]

    prova_esplora = None

    # --- intestazione -----------------------------------------------------------
    testata = tk.Canvas(root, height=92, highlightthickness=0, bd=0)
    testata.pack(fill="x")

    def disegna_testata(_=None):
        c = testata
        c.delete("all")
        l = c.winfo_width()
        a = 88
        fascia(c, l, a, MELANZANA_SCURA, MELANZANA_VIVA)
        c.create_rectangle(0, a, l, a + 4, fill=ARANCIO, outline="")
        c.create_image(22, 44, image=immagine_icona(False), anchor="w")
        c.create_text(100, 34, text="Newsletter Ubuntu-it", anchor="w", fill="white",
                      font=F["titolo"])
        c.create_text(100, 60, text="Dal wiki a LaTeX e PDF, in un clic", anchor="w",
                      fill="#E6CFE0", font=F["sottotitolo"])
        c.create_text(l - 24, 36, text=f"Design {DESIGN}", anchor="e", fill="#E6CFE0", font=F["piccolo"])
        c.create_text(l - 24, 56, text=f"versione {VERSIONE}", anchor="e", fill="#B98FAF",
                      font=F["piccolo"])
        destra_x = l - 24 - max(F["piccolo"].measure(f"Design {DESIGN}"),
                                F["piccolo"].measure(f"versione {VERSIONE}")) - 34
        for nome, cx in (("tema", destra_x), ("stat", destra_x - 50)):
            centri_testata[nome] = cx
            fondo = "#7A3A70" if sopra_testata.get("nome") == nome else "#4A1A42"
            disco(c, cx, 44, 19, fondo, tags=(nome, nome + "_fondo"))
            chiaro = "#F7E7F2"
            if nome == "stat":
                for x1, alto in ((-8, 7), (-2, 14), (4, 10)):
                    c.create_rectangle(cx + x1, 44 + 7 - alto, cx + x1 + 5, 44 + 7, fill=chiaro,
                                       outline="", tags=(nome,))
            elif tema == "chiaro":           # luna: passa alla modalità notte
                disco(c, cx, 44, 8, chiaro, ritaglio=(4, -5, 7), tags=(nome,))
            else:                            # sole: passa alla modalità giorno
                disco(c, cx, 44, 5, "#FFD27A", tags=(nome,))
                for k in range(8):
                    a = math.radians(k * 45)
                    linea(c, (cx + 8 * math.cos(a), 44 + 8 * math.sin(a), cx + 11 * math.cos(a),
                              44 + 11 * math.sin(a)), 2, "#FFD27A", tags=(nome,))

    # Il mouse si segue per posizione sull'intera intestazione: niente eventi sulle singole
    # forme (ricrearle sotto il puntatore generava un ciclo infinito di ridisegni).
    sopra_testata = {"nome": None}
    centri_testata = {}

    def pulsante_sotto(x, y):
        for nome, cx in centri_testata.items():
            if (x - cx) ** 2 + (y - 44) ** 2 <= 19 ** 2:
                return nome
        return None

    def evidenzia_testata(nome):
        if nome == sopra_testata["nome"]:
            return
        sopra_testata["nome"] = nome
        disegna_testata()
        testata.configure(cursor="hand2" if nome else "")
        if nome:
            testo = {"stat": "Statistiche dei bug da Launchpad",
                     "tema": "Modalità notte" if tema == "chiaro" else "Modalità giorno"}[nome]
            suggerimento.mostra(testo, testata.winfo_rootx() + centri_testata[nome] - 60,
                                testata.winfo_rooty() + 70)
        else:
            suggerimento.nascondi()

    def clic_testata(e):
        nome = pulsante_sotto(e.x, e.y)
        if nome:
            evidenzia_testata(None)
            (cambia_tema if nome == "tema" else mostra_statistiche)()

    testata.bind("<Motion>", lambda e: evidenzia_testata(pulsante_sotto(e.x, e.y)))
    testata.bind("<Leave>", lambda e: evidenzia_testata(None))
    testata.bind("<Button-1>", clic_testata)
    testata.bind("<Configure>", disegna_testata)

    banner = tk.Frame(root, bg=ARANCIO_TENUE)
    banner_testo = tk.StringVar()
    tk.Frame(banner, bg=ARANCIO, width=4).pack(side="left", fill="y")
    tk.Label(banner, textvariable=banner_testo, bg=ARANCIO_TENUE, fg=TESTO, font=F["bottone"], anchor="w",
             padx=16, pady=10).pack(side="left", fill="x", expand=True)
    banner_azioni = tk.Frame(banner, bg=ARANCIO_TENUE)
    banner_azioni.pack(side="right", padx=(0, 14))

    def mostra_banner(testo, azioni=()):
        banner_testo.set(testo)
        for w in banner_azioni.winfo_children():
            w.destroy()
        for i, (etichetta_b, comando) in enumerate(azioni):
            Bottone(banner_azioni, etichetta_b, comando, tipo="primario" if i == 0 else "piatto",
                    alto=32, padx=14).pack(side="left", padx=(8, 0), pady=6)
        if not banner.winfo_ismapped():
            banner.pack(fill="x", before=corpo)

    def nascondi_banner():
        banner.pack_forget()

    corpo = tk.Frame(root, bg=SFONDO, padx=22, pady=18)
    corpo.pack(fill="both", expand=True)
    corpo.columnconfigure(0, weight=0, minsize=480)
    corpo.columnconfigure(1, weight=1)
    corpo.rowconfigure(0, weight=1)
    sinistra = tk.Frame(corpo, bg=SFONDO)
    sinistra.grid(row=0, column=0, sticky="nsew")
    aiuto_tasti = tk.Label(sinistra, text="oppure premi Invio  ·  F1 per le scorciatoie", bg=SFONDO,
                           fg=GRIGIO_CALDO, font=F["piccolo"], cursor="hand2")
    aiuto_tasti.pack(side="bottom", pady=(6, 0))
    aiuto_tasti.bind("<Button-1>", lambda e: mostra_scorciatoie())
    b_converti = Bottone(sinistra, "Converti", tipo="primario", font=F["grande"], alto=48, espandi=True)
    b_converti.pack(side="bottom", fill="x", pady=(14, 0))
    area = AreaScorrevole(sinistra)
    area.pack(fill="both", expand=True)
    colonna = area.interno
    destra = tk.Frame(corpo, bg=SFONDO)
    destra.grid(row=0, column=1, sticky="nsew", padx=(18, 0))

    # --- sorgente ---------------------------------------------------------------------
    v_sorgente = tk.StringVar(value="ultimo")
    v_numero = tk.StringVar(value=f"{dt.date.today().year}.")
    v_file = tk.StringVar()
    c_sorg, s_corpo, _ = scheda(colonna, "Sorgente", "da dove prendere il testo")
    c_sorg.pack(fill="x")
    Segmentato(s_corpo, [("ultimo", "Ultimo numero"), ("numero", "Numero specifico"),
                         ("file", "File .txt")], v_sorgente).pack(anchor="w")
    dettaglio = tk.Frame(s_corpo, bg=SCHEDA)
    dettaglio.pack(fill="x", pady=(12, 0))
    pannelli = {}

    # pannello "ultimo numero": stato del controllo sul wiki
    p = tk.Frame(dettaglio, bg=SCHEDA)
    stato_wiki = tk.Frame(p, bg=SCHEDA)
    stato_wiki.pack(side="left", fill="x", expand=True)
    pallino = tk.Canvas(stato_wiki, width=12, height=12, bg=SCHEDA, highlightthickness=0)
    pallino.pack(side="left", padx=(2, 10))
    v_wiki = tk.StringVar(value="Controllo del wiki in corso…")
    v_wiki2 = tk.StringVar(value="")
    testi_wiki = tk.Frame(stato_wiki, bg=SCHEDA)
    testi_wiki.pack(side="left", fill="x", expand=True)
    tk.Label(testi_wiki, textvariable=v_wiki, bg=SCHEDA, fg=TESTO, font=F["bottone"], anchor="w",
             justify="left", wraplength=270).pack(fill="x")
    tk.Label(testi_wiki, textvariable=v_wiki2, bg=SCHEDA, fg=TENUE, font=F["piccolo"], anchor="w",
             justify="left", wraplength=270).pack(fill="x")
    v_wiki3 = tk.StringVar(value="")
    tk.Label(testi_wiki, textvariable=v_wiki3, bg=SCHEDA, fg=GRIGIO_CALDO, font=F["piccolo"], anchor="w",
             justify="left").pack(fill="x", pady=(2, 0))
    b_controlla = Bottone(p, "Controlla ora", lambda: avvia_controllo(manuale=True))
    b_controlla.pack(side="right", before=stato_wiki)   # il pulsante ha la precedenza sullo spazio
    pannelli["ultimo"] = p

    def colore_pallino(colore):
        pallino.delete("all")
        disco(pallino, 6, 6, 5, colore)
    colore_pallino(GRIGIO_CALDO)

    p = tk.Frame(dettaglio, bg=SCHEDA)
    campo_numero = Campo(p, v_numero, larghezza=12)
    campo_numero.pack(side="left")
    nota(p, "formato AAAA.NNN, es. 2026.031").pack(side="left", padx=12)
    pannelli["numero"] = p

    p = tk.Frame(dettaglio, bg=SCHEDA)
    p.columnconfigure(0, weight=1)
    Campo(p, v_file, segnaposto="Nessun file scelto").grid(row=0, column=0, sticky="ew")

    def scegli_file():
        x = esplora("file", "Scegli il file .txt della newsletter", v_file.get() or None)
        if x:
            v_file.set(x)
    Bottone(p, "Sfoglia…", scegli_file).grid(row=0, column=1, padx=(10, 0))
    pannelli["file"] = p

    def mostra_pannello(*_):
        for k, w in pannelli.items():
            w.pack_forget()
        pannelli[v_sorgente.get()].pack(fill="x")
    v_sorgente.trace_add("write", mostra_pannello)
    mostra_pannello()

    # --- destinazione --------------------------------------------------------------------
    v_cartella = tk.StringVar(value=cfg.get("cartella_lavoro") or "")
    casa_utente = os.path.expanduser("~")
    v_pdf = tk.BooleanVar(value=bool(shutil.which("pdflatex")))
    v_txt = tk.BooleanVar(value=True)
    c_dest, d_corpo, _ = scheda(colonna, "Destinazione", "cartella dell'anno, con le immagini")
    c_dest.pack(fill="x", pady=(14, 0))
    riga = tk.Frame(d_corpo, bg=SCHEDA)
    riga.pack(fill="x")
    riga.columnconfigure(0, weight=1)
    Campo(riga, v_cartella, segnaposto="Nessuna cartella: premi Sfoglia…").grid(row=0, column=0, sticky="ew")

    def scegli_cartella():
        attuale = v_cartella.get().replace("{anno}", str(dt.date.today().year)) or casa_utente
        x = esplora("cartella", "Scegli la cartella dell'anno (con le immagini)", attuale)
        if x:
            anno = str(dt.date.today().year)
            # se è la cartella dell'anno corrente, la rendiamo valida anche per i prossimi anni
            v_cartella.set(os.path.join(os.path.dirname(x), "{anno}") if os.path.basename(x) == anno else x)
    Bottone(riga, "Sfoglia…", scegli_cartella).grid(row=0, column=1, padx=(10, 0))
    nota(d_corpo, "{anno} diventa l'anno del numero; i file vanno\nnella sottocartella NNN (es. 2026/031/).").pack(
        anchor="w", pady=(6, 10))
    interr = tk.Frame(d_corpo, bg=SCHEDA)
    interr.pack(anchor="w")
    Interruttore(interr, "Compila anche il PDF", v_pdf).pack(side="left")
    Interruttore(interr, "Salva una copia del .txt", v_txt).pack(side="left", padx=(24, 0))

    # --- impostazioni (comprimibili) -----------------------------------------------------
    pdf0 = cfg["realizzato_pdf"][0] if cfg["realizzato_pdf"] else ["", ""]
    v_cura = tk.StringVar(value=cfg["a_cura_di"])
    v_pdf_utente = tk.StringVar(value=pdf0[0])
    v_pdf_nome = tk.StringVar(value=pdf0[1])
    v_edizione = tk.StringVar(value="; ".join(f"{u}:{n}" for u, n in cfg["edizione_predefinita"]))
    c_imp, i_corpo, i_testa = scheda(colonna, "Impostazioni personali")
    c_imp.pack(fill="x", pady=(14, 0))
    v_aperte = tk.BooleanVar(value=False)
    interruttore_imp = tk.Label(i_testa, text="Mostra", bg=SCHEDA, fg=ARANCIO, font=F["bottone"],
                                cursor="hand2")
    interruttore_imp.pack(side="right")
    griglia = tk.Frame(i_corpo, bg=SCHEDA)
    griglia.columnconfigure(0, weight=1, uniform="imp")
    griglia.columnconfigure(1, weight=1, uniform="imp")

    def etichetta(testo, r, c=0, span=1):
        tk.Label(griglia, text=testo, bg=SCHEDA, fg=TENUE, font=F["piccolo"]).grid(
            row=r, column=c, columnspan=span, sticky="w", padx=(0 if c == 0 else 10, 0), pady=(6, 2))
    etichetta("A cura di (colophon)", 0, span=2)
    Campo(griglia, v_cura).grid(row=1, column=0, columnspan=2, sticky="ew")
    etichetta("Realizza il PDF: utente wiki", 2)
    etichetta("Nome e cognome", 2, 1)
    Campo(griglia, v_pdf_utente, larghezza=10).grid(row=3, column=0, sticky="ew")
    Campo(griglia, v_pdf_nome).grid(row=3, column=1, sticky="ew", padx=(10, 0))
    etichetta("Collaboratori all'edizione, se mancano nel .txt", 4, span=2)
    Campo(griglia, v_edizione, segnaposto="utente:Nome Cognome; utente:Nome Cognome").grid(
        row=5, column=0, columnspan=2, sticky="ew")
    etichetta("Avvisi e aggiornamenti", 6, span=2)
    v_notifiche = tk.BooleanVar(value=bool(cfg.get("notifiche", True)))
    v_aggiorna = tk.BooleanVar(value=bool(cfg.get("aggiornamenti_automatici", True)))
    i_notifiche = Interruttore(griglia, "Avvisami dei nuovi numeri (lunedì sera e martedì)", v_notifiche)
    i_notifiche.grid(row=7, column=0, columnspan=2, sticky="w", pady=(2, 4))
    i_aggiorna = Interruttore(griglia, "Aggiornamenti automatici da GitHub", v_aggiorna)
    i_aggiorna.grid(row=8, column=0, columnspan=2, sticky="w", pady=(2, 0))
    tk.Label(griglia, text="Le impostazioni vengono salvate a ogni conversione.", bg=SCHEDA, fg=TENUE,
             font=F["piccolo"]).grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))
    link_log = tk.Label(griglia, text="Apri il log di sistema", bg=SCHEDA, fg=ARANCIO, font=F["bottone"],
                        cursor="hand2")
    link_log.grid(row=10, column=0, columnspan=2, sticky="w", pady=(6, 0))
    link_log.bind("<Button-1>", lambda e: apri_nel_browser(file_log_sistema())
                  if os.path.exists(file_log_sistema()) else None)
    con_suggerimento(link_log, lambda: file_log_sistema().replace(casa, "~"))

    def cambia_notifiche():
        attive = v_notifiche.get()
        salva_config(dict(carica_config(), notifiche=attive))
        if not os.path.exists(PERCORSO_INSTALLATO):
            scrivi("Avviso dei nuovi numeri: installa prima il programma con «sh installa.sh».", "AVVISO")
            return
        try:
            scrivi(imposta_notifiche(attive), "INFO", prompt=True)
        except (RuntimeError, OSError, subprocess.SubprocessError) as e:
            scrivi(f"Avviso dei nuovi numeri: {e}", "AVVISO")

    def cambia_aggiornamenti():
        salva_config(dict(carica_config(), aggiornamenti_automatici=v_aggiorna.get()))

    traccia(i_notifiche, v_notifiche, cambia_notifiche)
    traccia(i_aggiorna, v_aggiorna, cambia_aggiornamenti)

    def alterna_impostazioni(_=None):
        v_aperte.set(not v_aperte.get())
        if v_aperte.get():
            i_corpo.pack(fill="both", expand=True, pady=(12, 0))
            griglia.pack(fill="x")
            interruttore_imp.configure(text="Nascondi")
            area.in_fondo()
        else:
            griglia.pack_forget()
            i_corpo.pack_forget()
            interruttore_imp.configure(text="Mostra")
    i_corpo.pack_forget()
    for w in (interruttore_imp, i_testa):
        w.bind("<Button-1>", alterna_impostazioni)


    # --- risultato --------------------------------------------------------------------------
    c_ris, r_corpo, r_testa = scheda(destra, "Risultato", riempi=True)
    c_ris.pack(fill="both", expand=True)
    v_stato = tk.StringVar(value="Pronto.")
    tk.Label(r_corpo, textvariable=v_stato, bg=SCHEDA, fg=TESTO, font=F["testo"], anchor="w").pack(
        fill="x")
    barra = Avanzamento(r_corpo)
    barra.pack(fill="x", pady=(8, 12))
    gettoni = tk.Frame(r_testa, bg=SCHEDA)
    gettoni.pack(side="right")

    filtri = dict(stato.get("filtri") or {"ERRORE": True, "AVVISO": True, "REFUSO": True})

    def alterna_filtro(livello):
        filtri[livello] = not filtri[livello]
        {"ERRORE": g_err, "AVVISO": g_avv, "REFUSO": g_ref}[livello].configure_testo(acceso=filtri[livello])
        ridisegna_console()

    g_err = Gettone(gettoni, ROSSO, ROSSO_TENUE, lambda: alterna_filtro("ERRORE"))
    g_avv = Gettone(gettoni, AMBRA_TESTO, AMBRA_TENUE, lambda: alterna_filtro("AVVISO"))
    g_ref = Gettone(gettoni, REFUSO_TESTO, REFUSO_TENUE, lambda: alterna_filtro("REFUSO"))
    g_ok = Gettone(gettoni, VERDE_TESTO, VERDE_TENUE)
    for g, cosa in ((g_err, "gli errori"), (g_avv, "gli avvisi"), (g_ref, "i refusi")):
        con_suggerimento(g, lambda g=g, cosa=cosa: ("Nascondi " if g.acceso else "Mostra ") + cosa)

    # anteprima della copertina del PDF
    anteprima_f = tk.Frame(r_corpo, bg=SCHEDA)
    tela_copertina = tk.Canvas(anteprima_f, width=108, height=10, bg=SCHEDA, highlightthickness=0,
                               cursor="hand2")
    tela_copertina.pack(side="left")
    tela_copertina.bind("<Button-1>", lambda e: apri("pdf"))
    con_suggerimento(tela_copertina, "Apri il PDF")
    info_copertina = tk.Frame(anteprima_f, bg=SCHEDA)
    info_copertina.pack(side="left", fill="x", expand=True, padx=(16, 0))
    v_cop_titolo, v_cop_dett = tk.StringVar(), tk.StringVar()
    tk.Label(info_copertina, text="PDF PRONTO", bg=SCHEDA, fg=VERDE_TESTO, font=F["piccolo_b"]).pack(anchor="w")
    tk.Label(info_copertina, textvariable=v_cop_titolo, bg=SCHEDA, fg=TESTO, font=F["grande"]).pack(
        anchor="w", pady=(2, 0))
    tk.Label(info_copertina, textvariable=v_cop_dett, bg=SCHEDA, fg=TENUE, font=F["piccolo"]).pack(anchor="w")
    collegamento = tk.Label(info_copertina, text="Apri il PDF", bg=SCHEDA, fg=ARANCIO, font=F["bottone"],
                            cursor="hand2")
    collegamento.pack(anchor="w", pady=(8, 0))
    collegamento.bind("<Button-1>", lambda e: apri("pdf"))

    def mostra_anteprima(dato):
        cop = dato.get("miniatura") if dato else None
        if not cop or not os.path.exists(cop["png"]):
            anteprima_f.pack_forget()
            return
        try:
            img = tk.PhotoImage(file=cop["png"])
        except tk.TclError:
            anteprima_f.pack_forget()
            return
        immagini["copertina"] = img
        w, h = img.width(), img.height()
        tela_copertina.configure(width=w + 4, height=h + 4)
        tela_copertina.delete("all")
        tela_copertina.create_rectangle(2, 3, w + 3, h + 4, fill=BORDO, outline="")
        tela_copertina.create_image(1, 1, image=img, anchor="nw")
        tela_copertina.create_rectangle(1, 1, w + 1, h + 1, outline=BORDO_FORTE)
        d = dato.get("dati") or {}
        v_cop_titolo.set(f"Newsletter {d.get('numero', 0):03d} · {d.get('anno', '')}")
        parti = []
        if cop.get("pagine"):
            parti.append(f"{cop['pagine']} pagine")
        parti.append(f"{cop['dimensione'] / 1024:.0f} kB" if cop["dimensione"] < 1024 * 1024
                     else f"{cop['dimensione'] / 1048576:.1f} MB")
        parti.append(os.path.basename(dato["pdf"]))
        v_cop_dett.set(" · ".join(parti))
        anteprima_f.pack(fill="x", pady=(0, 12), before=console_pannello)

    console_pannello = Pannello(r_corpo, sfondo=CONSOLE, bordo=CONSOLE if tema == "chiaro" else BORDO, r=16,
                                padx=12, pady=10, riempi=True)
    console_pannello.pack(fill="both", expand=True)
    console_cornice = console_pannello.interno
    console = tk.Text(console_cornice, height=18, wrap="word", font=F["mono"], relief="flat", bd=0,
                      bg=CONSOLE, fg=CONSOLE_TESTO, insertbackground=ARANCIO,
                      selectbackground=MELANZANA_VIVA, padx=6, pady=4, highlightthickness=0,
                      state="disabled", cursor="arrow")
    console.pack(side="left", fill="both", expand=True)
    barra_scorrimento(console_cornice, console, CONSOLE, MELANZANA_VIVA).pack(
        side="right", fill="y")
    console.tag_configure("ERRORE", foreground="#FF7B7F")
    console.tag_configure("AVVISO", foreground="#FFB44D")
    console.tag_configure("REFUSO", foreground="#E59AD8")
    console.tag_configure("RIGA", foreground="white", font=F["mono_b"], spacing1=8)
    console.tag_configure("ESTRATTO", foreground=CONSOLE_TENUE)
    console.tag_configure("INFO", foreground=CONSOLE_TENUE)
    console.tag_configure("PASSO", foreground=CONSOLE_TESTO)
    console.tag_configure("OK", foreground="#7EE787", font=F["mono_b"])
    console.tag_configure("TITOLO", foreground="white", font=F["mono_b"], spacing1=6)
    console.tag_configure("NUMERO", foreground=ARANCIO, font=F["mono_b"], spacing1=10)
    console.tag_configure("PROMPT", foreground=ARANCIO, font=F["mono_b"])

    # La console tiene un registro degli eventi: così i filtri e il cambio di tema
    # possono ridisegnarla da capo.
    eventi = list(stato.get("eventi") or [])

    def _inserisci(riga, tag="PASSO", prompt=False):
        riga = riga.replace(casa, "~")
        console.configure(state="normal")
        if prompt:
            console.insert("end", "› ", "PROMPT")
        console.insert("end", riga + "\n", tag)
        console.see("end")
        console.configure(state="disabled")

    def scrivi(riga, tag="PASSO", prompt=False):
        eventi.append(("testo", riga, tag, prompt))
        _inserisci(riga, tag, prompt)

    def pulisci():
        eventi.clear()
        console.configure(state="normal")
        console.delete("1.0", "end")
        console.configure(state="disabled")

    def disegna_risultato(dato):
        lg = dato["log_obj"]
        voci = [v for v in lg.da_controllare() if filtri.get(v[0], True)]
        nascoste = len(lg.da_controllare()) - len(voci)
        if voci:
            _inserisci("\nDa controllare, in ordine di riga del .txt", "TITOLO")
        ultima = object()
        for livello, rg, msg in voci:
            if rg != ultima:
                if rg is None:
                    _inserisci("Generale", "RIGA")
                else:
                    _inserisci(f"Riga {rg}", "RIGA")
                    _inserisci("  " + lg.estratto(rg, 90), "ESTRATTO")
                ultima = rg
            _inserisci(f"  {livello.lower():<7} {msg}", livello)
        if nascoste:
            _inserisci(f"\n  ({nascoste} {'voce nascosta' if nascoste == 1 else 'voci nascoste'} "
                       "dai filtri: clicca le etichette in alto per mostrarle)", "INFO")
        info = [v for v in dato["voci"] if v[0] == "INFO"]
        if info:
            _inserisci("\nDettagli", "TITOLO")
            for _, rg, msg in sorted(info, key=lambda v: (v[1] is None, v[1] or 0)):
                _inserisci(("  riga %-4d " % rg if rg else "  ") + msg, "INFO")

    def ridisegna_console():
        console.configure(state="normal")
        console.delete("1.0", "end")
        console.configure(state="disabled")
        for e in eventi:
            if e[0] == "testo":
                _inserisci(*e[1:])
            else:
                disegna_risultato(e[1])
        console.see("end")

    if not eventi:
        scrivi("Pronto. Scegli la sorgente e premi Converti.", "INFO", prompt=True)

    piede = tk.Frame(r_corpo, bg=SCHEDA)
    piede.pack(fill="x", pady=(12, 0))
    risultato = dict(stato.get("risultato") or {})

    def apri(chiave):
        x = risultato.get(chiave)
        if x and os.path.exists(x):
            subprocess.Popen(["xdg-open", x], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    b_carica = Bottone(piede, "Carica sul wiki", lambda: carica_sul_wiki(), tipo="primario")
    b_apripdf = Bottone(piede, "Apri PDF", lambda: apri("pdf"))
    b_aprilog = Bottone(piede, "Apri log", lambda: apri("log"))
    b_cartella = Bottone(piede, "Apri cartella", lambda: apri("cartella"))
    for b in (b_carica, b_apripdf, b_aprilog, b_cartella):
        b.pack(side="right", padx=(8, 0))
        b.stato(False)
    con_suggerimento(b_carica, "Apre la pagina degli allegati del numero e copia il percorso del PDF")

    def pdf_pronto():
        x = risultato.get("pdf")
        return bool(x and os.path.exists(x) and risultato.get("dati"))

    def carica_sul_wiki():
        if not pdf_pronto():
            return
        pdf = risultato["pdf"]
        anno, num = risultato["dati"]["anno"], risultato["dati"]["numero"]
        url = url_allegati(cfg, anno, num)

        def copia():
            root.clipboard_clear()
            root.clipboard_append(pdf)
            root.update()               # gli appunti restano disponibili anche agli altri programmi

        copia()
        apri_nel_browser(url)
        registro.info("Carica sul wiki: aperta %s, percorso del PDF copiato negli appunti", url)
        scrivi(f"Pagina degli allegati aperta nel browser; il percorso del PDF è negli appunti.", "INFO",
               prompt=True)

        top = finestra_modale("Carica il PDF sul wiki", 620, 470)
        top.configure(bg=SCHEDA)
        testa = tk.Canvas(top, height=96, highlightthickness=0, bg=MELANZANA_SCURA)
        testa.pack(fill="x")

        def disegna(_=None):
            testa.delete("all")
            l = testa.winfo_width()
            fascia(testa, l, 92, "#2C001E", "#77216F")
            testa.create_rectangle(0, 92, l, 96, fill=ARANCIO, outline="")
            testa.create_text(28, 34, anchor="w", fill="#F7A27F", font=F["piccolo_b"],
                              text=f"NUMERO {num:03d}/{anno} · WIKI UBUNTU-IT")
            testa.create_text(28, 62, anchor="w", fill="white", font=F["enorme"], text="Carica il PDF sul wiki")
        testa.bind("<Configure>", disegna)

        corpo_c = tk.Frame(top, bg=SCHEDA, padx=28, pady=18)
        corpo_c.pack(fill="both", expand=True)
        for i, testo_passo in enumerate((
                "Ho aperto nel browser la pagina degli allegati del numero. Se il wiki lo chiede, "
                "accedi con il tuo account Launchpad.",
                "Nel modulo «Nuovo allegato» premi «Sfoglia…», poi Ctrl+L e Ctrl+V: "
                "il percorso del PDF è già negli appunti. Premi Invio.",
                "Controlla il nome e premi «Carica». In alternativa trascina il file dalla cartella "
                "nella finestra del browser.")):
            riga_p = tk.Frame(corpo_c, bg=SCHEDA)
            riga_p.pack(fill="x", pady=5)
            tondo = tk.Canvas(riga_p, width=28, height=28, bg=SCHEDA, highlightthickness=0)
            disco(tondo, 14, 14, 13, ARANCIO)
            tondo.create_text(14, 14, text=str(i + 1), fill="white", font=F["bottone"])
            tondo.pack(side="left", anchor="n")
            tk.Label(riga_p, text=testo_passo, bg=SCHEDA, fg=TESTO, font=F["testo"], anchor="w",
                     justify="left", wraplength=500).pack(side="left", padx=(12, 0), fill="x")

        tk.Label(corpo_c, text="PDF DA CARICARE", bg=SCHEDA, fg=TENUE, font=F["piccolo_b"]).pack(
            anchor="w", pady=(14, 4))
        pan = Pannello(corpo_c, sfondo=SFONDO, bordo=BORDO, r=12, padx=14, pady=10)
        pan.pack(fill="x")
        tk.Label(pan.interno, text=os.path.basename(pdf), bg=SFONDO, fg=TESTO, font=F["bottone"],
                 anchor="w").pack(fill="x")
        dim = os.path.getsize(pdf)
        tk.Label(pan.interno, text=f"{pdf.replace(casa, '~')}  ·  {dim / 1024:.0f} KB", bg=SFONDO, fg=TENUE,
                 font=F["piccolo"], anchor="w", justify="left", wraplength=520).pack(fill="x")
        v_copiato = tk.StringVar(value="Percorso copiato negli appunti.")
        tk.Label(corpo_c, textvariable=v_copiato, bg=SCHEDA, fg=VERDE_TESTO, font=F["piccolo"],
                 anchor="w").pack(fill="x", pady=(8, 0))

        tk.Frame(top, bg=BORDO, height=1).pack(fill="x")
        piede_c = tk.Frame(top, bg=SCHEDA, padx=28, pady=14)
        piede_c.pack(fill="x")

        def copia_di_nuovo():
            copia()
            v_copiato.set("Percorso copiato di nuovo negli appunti.")
        Bottone(piede_c, "Fatto", top.destroy, tipo="primario", alto=40).pack(side="right")
        Bottone(piede_c, "Mostra il file", lambda: mostra_nella_cartella(pdf), alto=40).pack(
            side="right", padx=(0, 10))
        Bottone(piede_c, "Copia il percorso", copia_di_nuovo, alto=40).pack(side="right", padx=(0, 10))
        Bottone(piede_c, "Riapri la pagina", lambda: apri_nel_browser(url), tipo="piatto", alto=40).pack(
            side="left")
        if prova_carica:
            prova_carica(top, url, pdf)
        mostra_modale(top)


    # --- impostazioni dalla GUI -------------------------------------------------------
    def leggi_impostazioni():
        """Aggiorna cfg con i campi della finestra; False se c'è un errore."""
        try:
            nuova = dict(cfg)
            nuova["cartella_lavoro"] = v_cartella.get().strip()
            nuova["a_cura_di"] = v_cura.get().strip()
            if v_pdf_utente.get().strip() or v_pdf_nome.get().strip():
                nuova["realizzato_pdf"] = [[v_pdf_utente.get().strip(), v_pdf_nome.get().strip()]]
            nuova["edizione_predefinita"] = [list(x) for x in leggi_persone(v_edizione.get())]
            nuova["notifiche"] = v_notifiche.get()
            nuova["aggiornamenti_automatici"] = v_aggiorna.get()
        except Errore as e:
            messagebox.showerror("Impostazioni", str(e), parent=root)
            return False
        cfg.update(nuova)
        return True

    # --- controllo dei nuovi numeri ---------------------------------------------------
    novita = {"dati": None, "in_corso": False, "segnalati": set(stato.get("segnalati") or ())}

    def scansione_periodica():
        # a programma aperto ricontrolla il wiki ogni 45 minuti, senza disturbare se si sta lavorando
        if not root.winfo_exists() or root_generazione[0] != generazione:
            return
        if lavoro_attivo["coda"] is None and root.grab_current() is None:
            avvia_controllo(periodico=True)
        root.after(45 * 60 * 1000, scansione_periodica)
    coda_controllo = queue.Queue()

    def aggiorna_ora_controllo(prefisso="Controllato"):
        momento = novita.get("ultimo")
        v_wiki3.set(f"{prefisso} {quando(momento)}" if momento else "")
        if momento:
            v_wiki3.prefisso = prefisso

    def ricontrolla_etichetta_ora():
        # a mezzanotte «alle 09:50» deve diventare «ieri alle 09:50»
        if not root.winfo_exists() or root_generazione[0] != generazione:
            return
        if novita.get("ultimo") and not novita["in_corso"]:
            aggiorna_ora_controllo(getattr(v_wiki3, "prefisso", "Controllato"))
        root.after(60 * 1000, ricontrolla_etichetta_ora)

    def avvia_controllo(manuale=False, poi=None, periodico=False):
        if novita["in_corso"]:
            return
        if manuale and not leggi_impostazioni():
            return
        novita["in_corso"] = True
        b_controlla.stato(False)
        colore_pallino(GRIGIO_CALDO)
        v_wiki.set("Controllo del wiki in corso…")
        v_wiki2.set("Cerco l'ultimo numero pubblicato")
        v_wiki3.set("")

        def lavora():
            try:
                coda_controllo.put(("ok", controlla_novita(dict(cfg))))
            except WikiBloccato as e:
                coda_controllo.put(("bloccato", str(e)))
            except Exception as e:
                coda_controllo.put(("errore", f"{e}"))

        threading.Thread(target=lavora, daemon=True).start()

        def attendi():
            if root_generazione[0] != generazione:
                return          # finestra ricostruita (cambio di tema) nel frattempo
            try:
                tipo, dato = coda_controllo.get_nowait()
            except queue.Empty:
                root.after(150, attendi)
                return
            novita["in_corso"] = False
            novita["ultimo"] = dt.datetime.now()
            b_controlla.stato(True)
            if tipo == "ok":
                novita["dati"] = dato
                num = f"{dato['numero']:03d}/{dato['anno']}"
                registro.info("Controllo del wiki: ultimo numero %s, da convertire %s", num,
                              dato["mancanti"] or "nessuno")
                if dato["mancanti"]:
                    colore_pallino(ARANCIO)
                    n = len(dato["mancanti"])
                    v_wiki.set(f"Nuovo numero disponibile: {num}")
                    v_wiki2.set(dato["anteprima"]["settimana"].capitalize()
                                + (f" · {n} numeri da convertire" if n > 1 else ""))
                else:
                    colore_pallino(VERDE)
                    v_wiki.set(f"Sei aggiornato: {num} già convertito")
                    v_wiki2.set(dato["anteprima"]["settimana"].capitalize())
                aggiorna_ora_controllo()
                if poi:
                    poi()
                elif periodico:
                    if dato["mancanti"] and dato["numero"] not in novita["segnalati"]:
                        novita["segnalati"].add(dato["numero"])
                        mostra_banner(f"È uscito il numero {dato['numero']:03d}/{dato['anno']} della newsletter.",
                                      [("Mostra", lambda: (nascondi_banner(), mostra_novita(dato))),
                                       ("Chiudi", nascondi_banner)])
                elif dato["mancanti"] or manuale:
                    novita["segnalati"].add(dato["numero"])
                    mostra_novita(dato)
            else:
                registro.warning("Controllo del wiki non riuscito (%s): %s", tipo, dato)
                novita["dati"] = None
                colore_pallino(ROSSO)
                v_wiki.set("Impossibile controllare il wiki")
                v_wiki2.set("Il wiki blocca le richieste automatiche: usa «File .txt»."
                            if tipo == "bloccato" else f"Errore di rete: {dato[:70]}")
                aggiorna_ora_controllo("Ultimo tentativo")
                if manuale or poi:
                    messagebox.showwarning("Controllo non riuscito",
                                           MSG_BLOCCATO.format(e=dato) if tipo == "bloccato" else dato,
                                           parent=root)
        root.after(150, attendi)

    def mostra_novita(dato):
        """Popup con il nuovo numero: Procedi avvia download già fatto + conversione."""
        top = finestra_modale("Nuovo numero della newsletter", 600, 560)
        top.configure(bg=SCHEDA)
        nuovo = bool(dato["mancanti"])
        # fascia superiore
        testa = tk.Canvas(top, height=128, highlightthickness=0, bg=MELANZANA_SCURA)
        testa.pack(fill="x")

        def disegna(_=None):
            testa.delete("all")
            l = testa.winfo_width()
            fascia(testa, l, 124, "#2C001E", "#77216F")
            testa.create_rectangle(0, 124, l, 128, fill=ARANCIO, outline="")
            testa.create_image(28, 62, image=immagine_icona(False), anchor="w")
            testa.create_text(110, 40, anchor="w", fill="#F7A27F", font=F["piccolo_b"],
                              text="NUOVO NUMERO DISPONIBILE" if nuovo else "NESSUN NUMERO NUOVO")
            testa.create_text(110, 68, anchor="w", fill="white", font=F["enorme"],
                              text=f"Newsletter {dato['numero']:03d} · {dato['anno']}")
            testa.create_text(110, 96, anchor="w", fill="#E6CFE0", font=F["testo"],
                              text=dato["anteprima"]["settimana"].capitalize())
        testa.bind("<Configure>", disegna)

        corpo_p = tk.Frame(top, bg=SCHEDA, padx=28, pady=18)
        corpo_p.pack(fill="both", expand=True)
        if not nuovo:
            nota(corpo_p, "Questo numero è già stato convertito. Puoi riconvertirlo, ad esempio se "
                          "nel frattempo il testo sul wiki è stato corretto.", TESTO, F["testo"]).pack(
                anchor="w", pady=(0, 10))
        articoli = dato["anteprima"]["articoli"]
        tk.Label(corpo_p, text=f"IN QUESTO NUMERO · {len(articoli)} ARTICOLI", bg=SCHEDA, fg=TENUE,
                 font=F["piccolo_b"]).pack(anchor="w")
        lista = tk.Frame(corpo_p, bg=SCHEDA)
        lista.pack(fill="x", pady=(6, 12))
        for t in articoli[:9]:
            r = tk.Frame(lista, bg=SCHEDA)
            r.pack(fill="x", pady=1)
            tk.Frame(r, bg=ARANCIO, width=6, height=6).pack(side="left", padx=(2, 10), pady=7, anchor="n")
            tk.Label(r, text=t, bg=SCHEDA, fg=TESTO, font=F["testo"], anchor="w", justify="left",
                     wraplength=500).pack(side="left", fill="x")
        if len(articoli) > 9:
            nota(lista, f"…e altri {len(articoli) - 9}").pack(anchor="w", padx=18)
        scelte = {}
        altri = [n for n in dato["mancanti"] if n != dato["numero"]]
        if altri:
            tk.Label(corpo_p, text="NON ANCORA CONVERTITI", bg=SCHEDA, fg=TENUE,
                     font=F["piccolo_b"]).pack(anchor="w", pady=(4, 4))
            riga_a = tk.Frame(corpo_p, bg=SCHEDA)
            riga_a.pack(anchor="w")
            for n in sorted(altri):
                scelte[n] = tk.BooleanVar(value=False)
                Spunta(riga_a, f"{n:03d}/{dato['anno']}", scelte[n]).pack(side="left", padx=(0, 16))
        opz = tk.Frame(corpo_p, bg=SCHEDA)
        opz.pack(anchor="w", pady=(14, 0))
        Interruttore(opz, "Compila anche il PDF", v_pdf).pack(side="left")
        link = tk.Label(opz, text="Apri sul wiki ↗", bg=SCHEDA, fg=ARANCIO, font=F["bottone"],
                        cursor="hand2")
        link.pack(side="left", padx=(24, 0))
        link.bind("<Button-1>", lambda e: subprocess.Popen(
            ["xdg-open", dato["url"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

        tk.Frame(top, bg=BORDO, height=1).pack(fill="x")
        piede_p = tk.Frame(top, bg=SCHEDA, padx=28, pady=14)
        piede_p.pack(fill="x")

        def procedi():
            elenco = [n for n, v in scelte.items() if v.get()] + [dato["numero"]]
            top.destroy()
            converti_numeri(dato, sorted(elenco))
        Bottone(piede_p, "Procedi" if nuovo else "Riconverti", procedi, tipo="primario",
                font=F["grande"], alto=42, padx=30).pack(side="right")
        Bottone(piede_p, "Più tardi", top.destroy, alto=42).pack(side="right", padx=(0, 10))
        top.bind("<Return>", lambda e: procedi())
        if prova_novita:
            prova_novita(top)
        mostra_modale(top)

    prova_novita = None

    # --- conversione -------------------------------------------------------------------
    lavoro_attivo = {"coda": None, "stop": None, "inizio": 0.0, "ultimo": ""}

    def lavoro(lista_parametri, coda, stop):
        for indice, (etichetta_n, parametri) in enumerate(lista_parametri):
            if stop.is_set():
                break
            try:
                coda.put(("inizio", etichetta_n))
                registro.info("Conversione avviata: %s", {k: v for k, v in parametri.items()
                                                          if k in ("numero", "file", "pdf")} or "testo già scaricato")
                r = esegui(avanzamento=lambda m: coda.put(("stato", m)), **parametri)
                if r.get("pdf"):
                    r["miniatura"] = miniatura_pdf(r["pdf"])
                coda.put(("risultato", r))
            except WikiBloccato as e:
                coda.put(("bloccato", {"messaggio": str(e), "voce": (etichetta_n, parametri),
                                       "resto": lista_parametri[indice + 1:]}))
                break
            except (Errore, RuntimeError, OSError, urllib.error.URLError) as e:
                registro.error("Conversione non riuscita (%s): %s", etichetta_n or parametri.get("numero")
                               or parametri.get("file") or "testo già scaricato", e)
                coda.put(("errore", f"{etichetta_n}: {e}" if etichetta_n else str(e)))
            except Exception as e:  # imprevisto: lo mostriamo comunque
                registro.exception("Errore imprevisto durante la conversione")
                coda.put(("errore", f"{type(e).__name__}: {e} (dettagli nel log di sistema)"))
        coda.put(("fine", None))

    def mostra_gettoni(errori, avvisi, refusi=0, mostra_ok=True):
        for g in (g_err, g_avv, g_ref, g_ok):
            g.pack_forget()
        for n, g, uno, piu, liv in ((errori, g_err, "errore", "errori", "ERRORE"),
                                    (avvisi, g_avv, "avviso", "avvisi", "AVVISO"),
                                    (refusi, g_ref, "refuso", "refusi", "REFUSO")):
            if n:
                g.configure_testo(f"{n} {uno if n == 1 else piu}", acceso=filtri[liv])
                g.pack(side="left", padx=(6, 0))
        if mostra_ok and not (errori or avvisi or refusi):
            g_ok.configure_testo("tutto ok")
            g_ok.pack(side="left", padx=(6, 0))

    totali = dict(stato.get("totali") or {"errori": 0, "avvisi": 0, "refusi": 0, "fallimenti": 0, "numeri": 0})
    esito_barra = {"colore": stato.get("barra")}

    def mostra_risultato(dato):
        risultato.clear()
        risultato.update(dato)
        lg = dato["log_obj"]
        errori, avvisi, refusi = lg.conta("ERRORE"), lg.conta("AVVISO"), lg.conta("REFUSO")
        totali["errori"] += errori
        totali["avvisi"] += avvisi
        totali["refusi"] += refusi
        eventi.append(("risultato", dato))
        disegna_risultato(dato)
        mostra_anteprima(dato)
        b_cartella.stato(True)
        b_aprilog.stato(True)
        b_apripdf.stato(bool(dato.get("pdf")))
        b_carica.stato(pdf_pronto())
        mostra_gettoni(totali["errori"], totali["avvisi"], totali["refusi"], mostra_ok=False)

    def controlla_coda(coda):
        if coda is not lavoro_attivo["coda"]:
            return          # lavoro interrotto: i suoi messaggi non interessano più
        try:
            while True:
                tipo, dato = coda.get_nowait()
                if tipo == "inizio":
                    totali["numeri"] += 1
                    if dato:
                        scrivi(f"Numero {dato}", "NUMERO")
                elif tipo == "stato":
                    m = re.match(r"^(Creato|Log):\s+(.+?)(  \(.*\))?$", dato)
                    if m:
                        dato = f"{m.group(1)}: {os.path.basename(m.group(2))}"
                    lavoro_attivo["ultimo"] = dato
                    v_stato.set(dato)
                    scrivi(dato, prompt=True)
                elif tipo == "risultato":
                    mostra_risultato(dato)
                elif tipo == "bloccato":
                    etichetta_b, parametri_b = dato["voce"]
                    m = re.match(r"^(\d{4})\D?(\d{1,3})$", str(parametri_b.get("numero", "")).strip())
                    if not m:
                        totali["fallimenti"] += 1
                        v_stato.set("Download bloccato dal wiki.")
                        scrivi(MSG_BLOCCATO.format(e=dato["messaggio"]), "ERRORE")
                        messagebox.showwarning("Download bloccato", MSG_BLOCCATO.format(e=dato["messaggio"]),
                                               parent=root)
                        v_sorgente.set("file")
                        continue
                    anno_b, num_b = int(m.group(1)), int(m.group(2))
                    lavoro_attivo["coda"] = None          # il lavoro riparte dopo il salvataggio dal browser
                    fine_lavoro()
                    barra.ferma(AMBRA)
                    v_stato.set(f"In attesa del numero {num_b:03d}/{anno_b} dal browser…")
                    registro.warning("Anti-bot: attendo dal browser il numero %s.%03d", anno_b, num_b)
                    scrivi(f"Il wiki ha bloccato il download di {anno_b}.{num_b:03d}: apro la pagina nel "
                           "browser e attendo il file in Scaricati.", "AVVISO")
                    resto = dato["resto"]

                    def riprendi(percorso, etichetta_b=etichetta_b, resto=resto):
                        registro.info("Anti-bot: %s", f"trovato {percorso}" if percorso else "annullato")
                        if not percorso:
                            esito_barra["colore"] = AMBRA
                            v_stato.set("Conversione annullata.")
                            scrivi("Conversione annullata: nessun file salvato dal browser.", "AVVISO")
                            return
                        scrivi(f"Trovato il testo salvato: {os.path.basename(percorso)}", "OK")
                        avvia_lavoro([(etichetta_b, {"file": percorso, "copia_txt": True})] + list(resto),
                                     continua=True)
                    root.after(50, lambda: attendi_dal_browser(anno_b, num_b, riprendi))
                    return
                elif tipo == "errore":
                    totali["fallimenti"] += 1
                    scrivi("Errore: " + dato, "ERRORE")
                    messagebox.showerror("Errore", dato, parent=root)
                elif tipo == "fine":
                    fine_lavoro()
                    e, a, r = totali["errori"], totali["avvisi"], totali["refusi"]
                    if totali["fallimenti"] and not risultato:
                        esito_barra["colore"] = ROSSO
                        barra.ferma(ROSSO)
                        v_stato.set("Conversione non riuscita.")
                        mostra_gettoni(0, 0, mostra_ok=False)
                        return
                    esito = ("Fatto" if not (e or a or r or totali["fallimenti"]) else
                             "Fatto: qualcosa da controllare" if not (e or totali["fallimenti"]) else
                             "Fatto, ma con errori da correggere")
                    scrivi(f"\n✓ {esito}." if not (e or totali["fallimenti"]) else f"\n! {esito}.",
                           "OK" if not (e or totali["fallimenti"]) else "ERRORE")
                    v_stato.set(f"{esito} · {os.path.basename(risultato.get('tex', ''))}")
                    esito_barra["colore"] = ROSSO if (e or totali["fallimenti"]) else AMBRA if (a or r) else VERDE
                    barra.ferma(esito_barra["colore"])
                    mostra_gettoni(e, a, r)
                    if novita["dati"] and v_sorgente.get() == "ultimo":
                        aggiorna_dopo_conversione()
                    return
        except queue.Empty:
            pass
        secondi = int(time.monotonic() - lavoro_attivo["inizio"])
        if secondi >= 3 and lavoro_attivo["ultimo"]:
            v_stato.set(f"{lavoro_attivo['ultimo']}   {secondi} s")
        root.after(100, controlla_coda, coda)

    def fine_lavoro():
        lavoro_attivo["coda"] = None
        b_converti.testo, b_converti.tipo, b_converti.comando = "Converti", "primario", converti_click
        b_converti.stato(True)

    def interrompi():
        registro.info("Conversione interrotta dall'utente")
        if lavoro_attivo["stop"]:
            lavoro_attivo["stop"].set()
        fine_lavoro()
        esito_barra["colore"] = AMBRA
        barra.ferma(AMBRA)
        v_stato.set("Interrotto.")
        scrivi("\nInterrotto. Il download o la conversione in corso proseguono in sottofondo e il "
               "risultato verrà ignorato; i numeri successivi non verranno elaborati.", "AVVISO")
        mostra_gettoni(totali["errori"], totali["avvisi"], totali["refusi"], mostra_ok=False)

    def aggiorna_dopo_conversione():
        d = novita["dati"]
        fatti = numeri_convertiti(cfg, d["anno"])
        d["mancanti"] = [n for n in d["mancanti"] if n not in fatti]
        if not d["mancanti"]:
            colore_pallino(VERDE)
            v_wiki.set(f"Sei aggiornato: {d['numero']:03d}/{d['anno']} già convertito")

    def cartella_scelta():
        """La destinazione la sceglie l'utente: se manca si apre subito Sfoglia…"""
        if v_cartella.get().strip():
            return True
        v_stato.set("Scegli prima dove salvare i file.")
        scegli_cartella()
        if not v_cartella.get().strip():
            v_stato.set("Nessuna cartella scelta: conversione annullata.")
            return False
        return leggi_impostazioni()

    def avvia_lavoro(lista_parametri, continua=False):
        if not continua and not cartella_scelta():
            return
        for _, p in lista_parametri:
            p.update({"pdf": v_pdf.get(), "salva_txt": v_txt.get(), "cfg": dict(cfg)})
        if not continua:
            pulisci()
            for k in totali:
                totali[k] = 0
            risultato.clear()
            anteprima_f.pack_forget()
            mostra_gettoni(0, 0, mostra_ok=False)
        try:
            salva_config(cfg)
        except OSError as e:
            scrivi(f"Impostazioni non salvate: {e}", "AVVISO")
        esito_barra["colore"] = None
        for b in (b_cartella, b_aprilog, b_apripdf, b_carica):
            b.stato(False)
        coda, stop = queue.Queue(), threading.Event()
        lavoro_attivo.update(coda=coda, stop=stop, inizio=time.monotonic(), ultimo="")
        b_converti.testo, b_converti.tipo, b_converti.comando = "Interrompi", "secondario", interrompi
        b_converti.stato(True)
        v_stato.set("Al lavoro…")
        barra.avvia()
        threading.Thread(target=lavoro, args=(lista_parametri, coda, stop), daemon=True).start()
        root.after(100, controlla_coda, coda)

    def converti_numeri(dato, numeri):
        if not leggi_impostazioni():
            return
        lista = []
        for n in numeri:
            etichetta_n = f"{n:03d}/{dato['anno']}" if len(numeri) > 1 else None
            testo_noto = (dato.get("testi") or {}).get(n) or (dato["testo"] if n == dato["numero"] else None)
            if testo_noto:
                lista.append((etichetta_n, {"pronto": (dato["anno"], n, testo_noto)}))
            else:
                lista.append((etichetta_n, {"numero": f"{dato['anno']}.{n:03d}"}))
        avvia_lavoro(lista)

    def converti_click():
        if lavoro_attivo["coda"] is not None or not b_converti.attivo or not leggi_impostazioni():
            return
        sorgente = v_sorgente.get()
        if sorgente == "ultimo":
            # mai in automatico: prima il popup con l'anteprima del numero
            if novita["dati"]:
                mostra_novita(novita["dati"])
            else:
                avvia_controllo(poi=lambda: novita["dati"] and mostra_novita(novita["dati"]))
            return
        if sorgente == "numero":
            avvia_lavoro([(None, {"numero": v_numero.get()})])
        else:
            if not v_file.get().strip():
                scegli_file()
                if not v_file.get().strip():
                    return
            avvia_lavoro([(None, {"file": v_file.get().strip()})])

    # --- blocco anti-bot: il testo arriva dal browser ---------------------------------------
    def attendi_dal_browser(anno, num, poi):
        url = url_raw(anno, num)
        scaricati = cartella_scaricati()
        inizio = time.time()
        esito = {"percorso": None, "dimensione": None}
        apri_nel_browser(url)

        top = finestra_modale("Il wiki ha bloccato il download", 600, 470)
        top.configure(bg=SCHEDA)
        testa = tk.Canvas(top, height=96, highlightthickness=0, bg=MELANZANA_SCURA)
        testa.pack(fill="x")

        def disegna(_=None):
            testa.delete("all")
            l = testa.winfo_width()
            fascia(testa, l, 92, "#2C001E", "#77216F")
            testa.create_rectangle(0, 92, l, 96, fill=ARANCIO, outline="")
            testa.create_text(28, 34, anchor="w", fill="#F7A27F", font=F["piccolo_b"],
                              text="IL WIKI HA BLOCCATO IL DOWNLOAD AUTOMATICO")
            testa.create_text(28, 62, anchor="w", fill="white", font=F["enorme"],
                              text=f"Salva il numero {num:03d}/{anno} dal browser")
        testa.bind("<Configure>", disegna)

        corpo_b = tk.Frame(top, bg=SCHEDA, padx=28, pady=18)
        corpo_b.pack(fill="both", expand=True)
        for i, testo_passo in enumerate((
                f"Ho aperto la pagina del numero {anno}.{num:03d} nel browser.",
                f"Salvala con Ctrl+S nella cartella {scaricati.replace(casa, '~')}.",
                "Il programma la trova da solo e riprende la conversione.")):
            riga_p = tk.Frame(corpo_b, bg=SCHEDA)
            riga_p.pack(fill="x", pady=5)
            tondo = tk.Canvas(riga_p, width=28, height=28, bg=SCHEDA, highlightthickness=0)
            disco(tondo, 14, 14, 13, ARANCIO if i < 2 else SEGMENTATO)
            tondo.create_text(14, 14, text=str(i + 1), fill="white" if i < 2 else TENUE, font=F["bottone"])
            tondo.pack(side="left")
            tk.Label(riga_p, text=testo_passo, bg=SCHEDA, fg=TESTO, font=F["testo"], anchor="w", justify="left",
                     wraplength=480).pack(side="left", padx=(12, 0), fill="x")
        v_attesa = tk.StringVar(value=f"In attesa del file in {scaricati.replace(casa, '~')}…")
        tk.Label(corpo_b, textvariable=v_attesa, bg=SCHEDA, fg=TENUE, font=F["piccolo"], anchor="w").pack(
            fill="x", pady=(16, 6))
        barra_b = Avanzamento(corpo_b)
        barra_b.pack(fill="x")
        nota(corpo_b, "Il nome del file non conta: va bene quello proposto dal browser.").pack(anchor="w", pady=(8, 0))

        tk.Frame(top, bg=BORDO, height=1).pack(fill="x")
        piede_b = tk.Frame(top, bg=SCHEDA, padx=28, pady=14)
        piede_b.pack(fill="x")

        def scegli():
            x = esplora("file", "Scegli il testo salvato dal browser", scaricati)
            if x:
                esito["percorso"] = x
                top.destroy()
        Bottone(piede_b, "Scegli il file…", scegli, alto=40).pack(side="right")
        Bottone(piede_b, "Riapri la pagina", lambda: apri_nel_browser(url), alto=40).pack(side="right", padx=(0, 10))
        Bottone(piede_b, "Annulla", top.destroy, tipo="piatto", alto=40).pack(side="left")

        def osserva():
            if not top.winfo_exists():
                return
            trovato = cerca_txt_salvato(scaricati, inizio, anno, num)
            if trovato:
                dimensione = os.path.getsize(trovato)
                if esito["dimensione"] == (trovato, dimensione):      # dimensione stabile: salvataggio finito
                    esito["percorso"] = trovato
                    v_attesa.set(f"Trovato: {os.path.basename(trovato)}")
                    barra_b.ferma(VERDE)
                    top.after(500, top.destroy)
                    return
                esito["dimensione"] = (trovato, dimensione)
            top.after(800, osserva)
        barra_b.avvia()
        top.after(800, osserva)
        if prova_browser:
            prova_browser(top, scaricati, inizio)
        mostra_modale(top)
        poi(esito["percorso"])

    prova_browser = None
    prova_carica = None

    # --- aggiornamenti da GitHub -------------------------------------------------------
    def riavvia_programma():
        registro.info("Riavvio del programma dopo l'aggiornamento")
        try:
            root.destroy()
        finally:
            os.execv(sys.executable, [sys.executable, os.path.realpath(sys.argv[0]), "--gui"])

    def controlla_aggiornamenti():
        coda_a = queue.Queue()

        def lavora():
            try:
                remota = versione_remota()
                if not remota or versione_tupla(remota) <= versione_tupla(VERSIONE):
                    return
                if cfg.get("aggiornamenti_automatici", True) and programma_installato():
                    coda_a.put(("aggiornato", aggiorna_programma() or remota))
                else:
                    coda_a.put(("disponibile", remota))
            except Exception as e:      # senza rete o GitHub irraggiungibile: nessun disturbo
                registro.warning("Controllo degli aggiornamenti non riuscito: %s", e)
                coda_a.put(("errore", str(e)))

        threading.Thread(target=lavora, daemon=True).start()

        def attendi():
            if not root.winfo_exists() or root_generazione[0] != generazione:
                return
            try:
                tipo, dato = coda_a.get_nowait()
            except queue.Empty:
                root.after(500, attendi)
                return
            if tipo in ("aggiornato", "disponibile"):
                registro.info("Aggiornamenti: versione %s %s", dato,
                              "installata" if tipo == "aggiornato" else "disponibile")
            if tipo == "aggiornato":
                conto = {"s": 5, "attivo": True}

                def piu_tardi():
                    conto["attivo"] = False
                    mostra_banner(f"Aggiornato alla versione {dato}: verrà usata al prossimo avvio.",
                                  [("Riavvia ora", riavvia_programma), ("Chiudi", nascondi_banner)])

                def scorri():
                    if not conto["attivo"] or not root.winfo_exists() or root_generazione[0] != generazione:
                        return
                    libero = lavoro_attivo["coda"] is None and root.grab_current() is None
                    if libero:
                        conto["s"] -= 1
                    if conto["s"] <= 0:
                        riavvia_programma()
                        return
                    attesa = f"riavvio tra {conto['s']} s" if libero else "riavvio a lavoro finito"
                    mostra_banner(f"Newsletter Ubuntu-it è stato aggiornato alla versione {dato} · {attesa}",
                                  [("Riavvia ora", riavvia_programma), ("Più tardi", piu_tardi)])
                    root.after(1000, scorri)
                scorri()
            elif tipo == "disponibile":
                azioni = [("Apri GitHub", lambda: apri_nel_browser(URL_REPO)), ("Chiudi", nascondi_banner)]
                if programma_installato():
                    def aggiorna_ora():
                        nascondi_banner()
                        cfg["aggiornamenti_automatici"] = True
                        controlla_aggiornamenti()
                    azioni = [("Aggiorna ora", aggiorna_ora), ("Chiudi", nascondi_banner)]
                mostra_banner(f"È disponibile la versione {dato} (questa è la {VERSIONE}).", azioni)
        root.after(500, attendi)

    # --- statistiche dei bug -------------------------------------------------------------
    def mostra_statistiche():
        top = finestra_modale("Statistiche dei bug", 620, 560)
        top.configure(bg=SCHEDA)
        testa = tk.Canvas(top, height=96, highlightthickness=0, bg=MELANZANA_SCURA)
        testa.pack(fill="x")

        def disegna(_=None):
            testa.delete("all")
            l = testa.winfo_width()
            fascia(testa, l, 92, "#2C001E", "#77216F")
            testa.create_rectangle(0, 92, l, 96, fill=ARANCIO, outline="")
            testa.create_text(28, 34, anchor="w", fill="#F7A27F", font=F["piccolo_b"],
                              text="LAUNCHPAD · UBUNTU")
            testa.create_text(28, 62, anchor="w", fill="white", font=F["enorme"],
                              text="Statistiche dei bug")
        testa.bind("<Configure>", disegna)

        corpo_s = tk.Frame(top, bg=SCHEDA, padx=24, pady=18)
        corpo_s.pack(fill="both", expand=True)
        riquadri = tk.Frame(corpo_s, bg=SCHEDA)
        riquadri.pack(fill="x")
        valori_v, diff_g = {}, {}
        for i, (chiave, nome) in enumerate(VOCI_STATISTICHE):
            riquadri.columnconfigure(i, weight=1, uniform="stat")
            pan = Pannello(riquadri, sfondo=SFONDO, bordo=BORDO, r=14, padx=16, pady=12)
            pan.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            tk.Label(pan.interno, text=nome.upper(), bg=SFONDO, fg=TENUE, font=F["piccolo_b"]).pack(anchor="w")
            valori_v[chiave] = tk.StringVar(value="…")
            tk.Label(pan.interno, textvariable=valori_v[chiave], bg=SFONDO, fg=TESTO,
                     font=F["numero"]).pack(anchor="w", pady=(2, 4))
            diff_g[chiave] = Gettone(pan.interno, TENUE, SFONDO)
            diff_g[chiave].pack(anchor="w")
        v_rif = tk.StringVar(value="")
        tk.Label(corpo_s, textvariable=v_rif, bg=SCHEDA, fg=TENUE, font=F["piccolo"], anchor="w",
                 justify="left", wraplength=560).pack(fill="x", pady=(12, 8))
        tk.Label(corpo_s, text="RIGHE PER IL WIKI · SEZIONE «BUG RIPORTATI»", bg=SCHEDA, fg=TENUE,
                 font=F["piccolo_b"]).pack(anchor="w")
        pan_testo = Pannello(corpo_s, sfondo=CONSOLE, bordo=CONSOLE, r=12, padx=12, pady=10)
        pan_testo.pack(fill="x", pady=(6, 0))
        blocco = tk.Text(pan_testo.interno, height=3, wrap="none", font=F["mono"], relief="flat", bd=0,
                         bg=CONSOLE, fg=CONSOLE_TESTO, highlightthickness=0, insertbackground=ARANCIO)
        blocco.pack(fill="x")
        v_stato_s = tk.StringVar(value="Interrogo Launchpad…")
        tk.Label(corpo_s, textvariable=v_stato_s, bg=SCHEDA, fg=TENUE, font=F["piccolo"], anchor="w").pack(
            fill="x", pady=(10, 0))
        barra_s = Avanzamento(corpo_s)
        barra_s.pack(fill="x", pady=(6, 0))

        tk.Frame(top, bg=BORDO, height=1).pack(fill="x")
        piede_s = tk.Frame(top, bg=SCHEDA, padx=24, pady=14)
        piede_s.pack(fill="x")
        b_copia = Bottone(piede_s, "Copia per il wiki", None, tipo="primario", alto=40, padx=24)
        b_copia.pack(side="right")
        b_aggiorna = Bottone(piede_s, "Aggiorna", None, alto=40)
        b_aggiorna.pack(side="right", padx=(0, 10))
        Bottone(piede_s, "Chiudi", top.destroy, tipo="piatto", alto=40).pack(side="left")
        b_copia.stato(False)

        rif = riferimento_statistiche(cfg)
        if not rif and novita["dati"]:
            st = leggi_statistiche(novita["dati"]["testo"])
            if st:
                rif = ({k: v[0] for k, v in st.items()},
                       f"{novita['dati']['anno']}.{novita['dati']['numero']:03d}")
        coda_s = queue.Queue()

        def copia():
            root.clipboard_clear()
            root.clipboard_append(blocco.get("1.0", "end").rstrip("\n") + "\n")
            v_stato_s.set("Copiato: incolla le righe nella sezione «Bug riportati» del wiki.")
        b_copia.comando = copia

        def avvia():
            b_aggiorna.stato(False)
            b_copia.stato(False)
            for k in valori_v:
                valori_v[k].set("…")
                diff_g[k].pack_forget()
            barra_s.avvia()

            def lavora():
                try:
                    coda_s.put(("ok", statistiche_launchpad(lambda m: coda_s.put(("passo", m)))))
                except Exception as e:
                    coda_s.put(("errore", str(e)))
            threading.Thread(target=lavora, daemon=True).start()
            root.after(150, attendi)
        b_aggiorna.comando = avvia

        def attendi():
            if not top.winfo_exists():
                return
            try:
                while True:
                    tipo, dato = coda_s.get_nowait()
                    if tipo == "passo":
                        v_stato_s.set("Interrogo Launchpad: " + dato)
                        continue
                    b_aggiorna.stato(True)
                    if tipo == "errore":
                        barra_s.ferma(ROSSO)
                        v_stato_s.set(dato + ". Riprova tra poco con «Aggiorna».")
                        return
                    barra_s.ferma(VERDE)
                    prec = rif[0] if rif else None
                    for k, _ in VOCI_STATISTICHE:
                        valori_v[k].set(f"{dato[k]:,}".replace(",", "."))
                        if prec and k in prec:
                            d = dato[k] - prec[k]
                            colori = ((ROSSO, ROSSO_TENUE) if d > 0 else (VERDE_TESTO, VERDE_TENUE) if d < 0
                                      else (TENUE, SEGMENTATO))
                            diff_g[k].colore, diff_g[k].sfondo = colori
                            diff_g[k].configure_testo(formatta_differenza(d))
                            diff_g[k].pack(anchor="w")
                    blocco.delete("1.0", "end")
                    blocco.insert("1.0", blocco_statistiche(dato, prec))
                    b_copia.stato(True)
                    adesso = dt.datetime.now().strftime("%H:%M")
                    v_stato_s.set(f"Valori letti da Launchpad alle {adesso}.")
                    return
            except queue.Empty:
                root.after(150, attendi)

        v_rif.set(f"Differenze calcolate rispetto al numero {rif[1].replace('.', '/')} "
                  "(il più recente con le statistiche nella tua cartella)." if rif else
                  "Nessun numero precedente con le statistiche: le differenze restano «???» "
                  "da completare a mano.")
        avvia()
        mostra_modale(top)

    # --- tema giorno/notte -----------------------------------------------------------------
    def raccogli_stato():
        return {
            "tema": tema, "sorgente": v_sorgente.get(),
            "numero": v_numero.get(), "file": v_file.get(), "cartella": v_cartella.get(),
            "pdf": v_pdf.get(), "txt": v_txt.get(), "cura": v_cura.get(), "pdf_utente": v_pdf_utente.get(),
            "pdf_nome": v_pdf_nome.get(), "edizione": v_edizione.get(), "imp_aperte": v_aperte.get(),
            "novita": novita["dati"], "novita_errore": (v_wiki.get(), v_wiki2.get()),
            "ultimo_controllo": (novita.get("ultimo"), getattr(v_wiki3, "prefisso", "Controllato")),
            "eventi": eventi, "totali": totali, "risultato": dict(risultato), "filtri": filtri,
            "barra": esito_barra["colore"], "v_stato": v_stato.get(),
        }

    def cambia_tema():
        if lavoro_attivo["coda"] is not None:
            messagebox.showinfo("Conversione in corso", "Aspetta la fine della conversione per cambiare tema.",
                                parent=root)
            return
        nuovo = "scuro" if tema == "chiaro" else "chiaro"
        cfg["tema"] = nuovo
        try:
            salva_config(dict(carica_config(), tema=nuovo))
        except OSError:
            pass
        st = raccogli_stato()
        st["tema"] = nuovo
        if st["barra"] in (PALETTE[tema]["ROSSO"], PALETTE[tema]["VERDE"], PALETTE[tema]["AMBRA"]):
            st["barra"] = {PALETTE[tema]["ROSSO"]: "ROSSO", PALETTE[tema]["VERDE"]: "VERDE",
                           PALETTE[tema]["AMBRA"]: "AMBRA"}[st["barra"]]
        st["segnalati"] = sorted(novita["segnalati"])
        suggerimento.nascondi()
        registro.info("Cambio di tema: %s", nuovo)
        transizione(PALETTE[nuovo]["SFONDO"], lambda: _finestra(root, prova, st))

    def transizione(colore, azione):
        # Dissolvenza: un velo del colore del nuovo tema copre la finestra, il contenuto
        # viene ricostruito sotto, poi il velo svanisce. Senza compositore: cambio diretto.
        root.update_idletasks()
        try:
            velo = tk.Toplevel(root)
            velo._velo = True
            velo.overrideredirect(True)
            velo.configure(bg=colore)
            velo.geometry(f"{root.winfo_width()}x{root.winfo_height() - testata.winfo_height()}"
                          f"+{root.winfo_rootx()}+{root.winfo_rooty() + testata.winfo_height()}")
            velo.attributes("-alpha", 0.0)
            velo.lift()
        except tk.TclError:
            azione()
            return

        def svanisci(alfa):
            try:
                if alfa <= 0:
                    velo.destroy()
                    return
                velo.attributes("-alpha", alfa)
                velo.lift()
                root.after(16, svanisci, round(alfa - 0.12, 2))
            except tk.TclError:
                pass

        def compari(alfa):
            try:
                velo.attributes("-alpha", min(alfa, 1.0))
            except tk.TclError:
                pass
            if alfa < 1.0:
                root.after(16, compari, round(alfa + 0.25, 2))
                return
            azione()
            root.update_idletasks()
            root.after(30, svanisci, 1.0)
        compari(0.25)

    def ripristina():
        for var, chiave in ((v_sorgente, "sorgente"), (v_numero, "numero"), (v_file, "file"),
                            (v_cartella, "cartella"), (v_pdf, "pdf"), (v_txt, "txt"), (v_cura, "cura"),
                            (v_pdf_utente, "pdf_utente"), (v_pdf_nome, "pdf_nome"), (v_edizione, "edizione")):
            if chiave in stato:
                var.set(stato[chiave])
        if stato.get("imp_aperte"):
            alterna_impostazioni()
        if stato.get("novita"):
            novita["dati"] = stato["novita"]
            d = novita["dati"]
            colore_pallino(ARANCIO if d["mancanti"] else VERDE)
        elif stato.get("novita_errore"):
            colore_pallino(ROSSO if "Impossibile" in stato["novita_errore"][0] else GRIGIO_CALDO)
        if stato.get("novita_errore"):
            v_wiki.set(stato["novita_errore"][0])
            v_wiki2.set(stato["novita_errore"][1])
        if stato.get("ultimo_controllo") and stato["ultimo_controllo"][0]:
            novita["ultimo"] = stato["ultimo_controllo"][0]
            aggiorna_ora_controllo(stato["ultimo_controllo"][1])
        if stato.get("v_stato"):
            v_stato.set(stato["v_stato"])
        ridisegna_console()
        if risultato:
            b_cartella.stato(True)
            b_aprilog.stato(True)
            b_apripdf.stato(bool(risultato.get("pdf")))
            b_carica.stato(pdf_pronto())
            mostra_anteprima(risultato)
            mostra_gettoni(totali["errori"], totali["avvisi"], totali["refusi"])
        if stato.get("barra"):
            esito_barra["colore"] = {"ROSSO": ROSSO, "VERDE": VERDE, "AMBRA": AMBRA}.get(stato["barra"],
                                                                                       stato["barra"])
            root.after(50, lambda: barra.ferma(esito_barra["colore"]))

    b_converti.comando = converti_click

    # --- scorciatoie da tastiera ------------------------------------------------------
    # Niente Ctrl+lettera già usate dalle caselle di testo di Tk (Ctrl+A/B/D/E/F/H/K/T):
    # premute mentre si scrive farebbero due cose insieme.
    def sorgente_numero():
        v_sorgente.set("numero")
        campo_numero.e.focus_set()
        campo_numero.e.icursor("end")

    def apri_log_sistema():
        if os.path.exists(file_log_sistema()):
            apri_nel_browser(file_log_sistema())

    def solo_se_libero(funzione):
        # mentre si converte, le scorciatoie che cambiano lo stato non fanno nulla
        return lambda: None if lavoro_attivo["coda"] is not None else funzione()

    SCORCIATOIE = [
        ("Conversione", None, None),
        ("Invio", ("<Return>", "<KP_Enter>"), ("Converti", converti_click)),
        ("Esc", ("<Escape>",), ("Interrompi la conversione in corso",
                                lambda: interrompi() if lavoro_attivo["coda"] is not None else None)),
        ("Ctrl+1", ("<Control-Key-1>",), ("Sorgente: ultimo numero", solo_se_libero(lambda: v_sorgente.set("ultimo")))),
        ("Ctrl+2", ("<Control-Key-2>",), ("Sorgente: numero specifico", solo_se_libero(sorgente_numero))),
        ("Ctrl+3", ("<Control-Key-3>",), ("Sorgente: file .txt", solo_se_libero(lambda: v_sorgente.set("file")))),
        ("Ctrl+O", ("<Control-o>",), ("Scegli il file .txt",
                                      solo_se_libero(lambda: (v_sorgente.set("file"), scegli_file())))),
        ("F5  ·  Ctrl+R", ("<F5>", "<Control-r>"), ("Controlla ora il wiki", lambda: avvia_controllo(manuale=True))),
        ("Risultato", None, None),
        ("Ctrl+P", ("<Control-p>",), ("Apri il PDF", lambda: apri("pdf"))),
        ("Ctrl+U", ("<Control-u>",), ("Carica il PDF sul wiki", lambda: carica_sul_wiki())),
        ("Ctrl+Maiusc+O", ("<Control-O>", "<Control-Shift-O>"), ("Apri la cartella del numero", lambda: apri("cartella"))),
        ("Ctrl+L", ("<Control-l>",), ("Apri il log di sistema", apri_log_sistema)),
        ("Finestra", None, None),
        ("Ctrl+,", ("<Control-comma>",), ("Mostra o nascondi le impostazioni personali", alterna_impostazioni)),
        ("Ctrl+Maiusc+T", ("<Control-T>", "<Control-Shift-T>"), ("Modalità giorno/notte", cambia_tema)),
        ("Ctrl+Maiusc+S", ("<Control-S>", "<Control-Shift-S>"), ("Statistiche dei bug", mostra_statistiche)),
        ("F1", ("<F1>",), ("Questo elenco di scorciatoie", lambda: mostra_scorciatoie())),
        ("Ctrl+Q", ("<Control-q>",), ("Chiudi il programma", lambda: root.destroy())),
    ]

    def collega(sequenza, funzione):
        def gestore(e):
            # solo nella finestra principale: nei popup Invio ed Esc hanno il loro significato
            if e.widget.winfo_toplevel() is not root or root.grab_current() is not None:
                return None
            funzione()
            return "break"
        root.bind(sequenza, gestore)

    for _, sequenze, azione in SCORCIATOIE:
        for sequenza in sequenze or ():
            collega(sequenza, azione[1])

    def mostra_scorciatoie():
        top = finestra_modale("Scorciatoie da tastiera", 500, 600)
        top.configure(bg=SCHEDA)
        testa = tk.Canvas(top, height=96, highlightthickness=0, bg=MELANZANA_SCURA)
        testa.pack(fill="x")

        def disegna(_=None):
            testa.delete("all")
            l = testa.winfo_width()
            fascia(testa, l, 92, "#2C001E", "#77216F")
            testa.create_rectangle(0, 92, l, 96, fill=ARANCIO, outline="")
            testa.create_text(28, 34, anchor="w", fill="#F7A27F", font=F["piccolo_b"], text="TASTIERA")
            testa.create_text(28, 62, anchor="w", fill="white", font=F["enorme"], text="Scorciatoie")
        testa.bind("<Configure>", disegna)

        elenco = tk.Frame(top, bg=SCHEDA, padx=28, pady=10)
        elenco.pack(fill="both", expand=True)
        elenco.columnconfigure(1, weight=1)
        for riga, (tasti, sequenze, azione) in enumerate(SCORCIATOIE):
            if sequenze is None:
                tk.Label(elenco, text=tasti.upper(), bg=SCHEDA, fg=TENUE, font=F["piccolo_b"]).grid(
                    row=riga, column=0, columnspan=2, sticky="w", pady=(12 if riga else 4, 4))
                continue
            tk.Label(elenco, text=tasti, bg=SFONDO, fg=TESTO, font=F["mono"], padx=8, pady=2,
                     highlightthickness=1, highlightbackground=BORDO).grid(
                row=riga, column=0, sticky="w", pady=2)
            tk.Label(elenco, text=azione[0], bg=SCHEDA, fg=TESTO, font=F["testo"], anchor="w").grid(
                row=riga, column=1, sticky="w", padx=(14, 0), pady=2)
        Bottone(top, "Chiudi", top.destroy, tipo="primario").pack(side="bottom", anchor="e", padx=28, pady=(0, 18))
        mostra_modale(top)

    root.after(60 * 1000, ricontrolla_etichetta_ora)

    if stato:
        ripristina()

    def imposta_browser(funzione):
        nonlocal prova_browser
        prova_browser = funzione

    if prova:   # solo per i test automatici
        def imposta(**kw):
            nonlocal prova_esplora, prova_novita, prova_carica
            prova_carica = kw.get("carica", prova_carica)
            prova_esplora = kw.get("esplora", prova_esplora)
            prova_novita = kw.get("novita", prova_novita)
        prova(root, {"sorgente": v_sorgente, "file": v_file, "converti": converti_click,
                     "impostazioni": alterna_impostazioni, "esplora": esplora,
                     "mostra_novita": mostra_novita, "imposta": imposta,
                     "controllo": avvia_controllo, "tema": cambia_tema, "statistiche": mostra_statistiche,
                     "filtro": alterna_filtro, "stato": stato, "banner": mostra_banner,
                     "attendi_browser": attendi_dal_browser, "aggiornamenti": controlla_aggiornamenti,
                     "imposta_browser": imposta_browser, "avvia_lavoro": avvia_lavoro,
                     "ora_controllo": v_wiki3, "scorciatoie": mostra_scorciatoie,
                     "carica": carica_sul_wiki, "risultato": risultato, "pulsante_carica": b_carica})
    elif not stato:
        root.after(600, avvia_controllo)
        root.after(1500, controlla_aggiornamenti)   # avvisa sempre; installa da solo se attivo
    if not prova:
        root.after(45 * 60 * 1000, scansione_periodica)


# ---------------------------------------------------------------------------
# TERMINALE
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="Converte la Newsletter Ubuntu-it dal wiki (.txt) a LaTeX (.tex).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Esempi:\n"
               "  newsletter2tex                  ultimo numero dal wiki\n"
               "  newsletter2tex -n 2026.031      numero preciso dal wiki\n"
               "  newsletter2tex -f vecchio.txt   file locale\n"
               "  newsletter2tex --pdf            ultimo numero + PDF\n"
               "  newsletter2tex --gui            interfaccia grafica\n\n"
               "Impostazioni personali (cartella, nomi): " + CONFIG_FILE)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("-f", "--file", help="file .txt (sorgente wiki) da convertire")
    g.add_argument("-n", "--numero", help="numero da scaricare, es. 2026.031")
    g.add_argument("--gui", action="store_true", help="apre l'interfaccia grafica")
    g.add_argument("--aggiorna", action="store_true", help="aggiorna il programma installato da GitHub")
    g.add_argument("--notifiche", choices=("on", "off", "auto", "stato"),
                   help="avviso dei nuovi numeri il lunedì sera e il martedì (timer di systemd)")
    g.add_argument("--notifica", action="store_true", help=argparse.SUPPRESS)
    g.add_argument("--log", action="store_true", help="mostra dove si trova il log di sistema e le ultime righe")
    g.add_argument("--statistiche", action="store_true",
                   help="legge da Launchpad i bug aperti, critici e nuovi e stampa le righe per il wiki")
    g.add_argument("--controlla", action="store_true",
                   help="controlla se sul wiki ci sono numeri non ancora convertiti")
    g.add_argument("--esporta-icona", metavar="PERCORSO", nargs="?", const=PERCORSO_ICONA,
                   help="salva l'icona del programma (per il menu applicazioni)")
    ap.add_argument("-o", "--output", help="cartella dell'anno (il numero va nella sottocartella NNN)")
    ap.add_argument("--pdf", action="store_true", help="compila anche il PDF con pdflatex")
    ap.add_argument("--edizione", action="append", metavar='UTENTE:"Nome"',
                    help="collaboratore all'edizione (ripetibile); sostituisce quelli del .txt")
    ap.add_argument("--no-txt", action="store_true", help="non salvare il .txt scaricato")
    ap.add_argument("--attendi", action="store_true", help="attende Invio prima di chiudere")
    ap.add_argument("--versione", action="version",
                    version=f"newsletter2tex {VERSIONE} · Design {DESIGN}")
    args = ap.parse_args()

    if args.log:
        print(f"Log di sistema: {file_log_sistema()}\n")
        print("".join(coda_log_sistema(40)) or "(ancora vuoto)")
        return
    modalita = ("interfaccia grafica" if args.gui else "controllo programmato" if args.notifica else
                "terminale: " + " ".join(sys.argv[1:]) if sys.argv[1:] else "terminale")
    avvia_registro(modalita)

    if args.gui:
        avvia_gui()
        return
    if args.esporta_icona:
        print(esporta_icona(os.path.expanduser(args.esporta_icona)))
        return
    if args.notifica:
        notifica_nuovi_numeri()
        return
    if args.notifiche:
        try:
            if args.notifiche == "stato":
                print("Avviso dei nuovi numeri: " + ("attivo" if notifiche_attive() else "non attivo"))
                return
            attive = args.notifiche == "on" or (args.notifiche == "auto" and carica_config().get("notifiche", True))
            if args.notifiche in ("on", "off"):
                salva_config(dict(carica_config(), notifiche=attive))
            print(imposta_notifiche(attive))
        except (RuntimeError, OSError, subprocess.SubprocessError) as e:
            sys.exit(f"Avviso dei nuovi numeri: {e}")
        return
    if args.aggiorna:
        try:
            nuova = aggiorna_programma()
        except (RuntimeError, OSError, urllib.error.URLError) as e:
            sys.exit(f"Aggiornamento non riuscito: {getattr(e, 'reason', e)}")
        print(f"Aggiornato alla versione {nuova}" if nuova else f"Già aggiornato (versione {VERSIONE})")
        return
    if args.statistiche:
        cfg = carica_config()
        try:
            valori = statistiche_launchpad(lambda m: print("  " + m, file=sys.stderr))
        except RuntimeError as e:
            sys.exit(str(e))
        rif = riferimento_statistiche(cfg)
        if rif:
            print(f"Differenze rispetto al numero {rif[1]}:\n", file=sys.stderr)
        print(blocco_statistiche(valori, rif[0] if rif else None))
        return
    if args.controlla:
        try:
            n = controlla_novita(carica_config())
        except WikiBloccato as e:
            sys.exit(MSG_BLOCCATO.format(e=e))
        except (OSError, RuntimeError, urllib.error.URLError) as e:
            sys.exit(f"Impossibile controllare il wiki: {getattr(e, 'reason', e)}")
        print(f"Ultimo numero sul wiki: {n['anno']}.{n['numero']:03d}  ({n['anteprima']['settimana']})")
        if n["mancanti"]:
            print("Da convertire: " + ", ".join(f"{n['anno']}.{x:03d}" for x in n["mancanti"]))
            for t in n["anteprima"]["articoli"]:
                print("  · " + t)
        else:
            print("Già convertito: sei aggiornato.")
        return

    codice = 0
    try:
        r = esegui(file=args.file, numero=args.numero, output=args.output, pdf=args.pdf,
                   salva_txt=not args.no_txt, edizione=leggi_persone(args.edizione))
        codice = r["codice"]
    except WikiBloccato as e:
        print("\n" + MSG_BLOCCATO.format(e=e) + "\n(da terminale:  newsletter2tex -f file.txt)",
              file=sys.stderr)
        codice = 2
    except (Errore, RuntimeError, OSError, urllib.error.URLError) as e:
        registro.error("Errore da terminale: %s", e)
        print(f"\nErrore: {e}", file=sys.stderr)
        codice = 2

    if args.attendi:
        try:
            input("\nPremi Invio per chiudere...")
        except EOFError:
            pass
    sys.exit(codice)


if __name__ == "__main__":
    main()
