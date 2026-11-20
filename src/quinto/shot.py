"""Screenshots of notes pages from the live preview, for checking layout without a browser window.

Usage: quinto shot 01 [3 5-7]     (all slides if none are given)
The preview server of the deck must be running (quinto preview 01). Pages are written to
_quinto/preview/NN/slide-XX.png at about 110 dpi, with headless Google Chrome (or Chromium).
"""
import json, os, shutil, subprocess, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor

from quinto import qmdfile

QMD = qmdfile.find(sys.argv[1])
NN = qmdfile.number(QMD)
WORK = qmdfile.workdir(QMD)
PORT = 8000 + int(NN if NN.isdigit() else 50)
OUT = os.path.join(WORK, "preview", NN)
CHROME = next(c for c in ("google-chrome", "chromium", "chromium-browser") if shutil.which(c))
DPI = 110

state = json.load(urllib.request.urlopen(f"http://localhost:{PORT}/state.json"))
n = len(state["slides"])
wanted = []
for a in sys.argv[2:] or [f"1-{n}"]:
    lo, _, hi = a.partition("-")
    wanted += range(int(lo), int(hi or lo) + 1)
pw, ph = (round(v * 96 / 72) for v in state["page"]["page"])


def shot(i):
    path = os.path.join(OUT, f"slide-{i:02d}.png")
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    f"--user-data-dir={os.path.join(WORK, '.chrome', str(i))}",
                    f"--force-device-scale-factor={DPI / 96}", f"--window-size={pw},{ph}",
                    "--virtual-time-budget=5000", f"--screenshot={path}",
                    f"http://localhost:{PORT}/?shot={i}"], capture_output=True, check=True)
    return path


with ThreadPoolExecutor(4) as ex:
    for p in ex.map(shot, wanted):
        print(p)
