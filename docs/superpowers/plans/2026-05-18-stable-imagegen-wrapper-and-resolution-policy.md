# Stable Imagegen Wrapper And Resolution Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove agent runtime path-discovery friction from the image generation layer and replace the current resolution defaults with a deterministic policy: default 2K, simple small assets 1K, and large backgrounds / high-density `5x5` / `6x6` assets 4K.

**Architecture:** Wrap the existing OpenAI-compatible adapter in a deterministic, setup-driven user configuration flow so normal generation no longer requires the agent to discover config/request/output paths. Keep the current `agent_sprite_forge.imagegen` package and post-processing scripts, but add a stable CLI entry contract and a central resolution policy in `model_resolver.py` so agents and users get consistent model selection without improvising per run.

**Tech Stack:** Python 3.11+, existing `argparse` CLI, JSON config/request files, current `Pillow` / `numpy` post-processors, unit tests under `tests/imagegen`, Markdown docs and skill files.

---

## 1. Scope

### In scope

- Add a stable, fixed-path imagegen configuration flow so agents do not need to discover the provider config path at runtime.
- Add a user-facing setup command that asks only for API base URL and API key.
- Add a stable generation wrapper flow so agents only need to know one run directory, not `--config` + `--request` + `--output-dir` separately.
- Add a short command alias (`ohmyasf`) while keeping the existing `agent-sprite-forge-imagegen` entry point for compatibility.
- Replace the current “default 1K, selective 2K” behavior with the requested resolution strategy:
  - default 2K
  - simple small assets 1K
  - large backgrounds / maps / high-density `5x5` / `6x6` assets 4K
- Make the resolution policy deterministic in code and documented in skills / README.
- Preserve advanced explicit override paths (`--config`, explicit `model`, explicit `quality`) for debugging and expert usage.

### Out of scope

- Rewriting the low-level post-processors in `skills/generate2dsprite/scripts/` or `skills/generate2dmap/scripts/`.
- Adding image-to-image or provider-native reference editing in this pass.
- Supporting multiple concurrent provider profiles with interactive switching in the first pass.
- Replacing existing manifest schema wholesale unless required for stable path wrapping.

---

## 2. Current pain points to solve

### 2.1 Runtime path-discovery costs introduced by the external provider layer

The original Codex-first flow relied on built-in `image_gen` and a platform-managed raw image location under `$CODEX_HOME/generated_images/...`. The modified adapter-first flow now requires the agent to resolve:

- provider config path
- request JSON path
- run directory
- raw output directory
- manifest path
- raw PNG path inside the manifest

The highest-friction new burden is the external config path because `cli.py` currently requires:

```python
generate_parser.add_argument("--config", required=True, type=Path)
generate_parser.add_argument("--request", required=True, type=Path)
generate_parser.add_argument("--output-dir", required=True, type=Path)
```

and `config.py` currently requires a JSON file before generation:

```python
data = _load_json(Path(path))
```

### 2.2 Resolution policy is split and partially contradictory

Current behavior is controlled by several overlapping mechanisms:

- `ImageGenConfig.default_resolution = "1k"`
- `QUALITY_PROFILES["standard"] = ("firefly-gpt-image", "1k")`
- role-based overrides in `model_resolver.py`
- README prose saying some assets should use 2K
- skill prose telling agents to use higher quality for dense / high-value sheets without deterministic rules

This means changing config defaults alone is not enough to make normal requests use 2K, and agent behavior is not predictable enough for non-ideal models.

---

## 3. Target user experience

### 3.1 Installation and setup

The default user flow should become:

```powershell
python -m pip install -e .
ohmyasf setup
```

`setup` should:

1. ask for API base URL
2. normalize it to include `/v1` when missing
3. ask for API key
4. save config to a deterministic user-level path
5. tell the user the fixed environment variable name to use (or save it if the platform integration is safe enough)
6. run a dry-run validation
7. print the resulting endpoint and config path

### 3.2 Agent generation flow

The normal agent flow should become:

```powershell
ohmyasf generate --run-dir <run-dir>
```

Where the CLI deterministically infers:

- config path
- request path = `<run-dir>/imagegen-request.json`
- raw output directory = `<run-dir>/raw`
- manifest path = `<run-dir>/raw/imagegen-manifest.json`

The agent should no longer need to pass or discover those paths individually in the normal path.

### 3.3 Advanced / debug flow

Advanced users may still use:

```powershell
agent-sprite-forge-imagegen generate --config ... --request ... --output-dir ...
```

or

```powershell
ohmyasf generate --config ... --request ... --output-dir ...
```

but that should no longer be the documented default.

---

## 4. Stable wrapper design

### 4.1 Fixed config location

Adopt one deterministic default config path:

```text
%USERPROFILE%\.agent-sprite-forge\imagegen.json
```

The wrapper should use this path by default.

Rules:

- normal mode: use default config path automatically
- explicit `--config`: override for expert/debug mode only
- missing default config: fail with a targeted “run `ohmyasf setup` first” error

### 4.2 Fixed API key convention

Adopt one stable default environment variable name, for example:

```text
OHMYASF_IMAGEGEN_API_KEY
```

Rules:

- setup teaches/validates this variable name
- normal mode does not require the agent to discover `api_key_env`
- legacy `api_key_env` remains supported only for explicit custom config usage

### 4.3 Stable request/output conventions

Given `--run-dir <run-dir>`, the wrapper should infer:

- request file: `<run-dir>/imagegen-request.json`
- raw output dir: `<run-dir>/raw`
- manifest: `<run-dir>/raw/imagegen-manifest.json`

This keeps only one runtime path decision in the agent’s hands: the run directory.

### 4.4 Backward-compatible CLI surface

Add a second console script entry point:

```toml
[project.scripts]
ohmyasf = "agent_sprite_forge.imagegen.cli:main"
agent-sprite-forge-imagegen = "agent_sprite_forge.imagegen.cli:main"
```

Add subcommands:

- `setup`
- `generate`

`generate` should support two modes:

1. **simple mode**: `ohmyasf generate --run-dir <dir>`
2. **expert mode**: explicit `--config`, `--request`, `--output-dir`

### 4.5 Failure model

The wrapper should produce deterministic user-facing failures for:

- missing setup/default config
- missing API key
- missing request file under run-dir
- invalid request JSON
- output collision or missing output directory permissions

These failures should point to the exact next action.

---

## 5. Resolution strategy design

### 5.1 Requested policy

The new policy should be:

- **Default 2K** for most normal sprite and map asset generation.
- **1K** only for very simple, small, low-detail assets such as:
  - item icons
  - UI icons
  - portraits / busts / heads
  - tiny props
  - simple projectile / impact / lightweight FX
- **4K** for:
  - large backgrounds
  - map base images
  - dressed references
  - large stage / parallax / side-scroll canvases
  - tilesets / large scene foundations
  - high-density `5x5` and `6x6` sheets
  - other dense final-delivery sheets where per-cell detail would collapse at 2K

### 5.2 Deterministic rule hierarchy

Resolution should be chosen in this order:

1. **Explicit model override** in request wins.
2. **Explicit quality override** wins next.
3. **Role / map_mode / grid-density policy** decides next.
4. **Global default** applies only when no stronger evidence exists.

### 5.3 Quality profile redesign

Current profiles:

- `draft` -> 1K
- `standard` -> 1K
- `high` -> 2K
- `final` -> 4K

Recommended replacement:

- `draft` -> 1K
- `standard` -> 2K
- `high` -> 2K
- `final` -> 4K

Rationale:

- `standard` should match the new user expectation: normal assets are 2K by default.
- `high` can remain 2K if “high” is mostly about role-driven detail, not cost tier.
- `draft` preserves a cheap iteration path.
- `final` keeps 4K for explicit premium runs.

### 5.4 Role-based 1K downgrade rules

Use 1K for:

- `item_icon`
- `ui_icon`
- `portrait`
- `headshot`
- `simple_projectile`
- `simple_impact`
- `simple_fx`
- `tiny_prop`

These asset roles may need to be added to the request vocabulary or normalized through constraints/model policy.

### 5.5 Role-based 4K promotion rules

Use 4K for:

- `map_base`
- `dressed_reference`
- `tileset`
- `side_scroll_layer`
- `parallax_layer`
- large background / stage / scene foundations
- any request whose grid density is `5x5` or `6x6`
- explicit final showcase hero sheets when requested

### 5.6 Grid-density-aware policy

The current resolver does not reason directly from grid density unless the agent maps it into a role or explicit quality. That is too implicit.

Add a deterministic policy layer using request fields or `model_policy` / `constraints`, for example:

- `grid_rows`
- `grid_cols`
- `asset_scale`
- `asset_importance`
- `delivery_stage`
- `cost_preference`

Examples:

- `2x2` idle creature -> 2K default
- `3x3` boss idle -> 2K default
- `4x4` player sheet -> 2K default unless final-showcase override promotes to 4K
- `5x5` or `6x6` dense action sheet -> 4K

### 5.7 Ratio remains independent from resolution

Keep current ratio routing separate from resolution policy:

- `1x1` for sprite sheets / compact prop packs
- `16x9` for side-scroll / parallax / stage backgrounds
- `9x16` for portrait scenes
- `3x4` for tall route maps
- `4x1` / `8x1` for strips via `firefly-nano-banana2`

Do not couple “4K” to “square only.”

---

## 6. File structure impact

### Modify

- `agent_sprite_forge/imagegen/cli.py`
  - add `setup`
  - add simplified `generate --run-dir`
  - preserve expert explicit mode
- `agent_sprite_forge/imagegen/config.py`
  - support deterministic default config path
  - support default API key convention
  - keep compatibility for explicit custom config
- `agent_sprite_forge/imagegen/model_resolver.py`
  - update quality profiles
  - centralize 1K / 2K / 4K policy
  - add grid-density-aware resolution logic
- `agent_sprite_forge/imagegen/schema.py`
  - optionally support explicit policy hints like `grid_rows`, `grid_cols`, `asset_importance`, or structured `model_policy`
- `pyproject.toml`
  - add `ohmyasf` entry point
- `README.md`
  - replace the current “copy config + export key + explicit generate” default flow with `setup` + simplified `generate`
- `README.en.md`
  - sync the same onboarding changes
- `skills/generate2dsprite/SKILL.md`
  - switch normal generation flow to the stable wrapper
  - remove runtime config path ambiguity
  - document deterministic resolution policy
- `skills/generate2dmap/SKILL.md`
  - switch map flow to the same stable wrapper and resolution policy expectations
- `skills/generate2dsprite/agents/openai.yaml`
  - shorten the model-facing prompt and remove dependency on runtime path discovery
- `skills/generate2dmap/agents/openai.yaml`
  - same simplification for map generation
- `tests/imagegen/test_cli.py`
- `tests/imagegen/test_config_schema.py`
- `tests/imagegen/test_model_resolver.py`

### Create

- optional helper module for default path resolution, e.g. `agent_sprite_forge/imagegen/paths.py`
- tests for setup/default-path behavior
- tests for new resolution policy
- new plan / spec references if desired

---

## 7. Phased implementation plan

### Phase A: Stable wrapper and deterministic setup

Deliverables:

- fixed default config path
- fixed default API key convention
- `setup` command
- simple `generate --run-dir`
- backward compatibility for old explicit mode

Success criteria:

- agent no longer needs to discover config path in normal workflow
- user can complete setup by entering only API URL and API key
- dry-run works after setup without passing `--config`

### Phase B: Resolution policy refactor

Deliverables:

- default 2K
- simple assets downgrade to 1K
- large backgrounds / dense `5x5` / `6x6` upgrade to 4K
- tests and manifest reasoning updated

Success criteria:

- `standard` sprite requests route to 2K unless explicitly simple/small
- known small roles route to 1K
- map/stage/large dense roles route to 4K where specified
- selection reasons in manifests are deterministic and auditable

### Phase C: Documentation and skill simplification

Deliverables:

- README switched to stable wrapper flow
- skill docs switched away from `<repo-or-user-config>` ambiguity
- agent prompts shortened and hardened

Success criteria:

- Claude/Codex/OpenCode-style agents can follow one obvious path
- fewer runtime filesystem searches are needed before generation

---

## 8. Verification strategy

### CLI / config tests

- verify `setup` creates expected config path
- verify simplified `generate --run-dir` infers request/output paths correctly
- verify missing setup yields deterministic failure
- verify default API key variable is honored
- verify explicit advanced flags still work

### Resolution tests

- ordinary sprite sheet defaults to 2K
- simple icon / portrait roles route to 1K
- `player_sheet` / `boss_sheet` route as intended
- `5x5` and `6x6` dense sheets route to 4K
- large map base / stage layer routes to 4K where policy requires it
- explicit model override still wins

### Skill / doc verification

- skill examples reference `ohmyasf setup` and simplified `generate`
- no remaining default-path prose tells the agent to guess config location

---

## 9. Risks and tradeoffs

### Risk: default 2K increases cost

Mitigation:

- keep `draft=1K`
- downgrade explicitly simple asset roles to 1K
- keep explicit `quality` / `model` overrides

### Risk: fixed config path reduces flexibility

Mitigation:

- fixed path for normal flow
- retain `--config` for advanced/debug usage

### Risk: 4K overuse on dense sheets could slow iteration

Mitigation:

- promote to 4K only on clear density / canvas / final-delivery signals
- keep 2K as the default production path

---

## 10. Recommended implementation order

1. Add path helper + default config convention
2. Add `setup`
3. Add simplified `generate --run-dir`
4. Add `ohmyasf` alias
5. Update tests for wrapper flow
6. Refactor `model_resolver.py` resolution policy
7. Update tests for 1K / 2K / 4K policy
8. Update README and both skills
9. Run unit tests and dry-run smoke tests

---

## 11. Immediate acceptance target

After this refactor, the intended user flow should be:

```powershell
python -m pip install -e .
ohmyasf setup
```

Then the intended agent flow should be:

```text
Write <run-dir>/imagegen-request.json
Run: ohmyasf generate --run-dir <run-dir>
Read: <run-dir>/raw/imagegen-manifest.json
Postprocess: scripts/generate2dsprite.py process ...
```

with no runtime search for provider config paths and a deterministic default of **2K**, reserved downgrades to **1K**, and targeted upgrades to **4K**.
