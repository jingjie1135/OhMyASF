# OhMyASF

语言：[English](./README.en.md) | [繁體中文](./README.zh-TW.md) | [简体中文](./README.md) | [日本語](./README.ja.md) | [한국어](./README.ko.md)

<p align="center">
  <img src="./src/banner.png" alt="OhMyASF banner" width="900" />
</p>

<p align="center">
  <strong>面向任何支持 Skills 的 AI agent 的 2D 游戏资产工作流：通过 OpenAI-compatible 生图端点生成可用角色精灵、分层地图和引擎原型素材。</strong>
</p>

<p align="center">
  用自然语言描述需求，agent 负责规划资产流程，通过 new-api / One-API / LiteLLM 风格的 OpenAI-compatible 图像接口产出原始视觉，再用本地处理器去背、切格、对齐、验证，并导出给 Godot、Unity 或普通 2D 游戏项目使用。
</p>

<p align="center">
  OhMyASF 基于 Agent Sprite Forge 演进而来，但已经从原本偏 Codex-first 的资产生成流程，改造成可移植的 Skills、本地处理器和外部 OpenAI-compatible 生图适配器组合。只要你的 AI 工具能加载 skills，就可以把这套工作流接入 OpenCode、Claude Code、Gemini CLI、Codex 或其他 agent runtime。
</p>

<p align="center">
  <a href="#showcase">Showcase</a> |
  <a href="#included-skills">Skills</a> |
  <a href="#install">安装</a> |
  <a href="#使用方法">使用</a> |
  <a href="#star-history">Star History</a>
</p>

## OhMyASF 与原 Agent Sprite Forge 的不同

OhMyASF 不是一组 prompt 模板，也不是只绑定某个平台内置生图能力的 demo。它保留了 Agent Sprite Forge 的核心目标——让 agent 生成游戏可用资产——但把关键路径改成更通用、更稳定、更容易配置的工作流：agent 先判断需要什么资产，OpenAI-compatible 生图 provider 负责创作原始视觉，本地脚本只做可重复的清理、切割、对齐、验证和导出。

相对原项目，OhMyASF 重点做了这些改造：

- **从 Codex-first 到 Skills-first**：skills 文件可以复制到 OpenCode、Claude Code、Gemini CLI、Codex 或其他支持 Skills 的 AI 工具中使用，不再要求用户必须在单一 agent runtime 内工作。
- **外部 OpenAI-compatible 生图 provider**：通过 new-api / One-API / LiteLLM 风格的 `/v1/images/generations` 端点接入，不依赖平台内建 `image_gen`。
- **更简单的用户入口**：新增 `ohmyasf setup` 和 `ohmyasf generate --run-dir ...`，用户只需输入 API 地址和 key；旧的 `agent-sprite-forge-imagegen` 仍保留给高级调试和兼容场景。
- **确定性的分辨率策略**：默认 2K，图标、头像等简单资产走 1K，大地图、背景、高密度 `5x5` / `6x6` sheet 走 4K，减少 agent 每次临场猜模型的成本。
- **更安全的 sprite 后处理兜底**：agent 仍应按资源类型主动传 `--cell-size`；如果漏传，处理器会保留原图每格分辨率，不再自动压缩到旧的 96 / 128 小格子。
- **更明确的引擎交付目标**：除 sprite 和 map 图像外，文档和 skills 更强调 Godot editable map、分层地图、prop pack、collision / zones、Unity / Godot prototype wiring 等可落地输出。

<table>
  <tr>
    <td width="25%"><strong>精灵表</strong><br />角色、怪物、NPC、道具、攻击、法术、投射物、命中特效、idle、walk，以及参考图驱动的变体。</td>
    <td width="25%"><strong>分层地图</strong><br />ground-only base、dressed reference、prop pack、透明 props、y-sort 摆放、碰撞、区域和预览图。</td>
    <td width="25%"><strong>引擎交付</strong><br />Godot 场景、可编辑 TileMapLayer、分离式 props、遇怪草丛、碰撞体、出口和 debug player。</td>
    <td width="25%"><strong>本地清理</strong><br />洋红去背、frame extraction、alignment、透明 PNG/GIF 导出、prop pack 切割和 QA metadata。</td>
  </tr>
</table>

## Showcase

### Engine-Ready Prototypes

这些案例使用 agentic OhMyASF 工作流组装，重点是完整闭环：生成资产、结构化场景数据，以及可玩的 prototype wiring。

<table>
  <tr>
    <td align="center" width="50%">
      <img src="./src/summon-survivors-game-preview1.png" alt="Summon Survivors Unity WebGL gameplay" width="420" />
      <br />
      <strong>Summon Survivors - Unity WebGL</strong>
      <br />
      生成地图、主角 sheet、召唤物、进化、敌人、Boss、拾取物、HUD、FX、升级选项和 WebGL 部署。
      <br />
      <a href="https://summon-survivors.vercel.app/">Play build</a> | <a href="https://drive.google.com/file/d/1TL7qRX95przTToZILVQ1EFwEXm3flB6t/view?usp=sharing">Build conversation</a>
    </td>
    <td align="center" width="50%">
      <img src="./src/kingdomrush-forest-pass.png" alt="Forest Pass Defense Godot tower-defense map" width="420" />
      <br />
      <strong>Forest Pass Defense - Godot Tower Defense</strong>
      <br />
      Godot 4 塔防原型，包含地图、分离式 props、塔位、塔、敌人 sheet、Boss、飞行敌、波次、HUD、建造 / 升级 / 出售流程和投射物规则。
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="./src/godot-editor.png" alt="Generate2DMap Godot editor scene" width="420" />
      <br />
      <strong>Editable RPG Map - Godot TileMap</strong>
      <br />
      图像生成 tileset 和 prop sheet，再接进可编辑 <code>TileMapLayer</code>、<code>Sprite2D</code> props、遇怪草丛 <code>Area2D</code>、<code>StaticBody2D</code> 碰撞、出口、metadata 和 debug player/camera。
    </td>
    <td align="center" width="50%">
      <img src="./src/neon-breach.png" alt="Neon Breach cyberpunk side-scroller" width="420" />
      <br />
      <strong>Neon Breach - Cyberpunk Side-Scroller</strong>
      <br />
      使用生成的角色、攻击、地图和 gameplay assets 组装出的可玩横向卷轴 prototype。
    </td>
  </tr>
  <tr>
    <td align="center" width="50%">
      <img src="./src/pokemonlike2.png" alt="Sengoku Era JavaScript RPG starter selection" width="420" />
      <br />
      <strong>Sengoku Era - JavaScript monster-taming RPG</strong>
      <br />
      浏览器 RPG prototype，包含生成角色、初始怪物选择、地图流程和战斗 UI。
      <br />
      <a href="https://sengoku-era.vercel.app/">Play build</a>
    </td>
    <td align="center" width="50%">
      <img src="./src/pokemonlike.png" alt="Sengoku Era JavaScript RPG battle scene" width="420" />
      <br />
      <strong>Starter selection and battle loop</strong>
      <br />
      用 skill workflow 生成 sprite、monster、battle 和 map assets 后完成的小型 JavaScript 游戏展示。
    </td>
  </tr>
</table>

### Sprite Sheets And FX

当你需要动画单位、玩家角色、怪物、props、spell bundles、projectile/impact FX，或参考图驱动的变体时，使用 `$generate2dsprite`。

<table>
  <tr>
    <td align="center" width="25%"><img src="./src/goku-kame.gif" alt="Goku Kamehameha sprite animation" width="170" /><br /><strong>Text to sprite</strong><br />从自然语言生成攻击动画。</td>
    <td align="center" width="25%"><img src="./src/naruto-rasengan.gif" alt="Naruto Rasengan sprite animation" width="170" /><br /><strong>Character action</strong><br />紧凑的 2D 动作 sheet 和透明导出。</td>
    <td align="center" width="25%"><img src="./src/cast.gif" alt="Fire mage cast animation" width="150" /><br /><strong>Spell cast</strong><br />适合 bundle 的施法动画。</td>
    <td align="center" width="25%"><img src="./src/projectile.gif" alt="Fire mage projectile animation" width="150" /><br /><strong>Projectile</strong><br />匹配的 projectile / impact workflow。</td>
  </tr>
</table>

### Layered RPG Map Pipeline

当你需要地图而不是单独 sprite 时，使用 `$generate2dmap`。可读性较高的 layered raster map 目前推荐 clean hand-painted HD game-map style：先生成 ground-only base，再生成 dressed reference，接着生成 prop pack，最后做透明 prop extraction 和 layered preview composition。

<table>
  <tr>
    <td align="center" width="33%"><img src="./src/cyber-canal-base.png" alt="Ground-only cyberpunk canal RPG base map" width="300" /><br /><strong>Ground-only base</strong></td>
    <td align="center" width="33%"><img src="./src/cyber-canal-dressed-reference.png" alt="Dressed cyberpunk canal reference map" width="300" /><br /><strong>Dressed reference</strong></td>
    <td align="center" width="33%"><img src="./src/cyber-canal-prop-pack.png" alt="Generated 3x3 cyberpunk canal prop pack" width="300" /><br /><strong>3x3 prop pack</strong></td>
  </tr>
</table>

<p align="center">
  <img src="./src/cyber-canal-layered-preview.png" alt="Layered cyberpunk canal RPG map preview" width="760" />
  <br />
  <strong>Flattened layered RPG map preview</strong>
</p>

```text
layered_raster + y_sorted_props + precise_shapes + trigger_zones + raw_canvas
```

### Godot Editable TileMap Export

`$generate2dmap` 也可以输出可编辑 Godot map project，而不是只有一张 flattened image。这个 showcase 使用图像生成的 tileset 和 3x3 prop sheet，再接入 Godot 4.5 scene。

<p align="center">
  <img src="./src/godot-editor.png" alt="Generate2DMap Godot editor scene with editable TileMapLayer and nodes" width="860" />
  <br />
  <strong>Godot editor scene: editable layers, props, zones, collision, exits, and debug player</strong>
</p>

Godot 输出可以包含可编辑 `TileMapLayer` nodes、独立 `Sprite2D` props、遇怪草丛 `Area2D` zones、`StaticBody2D` collision blockers、exit `Area2D` zones，以及 debug player/camera。

```text
imagegen manifest + prop_pack_3x3 + layered_tilemap + separate_props + trigger_zones + Godot_TileMap
```

## Included Skills

| Skill | 用途 | 输出 |
| --- | --- | --- |
| [`generate2dsprite`](./skills/generate2dsprite) | Sprites、animation sheets、props、spell bundles、FX、参考图变体、固定 frame sheet 的 layout guide | raw sheet、cleaned transparent sheet、frames、GIFs、metadata |
| [`generate2dmap`](./skills/generate2dmap) | baked maps、layered raster maps、clean HD RPG maps、prop packs、collision/zones、Godot-editable scenes、side-scroll/parallax scenes | base map、dressed/stage reference、prop pack、extracted props、preview、scene metadata |

`$generate2dmap` 只有在地图流程需要可复用透明 props 时，才会搭配 `$generate2dsprite`。小型环境 props 可以批成 `2x2`、`3x3` 或 `4x4` prop packs，再切成独立透明 props。平台、地板、桥、墙、门和长条 hazard 这类碰撞关键物件，通常应该单独生成或用 tile/object layer 表达。

## How It Works

1. 用户请 agent 生成 sprite、prop pack、map 或 engine-ready prototype。
2. Agent 判断 asset type、action、bundle shape、sheet layout、frame count、style 和 alignment strategy。
3. Agent 写入 `imagegen-request.json`，运行 `agent-sprite-forge-imagegen generate` 调用 OpenAI-compatible `/v1/images/generations` 端点。
4. Adapter 写出 raw PNG 和 `imagegen-manifest.json`；本地脚本再做 deterministic post-processing：chroma-key cleanup、despill、frame extraction、alignment、prop-pack slicing、GIF/PNG export 和 validation metadata。
5. 对地图和 prototype，agent 也可以组装 placement metadata、collision、trigger zones、Godot scenes 或 Unity project wiring。

脚本不是创意大脑。Agent 负责视觉和 pipeline 决策；Python 工具只做可重复的像素处理和导出。

## Install

先 clone 仓库、安装 Python 包，再把两个 skills 复制到你的 agent skills 目录。下面沿用 Codex 默认路径示例；如果你使用 OpenCode、Claude Code、Gemini CLI 或其他 agent runtime，请改成对应的 skills 目录。

### Windows PowerShell

```powershell
git clone https://github.com/jingjie1135/OhMyASF.git
cd .\OhMyASF
python -m pip install -e .
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.codex\skills" | Out-Null
Copy-Item -Recurse -Force `
  ".\skills\*" `
  "$env:USERPROFILE\.codex\skills\"
```

### macOS / Linux

```bash
git clone https://github.com/jingjie1135/OhMyASF.git
cd ./OhMyASF
python3 -m pip install -e .
mkdir -p ~/.codex/skills
cp -R ./skills/* ~/.codex/skills/
```

安装后请重开 agent session，让 skills 和命令入口被重新载入。

## 使用方法

### 1. 配置 OpenAI-Compatible 生图 provider

OhMyASF 使用单一 OpenAI-compatible 端点生成 raw image，可接入 new-api、One-API、LiteLLM 风格网关，或任何实现 `/v1/images/generations` 的 provider。

安装后运行一次 setup，输入网关地址和 API key。CLI 会把默认配置写入用户目录下的 `.agent-sprite-forge/imagegen.json`，并保存 API key；如果你更希望用环境变量管理密钥，也可以用固定变量名 `OHMYASF_IMAGEGEN_API_KEY` 覆盖配置中的 key。

```bash
ohmyasf setup
```

按提示输入 API 地址和 KEY。自动化脚本也可以使用 `--base-url` / `--api-key`，但真实密钥不建议直接写进 shell history。

### 2. 先执行 dry-run

先在一个 run directory 写入 `imagegen-request.json`，再用 `--dry-run` 验证 request 解析、模型选择、路由和 manifest 写入，不消耗 provider 额度。正常模式只需要传 `--run-dir`，CLI 会自动使用默认配置、读取 `<run-dir>/imagegen-request.json`，并把 manifest 写到 `<run-dir>/raw/imagegen-manifest.json`。

```bash
mkdir -p outputs/imagegen-smoke/sprite
cp examples/imagegen/sprite-2x2-idle.request.json outputs/imagegen-smoke/sprite/imagegen-request.json
ohmyasf generate --run-dir outputs/imagegen-smoke/sprite --dry-run
```

### 3. 在 agent 中调用 skill

完成安装与配置后，重开 agent session，然后直接在对话里调用 `$generate2dsprite` 或 `$generate2dmap`。例如：

```text
Use $generate2dsprite to create a 3x3 idle for an ultimate earth titan.
```

```text
Use $generate2dmap to create a Godot-editable RPG map with separated props, encounter grass Area2D zones, collision StaticBody2D blockers, exit zones, and a debug player scene.
```

如果你只是想调试底层适配器，而不是整条 skill 工作流，也可以直接构造 `imagegen-request.json` 后运行 `ohmyasf generate --run-dir <run-dir>`。高级调试场景仍保留旧的显式参数：`agent-sprite-forge-imagegen generate --config ... --request ... --output-dir ...`。

live smoke test 会消耗 provider 额度，不属于普通单元测试。

## 模型选择

Adapter 不固定单一模型，因为 sprite sheet 和地图需要不同宽高比。默认使用 `{family}-{resolution}-{ratio}` 形式的 Firefly 图片模型 ID，并把最终选择写入 `imagegen-manifest.json`。

- 标准 sprite sheet：默认 `firefly-gpt-image-2k-1x1`
- 简单小图（物品图标、UI 图标、头像、简单 projectile/impact/FX、小型 prop）：`firefly-gpt-image-1k-1x1`
- 大背景、地图 base、dressed reference、tileset、side-scroll / parallax layer：默认 `firefly-gpt-image-4k-16x9`
- 高密度 `5x5` / `6x6` sheet：`firefly-gpt-image-4k-1x1`
- 高价值主角或密集 `4x4` sheet：`firefly-gpt-image-2k-1x1`
- compact prop pack：方形 `1x1` 模型
- side-scroll parallax layer / stage reference：`16x9` 模型
- portrait/mobile 场景：`9x16` 模型
- 宽平台、桥、长条 hazard：通过 `firefly-nano-banana2` 走 `4x1` 或 `8x1`

默认 `size_mode` 是 `model_id`，即不额外发送 `size`，避免网关模型名已经编码分辨率/比例时产生冲突。Sora、Veo、Kling 等视频模型不会进入当前图片 selector；GIF 仍由本地 sprite sheet 切帧生成。

## Suggested Prompts

### Sprite

```text
Use $generate2dsprite to create a 3x3 idle for an ultimate earth titan.
```

```text
Use $generate2dsprite to create a side-view lightning knight attack animation.
```

```text
Use $generate2dsprite to create a wizard spell bundle with cast, projectile, and impact sprites.
```

### Map

```text
Use $generate2dmap to create a Godot-editable RPG map with separated props, encounter grass Area2D zones, collision StaticBody2D blockers, exit zones, and a debug player scene.
```

```text
Use $generate2dmap to create a playable side_scroll_mode platformer stage with parallax layers, stage-reference, separate platform_objects, collision metadata, camera bounds, and a stage-preview.
```

## What You Get

典型 sprite sheet 输出：

- `raw-sheet.png`
- `raw-sheet-clean.png`
- `sheet-transparent.png`
- frame PNGs
- `animation.gif`
- `prompt-used.txt`
- `pipeline-meta.json`

地图输出取决于 pipeline：

- Single baked map：完整地图图像、可选 prompt file、可选 collision metadata。
- Layered raster map：base map、dressed reference、prop folders 或 prop-pack extraction manifest、prop placement metadata、collision/zones metadata、flattened layered preview。
- Side-scroll map：parallax layers、stage reference、separate platform/object assets、objects/collision metadata、camera bounds、stage preview。
- Godot editable map：tileset/prop assets、scene files、layer metadata、collision/zones、exits、debug player setup。

## Notes

- 最好的结果来自明确指定视角、动作和动作节奏的 prompt。
- 对 sprite 后处理，agent 通常仍应根据资源类型、目标引擎和交付尺寸主动传 `--cell-size`。如果漏传，处理器现在会保留原图每格分辨率作为安全兜底，而不是再自动压缩到旧的 96 / 128 小格子。
- 大型 creature 通常更适合 `3x3 idle`。
- 小型 spell、projectile 和 impact 通常适合 `2x2` 或 `2x3`。
- 主角攻击、射击、施法动作建议 body-only；大范围 slash、muzzle flash、projectile、impact 独立生成成 FX。
- 商业项目请优先使用原创角色或你拥有权利的 IP。

## Star History

<a href="https://www.star-history.com/?repos=jingjie1135%2FOhMyASF&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=jingjie1135/OhMyASF&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=jingjie1135/OhMyASF&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=jingjie1135/OhMyASF&type=date&legend=top-left" />
 </picture>
</a>

## License

MIT. See [LICENSE](./LICENSE).
