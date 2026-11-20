"""HTML version of a deck built with style.py, for the live preview.

Converts the presentation in memory to one HTML fragment per slide, positioned in points on a page of
the slide size. It covers what the decks use: text boxes and placeholders, booktabs tables,
pictures, audio clips and filled ellipses or rectangles. Pictures are written to img/ next to slides.json, named
by their content, so that the browser can cache them.

Line breaks in the browser are close to those in PowerPoint but not identical; render.py renders
the real deck through LibreOffice as a final check.
"""
import hashlib, html, json, os
from pptx.oxml.ns import qn

LINE = 1.19  # single line spacing, in em: measured in LibreOffice for Libertinus Serif (PowerPoint: about 1.2)
DEFAULT_SIZE = 18  # pt, when no size is set anywhere
SERIF, MONO, CJK = "Libertinus Serif", "IBM Plex Mono", "Noto Serif CJK SC"


def pt(emu):
    return round(int(emu) / 12700, 2)


def chain(shape, slide):
    """The shape followed by the placeholders it inherits from: the placeholder of the same type on
    the layout, then on the master. Matched by type, because the template gives the title and the
    subtitle the same index."""
    out = [shape]
    if not shape.is_placeholder:
        return out
    kind, idx = shape.placeholder_format.type, shape.placeholder_format.idx
    for parent in (slide.slide_layout, slide.slide_layout.slide_master):
        same = [p for p in parent.placeholders if p.placeholder_format.type == kind]
        same = [p for p in same if p.placeholder_format.idx == idx] or same
        if same:
            out.append(same[0])
    return out


def box(shapes):
    """Position and size of the first shape in a chain that sets them."""
    for sh in shapes:
        xfrm = sh._element.find(qn("p:spPr") + "/" + qn("a:xfrm"))
        if xfrm is None:
            xfrm = sh._element.find(qn("p:xfrm"))  # graphic frames (tables)
        if xfrm is not None and xfrm.find(qn("a:off")) is not None:
            off, ext = xfrm.find(qn("a:off")), xfrm.find(qn("a:ext"))
            return (f"left:{pt(off.get('x'))}pt;top:{pt(off.get('y'))}pt;"
                    f"width:{pt(ext.get('cx'))}pt;height:{pt(ext.get('cy'))}pt")
    raise ValueError(f"shape {shapes[0].name} has no position")


def first(elements, path, attr):
    """The first value of attr on an element matching path, along a chain of XML elements."""
    for el in elements:
        if el is None:
            continue
        for found in el.iterfind(path, {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}):
            v = found.get(attr)
            if v is not None:
                return v
    return None


def colour(el):
    """Colour of an a:solidFill (or of an element containing one), as #rrggbb, or None."""
    if el is None:
        return None
    if el.tag != qn("a:solidFill"):
        el = el.find(qn("a:solidFill"))
    if el is None:
        return None
    c = el.find(qn("a:srgbClr"))
    return "#" + c.get("val") if c is not None else None


def run_html(r, defaults, number):
    """One a:r or a:fld as a span; defaults: rPr elements to fall back on."""
    rPr = r.find(qn("a:rPr"))
    rprs = [rPr] + defaults
    text = r.findtext(qn("a:t")) or ""
    if r.tag == qn("a:fld") and r.get("type") == "slidenum":
        text = str(number)
    size = first(rprs, ".", "sz")
    style = [f"font-size:{int(size) / 100 if size else DEFAULT_SIZE}pt"]
    if first(rprs, ".", "b") in ("1", "true"):
        style.append("font-weight:bold")
    if first(rprs, ".", "i") in ("1", "true"):
        style.append("font-style:italic")
    col = next((c for c in (colour(e) for e in rprs if e is not None) if c), None)
    if col:
        style.append(f"color:{col}")
    face = first(rprs, "a:latin", "typeface")
    if face == CJK:
        style.append(f"font-family:'{CJK}',serif")
    elif face == MONO:
        style.append(f"font-family:'{MONO}',monospace;white-space:pre")
    inner = html.escape(text)
    base = first(rprs, ".", "baseline")
    if base and int(base) > 0:
        inner = f"<sup>{inner}</sup>"  # raised and smaller, as in PowerPoint
    return f'<span style="{";".join(style)}">{inner}</span>'


def paragraphs_html(txBody, lst_chain, number):
    """The paragraphs of a txBody; lst_chain: txBody elements whose a:lstStyle gives defaults."""
    lvl1 = [t.find(qn("a:lstStyle") + "/" + qn("a:lvl1pPr")) if t is not None else None for t in lst_chain]
    defs = [l.find(qn("a:defRPr")) for l in lvl1 if l is not None]
    out = []
    for p in txBody.iterfind(qn("a:p")):
        pPr = p.find(qn("a:pPr"))
        pprs = [pPr] + lvl1
        algn = first(pprs, ".", "algn") or "l"
        style = ["text-align:" + {"l": "left", "ctr": "center", "r": "right", "just": "justify"}.get(algn, "left")]
        pct = first(pprs, "a:lnSpc/a:spcPct", "val")
        pts = first(pprs, "a:lnSpc/a:spcPts", "val")
        style.append(f"line-height:{int(pts) / 100}pt" if pts else f"line-height:{LINE * int(pct) / 100000 if pct else LINE:.3f}")
        for tag, prop in (("a:spcBef", "margin-top"), ("a:spcAft", "margin-bottom")):
            v = first(pprs, tag + "/a:spcPts", "val")
            if v:
                style.append(f"{prop}:{int(v) / 100}pt")
        marL = first(pprs, ".", "marL")
        if marL:
            style.append(f"padding-left:{pt(marL)}pt")
        parts, sizes = [], []
        for child in p:
            if child.tag in (qn("a:r"), qn("a:fld")):
                parts.append(run_html(child, defs, number))
                sz = first([child.find(qn("a:rPr"))] + defs, ".", "sz")
                sizes.append(int(sz) / 100 if sz else DEFAULT_SIZE)
            elif child.tag == qn("a:br"):
                parts.append("<br>")
        end = first([p.find(qn("a:endParaRPr"))] + defs, ".", "sz")
        psize = max(sizes) if sizes else (int(end) / 100 if end else DEFAULT_SIZE)
        # a zero-width space gives empty paragraphs the height of a line, as in PowerPoint
        out.append(f'<p style="{";".join(style)};font-size:{psize}pt">{"".join(parts)}​</p>')
    return "".join(out)


def body_style(bodyPrs, default_ins=(91440, 45720, 91440, 45720)):
    pad = [first(bodyPrs, ".", k) for k in ("tIns", "rIns", "bIns", "lIns")]
    dflt = {0: default_ins[1], 1: default_ins[0], 2: default_ins[3], 3: default_ins[2]}
    pad = [pt(v if v is not None else dflt[i]) for i, v in enumerate(pad)]
    anchor = first(bodyPrs, ".", "anchor") or "t"
    justify = {"t": "flex-start", "ctr": "center", "b": "flex-end"}.get(anchor, "flex-start")
    wrap = "" if first(bodyPrs, ".", "wrap") != "none" else ";white-space:pre"
    return f"padding:{pad[0]}pt {pad[1]}pt {pad[2]}pt {pad[3]}pt;justify-content:{justify}{wrap}"


def text_shape(sh, slide, number):
    shapes = chain(sh, slide)
    bodies = [s._element.find(qn("p:txBody")) for s in shapes]
    bodyPrs = [b.find(qn("a:bodyPr")) if b is not None else None for b in bodies]
    inner = paragraphs_html(bodies[0], bodies, number)
    return f'<div class="tb" style="{box(shapes)};{body_style(bodyPrs)}"><div>{inner}</div></div>'


def table_shape(sh, number):
    tbl = sh._element.find(".//" + qn("a:tbl"))
    cols = [pt(c.get("w")) for c in tbl.find(qn("a:tblGrid"))]
    rows = []
    for tr in tbl.iterfind(qn("a:tr")):
        cells = []
        for tc in tr.iterfind(qn("a:tc")):
            assert tc.get("gridSpan") is None and tc.get("rowSpan") is None, "merged cells are not supported"
            tcPr = tc.find(qn("a:tcPr"))
            get = lambda k, d: pt(tcPr.get(k, d)) if tcPr is not None else pt(d)
            style = [f"padding:{get('marT', 45720)}pt {get('marR', 91440)}pt {get('marB', 45720)}pt {get('marL', 91440)}pt"]
            anchor = tcPr.get("anchor", "t") if tcPr is not None else "t"
            style.append("vertical-align:" + {"t": "top", "ctr": "middle", "b": "bottom"}[anchor])
            for tag, side in (("a:lnT", "top"), ("a:lnB", "bottom"), ("a:lnL", "left"), ("a:lnR", "right")):
                ln = tcPr.find(qn(tag)) if tcPr is not None else None
                if ln is not None and ln.find(qn("a:noFill")) is None and int(ln.get("w", "0")) > 0:
                    style.append(f"border-{side}:{pt(ln.get('w'))}pt solid {colour(ln) or '#000'}")
            cells.append(f'<td style="{";".join(style)}">{paragraphs_html(tc.find(qn("a:txBody")), [], number)}</td>')
        rows.append(f'<tr style="height:{pt(tr.get("h"))}pt">{"".join(cells)}</tr>')
    colgroup = "".join(f'<col style="width:{w}pt">' for w in cols)
    return (f'<table class="tbl" style="left:{pt(sh.left)}pt;top:{pt(sh.top)}pt;width:{sum(cols):.2f}pt">'
            f'<colgroup>{colgroup}</colgroup>{"".join(rows)}</table>')


def picture_shape(sh, imgdir):
    assert sh._element.find(".//" + qn("a:srcRect")) is None or not sh._element.find(".//" + qn("a:srcRect")).attrib, \
        "cropped pictures are not supported"
    blob, ext = sh.image.blob, sh.image.ext
    name = hashlib.md5(blob).hexdigest()[:16] + "." + ext
    path = os.path.join(imgdir, name)
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(blob)
    return f'<img src="img/{name}" style="{box([sh])}" alt="">'


def media_shape(sh, imgdir):
    """An audio clip: its poster picture, which plays or pauses the sound when clicked."""
    def store(blob, ext):
        name = hashlib.md5(blob).hexdigest()[:16] + "." + ext
        path = os.path.join(imgdir, name)
        if not os.path.exists(path):
            with open(path, "wb") as f:
                f.write(blob)
        return name
    poster = sh.poster_frame if hasattr(sh, "poster_frame") else sh.image
    media = sh._element.find(".//{http://schemas.microsoft.com/office/powerpoint/2010/main}media")
    part = sh.part.related_part(media.get(qn("r:embed")))
    clip = store(part.blob, part.partname.ext)
    play = "const a=this.nextElementSibling;a.paused?a.play():a.pause()"
    return (f'<img src="img/{store(poster.blob, poster.ext)}" style="{box([sh])};cursor:pointer" alt="play" '
            f'onclick="{play}"><audio src="img/{clip}" preload="auto"></audio>')


def auto_shape(sh, slide, number):
    spPr = sh._element.find(qn("p:spPr"))
    geom = first([spPr], "a:prstGeom", "prst") or "rect"
    fill = colour(spPr.find(qn("a:solidFill"))) if spPr is not None else None
    style = [box([sh])] + ([f"background:{fill}"] if fill else []) + (["border-radius:50%"] if geom == "ellipse" else [])
    out = f'<div class="shape" style="{";".join(style)}"></div>'
    if sh.has_text_frame and sh.text_frame.text.strip():
        out += text_shape(sh, slide, number)
    return out


def slide_html(slide, number, imgdir):
    parts = []
    for sh in slide.shapes:
        if sh._element.find(".//" + qn("a:audioFile")) is not None or sh.shape_type == 16:  # sound, or MEDIA
            parts.append(media_shape(sh, imgdir))
        elif sh.shape_type is not None and sh.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE
            parts.append(picture_shape(sh, imgdir))
        elif getattr(sh, "has_table", False) and sh.has_table:
            parts.append(table_shape(sh, number))
        elif sh.is_placeholder or sh.shape_type == 17:  # MSO_SHAPE_TYPE.TEXT_BOX
            if sh.has_text_frame:
                parts.append(text_shape(sh, slide, number))
        elif sh.shape_type == 1:  # MSO_SHAPE_TYPE.AUTO_SHAPE
            parts.append(auto_shape(sh, slide, number))
        else:
            raise ValueError(f"slide {number}: shape type {sh.shape_type} is not supported in the preview")
    return "".join(parts)


def notes_page(prs):
    """Geometry of the notes page, in points: page size, slide image and notes box."""
    nm = prs.notes_master
    get = lambda t: next(p for p in nm.placeholders if p.placeholder_format.type == t)
    img, body = get(101), get(2)  # SLIDE_IMAGE, BODY
    sz = prs.part._element.find(qn("p:notesSz"))
    bodyPr = body._element.find(qn("p:txBody") + "/" + qn("a:bodyPr"))
    pad = [pt(bodyPr.get(k, d)) for k, d in (("tIns", 45720), ("rIns", 91440), ("bIns", 45720), ("lIns", 91440))]
    marL = first([body._element.find(qn("p:txBody"))], "a:p/a:pPr", "marL")
    return {"page": [pt(sz.get("cx")), pt(sz.get("cy"))],
            "image": [pt(img.left), pt(img.top), pt(img.width), pt(img.height)],
            "box": [pt(body.left), pt(body.top), pt(body.width), pt(body.height)],
            "padding": pad, "indent": pt(marL or 0)}


def write(prs, out, keys, notes_style):
    """Write slides.json (and pictures to img/) in directory out. keys: the notes key of each slide."""
    imgdir = os.path.join(out, "img")
    os.makedirs(imgdir, exist_ok=True)
    slides = []
    for i, sl in enumerate(prs.slides, 1):
        h = slide_html(sl, i, imgdir)
        slides.append({"key": keys[i - 1] if i <= len(keys) else None, "html": h,
                       "hash": hashlib.md5(h.encode()).hexdigest()})
    data = {"size": [pt(prs.slide_width), pt(prs.slide_height)], "notes": dict(notes_page(prs), **notes_style),
            "line": LINE, "slides": slides}
    tmp = os.path.join(out, "slides.json.tmp")
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, os.path.join(out, "slides.json"))
    print("preview", out, len(slides), "slides")
