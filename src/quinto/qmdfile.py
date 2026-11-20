"""A .qmd deck as text: its slides, their keys and speaker notes, and edits to them.

The preview (preview.py) and build.py use this module, so that both read the notes in the
same way. Edits change only the lines concerned and keep the rest of the file as it is.

A slide starts at a level-2 heading (`## Title {#key}` or `## {#key}`), outside code blocks, and
runs to the next one. Its key is the id of the heading; without one, the id pandoc would derive
from the title. Its notes are the text of its `::: notes` block, without the surrounding blank lines.
The notes are Markdown, rendered by notesfile.py.
"""
import glob, os, re

def find(deck):
    """The path of a deck given as its number (01: 01_*.qmd in the current directory) or as a path
    to a .qmd."""
    if deck.endswith(".qmd"):
        return os.path.abspath(deck)
    found = glob.glob(f"{deck}_*.qmd")
    if len(found) != 1:
        raise SystemExit(f"no single deck {deck}_*.qmd in {os.getcwd()}: {found}")
    return os.path.abspath(found[0])


def workdir(path):
    """The directory for generated files of a deck (figure cache, preview, LibreOffice profile):
    QUINTO_DIR if set, otherwise _quinto/ next to the .qmd."""
    return os.environ.get("QUINTO_DIR") or os.path.join(os.path.dirname(os.path.abspath(path)), "_quinto")


def number(path):
    """The number of a deck from its file name (01 for 01_language_speech_text.qmd), or its name."""
    name = os.path.splitext(os.path.basename(path))[0]
    m = re.match(r"\d+", name)
    return m.group() if m else name


FENCE = re.compile(r"^(`{3,}|~{3,})")
DIV_OPEN = re.compile(r"^(:{3,})\s*\S")
DIV_CLOSE = re.compile(r"^:{3,}\s*$")
NOTES_OPEN = re.compile(r"^:{3,}\s*(notes|\{[^}]*\.notes\b[^}]*\})\s*$")
HEADING = re.compile(r"^## (?!#)")
KEY = re.compile(r"\{[^}]*#([\w:.-]+)[^}]*\}\s*$")
CELL = re.compile(r"^(`{3,})\{(\w+)([^}]*)\}", re.M)


def slug(title):
    """The identifier pandoc derives from a heading (auto_identifiers), for plain titles."""
    s = re.sub(r"[^\w\s_.-]", "", title.lower()).strip()
    s = re.sub(r"\s+", "-", s)
    return re.sub(r"^[^a-z]+", "", s) or "section"


class Qmd:
    def __init__(self, path):
        self.path = path
        with open(path, encoding="utf8") as f:
            self.lines = f.read().split("\n")
        self.parse()

    def parse(self):
        """Find the slides: self.starts holds the first line of each, and self.end the end of the last."""
        self.starts, fence, front = [], None, self.lines[:1] == ["---"]
        for i, line in enumerate(self.lines):
            if front:
                if i > 0 and line in ("---", "..."):
                    front = False
                continue
            m = FENCE.match(line)
            if fence:
                if m and line.strip() == fence:
                    fence = None
                continue
            if m:
                fence = m.group(1)
            elif HEADING.match(line):
                self.starts.append(i)
        self.end = len(self.lines)

    def meta(self):
        """The YAML header as a dict (empty without one)."""
        import yaml
        if self.lines[:1] != ["---"]:
            return {}
        end = next(i for i, line in enumerate(self.lines) if i > 0 and line in ("---", "..."))
        return yaml.safe_load("\n".join(self.lines[1:end])) or {}

    def span(self, i):
        return self.starts[i], self.starts[i + 1] if i + 1 < len(self.starts) else self.end

    def key(self, i):
        head = self.lines[self.starts[i]][3:]
        m = KEY.search(head)
        return m.group(1) if m else slug(head)

    def keys(self):
        return [self.key(i) for i in range(len(self.starts))]

    def notes_block(self, i):
        """Lines (start, end) of the inside of the notes block of slide i, or None."""
        a, b = self.span(i)
        fence = None
        for j in range(a, b):
            line = self.lines[j]
            m = FENCE.match(line)  # skip code blocks
            if fence:
                if m and line.strip() == fence:
                    fence = None
                continue
            if m:
                fence = m.group(1)
                continue
            if NOTES_OPEN.match(line):
                depth = 1
                for k in range(j + 1, b):
                    if DIV_CLOSE.match(self.lines[k]):
                        depth -= 1
                        if depth == 0:
                            return j + 1, k
                    elif DIV_OPEN.match(self.lines[k]):
                        depth += 1
                raise ValueError(f"slide {self.key(i)}: the notes block is not closed")
        return None

    def notes(self, i):
        blk = self.notes_block(i)
        return "\n".join(self.lines[blk[0]:blk[1]]).strip("\n") if blk else ""

    def all_notes(self):
        return [(self.key(i), self.notes(i)) for i in range(len(self.starts))]

    # ── edits ───────────────────────────────────────────────────────────────

    def set_notes(self, i, text):
        """Replace the notes of slide i, with a blank line inside each fence (see README)."""
        inner = [""] + text.strip("\n").split("\n") + [""] if text.strip() else [""]
        blk = self.notes_block(i)
        if blk:
            self.lines[blk[0]:blk[1]] = inner
        else:
            a, b = self.span(i)
            while b > a + 1 and self.lines[b - 1] == "":
                b -= 1
            self.lines[b:b] = ["", "::: notes"] + inner + [":::"]
        self.parse()

    def unique(self, base):
        keys, n = set(self.keys()), 2
        base = re.sub(r"-\d+$", "", base)
        while f"{base}-{n}" in keys:
            n += 1
        return f"{base}-{n}"

    def _section_end(self, i):
        """Insertion point after slide i (i = -1: before the first slide), on a fresh line."""
        at = self.starts[i + 1] if i + 1 < len(self.starts) else self.end
        if i + 1 >= len(self.starts):
            while at > 0 and self.lines[at - 1] == "":
                at -= 1
            self.lines[at:] = [""]
            at += 1
        return at

    def insert(self, i):
        """A new, empty slide after slide i (-1: before the first one). Returns its key."""
        key = self.unique("slide")
        at = self._section_end(i)
        self.lines[at:at] = [f"## {{#{key}}}", "", "::: notes", "", ":::", ""]
        self.parse()
        return key

    def duplicate(self, i):
        """A copy of slide i after it, under a new key. Returns the key."""
        a, b = self.span(i)
        block = self.lines[a:b]
        while block and block[-1] == "":
            block.pop()
        key = self.unique(self.key(i))
        head = block[0]
        block[0] = KEY.sub(lambda m: m.group(0).replace("#" + m.group(1), "#" + key), head) if KEY.search(head) \
            else f"{head.rstrip()} {{#{key}}}"
        at = self._section_end(i)
        self.lines[at:at] = block + [""]
        self.parse()
        return key

    def remove(self, i):
        a, b = self.span(i)
        del self.lines[a:b]
        self.parse()

    def save(self):
        text = "\n".join(self.lines)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf8") as f:
            f.write(text if text.endswith("\n") else text + "\n")
        import os
        os.replace(tmp, self.path)

    # ── for pandoc ──────────────────────────────────────────────────────────

    def for_pandoc(self):
        """The text with Quarto cells (```{python}) as code blocks that plain pandoc reads, classed .cell."""
        return CELL.sub(lambda m: f"{m.group(1)}{{.{m.group(2)} .cell{m.group(3)}}}", "\n".join(self.lines))

    def body_without_notes(self):
        """The text with the notes left out: when only notes change, no rebuild is needed."""
        out, skip = [], set()
        for i in range(len(self.starts)):
            blk = self.notes_block(i)
            if blk:
                skip.update(range(*blk))
        return "\n".join(l for j, l in enumerate(self.lines) if j not in skip)
