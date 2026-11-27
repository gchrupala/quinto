"""Speaker notes in Markdown, rendered in the same way in the .pptx and in HTML.

The notes of a slide are Markdown (CommonMark): paragraphs separated by blank lines, *italics*,
**bold**, `code`, [links](https://...), lists, headings and code blocks, and, as in Pandoc,
superscripts and subscripts without spaces: W^Q^, d~k~. Raw HTML is shown as text.
In a deck they are the ::: notes block of each slide (see qmdfile.py).

paragraphs() turns the Markdown of one slide into the paragraphs of the notes, so that the .pptx
(style.notes), the live preview (preview.py) and reveal.js (to_html, via build.py) render the
notes in the same way.
"""
import html
import re

from markdown_it import MarkdownIt

MD = MarkdownIt("commonmark", {"html": False})
SUPSUB = re.compile(r"\^([^\s^]+)\^|~([^\s~]+)~")  # Pandoc: ^superscript^, ~subscript~, without spaces


def paragraphs(text):
    """The paragraphs of a section in Markdown. Each is a dict:
    level: list nesting depth (0 outside lists); mark: "•" or "3." on the first paragraph of a list
    item, else None; runs: list of (text, fmt), fmt a dict with any of italic, bold, code, sup, sub
    (True) and link (the address); a run with text "\\n" is a line break."""
    out, lists, mark, quote = [], [], None, 0
    fmt = {}
    tokens = MD.parse(text)
    for i, t in enumerate(tokens):
        if t.type in ("bullet_list_open", "ordered_list_open"):
            if t.type == "ordered_list_open":  # no start attribute: from 1; it can be 0
                start = t.attrGet("start")
                start = 1 if start is None else int(start)
            else:
                start = None
            lists.append(start)
        elif t.type in ("bullet_list_close", "ordered_list_close"):
            lists.pop()
        elif t.type == "list_item_open":
            if lists[-1] is None:
                mark = "•"
            else:
                mark = f"{lists[-1]}."
                lists[-1] += 1
        elif t.type == "blockquote_open":
            quote += 1
        elif t.type == "blockquote_close":
            quote -= 1
        elif t.type == "heading_open":
            fmt = {"bold": True}
        elif t.type == "heading_close":
            fmt = {}
        elif t.type in ("fence", "code_block"):
            runs = []
            for k, line in enumerate(t.content.rstrip("\n").split("\n")):
                runs += ([("\n", {})] if k else []) + [(line, {"code": True})]
            out.append({"level": len(lists) + quote, "mark": mark, "runs": runs})
            mark = None
        elif t.type == "inline":
            out.append({"level": len(lists) + quote, "mark": mark, "runs": _runs(t.children, fmt)})
            mark = None
    return out


def _runs(children, base):
    runs, f = [], dict(base)
    for c in children:
        if c.type == "text":
            runs += _supsub(c.content, f)
        elif c.type == "softbreak":
            runs.append((" ", dict(f)))
        elif c.type == "hardbreak":
            runs.append(("\n", {}))
        elif c.type == "code_inline":
            runs.append((c.content, dict(f, code=True)))
        elif c.type == "em_open":
            f["italic"] = True
        elif c.type == "em_close":
            f.pop("italic", None)
        elif c.type == "strong_open":
            f["bold"] = True
        elif c.type == "strong_close":
            f.pop("bold", None)
        elif c.type == "link_open":
            f["link"] = c.attrGet("href")
        elif c.type == "link_close":
            f.pop("link", None)
        elif c.type == "image":
            runs.append((c.content, dict(f)))
    # merge neighbouring runs with the same format
    merged = []
    for text, fm in runs:
        if merged and merged[-1][1] == fm and text != "\n" and merged[-1][0] != "\n":
            merged[-1] = (merged[-1][0] + text, fm)
        else:
            merged.append((text, fm))
    return merged


def _supsub(text, f):
    """Runs of a text, with ^superscripts^ and ~subscripts~ as runs of their own."""
    runs, pos = [], 0
    for m in SUPSUB.finditer(text):
        if m.start() > pos:
            runs.append((text[pos:m.start()], dict(f)))
        runs.append((m.group(1), dict(f, sup=True)) if m.group(1) else (m.group(2), dict(f, sub=True)))
        pos = m.end()
    if pos < len(text):
        runs.append((text[pos:], dict(f)))
    return runs


def to_html(text):
    """The paragraphs of a section as [{level, mark, html}], html being the inline content."""
    out = []
    for p in paragraphs(text):
        h = ""
        for t, f in p["runs"]:
            if t == "\n":
                h += "<br>"
                continue
            s = html.escape(t, quote=False)
            if f.get("code"):
                s = f'<span class="code">{s}</span>'
            if f.get("sup"):
                s = f"<sup>{s}</sup>"
            if f.get("sub"):
                s = f"<sub>{s}</sub>"
            if f.get("italic"):
                s = f"<i>{s}</i>"
            if f.get("bold"):
                s = f"<b>{s}</b>"
            if f.get("link"):
                s = f'<a href="{html.escape(f["link"])}" target="_blank">{s}</a>'
            h += s
        out.append({"level": p["level"], "mark": p["mark"], "html": h})
    return out
