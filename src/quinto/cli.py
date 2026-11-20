"""The quinto command: runs one of the modules of the package as a script.

Usage: quinto COMMAND ARGS...   (quinto help for the list)
"""
import os, runpy, subprocess, sys

COMMANDS = {  # name: (module, arguments, description)
    "pptx": ("build", "DECK", "write the .pptx of a deck"),
    "preview": ("preview", "DECK [PORT]", "live preview in the browser, at port 8000 + deck number"),
    "pdf": ("pdf", "DECK...", "write the .pptx and export PDFs of the slides and the notes pages"),
    "render": ("render", "DECK", "render the notes pages of the .pptx through LibreOffice"),
    "shot": ("shot", "DECK [SLIDES]", "screenshots of preview pages (the preview must be running)"),
    "fonts": ("fonts", "[DECK]", "check that the fonts of the style of a deck are installed"),
    "install-fonts": (None, "", "download the fonts of zeroclutter to ~/.local/share/fonts"),
}


def usage():
    lines = ["usage: quinto COMMAND ARGS", "",
             "A DECK is a number (01: the file 01_*.qmd in the current directory) or a path to a .qmd.", ""]
    lines += [f"  {f'quinto {name} {args}':<30}{text}" for name, (_, args, text) in COMMANDS.items()]
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(usage())
    name, args = sys.argv[1], sys.argv[2:]
    module = COMMANDS[name][0]
    if module is None:
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "install_fonts.sh")
        sys.exit(subprocess.run(["sh", script]).returncode)
    sys.argv = [f"quinto {name}"] + args
    runpy.run_module(f"quinto.{module}", run_name="__main__", alter_sys=True)


if __name__ == "__main__":
    main()
