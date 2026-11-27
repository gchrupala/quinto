"""Property-based tests (Hypothesis) of notesfile: speaker notes from Markdown to runs and HTML."""
import re

from hypothesis import given, strategies as st

from quinto.notesfile import paragraphs, to_html

word = st.text("abcdefghijklmnopqrstuvwxyzABCXYZ0123456789", min_size=1, max_size=8)
words = st.lists(word, min_size=1, max_size=6).map(" ".join)
# Text with plenty of Markdown and HTML syntax in it, and any text at all.
markdownish = st.text("ab \n*_`[]()<>&\"'^~#-+1.!:/\\|", max_size=80)
any_text = st.one_of(markdownish, st.text(max_size=80))

TAG = re.compile(r'<(/?)(b|i|sup|sub|span|a)(?: class="code"| href="[^"<>]*" target="_blank")?>|<br>')


@given(any_text)
def test_html_escapes_all_text(text):
    """Raw HTML in the notes is shown as text: every < and > in the output belongs to a tag that
    to_html makes, and the tags nest properly."""
    for p in to_html(text):
        stack = []
        for m in TAG.finditer(p["html"]):
            if m.group(0) == "<br>":
                continue
            if m.group(1):
                assert stack and stack.pop() == m.group(2), p["html"]
            else:
                stack.append(m.group(2))
        assert not stack, p["html"]
        assert not re.search("[<>]", TAG.sub("", p["html"])), p["html"]


@given(any_text)
def test_neighbouring_runs_differ_in_format(text):
    for p in paragraphs(text):
        for (t1, f1), (t2, f2) in zip(p["runs"], p["runs"][1:]):
            assert f1 != f2 or "\n" in (t1, t2)


@given(st.lists(st.lists(words, min_size=1, max_size=3), min_size=1, max_size=4))
def test_plain_paragraphs(paras):
    """Paragraphs are separated by blank lines; the lines of one are joined by spaces."""
    text = "\n\n".join("\n".join(lines) for lines in paras)
    assert paragraphs(text) == [{"level": 0, "mark": None, "runs": [(" ".join(lines), {})]}
                                for lines in paras]


@given(st.integers(0, 10**6), st.lists(words, min_size=1, max_size=4))
def test_ordered_list_numbers(start, items):
    text = "\n".join(f"{start + j}. {w}" for j, w in enumerate(items))
    ps = paragraphs(text)
    assert [p["mark"] for p in ps] == [f"{start + j}." for j in range(len(items))]
    assert all(p["level"] == 1 for p in ps)


@given(st.lists(words, min_size=1, max_size=3), st.lists(words, min_size=1, max_size=3))
def test_nested_bullets(outer, inner):
    text = "\n".join(f"- {w}" for w in outer) + "\n" + "\n".join(f"  - {w}" for w in inner)
    ps = paragraphs(text)
    assert [(p["mark"], p["level"]) for p in ps] == [("•", 1)] * len(outer) + [("•", 2)] * len(inner)


@given(word)
def test_inline_formats(w):
    def runs(text):
        return paragraphs(text)[0]["runs"]
    assert runs(f"x *{w}*") == [("x ", {}), (w, {"italic": True})]
    assert runs(f"x **{w}**") == [("x ", {}), (w, {"bold": True})]
    assert runs(f"x `{w}`") == [("x ", {}), (w, {"code": True})]
    assert runs(f"x [{w}](https://example.org/{w})") == [("x ", {}), (w, {"link": f"https://example.org/{w}"})]
    assert runs(f"W^{w}^ d~{w}~") == [("W", {}), (w, {"sup": True}), (" d", {}), (w, {"sub": True})]
    assert runs(f"a  \n{w}") == [("a", {}), ("\n", {}), (w, {})]  # hard line break
