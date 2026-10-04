"""Prova completa: converte il numero di esempio e compila il PDF con pdflatex.
Le immagini del template vengono sostituite da segnaposto generati qui.
Uso:  python3 tests/compila_pdf.py"""

import os
import struct
import sys
import tempfile
import zlib

RADICE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RADICE)
import newsletter2tex as N  # noqa: E402


def png_segnaposto(percorso, lato=64, colore=(233, 84, 32)):
    riga = b"\x00" + bytes(colore) * lato
    def blocco(tipo, dati):
        return (struct.pack(">I", len(dati)) + tipo + dati
                + struct.pack(">I", zlib.crc32(tipo + dati) & 0xFFFFFFFF))
    with open(percorso, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + blocco(b"IHDR", struct.pack(">IIBBBBB", lato, lato, 8, 2, 0, 0, 0))
                + blocco(b"IDAT", zlib.compress(riga * lato)) + blocco(b"IEND", b""))


def main():
    with tempfile.TemporaryDirectory() as d:
        anno = os.path.join(d, "2025")
        os.makedirs(anno)
        for img in N.IMMAGINI:
            png_segnaposto(os.path.join(anno, img))
        cfg = dict(N.CONFIG_PREDEFINITA, cartella_lavoro=os.path.join(d, "{anno}"))
        r = N.esegui(file=os.path.join(RADICE, "esempi", "NewsletterItaliana_2025.011.txt"),
                     pdf=True, cfg=cfg, verifica_statistiche=False)
        errori = [m for l, _, m in r["voci"] if l == "ERRORE"]
        for e in errori:
            print("ERRORE:", e)
            if os.environ.get("GITHUB_ACTIONS"):
                print("::error::" + e.replace("\n", " "))
        if errori or not r["pdf"]:
            sys.exit("Compilazione del PDF non riuscita")
        print(f"PDF creato correttamente ({os.path.getsize(r['pdf']) // 1024} kB)")


if __name__ == "__main__":
    main()
