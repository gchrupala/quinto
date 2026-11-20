# Slide style

Guidelines for decks made with Quinto. The visual style is the default of `style.py`; the other guidelines are about what goes on a slide and in its notes. A project can add its own rules, such as the length of a deck, how often to ask the audience a question, or who the notes are for.

When asked to check, review or design a deck, apply all of the following, slide by slide.

## Layout

Slide bodies should be illustrative (figures, illustrations, formulas, short prompts, questions), not dense prose or bullet lists. The explanatory substance belongs in the speaker notes, not the body. Any figure, table or formula reproduced from an external source needs a citation in the notes (author/year, link where practical).

Keep bodies uncluttered: no side text boxes or takeaway lines. A legend is fine when it is simple, clear and unobtrusive; leave it out when it is redundant or adds clutter. Use titles sparingly: most slides need none; use one only where it adds meaning (for example, naming a method).

## Visual style

Spare, in the manner of a well-made LaTeX document rather than a PowerPoint template. White background, no filled boxes or cards.

- **Font:** Libertinus Serif for all text, IPA included (free from Google Fonts, so it works in PowerPoint and Google Slides; embed it when saving in PowerPoint). Noto Serif CJK SC for Chinese. IBM Plex Mono for code (Libertinus Mono has no bold). In `style.py`: `SERIF`, `CJK`, `MONO`.
- **Colour:** near-black text (`INK`, 1A1A1A) and grey (`GREY`, 707070) for secondary text such as labels and glosses. One accent, vermilion (`ACCENT`, C0392B), for emphasis and for questions to the audience. Use it only where it carries meaning (the contrast or element being discussed), not to decorate. Blue (`ACCENT2`, 2E5C8A) is a second colour for visualizations with two contrasting categories, and muted green (`GREEN`, 3A7D44) a third, only when three must be told apart.
- **Tables:** booktabs style, with rules above and below the table and a thin rule under the header; no vertical rules, no shading (`table()`).
- **Size:** everything legible from the back of the room. Body text at least 24 pt; labels, glosses and axis ticks at least 18 pt. Leave out details that do not fit at these sizes.
- **Drawings:** simple, with a subtle hand-drawn look (matplotlib sketch style, `sketch()`); plot axes stay straight. Draw figures at their final size, so that text in figures has the same point size as on the slide (`canvas()`).

## Examples and visuals

Use concrete, widely recognizable examples whose point is obvious, and replace textbook examples that are obscure or weak; do not follow a source slavishly. Keep one running example across related slides rather than a new one on each. To show what a model has learned, use new sentences, not famous ones it has likely seen in training.

Show concepts explicitly as objects (dots, boxes, tokens, code in a monospace font) rather than through counts, columns and labels, and avoid redundant devices that say the same thing twice. Icons and symbols must stand for something specific, never decorate. The element under discussion must stand out on a weak projector: accent colour together with bold type or thicker lines. An animation changes one thing per frame and marks what changed.

## Speaker notes

Speaker notes work as lecture notes. They can be narrative and contain details, but they should still be fairly concise, and they should fit in the notes box at a legible font size (the preview marks notes that overflow). Use simple, clear language, and explain technical terms when they are used.

Stick to the content being taught: no meta commentary about the talk (for example "The last part of today: agents" or "the next slide shows"), and no remarks on the state of the sources. Do not repeat what the slide body or a neighbouring slide already says, and define a term before it is first used. Give a reference only when citing a specific passage or using an example, figure or numbers from a source, never just because a section covers the topic; say when numbers are made up.

## Factual correctness

Verify technical claims, numbers, and reproduced figures and formulas against the actual cited source (paper, textbook) rather than from memory. Fetch the source (for example the arXiv PDF) when a claim is specific enough to get wrong.
