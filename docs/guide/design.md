# Design

**Design** generates images from a prompt using a hosted image model you have
connected, keeps what it made in this workspace, and lets you work on one
picture at a time.

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

What is *not* there is still not there: no crop, no mask, no outpaint. Those need
provider capabilities behind the governed endpoint that this build does not have,
and a control that named them anyway would be a promise the runtime cannot keep.

Design remembers the model you chose for it, separately from Chat's and Build's.
Putting Chat on a small local model does not move your image prompts onto it.

## The canvas

Press a picture and Design composes itself around it:

- **Assets**, down the left — everything this workspace has made, newest first.
  Selecting one moves the canvas to it.
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

**Refused attempts** sits with them. An edit the provider refused is still
something you asked of *this* picture, so it is recorded against it and shown
there, with the reason, rather than disappearing.

**Back to everything**, above the picture, returns you to the history.

## What it needs before it can generate anything

Three separate things, each with its own remedy, because collapsing them into
"couldn't generate" would send you hunting:

| Gate | What it is | Where you change it |
|---|---|---|
| Capability | `image_generation` — off until you turn it on | Permissions |
| Egress | `RAIKER_MODEL_EGRESS_ALLOWLIST` must name the provider's host | Your environment |
| Credential | A saved connection for the provider, or its API key variable | Models, or your environment |

**An API key is not authorisation to reach the network.** Connecting OpenAI on
the Models page lets Raiker *use* your credential; allowlisting
`api.openai.com` is what lets anything leave the machine. The two are separate
decisions on purpose, and image generation is refused separately from chat for
the same reason: connecting a provider to answer questions is not asking Raiker
to spend your credit generating pictures.

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

**A picture belongs to the project you made it in.** When Design's context line
names a project, the pictures you generate are filed against it and appear on
that project's page beside its files and sessions. Pictures made with no project
chosen stand alone, and stay that way.

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
