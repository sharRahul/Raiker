# Design

**Design** generates images from a prompt using a hosted image model you have
connected, and keeps what it made in this workspace.

It is deliberately a small page: a prompt, a model, a size, and a thread of what
you have asked for and what came back. What it does not do is hide the path
underneath it.

## The composer

Design uses the same composer as Chat and Build, so the shape is one you already
know:

```text
[ + ]  1024x1024                          OpenAI · GPT Image  [ Generate ]
```

`+` adds to this turn; the size stays on the bar because it is the one visual
parameter changed often enough to earn the room; the model that will draw is on
the right, next to the one action.

Design draws no **Tools** control, and that is deliberate rather than
unfinished. Raiker's governed image endpoint takes a prompt, a size and a model
and returns one picture — there is no edit, no variation and no reference-image
request for a menu to invoke. A control that named those anyway would be a
promise the runtime cannot keep. What is missing is recorded as **BUG-277** in
[`docs/plans/TO_BE_FIXED.md`](../plans/TO_BE_FIXED.md).

Design remembers the model you chose for it, separately from Chat's and Build's.
Putting Chat on a small local model does not move your image prompts onto it.

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

## What leaves the machine

The prompt. That is what generating an image with a hosted model means, and it
is why the capability is off until you turn it on. Raiker does not moderate the
prompt itself — the provider's policy applies, and a policy refusal is reported
as one rather than dressed up as a network failure.

The endpoint is built from the profile you configured, never from the request,
so nothing in a prompt can redirect a generation — or your credential — at a
host you did not name.

Full contract: [`docs/threat-models/image-generation.md`](../threat-models/image-generation.md).
