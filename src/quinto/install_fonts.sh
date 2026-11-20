#!/bin/sh
# Install the fonts of the style zeroclutter: Libertinus Serif, IBM Plex Mono and the monochrome Noto Emoji,
# all from the Google Fonts repository, into ~/.local/share/fonts.
set -e
BASE=https://raw.githubusercontent.com/google/fonts/main/ofl
FONTS="$HOME/.local/share/fonts"
mkdir -p "$FONTS/libertinus" "$FONTS/ibmplexmono" "$FONTS/notoemoji"
# Not the SemiBold styles: their files also call themselves "Italic"/"Regular", and programs
# (Firefox, for one) then take SemiBold Italic for the italic.
for f in Regular Italic Bold BoldItalic; do
    curl -fsSL -o "$FONTS/libertinus/LibertinusSerif-$f.ttf" "$BASE/libertinusserif/LibertinusSerif-$f.ttf"
done
for f in Regular Italic Bold BoldItalic; do
    curl -fsSL -o "$FONTS/ibmplexmono/IBMPlexMono-$f.ttf" "$BASE/ibmplexmono/IBMPlexMono-$f.ttf"
done
curl -fsSL -o "$FONTS/notoemoji/NotoEmoji.ttf" "$BASE/notoemoji/NotoEmoji%5Bwght%5D.ttf"
fc-cache -f "$FONTS"
# matplotlib caches the list of fonts; clear it so the new fonts are found.
rm -rf "$HOME/.cache/matplotlib"
echo "Fonts installed in $FONTS"
# Noto Serif CJK SC (Chinese examples) comes from the system packages, not from here.
python3 -m quinto.fonts
