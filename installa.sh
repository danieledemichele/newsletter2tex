#!/bin/sh
# Installa (o aggiorna) newsletter2tex per l'utente corrente.
set -e
cd "$(dirname "$0")"

mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
install -m 755 newsletter2tex.py "$HOME/.local/bin/newsletter2tex"
sed "s|^Exec=.*|Exec=\"$HOME/.local/bin/newsletter2tex\" --gui|" newsletter2tex.desktop \
    > "$HOME/.local/share/applications/newsletter2tex.desktop"
"$HOME/.local/bin/newsletter2tex" --esporta-icona >/dev/null
gtk-update-icon-cache -q -t -f "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true

echo "Installato: $("$HOME/.local/bin/newsletter2tex" --versione) in ~/.local/bin/newsletter2tex"

python3 -c "import tkinter" 2>/dev/null \
    || echo "Per l'interfaccia grafica manca tkinter:  sudo apt install python3-tk"
if command -v pdflatex >/dev/null; then
    mancanti=""
    for f in cdpaddon.sty siunitx.sty italian.ldf subfig.sty emptypage.sty; do
        kpsewhich "$f" >/dev/null 2>&1 || mancanti="$mancanti $f"
    done
    [ -z "$mancanti" ] \
        || echo "Per il PDF mancano alcuni pacchetti LaTeX ($mancanti ):  sudo apt install texlive-latex-extra texlive-science texlive-lang-italian"
else
    echo "Per il PDF manca pdflatex:  sudo apt install texlive-latex-extra texlive-science texlive-lang-italian"
fi
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) echo "Attenzione: ~/.local/bin non è nel PATH. Esci e rientra nella sessione, oppure usa ~/.local/bin/newsletter2tex" ;;
esac
w=$(command -v newsletter2tex || true)
if [ -n "$w" ] && [ "$w" != "$HOME/.local/bin/newsletter2tex" ]; then
    echo "Attenzione: il comando newsletter2tex punta a $w (una copia diversa): rimuovila."
fi
echo "Avvio:  newsletter2tex --gui   oppure dal menu applicazioni (\"Newsletter Ubuntu-it\")."
echo "Se l'icona nella dock non si aggiorna subito, esci e rientra nella sessione."
