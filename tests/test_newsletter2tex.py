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


if __name__ == "__main__":
    unittest.main()
