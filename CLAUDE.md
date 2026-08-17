# Weiscracker — Project Brief (CLAUDE.md)

> Single source of truth for picking this project back up cold — whether that's
> future-me, a different AI session, or Tim himself six months from now.
> Last updated: Aug 2026, mid-build. Read this before touching anything.

---

## 1. Overview

**What it is:** Weiscracker (formerly called "CRACKER" — renamed, some old
references may still say CRACKER, treat as the same project) is a centralized
AI gateway hosted on GCP. It converts natural-language voice/text commands
into structured JSON function calls that tell Tim's other apps which internal
button/function to trigger.

**It is NOT a chatbot.** It's an action controller. You say "add an outlet,"
it figures out you mean the electrical outlet asset, and returns something
like `{"function": "place_asset", "args": {"code": "OUT"}}`. The receiving
app is responsible for actually executing that — Weiscracker never touches
the app's UI or code directly.

**Why it exists:** Tim has a portfolio of apps (Field Layout Tracker, Proposal
App, Business Excel Sheet, Fantasy Football Drafting App). Instead of building
separate AI/voice features into each one, there's ONE gateway agent. Each app
gets its own tool-schema; the core agent logic never changes when a new app
is added.

**Backup status:** code is version-controlled and pushed to a **private**
GitHub repo: `github.com/joecracker/weiscracker`. This is the real source of
truth for the code — if Cloud Shell ever gets wiped, `git clone` from there
gets everything back. Habit going forward: `git add . && git commit -m "..."
&& git push` after any real chunk of progress.

**Stack:**
- Google Cloud Platform (project ID `g-for-windows-12557`, display name
  "universal-action-ai-gw")
- [Google ADK](https://github.com/google/adk-python) (Agent Development Kit)
  — `google-adk==2.6.2`, handles the tool-calling loop
- Vertex AI — model is `gemini-3.6-flash`, **must** use `location="global"`
  (see Gotchas)
- Cloud Shell — current dev environment (not yet deployed anywhere
  permanent)
- Target deploy: Cloud Run (not done yet)

**Key dependency versions** (from last known-good install):
`google-adk-2.6.2`, `google-genai-2.16.0`, Python 3.12 (Cloud Shell default)

---

## 2. Dev Workflow

Everything happens in **Google Cloud Shell** (console.cloud.google.com →
terminal icon, top right). Project must be `g-for-windows-12557`.

### First time / after a long gap
```bash
cd ~/cracker
source venv/bin/activate
```
Cloud Shell disconnects overnight but the **home directory persists** — venv
and files survive, you just need to reactivate the venv each fresh session.

### Install (only needed if venv is missing/broken)
```bash
python3 -m venv venv
source venv/bin/activate
pip install google-adk
```

### Run / test locally
```bash
cd ~/cracker
adk web --allow_origins="*"
```
**The `--allow_origins="*"` flag is not optional.** Without it, Cloud Shell's
Web Preview proxy gets a 403 on session creation. This cost real debugging
time — don't skip it.

Then in Cloud Shell: click the **Web Preview** (eye icon, top right) → Change
port → whatever port `adk web` printed (usually 8000) → opens the ADK test
chat UI in a new tab. Pick the agent from the dropdown, type a command, watch
the **Events** panel to see which tools it called and in what order.

### Build / Deploy
**Not built yet.** No Cloud Run deployment exists. No Dockerfile. No CI.
This is the biggest "not real yet" gap — see Section 4.

### Test / Lint
**None exist.** All verification so far has been manual — typing a command
into the ADK web UI and eyeballing the Events trace. No automated tests, no
linter configured. Known gap, not an oversight to be nervous about but also
not something to pretend is more mature than it is.

---

## 3. Architecture

```
~/cracker/                                  (Cloud Shell home dir)
├── venv/                                   (Python virtualenv, not portable)
├── schemas/
│   └── field_layout_tracker/
│       └── asset_catalog.json              (327 items, ~60KB)
└── field_layout_tracker_agent/             (the actual ADK agent package)
    ├── __init__.py                         (just: from . import agent)
    ├── agent.py                            (tools + root_agent definition)
    └── .env                                (Vertex AI config, see below)
```

**One ADK "agent folder" = one app's schema.** To add a new app (e.g.
Proposal App), the pattern is: new sibling folder `proposal_app_agent/` with
its own `__init__.py` + `agent.py` + its own tool functions. The core
concept (search internal catalog → call one action tool) is the template to
copy, not shared code to import.

### Data flow (as currently tested)
```
User types/says command
    ↓
ADK agent (gemini-3.6-flash) reasons about intent
    ↓
[optional] calls search_catalog(query) — an INTERNAL tool, reads
    asset_catalog.json server-side, returns matches into the model's
    context. The calling app never sees this step.
    ↓
Model calls exactly ONE final "action" tool:
    set_tool | place_asset | undo | redo | save_project
    ↓
That tool function returns a plain dict, e.g.
    {"function": "place_asset", "args": {"code": "OUT"}}
    ↓
[NOT BUILT YET] This JSON is supposed to get sent back to the real app,
    which would call its own matching JS function (place_asset() etc.)
    with those args. Currently this only happens inside ADK's dev UI —
    there is no real HTTP endpoint the actual Field Layout Tracker app
    can call, and no code in the app itself that consumes this JSON.
```

### The `.env` file (`field_layout_tracker_agent/.env`)
```
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=g-for-windows-12557
GOOGLE_CLOUD_LOCATION=global
```
ADK auto-loads this per-agent-folder `.env` file. This is what survives
Cloud Shell's overnight disconnects — no need to re-export env vars by hand
each session.

---

## 4. Current State

### ✅ Implemented and confirmed working
- GCP project set up, billing linked to the $300 free credit
  (expires ~9/19/2026), budget alert "cracker-guardrail" at $200
- Vertex AI access confirmed live, using `gemini-3.6-flash` @ `location=global`
- `google-adk` installed clean in Cloud Shell venv
- `asset_catalog.json` extracted from the real Field Layout Tracker source
  (`app.ts`'s `ASSET_CATALOG` array), converted from TS object-literal syntax
  to valid JSON via `pyjson5`. 327 items: 271 cabinet, 29 electrical,
  20 plumbing, 7 custom.
- `field_layout_tracker_agent` built with 6 tools:
  - `search_catalog(query)` — internal, fuzzy-matches name/category/code
    against the catalog
  - `set_tool(tool)` — arms select/wall/door/window/rect_select
  - `place_asset(code)` — arms the place-asset tool with a specific catalog
    code (does NOT actually place it — see Known Issue below)
  - `undo()`, `redo()`, `save_project()`
- **Confirmed end-to-end reasoning loop works**: typed "add an outlet" into
  ADK's dev UI → agent correctly called `search_catalog("outlet")` →
  correctly called `place_asset("OUT")`. This was the core proof-of-concept
  moment — the intent-to-action translation genuinely works.
- **Git set up, pushed to private GitHub repo** (`joecracker/weiscracker`).
  `venv/`, `.env`, and ADK's local `.adk/` session db are gitignored — only
  real code/data is tracked.

### 🚧 In progress / last known issue
**Immediate blocker as of last session:** a manual edit to `agent.py`'s
`root_agent = Agent(...)` instruction string introduced an unclosed-paren
syntax error. A corrected full block was provided to paste back in, but
**this was not yet confirmed fixed and re-tested** before the session ended.
**First thing to do on resume: verify `agent.py` compiles clean
(`python3 -m py_compile field_layout_tracker_agent/agent.py`) and that
"add an outlet" still works via `adk web`.**

Also mid-fix: the action tools were forcing completely empty final replies,
which ADK's web UI treats as an error (`MODEL_RETURNED_NO_CONTENT`). Fix in
progress was to instruct the model to always say a short word like "Done."
after acting instead of replying with nothing.

### ❌ Not started / known gaps
- **No real deployment.** No Cloud Run service exists yet. Everything has
  only been tested inside ADK's local dev UI (`adk web`), which is a
  developer tool, not a production endpoint.
- **No connection to the real app.** The actual Field Layout Tracker
  (live on Netlify) has zero code written to call Weiscracker. The loop has
  only been proven inside ADK's own test chat, never against the real app's
  UI/canvas.
- **No auth/API key layer.** Whenever this becomes a real Cloud Run service,
  it'll need a key so random people can't call it and burn through credit.
- Personality/smartass toggle — discussed, not implemented
- Conversational responses ("Added an outlet by the sink" instead of
  "Done.") — not implemented, currently forced to be terse
- Web search tool (Vertex Search grounding) — not started
- Schemas for the other 3 apps (Proposal App, Business Excel Sheet, Fantasy
  Football Drafting App) — not started, Field Layout Tracker is the only
  one built so far

---

## 5. Conventions & Gotchas

- **Naming:** use "Weiscracker" everywhere going forward (renamed from
  CRACKER). Old code/docs may still say CRACKER — that's stale, not a
  different project.
- **Tool function pattern:** "action" tools (the ones that represent a real
  app command) return a plain dict shaped like
  `{"function": "<jsFunctionName>", "args": {...}}`. This dict IS the
  contract with the receiving app — keep it consistent when adding new
  tools/apps.
- **`search_catalog` pattern:** internal-only tools (ones the agent uses to
  reason, that the receiving app never sees) return actual computed data
  (as a JSON string), not an action dict. Don't confuse the two shapes.
- **Gemini 3.x models ONLY work with `location="global"` on Vertex AI.**
  `us-central1` returns a 404 NOT_FOUND for `gemini-3.6-flash`. This ate a
  chunk of a session before being figured out — don't re-debug it.
- **Cloud Shell + ADK web requires `--allow_origins="*"`.** Omitting it
  causes a silent-ish 403 on session creation that looks like a code bug
  but isn't.
- **Large pastes into the Cloud Shell terminal are unreliable.** Multi-line
  heredocs with blank lines inside them (like a formatted Python file) get
  mangled mid-paste. For anything nontrivial (the catalog JSON, agent.py),
  use **Cloud Shell's Editor** (pencil icon next to the terminal icon) →
  right-click target folder → **Upload Files** (for existing files) or
  **New File** + paste + Ctrl+S (for new code) instead of terminal `cat >`.
- **`place_asset` is intentionally a two-step, human-in-the-loop flow.**
  The agent arms the tool with a code; the human still has to click the
  canvas to actually place it at a specific location. This was a deliberate
  decision — auto-guessing placement coordinates from vague language
  ("north wall," "center of room") was judged too unreliable and not worth
  building. Items are movable after placement anyway.
- **`pyjson5`** (imported as `import pyjson5`) was used once to parse the
  TypeScript-style `ASSET_CATALOG` array (unquoted-ish keys, trailing
  commas) into real JSON. It's an ETL tool, not a runtime dependency of the
  agent itself.
- **Working style:** Tim prefers one or two steps at a time with
  confirmation before moving on, casual/direct tone, copy-pasted terminal
  output over screenshots, and plain-text clarifying questions (not
  multiple-choice buttons).

---

## 6. Next Steps (priority order, if picking this up with full autonomy)

1. **Confirm the agent.py fix landed** — verify syntax compiles clean and
   re-run the "add an outlet" test in `adk web` to confirm the loop still
   works end to end with a non-empty final reply.
2. **Stand up a real HTTP endpoint**, not just the ADK dev UI. Either
   `adk api_server` or wrap `google.adk.cli.fast_api.get_fast_api_app()` in
   a small FastAPI app — something an external app can actually POST to.
3. **Deploy to Cloud Run.** This was always the target architecture; nothing
   has been deployed anywhere yet.
4. **Wire ONE real button in the real Field Layout Tracker app** to prove
   the full loop (voice/text → Weiscracker → real JSON → real app executes
   `place_asset()`) before building out more features. Don't add scope
   until this single real connection is proven.
5. **Add basic auth** (API key check) before the Cloud Run URL is anything
   other than 127.0.0.1-only.
6. Then, in whatever order Tim wants: personality/smartass toggle, web
   search tool, conversational (non-terse) responses, additional app
   schemas.

---

*If you're an AI reading this cold: don't assume anything beyond what's
written above is true. Ask Tim to confirm current state with a quick
`ls ~/cracker` and `cat field_layout_tracker_agent/agent.py` before making
changes — things may have moved on since this was last updated.*
