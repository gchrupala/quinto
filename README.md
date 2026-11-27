# Quinto

Quinto builds slide decks written as Quarto files (.qmd). A deck holds the slides and their speaker notes. Quinto turns it into a .pptx, a live preview for editing, and a reveal.js page for presenting from the browser. All three show the same slides, built once by `quinto.build` with the helpers of `style.py` on the layouts of `template.pptx`.

## Styles

A style is a way slides look and what goes on them. A deck chooses its style in its YAML header:

```yaml
quinto:
  style: zeroclutter
```

Without this setting, a deck is in zeroclutter. Quinto has one style so far, zeroclutter: spare and mostly monochrome, in the manner of a LaTeX document, with text in Libertinus Serif, lines and figures drawn with matplotlib in a lightly hand-drawn manner, and tables in booktabs style. Each slide shows one thing, and the explanation is in the speaker notes. The helpers of `style.py` draw in this style. Its guidelines, for authors and for coding agents that review or write decks, are in [styles/zeroclutter.md](styles/zeroclutter.md). Other styles may be added later.

In the code, a style is a module of settings in `src/quinto/styles/`: colours, fonts and their files, sizes, the line height, the template, the matplotlib settings and the CSS for reveal.js. The helpers of `style.py`, the Markdown slides, the preview, the reveal.js page and `quinto fonts` take these settings from the style of the deck. A project can also have a style of its own: give the path of a Python file instead of a name (`style: mystyle.py`, relative to the .qmd). The file can start from zeroclutter and redefine what differs; see `styles/zeroclutter.py`.

## Install

Quinto has two parts: a Python package, which builds the decks, and a Quarto extension, which lets Quarto present them with reveal.js.

```sh
pip install git+https://github.com/gchrupala/quinto@v0.2.5   # the package and the quinto command
quarto add gchrupala/quinto@v0.2.5                            # the extension, run in the directory of the decks
```

`quarto add` copies the extension to `_extensions/quinto/`, which is meant to be committed with the decks. Install the same version of both.

Other requirements:

- Quarto (<https://quarto.org>, or the Python package `quarto-cli`: `pip install "quinto[quarto] @ git+..."`), tested with 1.10.19. Its bundled pandoc parses the .qmd.
- Fonts: zeroclutter needs four fonts, listed in its module (`FONTS`). `quinto fonts [DECK]` checks that the fonts of the style of a deck are installed.
  - Libertinus Serif (all text), IBM Plex Mono (code) and the monochrome Noto Emoji (icons): `quinto install-fonts` downloads them from Google Fonts to `~/.local/share/fonts/libertinus/`, `~/.local/share/fonts/ibmplexmono/` and `~/.local/share/fonts/notoemoji/NotoEmoji.ttf`. Quinto reads Libertinus Serif and Noto Emoji from these paths to measure text and draw figures.
  - Noto Serif CJK SC, for Chinese: Debian/Ubuntu package `fonts-noto-cjk`.
  - The .pptx only names the fonts, so LibreOffice or PowerPoint substitutes another font, without a warning, for any font that is missing. `quinto render` and `quinto pdf` therefore stop if a font is missing.
- Formulas (`formula()` in `style.py`) are set by LaTeX through matplotlib, with the preamble of the style. zeroclutter uses the Libertinus math fonts, which need a TeX installation with `latex`, `dvipng` and the packages amsmath, libertinus and libertinust1math (on Debian/Ubuntu: `texlive-latex-extra`, `texlive-fonts-extra`, `dvipng`). LaTeX in several colours (`latex()`) is set by `pdflatex` instead, with the packages xcolor and fancybox, and converted to PNG by `pdftocairo` (package `poppler-utils`).
- To check the real deck and export PDFs in LibreOffice (`quinto render`, `quinto pdf`): LibreOffice (`soffice`) and `pdftoppm` (package `poppler-utils`). Screenshots of the preview (`quinto shot`) need Google Chrome or Chromium.

## Commands

Run `quinto` in the directory of the decks. A deck is named by its number, for example `01` for the file `01_*.qmd`, or by the path of its .qmd.

| Command | What it does |
|---|---|
| `quinto pptx 01` | write the .pptx next to the .qmd |
| `quinto preview 01 [port]` | live preview at <http://localhost:8001> (port 8000 + deck number) |
| `quinto pdf 00 01 02` | write the .pptx of each deck and export PDFs of the slides and of the notes pages |
| `quinto render 01` | write the .pptx and render its notes pages through LibreOffice |
| `quinto shot 01 [3 5-7]` | screenshots of preview pages, with the preview running |
| `quinto fonts [01]` | check that the fonts of the style of a deck are installed |
| `quinto install-fonts` | download the fonts of zeroclutter |

Generated files go to `_quinto/` next to the .qmd (or to the directory in `QUINTO_DIR`): the figure cache in `fig/`, the preview of each deck in `preview/NN/`, and the profiles of LibreOffice and Chrome. Add `_quinto/` and `_deck/` to `.gitignore`.

## The .qmd file

- A YAML header gives the title, an optional subtitle and the author, which make the title slide, the format (`format: quinto-revealjs` and `engine: markdown`) and optionally the style (`quinto: style: ...`).
- A Python cell before the first slide (`from quinto import *`) is the setup: it imports the helpers of `style.py` and defines what several slides use. The cells run with the directory of the .qmd as the current directory, so paths can be relative to it.
- Each `## {#key}` starts a slide. The key names the slide; the preview and the .pptx use it to match notes to slides.
- A slide is either a Python cell or Markdown. A cell draws the slide with the helpers of `style.py`: `s = new()`, then `tb`, `arrow`, `pic`, `table` and so on. All cells share one namespace, in order. Markdown slides are laid out by `build.py`: a title, paragraphs, `::: question` and tables (booktabs), centred together on the slide, with `[text]{.accent}` and `[text]{.grey}` for colour. Only this small set of Markdown is supported; anything else is an error. To centre a Markdown slide, its paragraph heights are estimated from the width of the words, so the text can sit slightly off centre when PowerPoint or the browser breaks a line differently.
- The speaker notes of a slide are in a `::: notes` block below it. Leave a blank line after `::: notes` and before the closing `:::`; otherwise rewrapping a paragraph pulls the marker into the text, and the notes end up on the slide. The notes are Markdown (CommonMark), parsed with markdown-it-py (`notesfile.py`): paragraphs are separated by blank lines, and italics, bold, `code`, links, lists, and superscripts and subscripts written as in Pandoc (`W^Q^`, `d~k~`, without spaces) show up in the preview, the .pptx and the speaker view of reveal.js alike. Edit notes in the .qmd or in the live preview, not in PowerPoint: the next build overwrites the notes in the .pptx.
- `qmdfile.py` reads and edits the .qmd as text (slides, keys, notes, inserting and removing slides), changing only the lines concerned.

A minimal deck:

````markdown
---
title: "A deck"
author: "A. Author"
engine: markdown
format: quinto-revealjs
quinto:
  style: zeroclutter
---

```{python}
from quinto import *
```

## {#question}

::: question
What is a word?
:::

::: notes

The speaker notes, in Markdown.

:::

## {#drawn}

```{python}
s = new()
tb(s, 1, 1, 9, 1, "A text box, drawn in Python", size=32)
arrow(s, 2, 3, 8, 3, color=ACCENT)
```
````

## Preview

For a live preview, run `quinto preview 01` and open <http://localhost:8001> in a browser or in VS Code (Simple Browser: Show). The preview does not write the .pptx: it runs `quinto.build` with `DECK_HTML` set, and `tohtml.py` turns the slides into HTML instead. Each slide is shown on its notes page. A change to the slides in the .qmd, or to `style.py`, `tohtml.py` or the other modules, rebuilds the slides, in about 1.5 s for a deck of 30 slides. A change to the notes only shows within a fraction of a second, without a rebuild.

Notes that do not fit in the notes box are outlined in red and listed in the status line. Slides that changed get a red border. Use ← and → to move between slides, Home and End to jump, and g for a grid of all slides. Press e to edit the notes of the current slide next to it; saving (ctrl+s) writes them into its `::: notes` block. If the notes were changed elsewhere in the meantime, the save is refused and your text is kept. Press i to insert an empty slide after the current one, d to duplicate it, and x then y to remove it. The page reports the slide it shows to `_quinto/preview/01/current.txt`, and the slides whose notes overflow to `_quinto/preview/01/overflow.txt`, so an agent can tell which slide you are looking at. The page updates by itself. Changes to `preview.py` itself need a restart of the server.

Line breaks in the browser are close to those in PowerPoint, but not always identical. The overflow check leaves 4 pt to spare, because LibreOffice sets the notes slightly lower than the browser.

## Output

- **PowerPoint:** `quinto pptx 01` writes `01_name.pptx`. It replaces the PowerPoint output of Quarto: the pandoc bundled with Quarto parses the .qmd, and `build.py` runs the cells, lays out the Markdown slides and adds the notes.
- **PDF:** `quinto pdf 00 01 02` writes the .pptx of each deck and exports it through LibreOffice to two PDFs: `01_name.pdf` with the slides, and `01_name_notes.pdf` with the notes pages (each slide with its speaker notes). An animated GIF shows its last frame in the PDFs; the .pptx keeps the animation.
- **Checking the .pptx:** `quinto render 01` writes the .pptx and renders its notes pages through LibreOffice to `_quinto/preview/01/pptx/`. `quinto shot 01 [3 5-7]` takes screenshots of preview pages to `_quinto/preview/01/slide-NN.png`, with the preview server running.
- **reveal.js:** `quarto preview 01_name.qmd` serves the deck for presenting from the browser (`quarto render` writes the HTML). The filter of the extension, `quinto.lua`, runs `quinto.build`, which writes the slides as HTML to `_deck/`, and puts that HTML in place of the content of each slide, so the slides look as in the .pptx. It also adds the CSS of the style (fonts and colours). Quarto provides the page, the moving between slides and the speaker view (press S). The cells do not run in Jupyter. `slides.css` holds only what the positioned HTML needs. Python is `python3`, or the interpreter in `QUARTO_PYTHON`; Quinto must be installed in it.

## Figures

`audio()` in `style.py` puts a sound clip on a slide as a loudspeaker icon; in the preview and in reveal.js, clicking the icon plays it. An animation is an animated GIF, drawn like any other figure with `figure(draw, ext="gif")`. `icon()` draws monochrome Noto Emoji.

Figures are cached in `_quinto/fig/`. A figure is drawn again only when its inputs change. The helpers in `style.py` (`arrow`, `icon`, `dep_tree`) know their inputs. A figure drawn in a cell goes in a function that saves it to the path it is given, called through `figure`: `pic(s, figure(draw_tree), ...)`. The key of such a figure is the source of the function, the values it reads from the cells, and the contents of any input files listed with `files=[...]`. Every key also includes `style.py` and the settings of the style, so a change there redraws all figures.

## Development

Install a clone in editable mode (`pip install -e .`), so that the preview picks up changes to the modules. The tests (`tests/`, property-based with Hypothesis) run with `pip install -e '.[test]'` and `python -m pytest`. After a change to `_extensions/quinto/`, run `quarto update` in the directory of the decks (or copy the files) to update their copy of the extension.

## Licence

MIT; see `LICENSE`. The fonts are not part of Quinto and keep their own licences (SIL Open Font License).
