# F_25 Desktop coordinate units

## Metadata

| Item | Value |
|---|---|
| Date | 2026-10-22 |
| Scope | Desktop tool boundary, configuration, schemas and observations |
| Test baseline | Unit coverage for transforms, batches, freshness and output projection |
| Refs | #1043 |

## Background and contract

Vision endpoints can use screenshot pixels, fractions, or a 1000-unit grid.
`DesktopSettings.coordinate_system` selects `pixels` (the compatible default),
`normalized_1`, or `normalized_1000` once for a tool instance. This is an endpoint
configuration, not a task instruction or a model-name heuristic.

## Decisions

The tool advertises the selected units in its schema and observations. After
ownership and freshness validation it converts all pointer coordinates, including
drag paths and batch entries, using the associated image width and height. Values
must be finite and in the half-open image range; no clamping or snapping occurs.
The worker, native safety checks and evidence remain in screenshot pixels. Model
observations project control bounds and cursor into the selected units without
mutating native state. Image dimensions remain pixels and desktop geometry remains
explicitly labeled. Cropping and Retina mapping use the existing geometry layer.

## Rejected alternatives

Numeric-range guessing is ambiguous: small pixel coordinates are valid normalized
coordinates too. Model-name lookup can silently misclassify custom endpoints.
The mobile helper coerces malformed inputs and clamps edges; the strict desktop
boundary must preserve fractional coordinates and reject out-of-range points.
Neither host prompts nor framework internals require changes.

## Verification and limits

Tests cover varied image shapes and desktop offsets, edges, malformed values,
all pointer actions, batch rejection before any input, stale tokens, unchanged
pixel defaults and non-mutating observation projection. These establish the
conversion contract, not grounding accuracy for every model. Deployers select
units once; end users do not perform coordinate arithmetic. Models still need
vision, function calls and sufficient task-following capability.
