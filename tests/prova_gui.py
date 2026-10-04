"""Prova dell'interfaccia grafica (richiede uno schermo, anche virtuale: xvfb-run).

Uso:  xvfb-run -a python3 tests/prova_gui.py

Controlla che la finestra resti reattiva quando il mouse passa sui pulsanti
dell'intestazione, che il popup del nuovo numero si apra e si chiuda senza
lasciare errori, che il cambio di tema ricostruisca la finestra e che
l'esplora file si apra. La rete è simulata: il wiki non viene contattato.
"""

import json
import os
import sys
import tempfile
import time
import traceback

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADICE)

casa = tempfile.mkdtemp()
os.environ["HOME"] = casa
os.environ["XDG_CONFIG_HOME"] = os.path.join(casa, ".config")
os.environ["XDG_CACHE_HOME"] = os.path.join(casa, ".cache")
os.environ["XDG_STATE_HOME"] = os.path.join(casa, ".local", "state")
os.makedirs(os.path.join(casa, ".config", "newsletter2tex"))
os.makedirs(os.path.join(casa, "2025"))          # cartella dell'anno della prova
with open(os.path.join(casa, ".config", "newsletter2tex", "config.json"), "w") as f:
    json.dump({"tema": "chiaro", "cartella_lavoro": os.path.join(casa, "{anno}")}, f)

import newsletter2tex as N  # noqa: E402

TESTO = open(os.path.join(RADICE, "esempi", "NewsletterItaliana_2025.011.txt"), encoding="utf-8").read()
N.avvia_registro("prova dell'interfaccia")
N.versione_remota = lambda: N.VERSIONE
N.trova_ultimo_numero = lambda log: (2025, 11, TESTO)

errori = []
passi = []
giro = {"n": 0}


def tutti(w):
    yield w
    for figlio in w.winfo_children():
        yield from tutti(figlio)


def controlla(cond, messaggio):
    passi.append(("ok" if cond else "ERRORE") + ": " + messaggio)
    if not cond:
        errori.append(messaggio)


def prova(root, c):
    giro["n"] += 1
    import tkinter as tk
    # ogni eccezione nelle callback di Tk è un errore della prova
    root.report_callback_exception = lambda *e: errori.append("".join(traceback.format_exception(*e)))

    if giro["n"] == 1:
        giro["finestra"] = root.winfo_id()
    if giro["n"] == 2:     # contenuto ricostruito dopo il cambio di tema
        controlla(c["stato"].get("tema") == "scuro", "il cambio di tema passa alla modalità notte")
        controlla(root.winfo_id() == giro["finestra"] and root.winfo_exists(),
                  "il cambio di tema avviene nella stessa finestra, senza chiuderla")
        root.after(300, lambda: antibot(root, c))
        return

    testata = [w for w in tutti(root) if w.winfo_class() == "Canvas" and str(w["height"]) == "92"][0]
    misure = {}

    def mouse_sui_pulsanti():
        l = testata.winfo_width()
        trovati = 0
        for x in range(l - 300, l - 100, 3):
            if any(t in ("tema", "stat") for i in testata.find_overlapping(x, 44, x, 44)
                   for t in testata.gettags(i)):
                testata.event_generate("<Motion>", warp=True, x=x, y=44)
                root.update()
                trovati += 1
        controlla(trovati > 0, "il mouse raggiunge i pulsanti dell'intestazione")
        misure["id"] = max(testata.find_all())
        misure["t"] = time.monotonic()

    def finestra_reattiva():
        ritardo = time.monotonic() - misure["t"] - 1.0
        controlla(ritardo < 0.5, f"la finestra resta reattiva con il mouse sui pulsanti (ritardo {ritardo:.2f} s)")
        controlla(max(testata.find_all()) == misure["id"], "nessun ridisegno continuo dell'intestazione")
        testata.event_generate("<Motion>", warp=True, x=40, y=44)
        c["imposta"](novita=lambda top: top.after(400, top.destroy))
        c["mostra_novita"](N.controlla_novita(N.carica_config()))

    def dopo_il_popup():
        interruttori = [w for w in tutti(root) if w.__class__.__name__ == "Interruttore"]
        for w in interruttori:          # cambiare l'impostazione non deve toccare il popup chiuso
            w.var.set(not w.var.get())
            w.var.set(not w.var.get())
        controlla(True, "popup aperto e chiuso; interruttori modificati dopo la chiusura")
        c["imposta"](esplora=lambda top: top.after(400, top.destroy))
        c["esplora"]("file", "Prova", casa)
        controlla(True, "esplora file aperto e chiuso")
        root.after(300, c["tema"])

    root.after(500, mouse_sui_pulsanti)
    root.after(1600, finestra_reattiva)
    root.after(2800, dopo_il_popup)


def antibot(root, c):
    # il wiki rifiuta il download: il programma apre il "browser", che salva la pagina in Scaricati
    import threading
    scaricati = os.path.join(casa, "Scaricati")
    os.makedirs(scaricati, exist_ok=True)
    N.scarica_raw = lambda *a, **k: (_ for _ in ()).throw(N.WikiBloccato("anti-bot simulato"))

    def browser(url):
        passi.append("ok: pagina aperta nel browser: " + url)

        def salva():
            time.sleep(1.5)
            with open(os.path.join(scaricati, "2025.011"), "w", encoding="utf-8") as f:
                f.write(TESTO)
        threading.Thread(target=salva, daemon=True).start()
    N.apri_nel_browser = browser
    N.cartella_scaricati = lambda: scaricati

    def verifica():
        cartella = os.path.join(casa, "2025", "011")
        fatti = os.listdir(cartella) if os.path.isdir(cartella) else []
        controlla("Newsletter Ubuntu-it 011.2025.tex" in fatti,
                  "dopo il blocco anti-bot il testo salvato dal browser viene convertito da solo")
        controlla("NewsletterItaliana_2025.011.txt" in fatti, "il testo salvato viene archiviato col nome standard")
        root.destroy()
    c["avvia_lavoro"]([(None, {"numero": "2025.011", "pdf": False})])
    root.after(9000, verifica)


N.avvia_gui(prova)
log_sistema = open(N.file_log_sistema(), encoding="utf-8").read()
controlla("Avvio di newsletter2tex" in log_sistema and "Cambio di tema: scuro" in log_sistema
          and "Anti-bot: trovato" in log_sistema, "il log di sistema registra avvio, cambio di tema e anti-bot")
# gli errori di pdflatex dipendono dai pacchetti LaTeX installati, non dal programma
inattesi = [r for r in log_sistema.splitlines() if (" ERROR " in r or " CRITICAL " in r)
            and "pdflatex" not in r and "Compilazione PDF" not in r]
controlla(not inattesi, "nessun errore inatteso nel log di sistema" + ("".join("\n  " + r for r in inattesi)))
for p in passi:
    print(p)
for e in errori:
    print("ERRORE:", e)
if errori or giro["n"] < 2:
    sys.exit("Prova dell'interfaccia NON superata")
print("Prova dell'interfaccia superata")
