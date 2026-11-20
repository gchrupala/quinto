"""The fonts a style needs, and a check that they are installed.

The build reads the serif and the emoji font of the style from their files (style.py). The .pptx
only names the fonts, so whatever renders it (LibreOffice for the PDFs, PowerPoint) needs all of them
installed; otherwise it substitutes another font without warning.

Usage: quinto fonts [DECK]     (the fonts of the style of the deck; without one, of the default style)
"""
import subprocess, sys
from quinto import styles


def missing(style):
    """The font families of a style module that fontconfig does not find."""
    out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, check=True).stdout
    found = {name.strip() for line in out.splitlines() for name in line.split(",")}
    return [family for family in style.FONTS if family not in found]


def check(style):
    """Stop with instructions if a font of the style is missing."""
    gone = missing(style)
    if gone:
        raise SystemExit("missing fonts:\n" + "\n".join(f"  {f}: {style.FONTS[f]}" for f in gone))


if __name__ == "__main__":
    from quinto import qmdfile
    style = styles.load(styles.spec(qmdfile.find(sys.argv[1])) if len(sys.argv) > 1 else None)
    check(style)
    print(f"all fonts of {style.NAME} installed:", ", ".join(style.FONTS))
