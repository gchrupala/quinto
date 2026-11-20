"""Quinto: slide decks written in Quarto, built as .pptx with a live preview and a reveal.js version.

The Python cells of a deck start with `from quinto import *`, which brings in the helpers of
style.py (s = new(), tb, arrow, pic, ...), with numpy as np, os and sys. `quinto pptx` runs the
cells against the deck it builds; the reveal.js version and the preview show the HTML that
tohtml.py makes from the same slides, so a cell has nothing to output.

style.py is imported only by `from quinto import *` (or by importing quinto.style), because it draws
in the style the deck chooses, which build.py sets in QUINTO_STYLE first (see styles/__init__.py).
Importing another module of the package, such as quinto.qmdfile, does not import style.py.
"""
import functools, sys

__version__ = "0.2.0"


@functools.lru_cache(maxsize=None)
def _helpers():
    """The names `from quinto import *` gives the cells."""
    import os
    import numpy as np
    from . import style
    names = {n: v for n, v in vars(style).items() if not n.startswith("_")}
    names.update(os=os, sys=sys, np=np, R={"color": style.ACCENT})
    return names


def __getattr__(name):
    if name == "__all__":
        return list(_helpers())
    if "quinto.style" in sys.modules:  # the helpers, once style.py is imported
        helpers = _helpers()
        if name in helpers:
            return helpers[name]
    raise AttributeError(f"module 'quinto' has no attribute {name!r}")
