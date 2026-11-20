"""Build the .pptx of a Quarto deck, in place of the PowerPoint output of Quarto.

Usage: quinto pptx 01            (the deck 01_*.qmd in the current directory; writes the .pptx next to it)
       quinto pptx path/to/deck.qmd

The pandoc bundled with Quarto parses the .qmd (`quarto pandoc -t json`: a tenth of the time of
`quarto render`, which would also run Quarto's own filters) and this script walks the resulting
document. Each level-2 heading starts a slide:
- a slide with a Python cell: the cell is run here, against the real deck, and draws the slide
  with the helpers of style.py (see __init__.py); all cells share one namespace, in order, and cells
  before the first slide (setup) draw nothing;
- any other slide is built from its Markdown: an optional title, paragraphs, `::: question` and
  tables (booktabs), centred together on the slide, as slides.css does in reveal.js;
- `::: notes` becomes the speaker notes, read from the text by qmdfile.py and rendered as Markdown
  by notesfile.py, as in the preview.
The title slide comes from the title, subtitle (optional) and author in the YAML header.

With DECK_HTML set to a directory, it writes the slides as HTML there instead of the .pptx (see
style.save and tohtml.py), with the notes as HTML in notes.json. The preview and the reveal.js
version (quinto.lua) both show these slides, so all three outputs share one layout.
"""
import json, linecache, os, subprocess, sys

from quinto import qmdfile, styles

QMD = qmdfile.find(sys.argv[1])
DIR = os.path.dirname(QMD)
BASE = os.path.splitext(QMD)[0]
os.environ["QUINTO_DIR"] = qmdfile.workdir(QMD)  # before style is imported: the figure cache is there
os.environ["QUINTO_STYLE"] = styles.spec(QMD)  # the style of the deck, which style.py reads
os.chdir(DIR)

from quinto import *  # noqa: E402,F403
from quinto import style  # noqa: E402

qmd = qmdfile.Qmd(QMD)
r = subprocess.run(["quarto", "pandoc", "-f", "markdown", "-t", "json"], input=qmd.for_pandoc(),
                   capture_output=True, text=True)
if r.returncode:
    sys.exit(r.stderr)
doc = json.loads(r.stdout)


# ── pandoc AST ──────────────────────────────────────────────────────────────

def inline_runs(inlines, fmt=None):
    """Inlines as paragraphs of fill_text: a list of lists of (text, opts); a line break starts a
    new paragraph."""
    paras, fmt = [[]], dict(fmt or {})
    def add(text, f):
        paras[-1].append((text, dict(f)))
    def walk(xs, f):
        for x in xs:
            t, c = x["t"], x.get("c")
            if t == "Str":
                add(c, f)
            elif t in ("Space", "SoftBreak"):
                add(" ", f)
            elif t == "LineBreak":
                paras.append([])
            elif t == "Emph":
                walk(c, dict(f, italic=True))
            elif t == "Strong":
                walk(c, dict(f, bold=True))
            elif t == "Quoted":
                q = ("“", "”") if c[0]["t"] == "DoubleQuote" else ("‘", "’")
                add(q[0], f), walk(c[1], f), add(q[1], f)
            elif t == "Span":
                classes = c[0][1]
                g = dict(f)
                if "accent" in classes:
                    g["color"] = ACCENT
                if "grey" in classes:
                    g["color"] = GREY
                walk(c[1], g)
            elif t == "Code":
                add(c[1], f)
            else:
                raise ValueError(f"inline {t} is not supported on slides")
    walk(inlines, fmt)
    return paras


def text_of(inlines):
    return "".join(t for p in inline_runs(inlines) for t, _ in p)


def meta_text(v):
    if v is None:
        return ""
    if v["t"] == "MetaInlines":
        return text_of(v["c"])
    if v["t"] == "MetaString":
        return v["c"]
    if v["t"] == "MetaList":
        return ", ".join(meta_text(x) for x in v["c"])
    if v["t"] == "MetaMap":
        return meta_text(v["c"].get("name") or v["c"].get("literal"))
    return ""


# ── slides ──────────────────────────────────────────────────────────────────

LINE = style.STYLE.LINE  # line height in em, as in tohtml.py
BODY, QUESTION, TITLE = style.STYLE.BODY, style.STYLE.QUESTION, style.STYLE.TITLE
TABLE, TABLE_HEADER, ROW = style.STYLE.TABLE, style.STYLE.TABLE_HEADER, style.STYLE.ROW
ns = {"__name__": "__deck__"}
cells = 0


def run_cells(blocks, where):
    """Run the cells among blocks in the shared namespace; returns the number of slides they drew."""
    global cells
    before = len(style.prs.slides)
    for b in blocks:
        cells += 1
        code, name = b["c"][1], f"<cell {cells}>"
        linecache.cache[name] = (len(code), None, code.splitlines(True), name)  # for inspect.getsource
        try:
            exec(compile(code, name, "exec"), ns)
        except Exception as e:
            raise RuntimeError(f"{where}: {type(e).__name__}: {e}") from e
    return len(style.prs.slides) - before


def is_cell(b):
    return b["t"] == "CodeBlock" and "cell" in b["c"][0][1]


def table_rows(c):
    """Rows of a pandoc Table as lists of cell inlines; the first row is the header."""
    _, _, _, head, bodies, _ = c
    rows = [r[1] for r in head[1]]
    for b in bodies:
        rows += [r[1] for r in b[3]]
    out = []
    for r in rows:
        cells = []
        for cell in r:
            blocks = cell[4]
            cells.append(blocks[0]["c"] if blocks else [])
        out.append(cells)
    return out


TEXT_W = W - 1.6  # width of the text boxes of Markdown slides, in inches


def line_count(para, size, width, italic=False):
    """Lines that a paragraph (a list of (text, opts)) takes when wrapped at width inches, breaking
    at spaces as PowerPoint and the browser do."""
    words, cur = [], []
    for text, o in para:
        for i, piece in enumerate(text.split(" ")):
            if i:  # a space ends the word
                words.append(cur)
                cur = []
            if piece:
                cur.append((piece, o))
    words.append(cur)
    widths = [sum(text_width(t, size, o.get("bold", False), o.get("italic", italic)) for t, o in w)
              for w in words if w]
    space = text_width(" ", size, italic=italic)
    lines, x = 1, None
    for w in widths:
        if x is None:
            x = w
        elif x + space + w <= width:
            x += space + w
        else:
            lines, x = lines + 1, w
    return lines


def text_height(paras, size, italic=False):
    return sum(line_count(p, size, TEXT_W, italic) for p in paras) * size * LINE / 72


def markdown_slide(title, blocks):
    """A slide from Markdown: title and body stacked and centred vertically."""
    s = new("TITLE_ONLY" if title else "BLANK")
    items, total = [], 0.0  # (kind, height, data)
    for b in blocks:
        t, c = b["t"], b.get("c")
        if t in ("Para", "Plain"):
            paras = inline_runs(c)
            items.append(("text", text_height(paras, BODY), (paras, BODY, {})))
        elif t == "Div" and "question" in c[0][1]:
            paras = [p for blk in c[1] for p in inline_runs(blk["c"])]
            items.append(("text", text_height(paras, QUESTION, italic=True),
                          (paras, QUESTION, dict(italic=True, color=ACCENT))))
        elif t == "Table":
            rows = table_rows(c)
            items.append(("table", len(rows) * ROW, rows))
        else:
            raise ValueError(f"block {t} is not supported on Markdown slides")
    total = sum(h for _, h, _ in items)
    th = TITLE * LINE / 72 + 0.25 if title else 0
    y = (H - th - total) / 2
    if title:
        t = s.shapes.title
        t.left, t.top, t.width, t.height = Inches(0.55), Inches(y), Inches(W - 1.1), Inches(TITLE * LINE / 72)
        t.text_frame.text = ""
        t.text_frame.vertical_anchor = MSO_ANCHOR.TOP
        for side in ("left", "right", "top", "bottom"):
            setattr(t.text_frame, f"margin_{side}", 0)
        fill_text(t.text_frame, [title], TITLE, align="c")
        y += th
    for kind, h, data in items:
        if kind == "text":
            paras, size, kw = data
            tb(s, 0.8, y, TEXT_W, h, paras, size=size, align="c", **kw)
        else:
            rows = data
            ncol = len(rows[0])
            def width(j):
                return max(text_width(text_of(r[j]), TABLE_HEADER if i == 0 else TABLE, italic=i == 0)
                           for i, r in enumerate(rows)) + 0.24 + 0.05
            colw = [width(j) for j in range(ncol)]
            cells = [[inline_runs(cell)[0] for cell in r] for r in rows]
            table(s, (W - sum(colw)) / 2, y, colw, cells, rowh=ROW, size=TABLE, header_size=TABLE_HEADER)
        y += h
    return s


# ── the deck ────────────────────────────────────────────────────────────────

meta = doc["meta"]
s = new("TITLE")
ph = {str(p.placeholder_format.type).split()[0]: p for p in s.placeholders}
ph["TITLE"].text_frame.text = ""
fill_text(ph["TITLE"].text_frame, [meta_text(meta.get("title"))], 44, align="c")
fill_text(ph["SUBTITLE"].text_frame, [t for t in (meta_text(meta.get("subtitle")), meta_text(meta.get("author"))) if t],
          24, align="c")

sections, setup = [], []
for b in doc["blocks"]:
    if b["t"] == "Header" and b["c"][0] == 2:
        sections.append({"key": b["c"][1][0], "title": b["c"][2], "blocks": []})
    elif sections:
        sections[-1]["blocks"].append(b)
    elif is_cell(b):
        setup.append(b)
    else:
        raise ValueError("content before the first slide")
keys = [sec["key"] for sec in sections]
assert keys == qmd.keys(), f"slides found by pandoc and by qmdfile.py differ: {keys} vs {qmd.keys()}"
assert len(set(keys)) == len(keys), f"two slides have the same key: {keys}"
assert run_cells(setup, "setup") == 0, "the cells before the first slide must not draw slides"

for i, sec in enumerate(sections):
    code = [b for b in sec["blocks"] if is_cell(b)]
    body = [b for b in sec["blocks"] if not is_cell(b) and not (b["t"] == "Div" and "notes" in b["c"][0][1])]
    if code:
        assert not body and not sec["title"], f"slide {sec['key']}: a cell slide has no Markdown body or title"
        n = run_cells(code, f"slide {sec['key']}")
        assert n == 1, f"slide {sec['key']}: its cells must draw exactly one slide (s = new()), not {n}"
        s = style.prs.slides[-1]
    else:
        s = markdown_slide(text_of(sec["title"]), body)
    text = qmd.notes(i)
    if text:
        style.notes(s, text)


class Keys:  # for style.save: the key of each slide, which the preview uses to match notes to slides
    used = ["title"] + keys


def notes_html(text):
    """Notes as HTML for the speaker view of reveal.js, from the paragraphs of notesfile.to_html, as
    in the preview: list items hang their mark in the indent."""
    from quinto import notesfile
    out = []
    for p in notesfile.to_html(text):
        hang = LIST_HANG if p["mark"] else 0
        mark = f'<span style="display:inline-block;width:{LIST_HANG}pt;text-indent:0">{p["mark"]}</span>' if hang else ""
        out.append(f'<p style="padding-left:{p["level"] * LIST_INDENT + hang}pt;text-indent:{-hang}pt">'
                   f'{mark}{p["html"]}</p>')
    return "".join(out)


style._notes.append(Keys)
style.save(BASE + ".pptx")
if os.environ.get("DECK_HTML"):  # for quinto.lua; the preview reads the notes from the .qmd itself
    with open(os.path.join(os.environ["DECK_HTML"], "style.css"), "w") as f:
        f.write(style.STYLE.CSS)
    with open(os.path.join(os.environ["DECK_HTML"], "notes.json"), "w") as f:
        json.dump({k: notes_html(qmd.notes(i) or "") for i, k in enumerate(keys)}, f)
