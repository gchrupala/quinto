--[[ The reveal.js version of a .qmd deck, with the layout of the .pptx.

Quarto lays out none of the slides itself. This filter runs quinto.build with DECK_HTML set, which
builds the deck as for the .pptx and writes each slide as absolutely positioned HTML (tohtml.py), as
for the live preview. It then replaces the content of each slide with that HTML, and its notes with
the notes as rendered by notesfile.py. What Quarto still does: the reveal.js page, moving between
slides and the speaker view.

The title slide is built by quinto.build as well, so the title is taken out of the metadata, where it
would make Quarto add a title slide of its own; it stays the title of the page.

Python: python3, or the interpreter in QUARTO_PYTHON; the Python package quinto must be installed in it.
]]

-- quinto.build writes a deck to _deck/NAME/ next to the .qmd (pictures in img/)
local function absolute(p)
  if pandoc.path.is_absolute(p) then
    return p
  end
  return pandoc.path.join({ pandoc.system.get_working_directory(), p })
end

local function quote(s)
  return "'" .. s:gsub("'", "'\\''") .. "'"
end

local function read_json(path)
  local f = assert(io.open(path, "r"), "cannot read " .. path)
  local data = pandoc.json.decode(f:read("a"), false)
  f:close()
  return data
end

function Pandoc(doc)
  local input = (quarto and quarto.doc and quarto.doc.input_file) or PANDOC_STATE.input_files[1]
  input = absolute(input)
  local dir = pandoc.path.directory(input)
  local rel = "_deck/" .. pandoc.path.split_extension(pandoc.path.filename(input))
  local out = pandoc.path.join({ dir, rel })
  local python = os.getenv("QUARTO_PYTHON") or "python3"
  local cmd = "DECK_HTML=" .. quote(out) .. " " .. quote(python) .. " -m quinto.build "
    .. quote(input) .. " >&2"
  pandoc.system.make_directory(out, true)
  if not os.execute(cmd) then
    error("quinto.build failed: " .. cmd)
  end
  local slides = read_json(pandoc.path.join({ out, "slides.json" })).slides
  local notes = read_json(pandoc.path.join({ out, "notes.json" }))

  local function placed(html)
    html = html:gsub('src="img/', 'src="' .. rel .. '/img/')
    return pandoc.RawBlock("html", '<div class="placed">' .. html .. "</div>")
  end

  local html = {}
  for _, s in ipairs(slides) do
    html[s.key] = s.html
  end

  -- the slides: an empty heading with the attributes of the original, the HTML of the slide, and
  -- the notes; the Markdown and the cells are left out, as they are part of the HTML
  local blocks = pandoc.Blocks({ pandoc.Header(2, {}, pandoc.Attr("title")), placed(html["title"]) })
  local key = nil
  for _, b in ipairs(doc.blocks) do
    if b.t == "Header" and b.level == 2 then
      key = b.identifier
      if not html[key] then
        error("quinto.build made no slide " .. key)
      end
      blocks:insert(pandoc.Header(2, {}, b.attr))
      blocks:insert(placed(html[key]))
    elseif key and b.t == "Div" and b.classes:includes("notes") then
      blocks:insert(pandoc.Div({ pandoc.RawBlock("html", notes[key] or "") }, b.attr))
    end
  end

  doc.meta.pagetitle = doc.meta.pagetitle or doc.meta.title
  doc.meta.title = nil
  doc.blocks = blocks
  return doc
end
