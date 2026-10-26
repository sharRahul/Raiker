# Design

For the Design product target, structured-canvas requirements and delivery
boundary, see [Design workspace](../plans/DESIGN_WORKSPACE_SPEC.md).
This guide describes what ships today.

**Design** has two halves, switched at the top of the page:

- **Images** generates pictures from a prompt using a hosted image model you
  have connected, keeps what it made in this workspace, and lets you work on one
  picture at a time.
- **Documents** is a design you keep editing: frames of text, shapes and
  placed pictures, with versions, a design system, an agent that proposes
  changes, checks, exports and a handoff to Build. See
  [Documents](#documents) below.

Everything up to [Documents](#documents) is about **Images**.

Until you select something it is a small page: a prompt, a model, a size, a
count, and everything you have asked for. Open a picture and it becomes a canvas
— the picture in the middle, everything else down the left, and what is known
about it on the right. What it does not do is hide the path underneath it.

## The composer

Design uses the same composer as Chat and Build, so the shape is one you already
know:

```text
[ + ] [ Tools ]  1024x1024  1 image        OpenAI · GPT Image  [ Generate ]
```

`+` adds to this turn and is where you choose the project it runs in; **Tools**
holds the reads; the size and the count stay on the bar because they are the
visual parameters changed often enough to earn the room; the model that will draw
is on the right, next to the one action.

**The button says what pressing it will do.** With nothing selected it is
**Generate**, or **Generate 4** when you have asked for four pictures. Select a
picture and it becomes **Edit**, because your next instruction is now about that
picture rather than about nothing. The count greys out while something is
selected: an edit makes one new version of one picture.

**Tools** holds Design's research reads — search the web, read a URL, extract a
page, check the weather — the same four Chat and Build offer, phrased for finding
visual references. Each says whether it is ready before you press it, and an
entry whose capability is off links to Permissions rather than failing at the
point of use.

A research result carries the pages it was drawn from, as the same chips Chat
uses. Press one and the passage the turn read opens under the findings, so a
reference can be checked without leaving Design. Two different things are being
said there and Raiker keeps them apart: every chip is a page the runtime really
read, and a chip marked as cited is the *model* saying a sentence rests on it —
a claim, not something Raiker can verify. The research turn reads pages; it
draws nothing, and image generation gains no network access from it.

**Research can travel with a prompt — only when you say so.** Under a research
result, **Use as a reference** turns it into a named reference above the
composer: the question you asked, the findings as plain text, and the pages they
came from. Making a reference sends nothing. Each one has its own box — **Send
with the prompt to *provider*** — and it starts unticked; only ticked references
go with the next request, as their own entry in the request's audited arguments
rather than pasted into your prompt, so the approval preview and the audit log
show exactly what went. Up to three at a time, each up to a thousand characters,
and the prompt and its references together stay within the prompt limit. The
picture's inspector then lists what it was **Sent with**, with the passage and
the pages.

What is *not* there is still not there: no mask, no outpaint, no upscale. Those
need provider capabilities behind the governed endpoint that this build does not
have, and a control that named them anyway would be a promise the runtime cannot
keep. Raiker reads what each provider's path really does — generate, edit,
several at once, a size — and draws only those controls: the count is greyed
out for a provider that cannot return several. Cropping and fitting a picture
are not provider operations at all; they are done, without changing the
picture, where it is placed in a design under **Documents**.

Design remembers the model you chose for it, separately from Chat's and Build's.
Putting Chat on a small local model does not move your image prompts onto it.

## The canvas

Press a picture — or generate one, which does the same thing — and Design
composes itself around it:

- **Assets**, down the left — everything this workspace has made, newest first,
  with how many that is. Selecting one moves the canvas to it.
- **Canvas**, in the middle and the largest of the three, because it is the
  thing you are working on.
- **Inspector**, on the right — the prompt, the model, the size, when it was
  made, and what it was made *from*.

The inspector also carries two strips that appear only when they have something
to show. **Versions** is the line this picture is on: the original, then each edit,
in the order they were made. It shows that line and no other — if you edited one
picture twice, those are two branches, and putting both in one strip would claim
the second came after the first when neither came from the other. **Variations**
is the set of pictures one request produced, side by side.

**Compare with**, under the version strip, puts an earlier version of this
picture beside the one you are looking at, each named by its place in the line.
**Go back to version N** then adds a *new* version carrying that earlier picture
on top of the line — nothing you made since is removed or changed, no provider
is asked to draw it again, and the inspector says which version it **Went back
to**. You can only go back along this picture's own line, never sideways to a
different picture.

**Refused attempts** sits with them. An edit the provider refused is still
something you asked of *this* picture, so it is recorded against it and shown
there, with the reason, rather than disappearing.

The inspector says where the picture is **Filed in** — a project's name, or
**Unfiled** — and offers **Open full size**, **Download** and **Delete**.
**Download** saves the picture under a name made from its prompt, with the
extension of the image the provider actually returned.

**Back to everything**, above the picture, returns you to the history.

A picture you have just generated goes straight onto the canvas, so the thing
you asked for stays in front of you rather than becoming the first row of a
history that grows all day. A refused request does not: there is nothing to put
on a canvas, and it is read in the history with its reason.

## Deleting and restoring

**Delete** is not permanent. If the picture is placed in a design under
**Documents**, Raiker names those designs and asks first; they keep the layer
and show it as missing until you restore the picture. The picture leaves the canvas and the history and
waits under **Recently deleted**, at the foot of the history, with its bytes and
its versions intact; **Restore** puts it back exactly where it was in its
lineage. A picture in Recently deleted cannot be the subject of an edit.

**Remove for good** is only offered there — always the second step, never the
first — and asks you to confirm. It deletes the record and the image together,
so nothing is left behind pointing at bytes that are gone. A version you went
back to shares its image with the version it came from, so removing one of them
for good keeps the image for the other.

## What it needs before it can generate anything

Three separate things, each with its own remedy, because collapsing them into
"couldn't generate" would send you hunting:

| Gate | What it is | Where you change it |
|---|---|---|
| Capability | `image_generation` — on by default; an explicit disable is respected | Permissions |
| Connection | A saved connection for the provider, made for its own API address (not a custom endpoint) | Models |
| Credential | The connection's key, or the provider's key variable if you connected with **Use the key from the environment** | Models |

**An API key is not authorisation to reach the network.** A key that is merely
set in your environment lets nothing leave the machine; connecting OpenAI on the
Models page is the decision that does, and it authorises OpenAI's own address
only. Image generation is still refused separately from chat: connecting a
provider to answer questions does not itself generate a picture. When you press
Generate, the request can send the prompt and selected image to that provider and
may use provider credit; no separate approval is requested for that direct action.

## Choosing a model

The composer's model control lists every image model your connected providers
declare — one entry per model, not per provider. Today that is OpenAI
(`gpt-image-1`) and Gemini (`gemini-2.5-flash-image`). Which provider you use for
chat makes no difference: a model appears here if and only if it can draw.

A model that cannot draw is never offered, and one Raiker's profiles do not
declare is refused rather than sent — a chosen model is a string this machine
posts to a provider, so it is bounded like the size is.

With nothing connected the control says so and links to Models, rather than
disappearing.

## What is stored, and where

The image goes into the same owner-scoped, checksummed store your uploaded
attachments use. The prompt, the model, the size and the outcome go beside it.
Both reads are scoped to you: the gallery returns metadata only, and asking for
an image is a separate request naming one generation.

**A refusal is a record, not an absence.** Every attempt is written down,
including the ones that were refused and why, so an attempt that produced
nothing is answerable from this page rather than from the audit log.

Each picture also records what it was made from and which kind of request made
it — generated from a prompt, edited from a named picture, or one of a set. That
is what the version strip and the variation grid are built from; neither guesses
from the order things were made in.

**A picture belongs to the project you made it in.** Design's context line
always says where the next picture will be filed before you press Generate: the
project's name, or **Unfiled** when none is chosen (choose one under `+`). The
destination is captured with the request, so changing the project afterwards
does not move a picture already made. Pictures filed in a project appear on that
project's page beside its files and sessions; unfiled ones stand alone, and stay
that way.

## What leaves the machine

The prompt — and, when you are editing, the picture you selected. That is what
generating or editing an image with a hosted model means, and it is why the
capability is off until you turn it on.

A picture you select is resolved against **your** store, after the policy check
and the credential check. A generation id that is not yours is answered exactly
as one that was never issued. Raiker does not moderate the
prompt itself — the provider's policy applies, and a policy refusal is reported
as one rather than dressed up as a network failure.

The endpoint is built from the profile you configured, never from the request,
so nothing in a prompt can redirect a generation — or your credential — at a
host you did not name.

Full contract: [`docs/threat-models/image-generation.md`](../threat-models/image-generation.md).

## Documents

**Documents** is where a design stays editable. A design is a document of
**frames** (pages or screens), each holding **layers** — text, rectangles,
ellipses, placed pictures, groups and stacks. Text stays text and a placed
picture stays linked to the picture under **Images**, so nothing is ever
flattened into a screenshot.

Start with **New design**: name it and choose what it starts as — a square or
story social post, an A4 page, a 16:9 slide, a mobile or desktop screen, or a
custom size. Designs are listed newest first; **Delete** puts one in
**Recently deleted**, where **Restore** brings it back.

### Editing

The page has three regions: frames and layers on the left, the canvas in the
middle, and the panels on the right.

- **Add a layer** with *Text*, *Rectangle*, *Ellipse*, *Stack* or *Image* — a
  picture you made under Images, or **Import your own picture…** (PNG, JPEG,
  WebP or GIF). An imported picture is checked like any upload, kept on this
  machine and listed under Images as **Imported**; it goes to an image provider
  only if you later ask to edit it there. A **stack** lines up what is inside it in a
  row or column, with a gap and padding, and keeps it lined up as you change it.
- **Select** a layer by clicking it on the canvas or in **Layers**; Shift
  (or Ctrl/Cmd) adds or removes one. Layers lists the front-most first; the eye
  hides a layer and the lock protects it. A locked layer can be shown, hidden,
  renamed or unlocked, and nothing else. Clicking inside a group on the canvas
  selects the group; pick one of its layers in Layers.
- **Drag** a layer to move it. It snaps to the frame's edges and centre and to
  other layers' edges and centres, drawing a dashed guide for each (and to the
  grid when it is shown); hold **Alt** to place it freely. The square **handles**
  resize — Shift on a corner keeps the proportions — and the round handle above
  rotates, in 15° steps with Shift. Each drag is one version.
- With several layers selected, the panel offers **Align** (left, centre, right,
  top, middle, bottom), **Distribute across / down** for three or more,
  **Group** and **Remove**, and the arrow keys move them all. One selected layer
  can be centred in the frame.
- **Inspect** edits the selected layer: position, size, rotation, opacity, text,
  font, size, weight, alignment, colour, fill, corner radius, stack spacing, and
  for a picture its alternative text, fit and **crop**. Crop and fit never change
  the picture itself.
- **On the canvas**, the arrow keys move the selection 1px (Shift: 10px),
  Delete removes it, Escape clears it, and Ctrl+Z / Ctrl+Shift+Z undo and redo.
- **Make variant** copies the frame at another size — a mobile version of a
  social post, say — scaled once and marked *variant of* its source. It does not
  follow the source afterwards; change each as you need.

### Components and notes

**Make component** (under the selected layer's **Component**) keeps a copy of
that layer — a card, a button, a logo lock-up — in this design. **Components →
Place** puts it on the frame again: its layers are ordinary layers you can
edit, linked to the component. Editing a placed copy never changes the
component; the panel says whether the copy still matches, and **Update from
component** replaces its layers with the component's, as one version. Removing
a component keeps every placed copy's layers, and Check reports the broken
link. Components belong to their design.

**Notes** sit on the selected layer, or on the frame when nothing is selected:
a reminder, a question for later. Each is a version like any change, can be
resolved and reopened, and shows as a numbered pin on the canvas (**Show
pins**) and a *note* badge in Layers. Notes are never drawn into an export;
open ones go to Build with a handoff.

### Versions

Every change is a numbered **version** — **v12** beside the name — recording who
made it (you, or the agent), what it touched and when. **Undo** and **Redo**
step through them, and **History** lists them all with **Go back to this**.
Going back adds a new version on top; nothing is ever removed from the history.

If the design changed since you loaded it (in another tab, say), a change that
touches the same layers is refused with *This design changed since you loaded
it*, and the page reloads; one that touches other layers is simply applied on
top.

### Design systems

**System** holds your brand as named variables: colours (`primary=#1144aa`),
fonts (`body=sans-serif`), spacing, usage rules, the variables a finished design
must use, and a note on where they came from. Saving a system again makes a new
version; designs using the earlier one are not changed.

Instead of typing the values, **Import from a tokens file** reads CSS variables
(`--brand-primary: #1144aa;`) or a JSON tokens file on this machine and fills
the form with the colours, fonts and px/rem sizes it found, listing anything it
skipped and why; **Or colours from a picture** reads the main colours of a logo
or screenshot you have. The source note names the file and its hash. Nothing is
saved until **Save system**.

A layer can use a variable — **Fill variable**, **Colour variable** — and keeps
the colour it is drawn in. **Choose** a system and press **Preview the change**:
Raiker lists every layer whose colour or font would change, from what to what,
and every variable the system does not define. Nothing changes until **Apply to
this design**, which changes only this design, as one version you can undo.

### The design agent

**Agent** asks a chat model you have connected to change the frame you are
looking at. Write what you want, choose the model, and press **Propose
changes**. What goes to the model's provider is that frame's layers and your
brief — text that looks like a credential is removed first — and the model gets
no tools.

What comes back is a **proposal**: a short plan (what goes where, what it
assumed, which pictures you would need, what to check) and a list of changes,
each with a box. Nothing is applied yet. Changes the agent may not make are
listed as **refused** with the reason: touching another frame, adding or
removing frames, placing pictures, removing a locked layer or a group of more
than three layers. **Accept selected** applies the ticked changes as one version
marked as the agent's, and new layers show an *agent* badge; **Reject** applies
nothing.

If you changed a layer after the agent read the design, a change to that layer
is never applied over yours: Raiker names the layers and offers **Apply the
rest, keep my changes**.

A proposal is recorded before the model is asked. If Raiker stopped while it
waited, the proposal reads **Outcome unknown** — whether the provider answered
is not known, nothing was applied, and it is never retried on its own; one whose
call failed reads **Failed** with the reason. **Ask again with this brief** puts
the brief back for a new request.

### Check

**Check** runs ten checks and says, for each, **Passed**, **Failed**, **Not
supported by the export** or **Cannot be known from the design**:

| Check | What it looks at |
|---|---|
| Pictures | Every placed picture is one you have, not in Recently deleted |
| Alternative text | Every visible picture describes itself |
| Text fits | Text fits its box, measured with the font exports are drawn in |
| Contrast | Text meets WCAG AA against a solid colour behind it; over a picture it cannot be known |
| Fonts | The font, and every character in the text, can be drawn in PNG and PDF |
| Inside the frame | No visible layer lies wholly outside its frame |
| Variables | Every variable a layer uses exists in the chosen system |
| Required variables | Every variable the system requires is used |
| Brand colours | Colours come from the chosen system |
| Components | Every placed copy of a component links to one still in the design |

Each finding names its layer (and frame, when there are several) and opens it.
Check never judges how good the design looks.

### Export

**Export** writes the frame as **PNG**, **PDF (vector, selectable text)** —
shapes as paths, text as real text, an A4 frame as an A4 page — **PDF (one
raster page)**, **SVG** (text stays text, so it remains editable in a vector
tool) or **JSON** (the frame's structure). The vector PDF writes text in the
Western European character set; any other character becomes `?`, and the export
records how many. Each export is listed with its version, the result of Check
at that moment, and the file's SHA-256, and downloads from there. PNG and PDF are
drawn in one sans font — the export records which (the vector PDF embeds it) — and a font you named is
drawn in it; SVG names your font and a viewer without it substitutes its own.
Exporting never changes the design.

### Hand to Build

**Hand to Build** gives Build this frame at this version — its layers, text,
colours, picture ids and your design system — as a document attached to Build's
composer the next time you open Build, with what you said it should become.
It is context, not permission: Build's modes and approvals decide every change
it proposes from it.

