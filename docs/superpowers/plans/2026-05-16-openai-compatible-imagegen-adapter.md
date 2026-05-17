# OpenAI-Compatible Image Generation Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert Agent Sprite Forge from a Codex-only `image_gen` workflow into an agent-compatible workflow backed by OpenAI-compatible image generation endpoints such as new-api.

**Architecture:** Add a local image-generation CLI adapter that accepts a JSON request, resolves the correct Firefly image model, calls an OpenAI-compatible `/v1/images/generations` endpoint, saves raw images locally, and writes a manifest consumed by the existing sprite/map post-processing scripts. Keep the current deterministic Python processors as the downstream asset pipeline; only replace the raw-image generation boundary.

**Tech Stack:** Python 3 standard library HTTP/JSON utilities, existing `Pillow` and `numpy` processors, JSON config/request/manifest files, Markdown skill documentation.

---

## 1. Scope

### In scope

- Add an OpenAI-compatible image generation adapter usable by Codex, OpenCode, Claude Code, Gemini CLI, or a plain terminal agent.
- Support new-api-style model IDs where model family, resolution, and aspect ratio are encoded in the `model` string.
- Add automatic model selection for the provided Firefly image model catalog.
- Preserve existing local post-processing scripts:
  - `skills/generate2dsprite/scripts/generate2dsprite.py`
  - `skills/generate2dmap/scripts/extract_prop_pack.py`
  - `skills/generate2dmap/scripts/compose_layered_preview.py`
- Update skill documents so agents generate raw images through the new CLI instead of Codex built-in `image_gen`.
- Add example requests and smoke-test instructions for OpenAI-compatible providers.

### Out of scope for the first implementation pass

- Video model support. Existing GIF output is produced by cutting sprite sheets into frames and encoding GIFs locally; Sora/Veo/Kling model IDs should not participate in sprite GIF generation.
- A multi-provider plugin matrix for ComfyUI, SD WebUI, Replicate, Stability, or vendor-specific APIs.
- A long-running server or UI. The adapter should be CLI-first.
- Mandatory image-reference/edit support. Reference and edit behavior varies across OpenAI-compatible gateways and should be a capability-gated future phase.
- Rewriting the pixel post-processing algorithms.

---

## 2. Current constraints from this repository

### Sprite and animation constraints

`generate2dsprite` is grid-first. The generator must produce a still PNG sprite sheet; the local processor removes magenta, splits frames, aligns/crops them, and writes transparent PNG frames plus GIFs.

Key constraints:

- Body animations should use multi-row grids, not raw `1xN` strips.
- Standard 4-frame body actions use `2x2`.
- 6-frame actions such as cast/summon/death use `2x3`.
- Longer actions can use `2x4`, `3x3`, `3x4`, or `4x4`.
- Top-down four-direction player walk uses `4x4`.
- Projectiles and simple FX may use `1x4` or `2x2`, but body assets should not default to `1x4`.
- Raw sprite sheets and prop packs usually need a square canvas, so the model ratio should normally be `1x1`.

### Map constraints

`generate2dmap` needs map-mode-specific canvas selection.

Key constraints:

- `side_scroll_mode` defaults to a 16:9 stage canvas such as `1536x864`.
- Primary side-scroll parallax layers, stage references, and previews must share the same aspect and framing.
- Layered RPG/tower-defense scenes can use `16x9`, `4x3`, `3x4`, or `9x16` depending on camera and gameplay layout.
- Base maps must be foundation-only; runtime props and collidable objects remain separate.

### Prop constraints

- Compact prop packs use square `2x2`, `3x3`, or `4x4`, so they should use `1x1` models.
- Wide platform strips, bridges, floor pieces, and long hazards should avoid square packs and may use wide ratios such as `4x1` or `8x1` when the selected model family supports them.

---

## 3. Target user experience

### Provider configuration

Users configure a single OpenAI-compatible endpoint.

Recommended configuration file path:

- `configs/imagegen.openai-compatible.example.json`

Configuration responsibilities:

- `base_url`: OpenAI-compatible root, for example `https://new-api.example.com/v1`.
- `api_key_env`: environment variable that stores the API key, for example `NEW_API_KEY`.
- `default_model` or model-selection defaults.
- `size_mode`: default `model_id`, meaning model IDs determine resolution/aspect and the adapter does not send a separate `size` parameter unless configured.
- `model_catalog`: supported Firefly image model families, resolutions, and ratios.
- `routing`: asset-type-to-model-selection rules.

### Agent workflow

The skill-guided agent should:

1. Infer the asset plan from the user request.
2. Write an `imagegen-request.json` file into the current run directory.
3. Run the image-generation CLI with the request, output directory, and config.
4. Read `imagegen-manifest.json` to find the generated raw PNG path.
5. Pass that raw PNG to the existing sprite or map post-processor.
6. Use post-processing metadata to decide whether to accept, reprocess, or regenerate.

---

## 4. Model selection design

### Do not fix a single model

A single fixed model cannot satisfy both square sprite sheets and widescreen maps. Fixing `firefly-gpt-image-1k-1x1` would work for many sprites and prop packs but fails for side-scroll/parallax maps. Fixing a `16x9` model would harm sprite-sheet grid stability.

Use this policy instead:

1. Automatic model selection is the default.
2. Manual model override is allowed per request.
3. Routing rules map asset intent to family/resolution/ratio.
4. The resolver validates the final model ID against the configured catalog.

### Image model catalog families

Only image model families participate in this adapter:

- `firefly-gpt-image`
- `firefly-nano-banana2`
- `firefly-nano-banana-pro`
- `firefly-nano-banana`

Video families are excluded from this selector:

- `firefly-sora2*`
- `firefly-veo31*`
- `firefly-kling*`

### Supported image-family capabilities

The model resolver should encode family-specific supported ratios:

- `firefly-gpt-image`
  - Resolutions: `1k`, `2k`, `4k`
  - Ratios: `1x1`, `5x4`, `9x16`, `21x9`, `16x9`, `3x2`, `4x3`, `4x5`, `3x4`, `2x3`
- `firefly-nano-banana2`
  - Resolutions: `1k`, `2k`, `4k`
  - Ratios: `1x1`, `16x9`, `9x16`, `4x3`, `3x4`, `1x8`, `1x4`, `4x1`, `8x1`
- `firefly-nano-banana-pro`
  - Resolutions: `1k`, `2k`, `4k`
  - Ratios: `1x1`, `16x9`, `9x16`, `4x3`, `3x4`
- `firefly-nano-banana`
  - Resolutions: `1k`, `2k`, `4k`
  - Ratios: `1x1`, `16x9`, `9x16`, `4x3`, `3x4`

### Model ID construction

The resolver should construct IDs using:

```text
{family}-{resolution}-{ratio}
```

Examples:

- `firefly-gpt-image-1k-1x1`
- `firefly-gpt-image-2k-16x9`
- `firefly-nano-banana2-2k-4x1`

The resolver must validate the constructed ID before using it. If a requested ratio is unsupported by the chosen family, it should use routing fallback rules rather than silently sending an invalid model.

### Default model policy

Recommended defaults:

- Default family: `firefly-gpt-image`
- Default resolution: `1k`
- Default ratio: `1x1`
- Default size mode: `model_id`

Quality profiles:

- `draft`: `firefly-nano-banana2`, `1k`
- `standard`: `firefly-gpt-image`, `1k`
- `high`: `firefly-gpt-image`, `2k`
- `final`: `firefly-gpt-image`, `4k`

### Routing rules

Recommended model routing:

| Asset intent | Family | Resolution | Ratio | Reason |
| --- | --- | --- | --- | --- |
| Standard sprite sheet | `firefly-gpt-image` | `1k` | `1x1` | Square grid stability |
| Main hero / high-value character sheet | `firefly-gpt-image` | `2k` | `1x1` | More detail per frame |
| Large boss `3x3` / complex `4x4` sheet | `firefly-gpt-image` | `2k` | `1x1` | More pixels per cell |
| NPC / simple mob draft | `firefly-nano-banana2` | `1k` | `1x1` | Lower-cost iteration |
| Projectile / simple FX | `firefly-gpt-image` or `firefly-nano-banana2` | `1k` | `1x1` | Stable default, local GIF output |
| Compact prop pack `2x2` / `3x3` / `4x4` | `firefly-gpt-image` | `2k` | `1x1` | Multiple objects need detail |
| Platform strip / long bridge / long hazard | `firefly-nano-banana2` | `1k` or `2k` | `4x1` or `8x1` | Wide object canvas |
| Standard RPG / tower-defense map | `firefly-gpt-image` | `2k` | `16x9` or `4x3` | Camera-dependent map framing |
| Side-scroll parallax layer | `firefly-gpt-image` | `2k` | `16x9` | Matches default stage canvas |
| Final parallax showcase layer | `firefly-gpt-image` | `4k` | `16x9` | High-detail final art |
| Mobile portrait map/background | `firefly-gpt-image` | `2k` | `9x16` | Portrait gameplay layout |
| Tall RPG route/map section | `firefly-gpt-image` | `2k` | `3x4` | Tall but not full mobile portrait |

### Manual override

`imagegen-request.json` should allow an explicit `model` field. If present, it wins over automatic routing. The manifest must record that the model was selected by explicit override.

### Size parameter policy

Default behavior should be:

```text
size_mode = model_id
```

In this mode, the adapter sends `model`, `prompt`, and `n`, but does not send `size`. This avoids conflicts because the selected model ID already encodes `1k/2k/4k` and aspect ratio.

Optional modes:

- `explicit`: send the exact request/config `size` string.
- `derived`: derive a `WIDTHxHEIGHT` size from the selected model ID using a configured map.
- `auto`: send `size` only when the request explicitly provides it.

The manifest must record whether `size` was sent and why.

---

## 5. Request and manifest design

### Image generation request fields

`imagegen-request.json` should support:

- `version`
- `task_type`
- `asset_role`
- `map_mode`
- `quality`
- `prompt`
- `negative_prompt`
- `n`
- `output_name`
- `model`
- `model_policy`
- `size`
- `size_mode`
- `constraints`
- `references`
- `extra_body`

The first implementation should require `prompt` and support `negative_prompt` by appending an explicit avoidance clause to the prompt. Provider-specific negative-prompt fields should be handled through `extra_body` when the configured gateway supports them.

### Manifest fields

`imagegen-manifest.json` should always be written on success or failure.

Required manifest content:

- Adapter version
- Provider name: `openai_compatible`
- Base URL with credentials removed
- Endpoint path
- Status: `succeeded` or `failed`
- Request path
- Duration in milliseconds
- Selected model
- Model-selection reason
- Size mode and sent size
- Prompt used
- Negative prompt used
- Output image list with local paths, roles, dimensions, and SHA-256 hashes
- Warnings
- Redacted response summary
- Error type/message for failed calls

The manifest becomes the stable handoff from the generation adapter to existing postprocessors.

---

## 6. File structure plan

### Create

- `pyproject.toml`
  - Package metadata and console script entry point.
- `agent_sprite_forge/__init__.py`
  - Package marker and version export.
- `agent_sprite_forge/imagegen/__init__.py`
  - Imagegen package marker.
- `agent_sprite_forge/imagegen/__main__.py`
  - Enables `python -m agent_sprite_forge.imagegen`.
- `agent_sprite_forge/imagegen/cli.py`
  - Parses CLI arguments and coordinates config, request loading, model resolution, generation, and manifest writing.
- `agent_sprite_forge/imagegen/config.py`
  - Loads JSON config and environment overrides.
- `agent_sprite_forge/imagegen/schema.py`
  - Validates request and manifest structures.
- `agent_sprite_forge/imagegen/model_catalog.py`
  - Defines Firefly image families, supported ratios, and model ID validation.
- `agent_sprite_forge/imagegen/model_resolver.py`
  - Applies routing rules and manual overrides to choose a model.
- `agent_sprite_forge/imagegen/openai_compatible.py`
  - Calls `/images/generations` using raw HTTP.
- `agent_sprite_forge/imagegen/io_utils.py`
  - Saves base64 or URL image responses, computes hashes, and writes JSON.
- `agent_sprite_forge/imagegen/errors.py`
  - Defines adapter-specific exceptions and user-facing error messages.
- `configs/imagegen.openai-compatible.example.json`
  - Example config for OpenAI-compatible endpoints.
- `examples/imagegen/sprite-2x2-idle.request.json`
  - Smoke-test sprite request.
- `examples/imagegen/hero-4x4-player-sheet.request.json`
  - Smoke-test hero player sheet request.
- `examples/imagegen/map-side-scroll-16x9.request.json`
  - Smoke-test side-scroll map request.
- `examples/imagegen/prop-pack-3x3.request.json`
  - Smoke-test prop pack request.
- `tests/imagegen/`
  - Unit tests for config, schema, model resolver, IO helpers, and OpenAI-compatible response handling.

### Modify

- `requirements.txt`
  - Keep runtime dependencies minimal. Add no dependency for HTTP in the first pass; use Python standard library.
- `skills/generate2dsprite/SKILL.md`
  - Replace Codex built-in image generation instructions with imagegen CLI instructions.
- `skills/generate2dsprite/agents/openai.yaml`
  - Remove hard dependency on built-in `image_gen` wording.
- `skills/generate2dsprite/references/prompt-rules.md`
  - Replace platform-specific visual-reference language with adapter request/manifest language.
- `skills/generate2dmap/SKILL.md`
  - Replace built-in `image_gen` and `view_image` assumptions.
- `skills/generate2dmap/agents/openai.yaml`
  - Replace Codex-specific raw-image-generation language.
- `skills/generate2dmap/references/map-strategies.md`
  - Explain model ratio selection for map modes.
- `skills/generate2dmap/references/prop-pack-contract.md`
  - Explain `1x1` prop-pack models and wide-strip exceptions.
- `skills/generate2dmap/references/layered-map-contract.md`
  - Replace visual-reference handoff wording with adapter-compatible behavior.
- `README.md`
  - Reposition the project as agent-compatible with OpenAI-compatible image generation endpoints.
- `README.zh-CN.md`
  - Update Chinese setup and usage docs.
- `README.zh-TW.md`, `README.ja.md`, `README.ko.md`
  - Sync core wording after the English and Simplified Chinese docs settle.

---

## 7. Phased implementation plan

### Phase 1: Package and CLI scaffold

**Outcome:** The project installs a CLI entry point and can load config/request files without calling a provider.

- [ ] Create the Python package structure under `agent_sprite_forge/`.
- [ ] Add `pyproject.toml` with an `agent-sprite-forge-imagegen` console script.
- [ ] Add JSON config loading with environment override support.
- [ ] Add request loading and basic schema validation.
- [ ] Add a dry-run mode that writes a manifest containing resolved request/config data without making an HTTP call.
- [ ] Add unit tests for config loading, environment overrides, request validation, and dry-run manifest writing.
- [ ] Verify with `python -m unittest discover tests`.

### Phase 2: Model catalog and resolver

**Outcome:** The adapter can choose a valid Firefly image model automatically.

- [ ] Add the Firefly image model catalog with family/resolution/ratio validation.
- [ ] Implement model ID construction using `{family}-{resolution}-{ratio}`.
- [ ] Add routing rules for sprite sheets, hero sheets, prop packs, wide strips, map bases, side-scroll layers, and mobile portrait scenes.
- [ ] Add quality profiles: `draft`, `standard`, `high`, `final`.
- [ ] Add manual model override behavior.
- [ ] Add size-mode resolution behavior: `model_id`, `explicit`, `derived`, and `auto`.
- [ ] Add unit tests covering valid models, unsupported ratios, manual overrides, routing fallbacks, and size-mode outputs.
- [ ] Verify with `python -m unittest discover tests`.

### Phase 3: OpenAI-compatible generation client

**Outcome:** The adapter can call an OpenAI-compatible `/images/generations` endpoint and save images locally.

- [ ] Implement raw HTTP request construction for `/images/generations`.
- [ ] Support `model`, `prompt`, `n`, optional `size`, and `extra_body`.
- [ ] Merge `negative_prompt` into the prompt as an avoidance clause for maximum compatibility.
- [ ] Support both `b64_json` and `url` image response formats.
- [ ] Save images using request `output_name` for single-image calls and deterministic suffixes for multi-image calls.
- [ ] Write success and failure manifests.
- [ ] Add tests using mocked HTTP responses for base64 success, URL success, HTTP failure, malformed response, missing API key, and timeout behavior.
- [ ] Verify with `python -m unittest discover tests`.

### Phase 4: Examples and smoke-test workflow

**Outcome:** Users can validate a new-api endpoint without running the full sprite/map skills.

- [ ] Add example config for OpenAI-compatible endpoints.
- [ ] Add example request files for a `2x2` idle sprite, `4x4` hero sheet, `3x3` prop pack, and `16x9` side-scroll map.
- [ ] Add README instructions for a live smoke test using `NEW_API_KEY`, `base_url`, and `model`.
- [ ] Add documentation that live smoke tests consume provider credits and are not part of normal unit tests.
- [ ] Verify dry-run examples with the CLI.
- [ ] Verify one live smoke test manually when an API key is available.

### Phase 5: Update `generate2dsprite` skill

**Outcome:** The sprite skill no longer depends on Codex built-in `image_gen`.

- [ ] Update `skills/generate2dsprite/SKILL.md` workflow to write `imagegen-request.json` and run the imagegen CLI.
- [ ] Replace `$CODEX_HOME/generated_images` instructions with manifest-based raw image discovery.
- [ ] Add model-selection guidance: sprite sheets and prop packs default to `1x1`; high-value or dense sheets use higher resolution.
- [ ] Keep existing prompt rules for magenta background, exact grid, centered subjects, stable scale, and no text.
- [ ] Update `skills/generate2dsprite/agents/openai.yaml` to remove built-in `image_gen` assumptions.
- [ ] Verify that the skill still instructs agents to run `generate2dsprite.py process` after raw image generation.

### Phase 6: Update `generate2dmap` skill

**Outcome:** The map skill uses the imagegen CLI and model resolver for base maps, dressed references, prop packs, tilesets, and parallax layers.

- [ ] Update `skills/generate2dmap/SKILL.md` to use the configured imagegen CLI.
- [ ] Replace `view_image`-specific reference handoff language with request/manifest reference capability language.
- [ ] Add model ratio guidance: side-scroll uses `16x9`, compact prop packs use `1x1`, portrait/mobile scenes use `9x16`, tall maps may use `3x4`.
- [ ] Update map references so `stage_canvas` and selected model ratio remain consistent.
- [ ] Update prop-pack contract so compact packs route to `1x1` and platform strips can route to `4x1`/`8x1` through `firefly-nano-banana2`.
- [ ] Verify that map workflows still continue into extraction, placement metadata, collision/zones, and preview composition.

### Phase 7: README and multilingual docs

**Outcome:** Users understand the project is agent-compatible and configured through an OpenAI-compatible image endpoint.

- [ ] Update `README.md` project positioning from Codex-only to agent-compatible.
- [ ] Add install instructions for the Python package and skill directory copying.
- [ ] Add new-api configuration examples.
- [ ] Add model-selection explanation and the default routing table.
- [ ] Explain that video models are not used for sprite GIF generation.
- [ ] Update `README.zh-CN.md` with equivalent guidance.
- [ ] Sync concise core updates to `README.zh-TW.md`, `README.ja.md`, and `README.ko.md`.

### Phase 8: Optional reference/edit capability

**Outcome:** Gateways that support image edits or reference images can opt in without breaking text-to-image providers.

- [ ] Extend request schema with `references[]` roles such as `layout_only`, `identity_style`, `base_map`, and `style_reference`.
- [ ] Add config capability flags for image reference/edit support.
- [ ] Add a separate code path for compatible `/images/edits` endpoints.
- [ ] Make unsupported required reference capabilities fail clearly before an API call.
- [ ] Make unsupported preferred reference capabilities write warnings and continue with text-only constraints.
- [ ] Add tests for required capability failure and preferred capability downgrade warnings.

---

## 8. Verification strategy

### Automated verification

- Unit tests should avoid live API calls.
- Mock HTTP responses should cover base64 images, URL images, failed requests, malformed responses, and missing credentials.
- Model resolver tests should prove sprite/map/prop routing chooses valid catalog models.
- Schema tests should prove invalid requests fail before provider calls.

### Manual smoke verification

Manual smoke verification requires a real OpenAI-compatible endpoint and API key.

Minimum live checks:

1. Generate a `2x2` sprite sheet request and confirm a local raw PNG plus manifest are written.
2. Process that raw PNG through `generate2dsprite.py process` and confirm `animation.gif`, frame PNGs, and `pipeline-meta.json` are produced.
3. Generate a `16x9` side-scroll map request and confirm the manifest records a `16x9` model selection.
4. Generate a `3x3` prop pack request and confirm the manifest records a `1x1` model selection.

---

## 9. Migration guidance for skills

### Before

Skills tell agents to:

- Use Codex built-in `image_gen`.
- Use `view_image` for reference handoff.
- Find raw files under `$CODEX_HOME/generated_images`.

### After

Skills should tell agents to:

- Write `imagegen-request.json`.
- Run `agent-sprite-forge-imagegen generate`.
- Read raw image paths from `imagegen-manifest.json`.
- Run existing local post-processing scripts.
- Make acceptance decisions using post-processing metadata and visual/QC checks.

---

## 10. Risk management

### Model does not follow grid constraints

Mitigation:

- Keep strict prompt rules for exact grids, magenta background, and no labels.
- Use higher resolution for dense `3x3`/`4x4` sheets.
- Use layout guides where the skill already recommends them.
- Regenerate when post-processing reports edge-touch or unstable scale.

### Model ID and size conflict

Mitigation:

- Default to `size_mode=model_id`.
- Do not send `size` unless explicitly configured.
- Record size behavior in the manifest.

### Aggregator response shape varies

Mitigation:

- Support both `b64_json` and `url` responses.
- Write failure manifests for unrecognized response shapes.
- Keep provider payload minimal: `model`, `prompt`, `n`, optional `size`, plus configured `extra_body`.

### Reference image support is inconsistent

Mitigation:

- Keep reference/edit support out of the initial critical path.
- Add capability flags before adding `/images/edits` behavior.
- Downgrade preferred references to text constraints when possible and record the warning.

### Video models create confusion

Mitigation:

- Exclude video model families from the image model resolver.
- Document that GIFs are generated from sprite sheets by local scripts.
- Treat video generation as a separate future skill, not as part of this adapter.

---

## 11. Completion criteria

The migration is complete when:

- The imagegen CLI can perform dry-run model resolution.
- The imagegen CLI can call an OpenAI-compatible endpoint and save raw image files.
- Success and failure manifests are written consistently.
- Model resolver chooses correct Firefly image models for sprite, prop, map, side-scroll, portrait, and wide-strip requests.
- `generate2dsprite` and `generate2dmap` skill docs no longer require Codex built-in `image_gen`.
- README documents new-api/OpenAI-compatible setup.
- Unit tests pass without external API calls.
- At least one live smoke test demonstrates raw image generation and downstream post-processing.

---

## 12. Self-review notes

- Scope covers OpenAI-compatible/new-api integration, Firefly model selection, request/manifest design, skill migration, docs, testing, and phased rollout.
- The plan keeps video models out of the current image pipeline.
- The plan avoids a single fixed model and instead defines automatic selection with manual override.
- The plan keeps existing post-processing scripts intact.
- The plan avoids requiring a server or non-standard provider plugin system.
