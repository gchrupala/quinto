"""Live preview of a deck in the browser.

Runs build.py on the deck (NN_*.qmd) with DECK_HTML set, so that it writes an HTML
version of the slides (see tohtml.py) instead of the .pptx, and serves a page that shows each slide
on its notes page. The notes are the ::: notes blocks of the .qmd, read and written by qmdfile.py;
a change to the notes only needs no rebuild. Notes that do not fit in the notes box are marked.
Slides that changed in the last rebuild are marked too. The slide shown in the page, with the time
it was last reported, is kept in _quinto/preview/NN/current.txt, and the slides whose notes overflow
in _quinto/preview/NN/overflow.txt. The notes of a slide can be edited in the page; saving writes them into
the .qmd. The page can also insert, duplicate and remove slides.

Usage: quinto preview 01 [port]     (default port 8000 + deck number, e.g. 8001)
Then open http://localhost:8001 in a browser or in VS Code (Simple Browser: Show).
The .pptx itself is written by build.py: quinto pptx 01.
"""
import glob, http.server, json, os, subprocess, sys, threading, time, urllib.parse
from quinto import notesfile, qmdfile

HERE = os.path.dirname(os.path.abspath(__file__))
QMD = qmdfile.find(sys.argv[1])
NN = qmdfile.number(QMD)
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8000 + int(NN if NN.isdigit() else 50)
DECK = QMD
BUILD = [sys.executable, "-m", "quinto.build", QMD]
SCRIPTS = [os.path.join(HERE, f) for f in ("build.py", "__init__.py", "qmdfile.py", "style.py", "tohtml.py")]
OUT = os.path.join(qmdfile.workdir(QMD), "preview", NN)
FONTS = os.path.expanduser("~/.local/share/fonts/libertinus/")
lock = threading.Lock()

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Deck %s preview</title>
<style>
/* the font files themselves, not local(): Firefox matches "Libertinus Serif Italic" to SemiBold Italic */
@font-face { font-family: "Libertinus Serif"; src: url(fonts/LibertinusSerif-Regular.ttf); }
@font-face { font-family: "Libertinus Serif"; font-style: italic; src: url(fonts/LibertinusSerif-Italic.ttf); }
@font-face { font-family: "Libertinus Serif"; font-weight: bold; src: url(fonts/LibertinusSerif-Bold.ttf); }
@font-face { font-family: "Libertinus Serif"; font-weight: bold; font-style: italic; src: url(fonts/LibertinusSerif-BoldItalic.ttf); }
body { margin: 0; padding: 12px 16px; background: #eee; font: 15px/1.4 sans-serif; color: #1a1a1a; }
body.shot { padding: 0; background: #fff; }
header { height: 24px; color: #707070; }
body.shot header { display: none; }
#error { display: none; white-space: pre-wrap; background: #fff; border: 2px solid #c0392b; padding: 12px; }
#main { display: flex; gap: 16px; align-items: flex-start; }
#pages { flex: 1; min-width: 0; }
/* pages that are not shown stay laid out, so that their notes can be measured */
.wrap { position: absolute; left: 0; top: 0; visibility: hidden; margin: 0 auto;
        border: 3px solid transparent; background: #fff; overflow: hidden; }
.wrap.current { position: static; visibility: visible; }
#pages { position: relative; }
.wrap.changed { border-color: #c0392b; }
body.shot .wrap { border: 0; }
body.grid #pages { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, 260px); justify-content: center; }
body.grid .wrap { position: static; visibility: visible; cursor: pointer; margin: 0; }
body.grid .wrap.current { outline: 3px solid #2e5c8a; }
.page { position: relative; transform-origin: 0 0; background: #fff; color: #000;
        font-family: "Libertinus Serif", serif; }
.frame { position: absolute; outline: 1px solid #c8c8c8; overflow: hidden; }
.slide { position: absolute; left: 0; top: 0; transform-origin: 0 0; background: #fff; }
.slide .tb { position: absolute; display: flex; flex-direction: column; box-sizing: border-box; }
.slide p { margin: 0; white-space: pre-wrap; }
.slide .tbl { position: absolute; border-collapse: collapse; table-layout: fixed; }
.slide td { box-sizing: border-box; }
.slide img, .slide .shape { position: absolute; }
.notes { position: absolute; box-sizing: border-box; }
.notes p { margin: 0; }
.notes .mark { display: inline-block; text-indent: 0; }
.notes .code { font-family: "Latin Modern Mono", monospace; }
.notes.overflow { outline: 2px solid #c0392b; outline-offset: 2px; }
.pageno { position: absolute; font-size: 14pt; text-align: right; }
#editor { display: none; flex: 0 0 min(40vw, 640px); }
body.editing:not(.grid) #editor { display: block; }
#editor textarea { box-sizing: border-box; width: 100%%; height: calc(100vh - 100px); padding: 10px;
                   font: 17px/1.45 "Libertinus Serif", serif; border: 1px solid #bbb; resize: none; }
#editor div { height: 28px; color: #707070; }
#editor button { font: inherit; margin-right: 8px; }
#editor #msg.warn, #status .warn { color: #c0392b; }
</style></head>
<body>
<header><span id="status">waiting for the first build…</span></header>
<pre id="error"></pre>
<div id="main">
<div id="pages"></div>
<aside id="editor">
<textarea id="notes" spellcheck="true"></textarea>
<div><button id="save">save</button><button id="close">close</button><span id="msg"></span></div>
</aside>
</div>
<script>
// ← → (also PageUp/PageDown, space) move between slides, Home/End jump, g toggles a grid overview,
// e opens the notes of the slide for editing. ?shot=N shows only page N at 96 dpi, for screenshots.
const PT = 96 / 72;  // CSS pixels per point
const params = new URLSearchParams(location.search), shot = parseInt(params.get("shot")) || 0;
let version = null, state = null, cur = shot || parseInt(location.hash.slice(1)) || 1, overflow = [];
if (shot) document.body.classList.add("shot");
async function poll() {
  try {
    const q = shot ? "" : `?at=${cur}&overflow=${overflow.join(",")}`;
    const v = await (await fetch("version" + q, {cache: "no-store"})).json();
    if (v.version !== version) {
      state = await (await fetch("state.json", {cache: "no-store"})).json();
      version = state.version;
      render();
    }
  } catch (e) {}
  if (!shot) setTimeout(poll, 500);
}
function status() {
  const s = state, el = document.getElementById("status");
  el.innerHTML = "";
  el.append(`${cur} / ${s.slides.length} · ${s.deck} · built ${s.time} in ${s.seconds} s` +
            (s.changed.length ? ` · changed: ${s.changed.join(", ")}` : ""));
  if (overflow.length) {
    const w = document.createElement("span"); w.className = "warn";
    w.textContent = ` · notes overflow: ${overflow.join(", ")}`; el.append(w);
  }
  el.append(" · ← → to move, g for grid, e to edit notes" + (s.qmd ? ", i to insert a slide, d to duplicate, x to remove" : ""));
}
function go(n) {
  if (!state || !state.slides.length) return;
  n = Math.min(Math.max(n, 1), state.slides.length);
  if (n !== cur && editing() && dirty && !confirm("Discard your unsaved changes to the notes?")) return;
  if (n !== cur) dirty = false;
  cur = n;
  if (editing()) load();
  if (!shot) history.replaceState(null, "", "#" + cur);
  [...document.getElementById("pages").children].forEach(w => w.classList.toggle("current", +w.dataset.n === cur));
  scale();
  status();
}
const LIST_INDENT = 20, LIST_HANG = 16;  // pt, as in style.py
function pageHTML(i) {
  const s = state, g = s.page, sl = s.slides[i], n = (s.notes[i] || {}).paras || [];
  const [pw, ph] = g.page, [ix, iy, iw, ih] = g.image, [bx, by, bw, bh] = g.box, [pt_, pr, pb, pl] = g.padding;
  const k = iw / s.size[0];
  // paragraphs rendered from Markdown by notesfile.to_html; list items hang their mark in the indent
  const paras = n.map(p => {
    const left = g.indent + p.level * LIST_INDENT, hang = p.mark ? LIST_HANG : 0;
    const mark = p.mark ? `<span class="mark" style="width:${LIST_HANG}pt">${p.mark}</span>` : "";
    return `<p style="padding-left:${left}pt;text-indent:${-hang}pt;margin-bottom:${g.space}pt;line-height:${s.line}">${mark}${p.html}</p>`;
  }).join("");
  return `<div class="page" style="width:${pw}pt;height:${ph}pt">` +
    `<div class="frame" style="left:${ix}pt;top:${iy}pt;width:${iw}pt;height:${ih}pt">` +
    `<div class="slide" style="width:${s.size[0]}pt;height:${s.size[1]}pt;transform:scale(${k})">${sl.html}</div></div>` +
    `<div class="notes" style="left:${bx}pt;top:${by}pt;width:${bw}pt;height:${bh}pt;` +
    `padding:${pt_}pt ${pr}pt ${pb}pt ${pl}pt;font-size:${g.size}pt"><div class="ntext">${paras}</div></div>` +
    `<div class="pageno" style="left:${pw - 130}pt;top:${ph - 30}pt;width:120pt">${i + 1}</div></div>`;
}
function render() {
  const s = state;
  const err = document.getElementById("error");
  err.style.display = s.error ? "block" : "none";
  err.textContent = s.error || "";
  const box = document.getElementById("pages");
  s.slides.forEach((sl, i) => {
    if (shot && i + 1 !== shot) return;
    let w = box.querySelector(`[data-n="${i + 1}"]`);
    if (!w) {
      w = document.createElement("div"); w.className = "wrap"; w.dataset.n = i + 1;
      w.onclick = () => { if (document.body.classList.contains("grid")) { document.body.classList.remove("grid"); go(i + 1); } };
      box.appendChild(w);
    }
    const h = pageHTML(i);
    if (w._html !== h) { w.innerHTML = h; w._html = h; }
    w.classList.toggle("changed", s.changed.includes(i + 1));
  });
  [...box.children].forEach(w => { if (+w.dataset.n > s.slides.length) w.remove(); });
  if (target && s.slides.some(sl => sl.key === target)) { cur = s.slides.findIndex(sl => sl.key === target) + 1; target = null; }
  go(cur);
  document.fonts.ready.then(check);
}
// Notes that do not fit in the notes box. Layout sizes are not affected by the scaling.
function check() {
  overflow = [];
  for (const w of document.querySelectorAll(".wrap")) {
    const nb = w.querySelector(".notes"), t = w.querySelector(".ntext"), g = state.page;
    const room = (g.box[3] - g.padding[0] - g.padding[2]) * PT;
    // the space after the last paragraph does not count
    const last = t.lastElementChild, after = last ? parseFloat(getComputedStyle(last).marginBottom) : 0;
    // LibreOffice sets the notes about 4 pt lower than the browser; keep that margin
    const over = t.offsetHeight - after > room - 4 * PT;
    nb.classList.toggle("overflow", over);
    if (over) overflow.push(+w.dataset.n);
  }
  status();
  document.body.dataset.ready = "1";
}
function scale() {
  if (!state) return;
  const [pw, ph] = state.page.page, grid = document.body.classList.contains("grid");
  const avail = shot ? ph * PT : Math.max(200, innerHeight - 60);
  for (const w of document.querySelectorAll(".wrap")) {
    const k = grid ? 254 / (pw * PT) : avail / (ph * PT);
    const p = w.querySelector(".page");
    if (!p) continue;
    p.style.transform = `scale(${k})`;
    w.style.width = pw * PT * k + "px"; w.style.height = ph * PT * k + "px";
  }
}
addEventListener("resize", scale);
// Editing notes, as Markdown, the same text as in the ::: notes block of the .qmd. base is the text the edit started from, to detect changes made elsewhere.
const area = document.getElementById("notes"), msg = document.getElementById("msg");
let dirty = false, base = "";
const editing = () => document.body.classList.contains("editing");
function note(text, warn) { msg.textContent = text; msg.classList.toggle("warn", !!warn); }
function load() {
  if (dirty) return;
  const n = (state.notes || [])[cur - 1];
  base = n ? n.text : "";
  area.value = base;
  note(n ? `${n.key} · ctrl+s to save · esc to close` : "this slide has no notes block in the .qmd", !n);
}
function openEditor() { document.body.classList.add("editing"); go(cur); area.focus(); }
function closeEditor() {
  if (dirty && !confirm("Discard your unsaved changes to the notes?")) return;
  dirty = false; document.body.classList.remove("editing"); area.blur(); go(cur);
}
async function save() {
  const text = area.value.split("\\n").map(l => l.trimEnd()).join("\\n").replace(/^\\n+|\\n+$/g, "");
  const r = await fetch("notes", {method: "POST", headers: {"Content-Type": "application/json"},
                                  body: JSON.stringify({slide: cur, text, base})});
  const res = await r.json();
  if (r.ok) {
    dirty = false; base = text;
    note("saved");
  } else if (r.status === 409) {
    base = res.current;
    note("these notes were changed elsewhere meanwhile; your text is kept, save again to overwrite", true);
  } else note(res.error || "could not save", true);
}
area.addEventListener("input", () => { dirty = true; });
// Inserting, duplicating and removing slides (.qmd decks): the server edits the file, and the page
// moves to the new slide (target, by key) once the rebuild shows it.
let target = null, armed = false;
async function slideOp(op) {
  if (!state || !state.qmd || dirty) return;
  const key = state.slides[cur - 1].key;
  const r = await fetch("slide", {method: "POST", headers: {"Content-Type": "application/json"},
                                  body: JSON.stringify({op, slide: cur, key})});
  const res = await r.json();
  const el = document.getElementById("status");
  if (!r.ok) { el.innerHTML = `<span class="warn">${res.error}</span>`; return; }
  // after a removal: the slide that followed it, or else the one before
  target = op === "remove" ? (state.slides[cur] || state.slides[cur - 2] || {}).key : res.key;
  el.textContent = `${op}: ${res.key} · rebuilding…`;
}
document.getElementById("save").onclick = save;
document.getElementById("close").onclick = closeEditor;
addEventListener("beforeunload", e => { if (dirty) e.preventDefault(); });
document.addEventListener("keydown", e => {
  const k = e.key;
  if (e.target === area) {
    if ((e.ctrlKey || e.metaKey) && (k === "s" || k === "Enter")) { e.preventDefault(); save(); }
    else if (k === "Escape") closeEditor();
    return;
  }
  if (k === "e") { e.preventDefault(); openEditor(); return; }
  if (state && state.qmd && !editing()) {
    if (k === "i") { slideOp("insert"); return; }
    if (k === "d") { slideOp("duplicate"); return; }
    if (k === "x") {
      const el = document.getElementById("status");
      el.innerHTML = `<span class="warn">remove slide ${cur} (${state.slides[cur - 1].key})? y to confirm, any other key to cancel</span>`;
      armed = true; return;
    }
  }
  if (armed) { armed = false; if (k === "y") { slideOp("remove"); return; } status(); return; }
  if (k === "Escape" && editing()) { closeEditor(); return; }
  if (["ArrowRight", "ArrowDown", "PageDown", " "].includes(k)) go(cur + 1);
  else if (["ArrowLeft", "ArrowUp", "PageUp"].includes(k)) go(cur - 1);
  else if (k === "Home") go(1);
  else if (k === "End") go(state ? state.slides.length : 1);
  else if (k === "g") { document.body.classList.toggle("grid"); go(cur); return; }
  else return;
  e.preventDefault();
});
poll();
</script></body></html>
"""

state = {"version": 0, "deck": os.path.basename(DECK), "qmd": bool(QMD), "slides": [], "notes": [], "changed": [],
         "error": "", "time": "", "seconds": 0, "size": [0, 0], "page": {}, "line": 1.2}
notes_seen = []


def read_notes():
    # the title slide comes from the YAML header and has no notes
    sections = [("title", "")] + qmdfile.Qmd(QMD).all_notes()
    return [{"key": k, "text": v, "paras": notesfile.to_html(v)} for k, v in sections]


def publish(changed):
    state.update(version=state["version"] + 1, changed=changed, time=time.strftime("%H:%M:%S"))


def build():
    """Run build.py for the HTML preview and load what it wrote."""
    t0 = time.time()
    env = dict(os.environ, DECK_HTML=OUT)
    r = subprocess.run(BUILD, cwd=os.path.dirname(QMD), capture_output=True, text=True, env=env)
    notes = read_notes()
    if r.returncode:
        state.update(error=r.stdout + r.stderr, notes=notes)
    else:
        with open(os.path.join(OUT, "slides.json")) as f:
            data = json.load(f)
        old = {i: (s["hash"], n["text"] if n else None)
               for i, (s, n) in enumerate(zip(state["slides"], state["notes"] + [None] * len(state["slides"])))}
        first = not state["slides"]
        changed = [] if first else [i + 1 for i, s in enumerate(data["slides"])
                                    if old.get(i) != (s["hash"], notes[i]["text"] if i < len(notes) else None)]
        state.update(error="", slides=data["slides"], size=data["size"], page=data["notes"],
                     line=data["line"], notes=notes)
        state["seconds"] = round(time.time() - t0, 2)
        publish(changed)
        print(time.strftime("%H:%M:%S"), f"built in {state['seconds']} s, changed: {changed}", flush=True)
        return
    state["seconds"] = round(time.time() - t0, 2)
    publish([])
    print(time.strftime("%H:%M:%S"), "build failed", flush=True)


def notes_changed():
    """Reload the notes without a rebuild, unless their sections no longer match the slides."""
    notes = read_notes()
    if [n["key"] for n in notes] != [s["key"] for s in state["slides"]]:
        return build()
    changed = [i + 1 for i, (a, b) in enumerate(zip(state["notes"], notes)) if a["text"] != b["text"]]
    state["notes"] = notes
    publish(changed)
    print(time.strftime("%H:%M:%S"), f"notes changed: {changed}", flush=True)


def watch():
    scripts = notes = body = None
    while True:
        try:
            now_s = [os.path.getmtime(p) for p in SCRIPTS]
            now_n = os.path.getmtime(QMD)
            if now_s != scripts:
                scripts, notes = now_s, now_n
                body = qmdfile.Qmd(QMD).body_without_notes()
                build()
            elif now_n != notes:
                notes = now_n
                now_b = qmdfile.Qmd(QMD).body_without_notes()
                if now_b != body:  # the slides changed, not only the notes
                    body = now_b
                    build()
                else:
                    notes_changed()
        except Exception as e:  # keep watching after a failed build
            state.update(error=repr(e))
            publish([])
        time.sleep(0.2)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=OUT, **kw)

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if url.path == "/version":
            # The page reports the slide it shows, and the slides whose notes overflow.
            q = urllib.parse.parse_qs(url.query)
            if q.get("at", [""])[0].isdigit():
                with open(os.path.join(OUT, "current.txt"), "w") as f:
                    f.write(f"{q['at'][0]} {time.strftime('%H:%M:%S')}\n")
                with open(os.path.join(OUT, "overflow.txt"), "w") as f:
                    f.write(q.get("overflow", [""])[0] + "\n")
            return self.reply(200, {"version": state["version"]})
        if url.path == "/state.json":
            return self.reply(200, state)
        if url.path.startswith("/fonts/"):
            name = os.path.basename(url.path)
            path = os.path.join(FONTS, name)
            if not os.path.exists(path):
                return self.reply(404, {"error": "no such font"})
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "font/ttf")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return self.wfile.write(body)
        super().do_GET()

    def do_POST(self):
        """/notes saves the notes of one slide: {slide, text, base}; 409 if the file changed since base.
        /slide edits the slides: {op: insert | duplicate | remove, slide, key}.
        Slide n of the page is section n - 2 of the .qmd (1 is the title)."""
        if self.path not in ("/notes", "/slide"):
            return self.reply(404, {"error": "not found"})
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with lock:
            q = qmdfile.Qmd(QMD)
            n = int(req["slide"])
            j = n - 2
            if self.path == "/notes":
                if j < 0:
                    return self.reply(400, {"error": "the title slide comes from the YAML header and has no notes"})
                if j >= len(q.starts):
                    return self.reply(400, {"error": f"no slide {n} in the .qmd"})
                if q.notes(j) != req["base"]:
                    return self.reply(409, {"current": q.notes(j)})
                q.set_notes(j, req["text"])
                q.save()
                print(time.strftime("%H:%M:%S"), f"notes of slide {n} saved", flush=True)
                return self.reply(200, {"ok": True})
            op = req["op"]
            keys = ["title"] + q.keys()
            if not 0 < n <= len(keys) or keys[n - 1] != req["key"]:
                return self.reply(409, {"error": "the slides were changed elsewhere meanwhile; try again"})
            if op == "insert":
                key, goto = q.insert(j), n + 1
            elif j < 0:
                return self.reply(400, {"error": "the title slide comes from the YAML header"})
            elif op == "duplicate":
                key, goto = q.duplicate(j), n + 1
            elif op == "remove":
                key, goto = req["key"], min(n, len(keys) - 1)
                q.remove(j)
            else:
                return self.reply(400, {"error": f"unknown operation {op}"})
            q.save()
        print(time.strftime("%H:%M:%S"), f"slide {n}: {op} ({key})", flush=True)
        self.reply(200, {"ok": True, "goto": goto, "key": key})

    def reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        # pictures are named by their content, so they can be cached; everything else cannot
        if not self.path.startswith(("/img/", "/fonts/")):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for old in glob.glob(os.path.join(OUT, "slide-*.png")):  # pages rendered by earlier versions
        os.remove(old)
    with open(os.path.join(OUT, "index.html"), "w") as f:
        f.write(PAGE % NN)
    threading.Thread(target=watch, daemon=True).start()
    print(f"preview of deck {NN} at http://localhost:{PORT}", flush=True)
    http.server.ThreadingHTTPServer(("localhost", PORT), Handler).serve_forever()
