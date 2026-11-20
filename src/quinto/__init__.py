"""Quinto: slide decks written in Quarto, built as .pptx with a live preview and a reveal.js version.

The Python cells of a deck start with `from quinto import *`, which brings in the helpers of
style.py (s = new(), tb, arrow, pic, ...). `quinto pptx` runs the cells against the deck it builds;
the reveal.js version and the preview show the HTML that tohtml.py makes from the same slides, so a
cell has nothing to output.
"""
import os, sys  # noqa: F401  (for the cells)
import numpy as np  # noqa: F401  (for the cells)

from .style import *  # noqa: E402,F401,F403

__version__ = "0.1.0"

R = {"color": ACCENT}  # noqa: F405
