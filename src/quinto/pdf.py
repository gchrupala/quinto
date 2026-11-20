"""Build the .pptx of one or more decks and export two PDFs of each through LibreOffice: the slides,
and the notes pages (each slide with its speaker notes).

Usage: quinto pdf 00 01 02
Writes NN_name.pdf and NN_name_notes.pdf next to each deck. Needs LibreOffice (soffice) and the fonts
in fonts.py. LibreOffice runs headless with its own profile, so an open LibreOffice window does not
interfere. A PDF cannot show an animation, and LibreOffice would show the first frame of each animated
GIF; the PDFs show the last frame instead, which holds the complete figure. The .pptx keeps its animations.
"""
import io, os, subprocess, sys, tempfile, zipfile
from PIL import Image
from quinto import fonts, qmdfile

# Explicit settings, whatever those of the user's own LibreOffice profile.
FILTERS = {
    "": 'pdf:impress_pdf_Export:{"ExportNotesPages":{"type":"boolean","value":"false"}}',
    "_notes": 'pdf:impress_pdf_Export:{"ExportNotesPages":{"type":"boolean","value":"true"},'
              '"ExportOnlyNotesPages":{"type":"boolean","value":"true"}}',
}



def last_frames(src, dst):
    """Copy the .pptx src to dst, with each animated GIF replaced by a still GIF of its last frame."""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("ppt/media/") and item.filename.lower().endswith(".gif"):
                with Image.open(io.BytesIO(data)) as im:
                    if getattr(im, "n_frames", 1) > 1:
                        im.seek(im.n_frames - 1)
                        buf = io.BytesIO()
                        im.convert("RGB").save(buf, format="GIF")
                        data = buf.getvalue()
            zout.writestr(item, data)


fonts.check()
for nn in sys.argv[1:]:
    qmd = qmdfile.find(nn)
    subprocess.run([sys.executable, "-m", "quinto.build", qmd], check=True)
    profile = "file://" + os.path.join(qmdfile.workdir(qmd), ".lo-profile")
    base = os.path.splitext(qmd)[0]
    for suffix, pdf_filter in FILTERS.items():
        with tempfile.TemporaryDirectory() as tmp:
            still = os.path.join(tmp, os.path.basename(base) + ".pptx")
            last_frames(base + ".pptx", still)
            subprocess.run(["soffice", f"-env:UserInstallation={profile}", "--headless", "--convert-to",
                            pdf_filter, "--outdir", tmp, still], capture_output=True, check=True)
            os.replace(os.path.join(tmp, os.path.basename(base) + ".pdf"), base + suffix + ".pdf")
        print("wrote", os.path.relpath(base + suffix + ".pdf"))
