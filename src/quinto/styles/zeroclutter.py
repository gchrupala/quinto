"""zeroclutter: spare and mostly monochrome, in the manner of a well-made LaTeX document.

The guidelines for this style are in styles/zeroclutter.md of the Quinto repository.

A style module holds only settings, read by style.py (drawing and the .pptx), build.py (Markdown
slides), tohtml.py and preview.py (HTML), fonts.py (the font check) and the reveal.js filter (CSS).
Every name here must be defined in a style. A style of one's own can start from this one:

    from quinto.styles.zeroclutter import *
    NAME = "mystyle"
    ACCENT = "2E8B57"

Settings computed from others here (RC, CSS) keep the old values unless they are redefined too.
"""
import os

NAME = "zeroclutter"
TEMPLATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "template.pptx")
W, H = 11.02, 6.20  # the slide size of TEMPLATE, in inches (rounded)

# Colour: ink and grey for almost everything; one accent for emphasis; a second only where a
# visualization needs two contrasting categories, and a third only where three must be told apart.
INK, GREY, LIGHT = "1A1A1A", "707070", "BDBDBD"
ACCENT, ACCENT2, GREEN = "C0392B", "2E5C8A", "3A7D44"  # vermilion; blue; muted green

# Fonts. The serif is read from its files to measure text (SERIF_FILES by (bold, italic)); the
# emoji font draws icons().
SERIF, MONO, CJK = "Libertinus Serif", "IBM Plex Mono", "Noto Serif CJK SC"
SERIF_DIR = os.path.expanduser("~/.local/share/fonts/libertinus/")  # Google Fonts release
SERIF_FILES = {(False, False): "LibertinusSerif-Regular.ttf", (False, True): "LibertinusSerif-Italic.ttf",
               (True, False): "LibertinusSerif-Bold.ttf", (True, True): "LibertinusSerif-BoldItalic.ttf"}
EMOJI = os.path.expanduser("~/.local/share/fonts/notoemoji/NotoEmoji.ttf")  # monochrome, Google Fonts
LINE = 1.19  # single line spacing, in em: measured in LibreOffice for Libertinus Serif (PowerPoint: about 1.2)
# The font families the decks need, with how to install each (checked by quinto fonts).
FONTS = {
    "Libertinus Serif": "run quinto install-fonts",
    "IBM Plex Mono": "run quinto install-fonts",
    "Noto Emoji": "run quinto install-fonts",
    "Noto Serif CJK SC": "install the package fonts-noto-cjk (Debian/Ubuntu)",
}
# formulas are set by LaTeX, in the Libertinus math fonts (needs a TeX installation with the libertinus,
# libertinust1math and amsmath packages, and dvipng)
LATEX_PREAMBLE = r"\usepackage{amsmath}\usepackage{libertinus}\usepackage{libertinust1math}"

# Sizes in pt: Markdown slides (body text, questions, titles, tables) and speaker notes; ROW is the
# height of a table row on Markdown slides, in inches.
BODY, QUESTION, TITLE, TABLE, TABLE_HEADER, ROW = 24, 36, 40, 28, 20, 0.6
TITLE_SLIDE = (44, 28, 24)  # title slide: title, subtitle, author
NOTES_SIZE, NOTES_SPACE = 16, 5  # speaker notes: font size and space after each paragraph

# Drawings: matplotlib sketch params, amplitude (px at 100 dpi), wavelength, randomness; and the
# matplotlib settings for plots.
SKETCH = (0.6, 70, 2.0)
RC = {
    "font.family": SERIF, "font.size": 20, "text.color": "#" + INK,
    "axes.labelcolor": "#" + GREY, "xtick.color": "#" + GREY, "ytick.color": "#" + GREY,
    "axes.edgecolor": "#" + INK, "axes.linewidth": 1.0,
    "axes.spines.top": False, "axes.spines.right": False,
    "xtick.labelsize": 18, "ytick.labelsize": 18, "axes.labelsize": 20,
    "mathtext.fontset": "custom", "mathtext.rm": SERIF, "mathtext.it": SERIF + ":italic",
}

# reveal.js: the fonts and colours of the page; the layout of the slides is in slides.css.
CSS = """@import url("https://fonts.googleapis.com/css2?family=Libertinus+Serif:ital,wght@0,400;0,700;1,400;1,700&family=IBM+Plex+Mono:ital,wght@0,400;0,700;1,400;1,700&display=swap");
.reveal-viewport { background: #fff; }
.reveal { font-family: "Libertinus Serif", serif; color: #1a1a1a; }
"""
