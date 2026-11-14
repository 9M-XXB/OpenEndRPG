# OpenEndRPG · A Fully Open-Ended RPG

[中文](README.md) | English

**A text adventure that "only provides a beginning": quests, NPCs, events — everything afterward is generated on the fly by an LLM from your input. Even the visuals: "glyph-slide" scenes arranged from characters, switching in sync with the story. The game supports both Chinese and English — Chinese scenes compose characters into objects, while English words become pictographic through size × rotation × arrangement (e.g. in "sword", the s forms the hilt, the w the cross-guard, and the ascender of a lowercase d the tip).**

No art assets, no image services, no preset story tree; story length is uncapped, held together by a world-state ledger and a rolling summary. Terminal and web modes share the same engine.

> Idea & research notes (Chinese, kept outside this repo): this project is the minimal prototype of the "fully open-ended RPG" idea. The design follows three research findings: **narration belongs to the LLM, state belongs to deterministic code** (Song et al. 2024, [arXiv:2409.06949](https://arxiv.org/abs/2409.06949)); **two-level rolling memory** (Zhou et al. 2023, [arXiv:2305.13304](https://arxiv.org/abs/2305.13304)); **persistent NPC memory streams** (Park et al. 2023, [arXiv:2304.03442](https://arxiv.org/abs/2304.03442)).

## Gameplay core

- **A prologue is all you get**: the Demon King awakens on the Obsidian Throne, and the village elder hands you an ancestral dagger — beyond that, the world has no preset content.
- **Free-form input drives everything**: each turn you type any action in natural language; the game master (LLM) generates the **consequence narrative** plus **2–4 next-step suggestions** (suggestions are just shortcuts — ignore them and improvise whenever you like).
- **Glyph slides (web mode)**: in the same LLM call that writes the story, the model also acts as art director, emitting 0–3 **glyph canvases** — every glyph carries stage coordinates (0–100%), a size tier (1–9) and a rotation angle (±90°). In Chinese, "the hero walks forward" means the glyph 「我」(I) gliding across the stage; in English, the word "sword" can be drawn as a tilted blade (s as the hilt, w as the guard, the ascender of a lowercase d as the tip). Slides switch PowerPoint-style (fade / smooth slide / scale-rotate transition, no per-character animation). The front end contains no shape library and no images — 100% of the visuals come from model output.
- **NPCs persist and can be revisited**: every NPC that appears is registered in the world ledger (last meeting, meeting count, recent-news notes); come back days later and they reunite with you carrying whatever happened to them in the meantime, relationships accumulating with every meeting — NPCs are not one-shot props.
- **The one-day rule**: unless you explicitly ask for a time skip (e.g. "three days later"), each turn advances at most one day of in-game time — the story unfolds at a day-by-day pace.
- **The fate die**: each turn secretly rolls a d20 (setback / quiet progress / small opportunity / major turn / fate event — five tendency tiers) injected into generation, so the same input can lead somewhere different; `/reroll` re-rolls and replays the turn.
- **Unlimited story**: the world ledger (facts / NPCs / items / time) is merged by deterministic code, a rolling plot summary plus recent turns are injected into context, and the game auto-saves every turn.

## Quick start

```bash
git clone https://github.com/9M-XXB/OpenEndRPG.git
cd OpenEndRPG
python3 rpg.py             # web mode (default): starts at the lobby, open in a browser and play
python3 rpg.py --terminal  # terminal mode: main menu + command-line play
python3 rpg.py config      # reconfigure the API (key input is password-style, not echoed)
```

Requirements: Python 3.10+ and `httpx` (`pip install httpx`; optional `pip install rich` for the terminal mode, falls back to plain text automatically if missing). The web server and front end use only the Python standard library and vanilla HTML/CSS/JS — nothing to install in the browser.

**Lobby**: the app starts at a lobby — create a save, pick a save (enter / delete), configure the API, or exit (saving and shutting down). A game starts only after you pick a save; nothing is auto-loaded. The whole API wizard runs in the browser: pick a provider → enter the key (password-style) → fetch the model list → test chat → save.

- **No fixed port**: defaults to 8770, falls back to a system-assigned free port when busy; `--port 0` always picks a random port.
- **Skip the lobby**: `--new <save>` / `--save <save>` jump straight into a save.
- **LAN play**: `--host 0.0.0.0` exposes the server to other devices on your network.

## Supported APIs (14 presets × 3 protocols, zero SDK dependencies)

| Protocol | Presets |
|---|---|
| OpenAI-compatible | OpenAI / DeepSeek / Kimi (Moonshot) / Zhipu GLM / Tongyi Qwen / OpenRouter / Groq / SiliconFlow / **Ollama (local)** / LM Studio (local) / custom endpoint (vLLM, one-api, proxies — anything) |
| Anthropic | Claude |
| Google | Gemini |
| Offline | Mock (no key needed, scripted story, for testing and demos) |

First-run wizard: pick the **game language** (中文 / English) → pick a provider → base URL (Enter for default) → API key (**password-style input, not echoed**) → model (list fetched online automatically) → test chat → saved to `config.json`. Reconfigure anytime with `python3 rpg.py config`; in web mode you can also switch the language in the lobby's "配置 API" dialog.

> **Privacy**: the API key is stored only in the local `config.json` (excluded via `.gitignore`); `config.example.json` is the field template.

## In-game commands

| Command | Effect |
|---|---|
| `/help` | Help |
| `/status` | Inspect the world ledger (day / location / facts / NPCs / items / summary) |
| `/roll` | Show last turn's fate die |
| `/reroll` | Undo this turn and re-roll |
| `/suggestions` | Re-show last turn's suggestions |
| `/save` · `/quit` · `/config` | Save now · save and exit · reconfigure the API |

Typing `1`/`2`/`3` quickly adopts last turn's suggestions; everything else you type is your action.

## Project structure

```
OpenEndRPG/
├── rpg.py       # Entry: main menu, API wizard, web mode
├── engine.py    # Game loop, commands, snapshot-based reroll
├── llm.py       # Clients for 3 protocols, 14 presets, SSE streaming, JSON parsing & self-repair, Mock
├── state.py     # Save read/write, deterministic ledger merge, time advance
├── prompts.py   # GM system rules (incl. bilingual glyph-slide teaching), zh/en prologues, fate table, context assembly
├── ui.py        # Terminal rendering (rich/plain, typewriter effect)
├── webui.py     # Web event adapter: same method surface as ui.py, collects render calls as events
├── server.py    # Local web server (stdlib HTTP, GET /api/state + POST /api/say)
├── web/         # Front end (vanilla HTML/CSS/JS, zero build)
│   ├── slides.js  # Glyph-slide engine v2: glyph parsing/normalization + instance-matched PowerPoint-style switching (zero image elements)
│   ├── app.js     # Client logic: state polling, turn rendering, typewriter, suggestion chips
│   ├── index.html / style.css
├── config.example.json
└── saves/       # Save directory (created at runtime, not committed)
```

Per-turn flow: player input → deep-copy snapshot → roll the fate die → LLM returns strict JSON (narrative + glyph slides + time delta + state delta + rolling summary + suggestions, auto-repair with error feedback on failure) → **deterministic code** validates and merges state (slides only get loose clamping; a failed slide never fails the turn) → narrative and glyphs are rendered → auto-save.

**Slide contract (v2, unified for both languages)**: `slides[] = {caption, tone(暗/明/暖/冷/灰), glyphs: [{ch, x, y, s, r}]}` — `x`/`y` are stage percentage coordinates (0–100), `s` is the size tier (1–9), `r` is rotation (±90°); at most 24 glyphs per slide, 3 slides per turn. The spec constants live in `prompts.py` (`STAGE_COORDS`/`S_MIN`/`S_MAX`/`R_MAX`/`GLYPHS_MAX`) and are served to the front end via `stage_spec` in `/api/state`; legacy v0.2 `canvas` grids are converted to glyphs by the renderer automatically — no save migration needed. The hero marker is always 「我」/"I", NPCs use the first character/letter of their name, north is up / west is left, single-step movement is ≤15 stage units with no teleporting — all of this lives in the bilingual glyph-slide teaching section of `prompts.py` (zh character-composition / en letter-pictography, including the sword's hilt-guard-blade-tip construction), the single source of truth that teaches the runtime LLM to draw.

## Roadmap

- [x] Web mode + glyph slides (2026-10-26, v0.2: LLM doubles as art director, zero image services, zero per-character animation, PowerPoint-style switching)
- [x] Unified bilingual glyph contract (2026-11-13, v0.3: coordinates / size tiers / rotation; English word pictography — the "sword" letter-blade construction; configurable zh/en game language)
- [ ] Real-API testing and per-provider tuning (temperature / max tokens) — including verifying glyph-art quality with real models
- [ ] Multiplayer self-hosting (host configures the key once; turn-taking + host arbitration, design finalized)
- [ ] Two-phase generation: settle state first, then stream the narrative (SSE streaming already built into llm.py)
- [ ] Persistent memory for key NPCs (memory stream + reflection), passers-by generated on the fly
- [ ] Content admission pipeline (filter/rewrite loop) to hedge against low small-model task quality

## Attribution

Designed and written by ZCode (coding agent, model GLM-5.3-Flash), 2026-10. Philosophical next of kin: AI Dungeon, 1001 Nights, Generative Agents.
