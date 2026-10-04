"""Test di newsletter2tex: si eseguono con  python3 -m unittest discover -s tests -v"""

import io
import os
import sys
import tempfile
import unittest
from unittest import mock

QUI = os.path.dirname(os.path.abspath(__file__))
RADICE = os.path.dirname(QUI)
sys.path.insert(0, RADICE)

import newsletter2tex as N  # noqa: E402

ESEMPIO = os.path.join(RADICE, "esempi", "NewsletterItaliana_2025.011.txt")
ATTESO = os.path.join(QUI, "attesi", "NewsletterItaliana_2025.011.tex")
PROBLEMI = os.path.join(QUI, "dati", "problemi.txt")
CFG = dict(N.CONFIG_PREDEFINITA, cartella_lavoro="/percorso/inesistente/{anno}")


def leggi(percorso):
    with open(percorso, encoding="utf-8") as f:
        return f.read()


def converti(testo, nome="prova.txt", **kw):
    log = N.Log()
    tex, dati = N.converti(testo, nome, log, dict(CFG), **kw)
    return tex, dati, log


def messaggi(log, livello=None):
    return [m for l, _, m in log.voci if livello is None or l == livello]


class TestConversione(unittest.TestCase):
    def test_numero_011_identico_al_riferimento(self):
        """Il .tex del numero di esempio non deve cambiare senza volerlo."""
        tex, _, _ = converti(leggi(ESEMPIO), "NewsletterItaliana_2025.011.txt")
        self.assertEqual(tex, leggi(ATTESO),
                         "Il .tex è cambiato: se la modifica è voluta, rigenera tests/attesi/")

    def test_intestazione(self):
        _, dati, _ = converti(leggi(ESEMPIO))
        self.assertEqual((dati["numero"], dati["anno"]), (11, 2025))
        self.assertEqual(dati["mese_testata"], "Marzo")

    def test_markup_principale(self):
        tex, _, _ = converti(leggi(ESEMPIO))
        self.assertIn(r"\section{Notizie da Ubuntu}", tex)
        self.assertIn(r"\textbf{Ubuntu 25.04 Beta}", tex)
        self.assertIn(r"\textsl{org.freedesktop.secrets}", tex)
        self.assertIn(r"$\href{https://releases.ubuntu.com/25.04/}{\textsl{download}}$", tex)
        self.assertIn(r"\item {[NEW!]} Bodhi Corner", tex)
        self.assertIn("MicroSoft Office", tex)
        self.assertNotIn("!MicroSoft", tex)
        self.assertIn(r"\textit{Linus Torvalds}", tex)
        self.assertIn(r"\textit{intestazioni}", tex)
        self.assertIn(r"Issue \#215", tex)
        self.assertIn(r"io\_uring", tex)

    def test_link_interni_e_interwiki(self):
        tex, _, _ = converti(leggi(ESEMPIO))
        self.assertIn(r"$\href{https://wiki.ubuntu.com/BugSquad}{\textsl{Bug Squad}}$", tex)
        self.assertIn(r"$\href{https://wiki.ubuntu-it.org/GruppoSviluppo}{\textsl{GruppoSviluppo}}$", tex)

    def test_fonti_raggruppate(self):
        tex, _, _ = converti(leggi(ESEMPIO))
        self.assertIn("\\textit{Fonte}:\\\\\n$\\href{https://www.omgubuntu.co.uk/2025/03/ubuntu-25-04-beta-download}"
                      "{\\textsl{omgubuntu.co.uk}}$\\\\\n$\\href{https://9to5linux.com/", tex)

    def test_sviluppatori(self):
        tex, _, _ = converti(leggi(ESEMPIO))
        self.assertIn("\\item \\textit{Riccardo Coccioli}:\n\\begin{itemize}", tex)

    def test_template_licenza_corretto(self):
        tex, _, _ = converti(leggi(ESEMPIO))
        self.assertIn("ma non con modalità tali", tex)
        self.assertIn("paternità adeguata", tex)
        self.assertNotIn(r"\'a", tex)
        self.assertNotIn(r"\'E", tex)


class TestCrediti(unittest.TestCase):
    def test_redazione_e_pdf(self):
        tex, _, _ = converti(leggi(ESEMPIO))
        self.assertIn(r"\item $\href{https://wiki.ubuntu-it.org/essedia1960}{\textsl{Stefano Dall'Agata}}$", tex)
        self.assertNotIn("collaborato all'edizione", tex)

    def test_edizione_dal_txt(self):
        testo = leggi(ESEMPIO).replace(
            " * [[essedia1960 | Stefano Dall'Agata]]\n",
            " * [[essedia1960 | Stefano Dall'Agata]]\n\nHa inoltre collaborato all'edizione:\n"
            " * [[garakkio | Massimiliano Arione]]\n")
        tex, _, _ = converti(testo)
        self.assertIn("Ha inoltre collaborato all'edizione:", tex)
        self.assertIn(r"$\href{https://wiki.ubuntu-it.org/garakkio}{\textsl{Massimiliano Arione}}$", tex)


class TestDate(unittest.TestCase):
    def intestazione(self, numero, anno, da, a):
        t = (f"Questo è il numero '''{numero}''' del '''{anno}''', riferito alla settimana che va da "
             f"'''{da}''' a '''{a}'''.")
        return N.leggi_intestazione(t, "", N.Log())

    def test_mese_della_domenica(self):
        d = self.intestazione(17, 2025, "lunedì 28 aprile", "domenica 4 maggio")
        self.assertEqual(d["mese_testata"], "Maggio")

    def test_settimana_a_cavallo_dell_anno(self):
        d = self.intestazione(52, 2026, "lunedì 28 dicembre", "domenica 3 gennaio")
        self.assertEqual((d["mese_testata"], d["anno_testata"]), ("Gennaio", 2027))

    def test_data_sbagliata_segnalata(self):
        log = N.Log()
        t = ("Questo è il numero '''11''' del '''2025''', riferito alla settimana che va da "
             "'''lunedì 25 marzo''' a '''domenica 30 marzo'''.")
        N.leggi_intestazione(t, "", log)
        self.assertTrue(any("non è un lunedì" in m for m in messaggi(log, "AVVISO")))


class TestControlli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, _, cls.log = converti(leggi(PROBLEMI))

    def test_errori_strutturali(self):
        err = " ".join(messaggi(self.log, "ERRORE"))
        self.assertIn("Titolo non riconosciuto", err)
        self.assertIn("Parentesi di link non bilanciate", err)

    def test_avvisi(self):
        avv = " ".join(messaggi(self.log, "AVVISO"))
        for atteso in ("Link senza testo", "Link con '|' ma testo vuoto", "URL con spazi",
                       "Macro wiki ignorata", "manca lo spazio iniziale", "Sezione vuota",
                       "Fonte ripetuta", "Nome senza link"):
            self.assertIn(atteso, avv)

    def test_refusi(self):
        ref = " ".join(messaggi(self.log, "REFUSO"))
        for atteso in ("Doppio spazio", "Spazio prima di «,»", "«perchè» → «perché»",
                       "Parola ripetuta: «il il»", "«pò» → «po'»", "Spazio dopo l'apostrofo",
                       "Parentesi tonde non bilanciate"):
            self.assertIn(atteso, ref)

    def test_numero_011_pulito(self):
        _, _, log = converti(leggi(ESEMPIO))
        self.assertEqual(messaggi(log, "ERRORE"), [])
        self.assertEqual(len(messaggi(log, "REFUSO")), 1)   # «e  migliorando» (doppio spazio reale)

    def test_escape(self):
        self.assertEqual(N.escape("100% & $5 #1 a_b {x}"), r"100\% \& \$5 \#1 a\_b \{x\}")


class TestStatistiche(unittest.TestCase):
    def test_lettura(self):
        self.assertEqual(N.leggi_statistiche(leggi(ESEMPIO)),
                         {"aperti": (142865, 8), "critici": (331, 2), "nuovi": (72689, -32)})

    def test_blocco_wiki(self):
        b = N.blocco_statistiche({"aperti": 10, "critici": 5, "nuovi": 7},
                                 {"aperti": 8, "critici": 6, "nuovi": 7})
        self.assertIn(" * Aperti: 10, '''+2''' rispetto alla scorsa settimana.", b)
        self.assertIn(" * Critici: 5, '''−1'''", b)
        self.assertIn(" * Nuovi: 7, '''0'''", b)

    def test_differenze_coerenti(self):
        t = leggi(ESEMPIO)
        prec = t.replace("142865", "142857").replace("331, '''+2'''", "329, '''+2'''").replace("72689", "72721")
        log = N.Log()
        N.controlla_statistiche(t, prec, "2025.010", log)
        self.assertEqual(messaggi(log, "ERRORE"), [])

    def test_differenze_sbagliate(self):
        t = leggi(ESEMPIO)
        prec = t.replace("142865", "142800")
        log = N.Log()
        N.controlla_statistiche(t, prec, "2025.010", log)
        self.assertTrue(any("«Aperti»: scritto +8" in m for m in messaggi(log, "ERRORE")))

    def test_launchpad_con_ripiego(self):
        """Se il totale degli aperti va in timeout, si sommano i singoli stati."""
        risposte = {"importance=Critical": "295", "status=New": "100", "status=Incomplete": "10",
                    "status=Confirmed": "20", "status=Triaged": "30", "status=In+Progress": "4",
                    "status=Fix+Committed": "6"}

        def finto_urlopen(req, timeout=None):
            url = req.full_url
            for chiave, valore in risposte.items():
                if url.endswith(chiave):
                    return io.BytesIO(valore.encode())
            raise OSError("timeout")
        with mock.patch.object(N.urllib.request, "urlopen", finto_urlopen):
            v = N.statistiche_launchpad()
        self.assertEqual(v, {"aperti": 170, "critici": 295, "nuovi": 100})


class TestCartelle(unittest.TestCase):
    def test_sottocartella_del_numero(self):
        with tempfile.TemporaryDirectory() as d:
            r = N.esegui(file=ESEMPIO, output=os.path.join(d, "{anno}"), cfg=dict(CFG),
                         avanzamento=lambda m: None, verifica_statistiche=False)
            self.assertTrue(r["tex"].endswith(os.path.join("2025", "011", "Newsletter Ubuntu-it 011.2025.tex")))
            self.assertTrue(os.path.exists(r["log"]))


class TestNovita(unittest.TestCase):
    def cartella(self, d, files):
        for f in files:
            percorso = os.path.join(d, "2026", f)
            os.makedirs(os.path.dirname(percorso), exist_ok=True)
            open(percorso, "w").close()
        return dict(CFG, cartella_lavoro=os.path.join(d, "{anno}"))

    def novita(self, cfg, ultimo=30):
        with mock.patch.object(N, "trova_ultimo_numero", lambda log: (2026, ultimo, "testo")):
            return N.controlla_novita(cfg)

    def test_riconosce_file_fatti_a_mano(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self.cartella(d, ["Newsletter Ubuntu-it 028.2026.pdf",          # nella cartella dell'anno
                                    "vecchi/Newsletter Ubuntu-it 029.2026.tex",   # in una sottocartella
                                    "030/Newsletter Ubuntu-it 030.2026.tex"])     # struttura del programma
            self.assertEqual(N.numeri_convertiti(cfg, 2026), {28, 29, 30})
            n = self.novita(cfg, 31)
            self.assertEqual(n["mancanti"], [31])

    def test_arretrati_solo_fino_all_ultimo_convertito(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self.cartella(d, ["027/Newsletter Ubuntu-it 027.2026.tex"])
            self.assertEqual(self.novita(cfg, 30)["mancanti"], [30, 29, 28])

    def test_nessun_arretrato_se_la_cartella_e_vuota(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self.cartella(d, [])
            self.assertEqual(self.novita(cfg, 30)["mancanti"], [30])

    def test_gia_convertito(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = self.cartella(d, ["Newsletter Ubuntu-it 030.2026.tex"])
            n = self.novita(cfg, 30)
            self.assertEqual(n["mancanti"], [])
            self.assertTrue(n["convertito"])


class TestRete(unittest.TestCase):
    def test_download_che_non_risponde(self):
        """Se il wiki non risponde il programma rinuncia con un messaggio chiaro, senza restare appeso."""
        chiamate = []

        def lento(req, timeout=None):
            chiamate.append(timeout)
            raise N.urllib.error.URLError(N.socket.timeout("timed out"))
        with mock.patch.object(N.urllib.request, "urlopen", lento):
            with self.assertRaises(RuntimeError) as ctx:
                N.scarica_raw("NewsletterItaliana/2026.029")
        self.assertEqual(len(chiamate), 2)
        self.assertEqual(chiamate[0], N.TIMEOUT_RETE)
        self.assertIn("non risponde", str(ctx.exception))

    def test_download_a_rilento_interrotto(self):
        class Rubinetto(io.BytesIO):
            def read(self, n=-1):
                return b"x"
        orologio = iter(range(0, 10000, 30))
        with mock.patch.object(N.urllib.request, "urlopen", lambda req, timeout=None: Rubinetto()), \
                mock.patch.object(N.time, "monotonic", lambda: next(orologio)):
            with self.assertRaises(RuntimeError):
                N.scarica_raw("NewsletterItaliana/2026.029")


class TestAggiornamenti(unittest.TestCase):
    def script(self, versione, rotto=False):
        testo = leggi(os.path.join(RADICE, "newsletter2tex.py")).replace(
            f'VERSIONE = "{N.VERSIONE}"', f'VERSIONE = "{versione}"', 1)
        return (testo + ("\ndef (\n" if rotto else "")).encode()

    def test_confronto_versioni(self):
        self.assertGreater(N.versione_tupla("1.10.0"), N.versione_tupla("1.9.9"))
        self.assertEqual(N.versione_tupla("1.2"), (1, 2))

    def test_installa_versione_nuova(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "newsletter2tex")
            open(dest, "w").write("vecchio")
            with mock.patch.object(N, "_scarica_url", lambda *a, **k: self.script("99.0.0")):
                self.assertEqual(N.aggiorna_programma(dest), "99.0.0")
            self.assertIn('VERSIONE = "99.0.0"', leggi(dest))
            self.assertTrue(os.access(dest, os.X_OK))

    def test_non_installa_file_rotto_o_vecchio(self):
        with tempfile.TemporaryDirectory() as d:
            dest = os.path.join(d, "newsletter2tex")
            open(dest, "w").write("vecchio")
            with mock.patch.object(N, "_scarica_url", lambda *a, **k: self.script("99.0.0", rotto=True)):
                with self.assertRaises(RuntimeError):
                    N.aggiorna_programma(dest)
            with mock.patch.object(N, "_scarica_url", lambda *a, **k: self.script("0.0.1")):
                self.assertIsNone(N.aggiorna_programma(dest))
            with mock.patch.object(N, "_scarica_url", lambda *a, **k: b"<html>errore</html>"):
                with self.assertRaises(RuntimeError):
                    N.aggiorna_programma(dest)
            self.assertEqual(leggi(dest), "vecchio")     # il file installato resta intatto


class TestBrowser(unittest.TestCase):
    def test_trova_il_testo_salvato(self):
        with tempfile.TemporaryDirectory() as d:
            inizio = time_now = __import__("time").time()
            open(os.path.join(d, "fattura.pdf"), "w").write("x")
            open(os.path.join(d, "2026.031.part"), "w").write(leggi(ESEMPIO))      # download in corso
            self.assertIsNone(N.cerca_txt_salvato(d, inizio))
            altro = os.path.join(d, "2025.011")                                      # nome dato dal browser
            open(altro, "w").write(leggi(ESEMPIO))
            self.assertEqual(N.cerca_txt_salvato(d, inizio), altro)
            self.assertEqual(N.cerca_txt_salvato(d, inizio, 2025, 11), altro)
            self.assertIsNone(N.cerca_txt_salvato(d, inizio, 2026, 31))             # numero diverso
            self.assertIsNone(N.cerca_txt_salvato(d, time_now + 60))                # file più vecchio


class TestNotifiche(unittest.TestCase):
    def test_unita_systemd(self):
        servizio, timer = N.testo_unita("/home/prova/.local/bin/newsletter2tex")
        self.assertIn("ExecStart=/usr/bin/env python3 /home/prova/.local/bin/newsletter2tex --notifica", servizio)
        self.assertIn("OnCalendar=Mon 21:30", timer)
        self.assertIn("OnCalendar=Tue 08:15", timer)
        self.assertIn("Persistent=true", timer)

    def test_attiva_e_disattiva(self):
        def finto_enable(argomenti, d):
            if argomenti[0] == "enable":
                cartella = os.path.join(d, "systemd", "user", "timers.target.wants")
                os.makedirs(cartella, exist_ok=True)
                open(os.path.join(cartella, N.NOME_UNITA + ".timer"), "w").close()
        with tempfile.TemporaryDirectory() as d:
            chiamate = []
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": d}), \
                    mock.patch.object(N.shutil, "which", lambda x: "/usr/bin/" + x), \
                    mock.patch.object(N, "_systemctl", lambda *a: (chiamate.append(a), finto_enable(a, d), (0, ""))[2]):
                N.imposta_notifiche(True, "/x/newsletter2tex")
                timer = os.path.join(d, "systemd", "user", N.NOME_UNITA + ".timer")
                self.assertTrue(os.path.exists(timer))
                self.assertIn(("enable", N.NOME_UNITA + ".timer"), chiamate)
                self.assertIn(("start", N.NOME_UNITA + ".timer"), chiamate)
                N.imposta_notifiche(False)
                self.assertFalse(os.path.exists(timer))

    def test_una_notifica_per_numero(self):
        novita = {"anno": 2026, "numero": 31, "mancanti": [31],
                  "anteprima": {"settimana": "da lunedì 28 settembre a domenica 4 ottobre", "articoli": ["a", "b"]}}
        inviate = []
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(N, "CONFIG_FILE", os.path.join(d, "config.json")), \
                mock.patch.object(N, "controlla_novita", lambda cfg: novita), \
                mock.patch.object(N, "invia_notifica", lambda *a, **k: inviate.append(a)):
            self.assertTrue(N.notifica_nuovi_numeri())
            self.assertFalse(N.notifica_nuovi_numeri())      # stesso numero: nessuna seconda notifica
        self.assertEqual(len(inviate), 1)
        self.assertIn("031/2026", inviate[0][0])

    def test_nessuna_notifica_se_gia_convertito_o_senza_rete(self):
        inviate = []
        with mock.patch.object(N, "invia_notifica", lambda *a, **k: inviate.append(a)):
            with mock.patch.object(N, "controlla_novita", lambda cfg: {"mancanti": []}):
                self.assertFalse(N.notifica_nuovi_numeri())
            with mock.patch.object(N, "controlla_novita", mock.Mock(side_effect=OSError("rete"))):
                self.assertFalse(N.notifica_nuovi_numeri())
        self.assertEqual(inviate, [])


if __name__ == "__main__":
    unittest.main()
