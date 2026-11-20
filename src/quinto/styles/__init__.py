"""The styles of Quinto, and the choice of one for a deck.

A deck chooses its style in its YAML header:

    quinto:
      style: zeroclutter

The value is the name of a module in this package, or the path of a Python file (relative to the
.qmd), for a style of one's own. Without it, the style is DEFAULT. build.py passes the choice to
style.py in the environment variable QUINTO_STYLE, as a name or an absolute path.
"""
import importlib, importlib.util, os, sys

DEFAULT = "zeroclutter"
NAMES = ["zeroclutter"]  # the styles in this package


def spec(qmd):
    """The style a deck chooses: a name, or the absolute path of a style file."""
    from quinto import qmdfile
    meta = qmdfile.Qmd(qmd).meta().get("quinto") or {}
    choice = str(meta.get("style") or DEFAULT)
    if choice.endswith(".py"):
        return os.path.join(os.path.dirname(os.path.abspath(qmd)), choice)
    if choice not in NAMES:
        raise SystemExit(f"{qmd}: no style {choice!r}; the styles are {', '.join(NAMES)}, or a .py file")
    return choice


def load(choice=None):
    """The module of a style, given as by spec(); by default the one in QUINTO_STYLE, or DEFAULT."""
    choice = choice or os.environ.get("QUINTO_STYLE") or DEFAULT
    if choice.endswith(".py"):
        name = "quinto_style_" + os.path.splitext(os.path.basename(choice))[0]
        if name not in sys.modules:
            s = importlib.util.spec_from_file_location(name, choice)
            module = importlib.util.module_from_spec(s)
            s.loader.exec_module(module)
            sys.modules[name] = module
        return sys.modules[name]
    return importlib.import_module(f"quinto.styles.{choice}")
