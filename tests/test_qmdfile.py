"""Property-based tests (Hypothesis) of qmdfile: reading a deck's slides and notes, and editing them."""
import re
import shutil
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, precondition, rule

from quinto import qmdfile
from quinto.qmdfile import Qmd

# ── generated decks ─────────────────────────────────────────────────────────

word = st.text("abcdefghijklmnopqrstuvwxyzABCXYZ", min_size=1, max_size=8)
title = st.lists(word, min_size=1, max_size=3).map(" ".join)


def plain_line(line):
    """A notes line that the deck format reads as text: no fences, divs or slide headings."""
    return not line.startswith((":::", "```", "~~~", "## "))


notes_line = st.text(st.characters(exclude_categories=["Cs", "Cc", "Zl", "Zp"]), max_size=30).filter(plain_line)
notes_text = st.lists(notes_line, max_size=5).map("\n".join)
body_line = st.lists(word, max_size=4).map(" ".join)


def stored(text):
    """The notes as read back after set_notes(text)."""
    return text.strip("\n") if text.strip() else ""


@st.composite
def decks(draw):
    """(text of a deck, [(key, notes)] of its slides). Keys are unique: explicit ids (id:N) can't
    clash with ids derived from titles, which have no colon."""
    lines = []
    if draw(st.booleans()):
        lines += ["---", "title: A deck", "## a YAML comment, not a slide", "---", ""]
    titles = draw(st.lists(title, min_size=1, max_size=5, unique_by=qmdfile.slug))
    slides = []
    for i, t in enumerate(titles):
        kind = draw(st.sampled_from(["id", "title", "id only"]))
        if kind == "title":
            lines.append(f"## {t}")
            key = qmdfile.slug(t)
        else:
            key = f"id:{i}"
            lines.append(f"## {t} {{#{key}}}" if kind == "id" else f"## {{#{key}}}")
        lines += [""] + draw(st.lists(body_line, max_size=2)) + [""]
        if draw(st.booleans()):  # a cell whose lines look like a heading and a notes block
            lines += ["```{python}", "## a comment, not a slide", "::: notes", "x = 1", "```", ""]
        if draw(st.booleans()):
            lines += ["::: question", "Why?", ":::", ""]
        notes = ""
        if draw(st.booleans()):
            inner = draw(notes_text).split("\n")
            if draw(st.booleans()):  # a div inside the notes
                inner += ["::: aside", "nested", ":::"]
            lines += ["::: notes", ""] + inner + ["", ":::", ""]
            notes = "\n".join(inner).strip("\n")
        slides.append((key, notes))
    return "\n".join(lines), slides


def load(text):
    d = tempfile.mkdtemp()
    p = Path(d) / "01_deck.qmd"
    p.write_text(text, encoding="utf8")
    return Qmd(str(p)), d


def with_deck(test):
    """Run test(q, slides, data) on a generated deck in a temporary directory."""
    @given(decks(), st.data())
    def wrapper(deck, data):
        text, slides = deck
        q, d = load(text)
        try:
            test(q, slides, data)
        finally:
            shutil.rmtree(d)
    wrapper.__name__ = test.__name__
    return wrapper


# ── reading ─────────────────────────────────────────────────────────────────

@with_deck
def test_reads_keys_and_notes(q, slides, data):
    """Slides start at level-2 headings outside code and the YAML header; notes are the inside of
    ::: notes, nested divs included, and not a ::: notes inside code."""
    assert q.all_notes() == slides


@with_deck
def test_for_pandoc_changes_only_cell_fences(q, slides, data):
    out = q.for_pandoc().split("\n")
    assert len(out) == len(q.lines)
    for a, b in zip(q.lines, out):
        assert a == b or qmdfile.CELL.match(a)


@given(st.text(max_size=40))
def test_slug_is_an_identifier(t):
    s = qmdfile.slug(t)
    assert s == "section" or re.fullmatch(r"[a-z][\w.-]*", s)
    assert qmdfile.slug(s) == s


# ── edits ───────────────────────────────────────────────────────────────────

@with_deck
def test_set_notes_changes_only_that_slide(q, slides, data):
    """Edits change only the lines concerned and keep the rest of the file as it is."""
    i = data.draw(st.integers(0, len(slides) - 1))
    text = data.draw(notes_text)
    a, b = q.span(i)
    before, after, had_notes, body = q.lines[:a], q.lines[b:], q.notes_block(i), q.body_without_notes()
    q.set_notes(i, text)
    assert q.notes(i) == stored(text)
    a2, b2 = q.span(i)
    assert q.lines[:a2] == before and q.lines[b2:] == after
    if had_notes:  # only the notes changed: no rebuild needed
        assert q.body_without_notes() == body


class DeckEdits(RuleBasedStateMachine):
    """Random sequences of the preview's edits, checked against a list of (key, notes)."""

    @initialize(deck=decks())
    def load(self, deck):
        text, slides = deck
        self.q, self.dir = load(text)
        self.model = list(slides)

    def teardown(self):
        if hasattr(self, "dir"):
            shutil.rmtree(self.dir)

    def slide(self, data, first=0):
        return data.draw(st.integers(first, len(self.model) - 1))

    @rule(data=st.data(), text=notes_text)
    def set_notes(self, data, text):
        i = self.slide(data)
        self.q.set_notes(i, text)
        self.model[i] = (self.model[i][0], stored(text))

    @rule(data=st.data())
    def insert(self, data):
        i = self.slide(data, first=-1)
        key = self.q.insert(i)
        assert key not in {k for k, _ in self.model}
        self.model.insert(i + 1, (key, ""))

    @rule(data=st.data())
    def duplicate(self, data):
        i = self.slide(data)
        key = self.q.duplicate(i)
        assert key not in {k for k, _ in self.model}
        self.model.insert(i + 1, (key, self.model[i][1]))

    @precondition(lambda self: len(self.model) > 1)
    @rule(data=st.data())
    def remove(self, data):
        i = self.slide(data)
        self.q.remove(i)
        del self.model[i]

    @rule()
    def save_and_reload(self):
        self.q.save()
        self.q = Qmd(self.q.path)

    @invariant()
    def matches_model(self):
        assert self.q.all_notes() == self.model


DeckEdits.TestCase.settings = settings(max_examples=50, stateful_step_count=20, deadline=None)
TestDeckEdits = DeckEdits.TestCase
