"""The fonts the decks need, and a check that they are installed.

The build reads Libertinus Serif and Noto Emoji from their files (style.py). The .pptx only names the
fonts, so whatever renders it (LibreOffice for the PDFs, PowerPoint) needs all of them installed;
otherwise it substitutes another font without warning.
"""
import subprocess

INSTALL = "run quinto install-fonts"
REQUIRED = {
    "Libertinus Serif": INSTALL,
    "IBM Plex Mono": INSTALL,
    "Noto Emoji": INSTALL,
    "Noto Serif CJK SC": "install the package fonts-noto-cjk (Debian/Ubuntu)",
}


def missing():
    """The required font families that fontconfig does not find."""
    out = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, check=True).stdout
    found = {name.strip() for line in out.splitlines() for name in line.split(",")}
    return [family for family in REQUIRED if family not in found]


def check():
    """Stop with instructions if a required font is missing."""
    gone = missing()
    if gone:
        raise SystemExit("missing fonts:\n" + "\n".join(f"  {f}: {REQUIRED[f]}" for f in gone))


if __name__ == "__main__":
    check()
    print("all fonts installed:", ", ".join(REQUIRED))
