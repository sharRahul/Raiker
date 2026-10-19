"""Raiker Design's composition layer (DW-01 to DW-12).

The Asset layer — governed image generation and lineage — lives in
``raiker.runtime.executors.tier2_image`` and ``raiker.api.routes_images``. This
package is the structured document beside it: frames, an ordered layer tree,
typed operations against stable node ids, versions, design systems,
validation, export and the Build handoff. None of it reaches a provider on its
own; the one model call (an agent proposal) goes through the owner's router.
"""
