"""Helpers for drawing the slides of a deck, in the style it chooses (see styles/).

Slides use the layouts of the template of the style (TITLE, TITLE_ONLY, BLANK). Text is native; lines, arrows and figures are drawn
with matplotlib in a lightly hand-drawn manner and placed as transparent PNGs at their final size,
so that figure text has the same point size as slide text.
"""
import copy, functools, hashlib, inspect, os, re, zipfile, shutil
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import PP_PLACEHOLDER
from pptx.oxml.ns import qn
from lxml import etree
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from PIL import ImageFont

from . import styles

# The settings of the style of the deck (QUINTO_STYLE, set by build.py; see styles/__init__.py).
STYLE = styles.load()
SRC, W, H = STYLE.TEMPLATE, STYLE.W, STYLE.H
INK, GREY, LIGHT = STYLE.INK, STYLE.GREY, STYLE.LIGHT
ACCENT, ACCENT2, GREEN = STYLE.ACCENT, STYLE.ACCENT2, STYLE.GREEN
SERIF, MONO, CJK = STYLE.SERIF, STYLE.MONO, STYLE.CJK
SERIF_DIR, SERIF_FILES, EMOJI = STYLE.SERIF_DIR, STYLE.SERIF_FILES, STYLE.EMOJI
NOTES_SIZE, NOTES_SPACE = STYLE.NOTES_SIZE, STYLE.NOTES_SPACE
SKETCH = STYLE.SKETCH
LATEX_PREAMBLE = STYLE.LATEX_PREAMBLE
# part of every figure key, so that a change here or in the settings of the style redraws the figures
with open(os.path.abspath(__file__), "rb") as _f:
    STYLE_HASH = hashlib.md5(_f.read() + repr(sorted((n, v) for n, v in vars(STYLE).items()
                                                      if n.isupper())).encode()).hexdigest()

plt.rcParams.update(STYLE.RC)

prs = Presentation(SRC)
sldIdLst = prs.slides._sldIdLst
for sldId in list(sldIdLst):
    prs.part.drop_rel(sldId.rId)
    sldIdLst.remove(sldId)
LAYOUT = {l.name: l for m in prs.slide_masters for l in m.slide_layouts}


def rgb(h):
    return RGBColor.from_string(h)


@functools.lru_cache(maxsize=None)
def _font(size, bold, italic):
    return ImageFont.truetype(SERIF_DIR + SERIF_FILES[(bold, italic)], size * 10)


def text_width(text, size, bold=False, italic=False):
    """Width in inches of a single line of text set in the serif font."""
    return _font(size, bold, italic).getlength(text) / 720


# ── text ────────────────────────────────────────────────────────────────────

def style_run(run, size, color=INK, bold=False, italic=False, font=SERIF, sup=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = rgb(color)
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        el = rPr.find(qn(tag))
        if el is None:
            el = etree.SubElement(rPr, qn(tag))
        el.set("typeface", CJK if (font == CJK and tag != "a:latin") else font)
    if font == CJK:
        rPr.find(qn("a:latin")).set("typeface", CJK)
    if sup:
        rPr.set("baseline", "30000")


def fill_text(tf, paras, size, color=INK, bold=False, italic=False, align="l",
              font=SERIF, space_after=0, line=None):
    """paras: list of paragraphs; a paragraph is a str or a list of str / (str, opts)."""
    tf.word_wrap = True
    al = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = al
        if space_after:
            p.space_after = Pt(space_after)
        if line:
            p.line_spacing = line
        if isinstance(para, str):
            para = [para]
        for seg in para:
            text, o = (seg, {}) if isinstance(seg, str) else seg
            r = p.add_run()
            r.text = text
            style_run(r, o.get("size", size), o.get("color", color), o.get("bold", bold),
                      o.get("italic", italic), o.get("font", font), o.get("sup", False))


def tb(s, x, y, w, h, paras, size=24, anchor="t", margin=0, **kw):
    shp = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shp.text_frame
    tf.vertical_anchor = {"t": MSO_ANCHOR.TOP, "m": MSO_ANCHOR.MIDDLE, "b": MSO_ANCHOR.BOTTOM}[anchor]
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(margin)
    fill_text(tf, paras if isinstance(paras, list) else [paras], size, **kw)
    return shp


def question(s, text, y=4.4, h=1.0, size=28):
    return tb(s, 0.8, y, W - 1.6, h, text if isinstance(text, list) else [text], size=size,
              italic=True, color=ACCENT, align="c", anchor="m")


LIST_INDENT, LIST_HANG = 20, 16  # notes: indent per list level and room for the bullet, in pt


def _notes_marL():
    """Left margin of the notes in the notes master, in EMU."""
    body = next(p for p in prs.notes_master.placeholders if p.placeholder_format.type == 2)  # BODY
    pPr = body._element.find(qn("p:txBody") + "/" + qn("a:p") + "/" + qn("a:pPr"))
    return int(pPr.get("marL", 0)) if pPr is not None else 0


def notes(s, text):
    """Speaker notes from Markdown (see notesfile.paragraphs)."""
    from . import notesfile
    tf = s.notes_slide.notes_text_frame
    for i, para in enumerate(notesfile.paragraphs(text)):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(NOTES_SPACE)
        # explicit indents on every paragraph: LibreOffice loses the one of the notes master otherwise
        pPr = p._p.get_or_add_pPr()
        mark = para["mark"]
        pPr.set("marL", str(_notes_marL() + Pt(para["level"] * LIST_INDENT)))
        pPr.set("indent", str(-Pt(LIST_HANG) if mark else 0))
        if mark == "•":
            etree.SubElement(pPr, qn("a:buFont"), typeface=SERIF)
            etree.SubElement(pPr, qn("a:buChar"), char="•")
        elif mark:
            etree.SubElement(pPr, qn("a:buFont"), typeface=SERIF)
            etree.SubElement(pPr, qn("a:buAutoNum"), type="arabicPeriod", startAt=mark[:-1])
        else:
            etree.SubElement(pPr, qn("a:buNone"))
        for text, f in para["runs"]:
            if text == "\n":
                p.add_line_break()
                continue
            r = p.add_run()
            r.text = text
            style_run(r, NOTES_SIZE, "000000", bold=f.get("bold", False), italic=f.get("italic", False),
                      font=MONO if f.get("code") else SERIF)
            if f.get("link"):
                r.hyperlink.address = f["link"]


def new(layout="BLANK", title=None, title_size=40):
    lay = LAYOUT[layout]
    s = prs.slides.add_slide(lay)
    for sp in lay.placeholders:
        if "SLIDE_NUMBER" in str(sp.placeholder_format.type):
            el = copy.deepcopy(sp._element)
            s.shapes._spTree.append(el)
            for r in el.iter(qn("a:rPr")):
                r.set("sz", "1400")
    if title is not None:
        t = s.shapes.title
        t.text_frame.text = ""
        fill_text(t.text_frame, [title], title_size, align="c")
    return s


# ── booktabs tables ─────────────────────────────────────────────────────────

def _ln(tag, width_pt):
    el = etree.Element(qn(tag))
    if width_pt:
        el.set("w", str(int(width_pt * 12700)))
        sf = etree.SubElement(el, qn("a:solidFill"))
        etree.SubElement(sf, qn("a:srgbClr")).set("val", INK)
    else:
        el.set("w", "0")
        etree.SubElement(el, qn("a:noFill"))
    return el


def table(s, x, y, colw, rows, rowh=0.62, size=26, header=True, header_size=20,
          align=None, top=1.25, mid=0.6, bottom=1.25):
    """Booktabs-style table: rules above and below, a thin rule under the header, nothing else.
    rows: list of rows; a cell is a paragraph as in fill_text (str, or list of str / (str, opts)).
    align: one of 'l', 'c', 'r' per column."""
    nr, nc = len(rows), len(colw)
    align = align or ["l"] * nc
    shp = s.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(sum(colw)), Inches(rowh * nr))
    tbl = shp.table
    tblPr = tbl._tbl.tblPr
    for k in ("firstRow", "bandRow"):
        tblPr.set(k, "0")
    for el in tblPr.findall(qn("a:tableStyleId")):
        tblPr.remove(el)
    for j, w in enumerate(colw):
        tbl.columns[j].width = Inches(w)
    for i in range(nr):
        tbl.rows[i].height = Inches(rowh)
        for j in range(nc):
            cell = tbl.cell(i, j)
            cell.margin_left = cell.margin_right = Inches(0.12)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.text = ""
            hdr = header and i == 0
            fill_text(tf, [rows[i][j]], header_size if hdr else size,
                      color=GREY if hdr else INK, italic=hdr, align=align[j])
            tcPr = cell._tc.get_or_add_tcPr()
            for child in list(tcPr):
                tcPr.remove(child)
            t = top if i == 0 else (mid if header and i == 1 else 0)
            b = bottom if i == nr - 1 else (mid if header and i == 0 else 0)
            for el in (_ln("a:lnL", 0), _ln("a:lnR", 0), _ln("a:lnT", t), _ln("a:lnB", b)):
                tcPr.append(el)
            etree.SubElement(tcPr, qn("a:noFill"))
    return shp


# ── hand-drawn lines, arrows and figures ────────────────────────────────────

def canvas(w, h):
    """A transparent figure of w × h inches whose data coordinates are inches, y downwards."""
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)
    ax.axis("off")
    return fig, ax


# Figures are cached in fig/ of the work directory of the deck (QUINTO_DIR, set by build.py; see
# qmdfile.workdir): a figure is drawn again only when its key changes. The key covers
# everything the drawing depends on, plus style.py itself.

def fig_path(name, key, ext="png"):
    """Path of the cached image (a PNG, or of type ext) for a figure with this name and key."""
    fig = os.path.join(os.environ.get("QUINTO_DIR") or os.path.abspath("_quinto"), "fig")
    os.makedirs(fig, exist_ok=True)
    return fig + f"/{name}_{hashlib.md5(repr((key, STYLE_HASH)).encode()).hexdigest()[:10]}.{ext}"


def save_fig(fig, path, **kw):
    # write to a temporary file first, so that a build running at the same time never reads half a file
    tmp = f"{path}.{os.getpid()}.tmp"
    fig.savefig(tmp, format="png", **dict(dict(dpi=300, transparent=True), **kw))
    plt.close(fig)
    os.replace(tmp, path)
    return path


def _globals_used(fn):
    """The values a function uses from the cells of the deck: names it reads, other than modules,
    classes and functions from style.py (which STYLE_HASH covers)."""
    def names(code):
        out = set(code.co_names)
        for c in code.co_consts:
            if inspect.iscode(c):
                out |= names(c)
        return out
    import numpy as np
    vals = []
    for n in sorted(names(fn.__code__)):
        if n not in fn.__globals__:
            continue
        v = fn.__globals__[n]
        if inspect.ismodule(v) or inspect.isclass(v) or inspect.isbuiltin(v):
            continue
        if callable(v):
            if getattr(v, "__module__", None) == fn.__module__:
                vals.append((n, inspect.getsource(v)))
            continue
        vals.append((n, hashlib.md5(v.tobytes()).hexdigest() if isinstance(v, np.ndarray) else repr(v)))
    return vals


def figure(draw, files=(), ext="png"):
    """A figure drawn by a function in a cell of the deck: draw(path) saves it to path. It is drawn
    again only when the source of draw, the values it uses from the script, the contents of the
    input files or style.py change. Returns the path of the image: a PNG, or of another type given
    by ext (for example "gif" for an animation)."""
    contents = []
    for f in files:
        with open(f, "rb") as fh:
            contents.append(hashlib.md5(fh.read()).hexdigest())
    path = fig_path(draw.__name__, (inspect.getsource(draw), _globals_used(draw), contents), ext)
    if not os.path.exists(path):
        draw(path)
    return path


def sketch(artist):
    artist.set_sketch_params(*SKETCH)
    return artist


DASH = (0, (5, 3))  # dashed lines: a second kind of line that does not depend on colour


def pen_arrow(ax, x1, y1, x2, y2, color=INK, lw=1.5, head=True, rad=0.0, ms=20, dash=False):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->" if head else "-",
                        connectionstyle=f"arc3,rad={rad}", mutation_scale=ms,
                        color="#" + color, lw=lw, shrinkA=0, shrinkB=0, capstyle="round",
                        joinstyle="round", linestyle=DASH if dash else "solid")
    ax.add_patch(sketch(a))
    return a


def arrow(s, x1, y1, x2, y2, color=INK, lw=1.5, head=True, rad=0.0, dash=False):
    """A lightly hand-drawn arrow (or line, head=False) from (x1, y1) to (x2, y2), in slide inches."""
    pad = 0.25
    bx, by = min(x1, x2) - pad, min(y1, y2) - pad
    bw, bh = abs(x2 - x1) + 2 * pad, abs(y2 - y1) + 2 * pad
    path = fig_path("arrow", (x1, y1, x2, y2, color, lw, head, rad) + (("dash",) if dash else ()))
    if not os.path.exists(path):
        fig, ax = canvas(bw, bh)
        pen_arrow(ax, x1 - bx, y1 - by, x2 - bx, y2 - by, color, lw, head, rad, dash=dash)
        save_fig(fig, path)
    return s.shapes.add_picture(path, Inches(bx), Inches(by), Inches(bw), Inches(bh))


def box(s, x, y, w, h, color=INK, lw=1.4, dash=False):
    """A lightly hand-drawn outline of a box, without fill, at (x, y) and w × h in slide inches."""
    pad = 0.1
    path = fig_path("box", (w, h, color, lw) + (("dash",) if dash else ()))
    if not os.path.exists(path):
        fig, ax = canvas(w + 2 * pad, h + 2 * pad)
        sketch(ax.plot([pad, pad + w, pad + w, pad, pad], [pad, pad, pad + h, pad + h, pad], color="#" + color,
                       lw=lw, solid_capstyle="round", solid_joinstyle="round", ls=DASH if dash else "solid")[0])
        save_fig(fig, path)
    return s.shapes.add_picture(path, Inches(x - pad), Inches(y - pad), Inches(w + 2 * pad), Inches(h + 2 * pad))


def pic(s, path, x, y, w=None, h=None):
    return s.shapes.add_picture(path, Inches(x), Inches(y),
                                Inches(w) if w else None, Inches(h) if h else None)


# formulas are set by LaTeX, with the preamble of the style (LATEX_PREAMBLE)

def formula(s, tex, cx, cy, w, h=0.9, size=28, color=INK):
    """A formula set by LaTeX, centred at (cx, cy) in a picture of w × h inches. tex is LaTeX math between
    dollar signs, as for matplotlib."""
    path = fig_path("formula", ("latex", tex, w, h, size, color))
    if not os.path.exists(path):
        with plt.rc_context({"text.usetex": True, "text.latex.preamble": LATEX_PREAMBLE}):
            fig, ax = canvas(w, h)
            ax.text(w / 2, h / 2, tex, ha="center", va="center", fontsize=size, color="#" + color)
            save_fig(fig, path)
    return pic(s, path, cx - w / 2, cy - h / 2, w, h)


def glyph(char, size=40, color=INK, font=EMOJI, w=None, white=False):
    """A PNG of a monochrome emoji, or a short text in another font file, d inches high and w wide.
    white: on a white background instead of a transparent one. Returns the path, w and d."""
    from matplotlib.font_manager import FontProperties
    d = size / 72 * 1.6
    w = w or d
    path = fig_path("icon", (char, size, color, font, w) + ((True,) if white else ()))
    if not os.path.exists(path):
        fig, ax = canvas(w, d)
        ax.text(w / 2, d / 2, char, ha="center", va="center", color="#" + color,
                fontproperties=FontProperties(fname=font, size=size))
        save_fig(fig, path, **(dict(transparent=False, facecolor="white") if white else {}))
    return path, w, d


def icon(s, char, cx, cy, size=40, color=INK, font=EMOJI, w=None):
    """A monochrome emoji, or a short text in another font file (font), centred at (cx, cy), in
    slide inches. w: width of the picture, for texts wider than one emoji."""
    path, w, d = glyph(char, size, color, font, w)
    return pic(s, path, cx - w / 2, cy - d / 2, w, d)


def audio(s, path, cx, cy, size=40, color=INK):
    """An audio clip, shown as a loudspeaker icon centred at (cx, cy) that plays it when clicked."""
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
    poster, w, d = glyph("🔊", size, color, white=True)  # media frames are dark behind transparency
    sh = s.shapes.add_movie(path, Inches(cx - w / 2), Inches(cy - d / 2), Inches(w), Inches(d),
                            poster_frame_image=poster, mime_type="audio/wav")
    # python-pptx inserts media as video; mark it as audio, as PowerPoint does for sound files
    vf = sh._element.find(".//" + qn("a:videoFile"))
    vf.tag = qn("a:audioFile")
    rel = s.part.rels[vf.get(qn("r:link"))]
    rel._reltype = rel.__dict__["reltype"] = RT.AUDIO  # reltype is a cached property
    return sh


# ── saving ──────────────────────────────────────────────────────────────────

def _drop_notes_numbers():
    """Remove the slide-number placeholder from every notes page. The slide image on the page already
    shows the number, and the placeholder of the notes master sits at the very bottom edge of the
    page, where it is clipped in the PDF."""
    for s in prs.slides:
        ns = s.notes_slide  # created if missing, so that the page does not fall back to the master
        for ph in list(ns.placeholders):
            if ph.placeholder_format.type == PP_PLACEHOLDER.SLIDE_NUMBER:
                ph._element.getparent().remove(ph._element)


def save(path):
    """Save, and replace the template fonts in the theme and masters, so that placeholders and
    slide numbers use the serif too. With DECK_HTML set to a directory, write the HTML preview
    there instead (see tohtml.py and preview.py)."""
    if os.environ.get("DECK_HTML"):
        from . import tohtml
        keys = _notes[-1].used if _notes else []
        tohtml.write(prs, os.environ["DECK_HTML"], keys, {"size": NOTES_SIZE, "space": NOTES_SPACE})
        return
    _drop_notes_numbers()
    prs.save(path)
    tmp = path + ".tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if re.match(r"ppt/theme/theme\d+\.xml", item.filename):
                xml = data.decode("utf8")
                xml = re.sub(r'(<a:(?:major|minor)Font>\s*<a:latin typeface=")[^"]*', r"\g<1>" + SERIF, xml)
                data = xml.encode("utf8")
            elif re.match(r"ppt/(slideMasters/slideMaster|slideLayouts/slideLayout|notesMasters/notesMaster)\d+\.xml", item.filename):
                data = data.replace(b'typeface="Cambria"', ('typeface="%s"' % SERIF).encode())
            zout.writestr(item, data)
    shutil.move(tmp, path)
    print("saved", path, len(prs.slides), "slides")


# ── figures ─────────────────────────────────────────────────────────────────

def word_xs(widths, w):
    """Centres of words set side by side in columns of the given widths, centred in a width w."""
    import numpy as np
    xs = np.cumsum([0] + [(widths[i] + widths[i + 1]) / 2 for i in range(len(widths) - 1)])
    return xs - xs[-1] / 2 + w / 2


def dep_tree(words, arcs, w, size=28, lab=19, hscale=0.5, tags=None, glosses=None, highlight=(),
             name=None, widths=None):
    """A dependency tree drawn to fit a width of w inches. arcs: (head, dependent, label), with
    head None for the root. widths: column widths of the words, to line them up with text
    elsewhere on the slide (see word_xs). Returns the PNG path and the figure height in inches."""
    from matplotlib.path import Path
    sub = 18
    if widths is None:
        widths = [max(text_width(t, size), text_width(tags[i], sub) if tags else 0,
                      text_width(glosses[i], sub, italic=True) if glosses else 0) + 0.4
                  for i, t in enumerate(words)]
    xs = word_xs(widths, w)
    maxd = max(abs(h - d) for h, d, _ in arcs if h is not None)
    height = lambda dist: 0.35 + hscale * dist
    extra = (0.38 if tags else 0) + (0.38 if glosses else 0)
    base = height(maxd) + (0.55 if any(h is None for h, _, _ in arcs) else 0.2)
    hgt = base + 0.75 + extra
    png = fig_path(name or "dep", (words, arcs, w, size, lab, hscale, tags, glosses, highlight, widths))
    if os.path.exists(png):
        return png, hgt
    fig, ax = canvas(w, hgt)
    for i, (x, t) in enumerate(zip(xs, words)):
        ax.text(x, base + 0.38, t, ha="center", va="center", fontsize=size)
        yy = base + 0.38 + size / 72 * 0.5 + 0.2
        if tags:
            ax.text(x, yy, tags[i], ha="center", va="center", fontsize=sub, color="#" + GREY)
            yy += 0.38
        if glosses:
            ax.text(x, yy, glosses[i], ha="center", va="center", fontsize=sub, color="#" + GREY,
                    style="italic")
    for h, d, l in arcs:
        col = "#" + (ACCENT if (h, d) in highlight else INK)
        lcol = "#" + (ACCENT if (h, d) in highlight else GREY)
        if h is None:
            pen_arrow(ax, xs[d], 0.4, xs[d], base, lw=1.4, ms=18, color=INK)
            ax.text(xs[d], 0.2, l, ha="center", va="center", fontsize=lab, color=lcol, style="italic")
            continue
        sgn = 1 if d > h else -1
        x1, x2 = xs[h] + 0.08 * sgn, xs[d] - 0.04 * sgn
        hh = height(abs(h - d))
        path = Path([(x1, base), (x1, base - hh), (x2, base - hh), (x2, base)],
                    [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4])
        ax.add_patch(sketch(FancyArrowPatch(path=path, arrowstyle="->", mutation_scale=18,
                                            color=col, lw=1.4)))
        ax.text((x1 + x2) / 2, base - 0.75 * hh - 0.02, l, ha="center", va="center", fontsize=lab,
                color=lcol, style="italic", bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
    return save_fig(fig, png), hgt


def dot(s, x, y, d=0.14, color=INK):
    from pptx.enum.shapes import MSO_SHAPE
    shp = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x - d / 2), Inches(y - d / 2), Inches(d), Inches(d))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(color)
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


_notes = []  # set by build.py: an object whose .used lists the key of each slide, for save()
