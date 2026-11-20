"""Build the .pptx of a deck and render its notes pages through LibreOffice, as a final check of the
real deck (the live preview shows an HTML version).

Usage: quinto render 01
Writes _quinto/preview/NN/pptx/slide-XX.png. Needs LibreOffice (soffice) and pdftoppm (poppler-utils).
LibreOffice runs headless with its own profile, so an open LibreOffice window does not interfere.
"""
import glob, os, subprocess, sys, tempfile
from quinto import fonts, qmdfile, styles

qmd = qmdfile.find(sys.argv[1])
NN = qmdfile.number(qmd)
OUT = os.path.join(qmdfile.workdir(qmd), "preview", NN, "pptx")
PROFILE = "file://" + os.path.join(qmdfile.workdir(qmd), ".lo-profile")
# Notes pages only, whatever the settings of the user's own LibreOffice profile.
PDF_FILTER = 'pdf:impress_pdf_Export:{"ExportNotesPages":{"type":"boolean","value":"true"},' \
             '"ExportOnlyNotesPages":{"type":"boolean","value":"true"}}'

fonts.check(styles.load(styles.spec(qmd)))
subprocess.run([sys.executable, "-m", "quinto.build", qmd], check=True)
deck = os.path.splitext(qmd)[0] + ".pptx"
os.makedirs(OUT, exist_ok=True)
for old in glob.glob(os.path.join(OUT, "slide-*.png")):
    os.remove(old)
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run(["soffice", f"-env:UserInstallation={PROFILE}", "--headless", "--convert-to", PDF_FILTER,
                    "--outdir", tmp, deck], capture_output=True, check=True)
    pdf = os.path.join(tmp, os.path.basename(deck)[:-5] + ".pdf")
    subprocess.run(["pdftoppm", "-r", "110", "-png", pdf, os.path.join(tmp, "p")], check=True)
    for i, src in enumerate(sorted(glob.glob(os.path.join(tmp, "p-*.png"))), 1):
        os.replace(src, os.path.join(OUT, f"slide-{i:02d}.png"))
print("rendered", i, "pages to", OUT)
