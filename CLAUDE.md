# Council of High Intelligence — Project Context Document

## Project Overview

**Council of High Intelligence** is a multi-persona AI deliberation system that convenes 18 distinct AI personas (modeled after historical thinkers and domain experts) to analyze complex decisions through structured, multi-round debate. It operates as a skill/plugin for AI coding assistants — primarily Claude Code, but also Codex and Gemini CLI.

The core value proposition: instead of one LLM giving a single confident answer, the council forces structured disagreement across multiple reasoning styles, with a Problem Restate Gate to catch bad questions early, cross-examination rounds to stress-test positions, and a deterministic weighted vote tally to reach verdicts.

**Repository:** `oldderekbomb-maker/council-of-high-intelligence`  
**License:** CC0 / MIT  
**Language:** Primarily Markdown + Bash (no compiled code)

---

## Architecture

### High-Level Structure

```
council-of-high-intelligence/
├── SKILL.md                    # Claude Code coordinator protocol (primary entry point)
├── SKILL.codex.md              # Codex-specific coordinator protocol
├── SKILL.gemini.md             # Gemini CLI-specific coordinator protocol
├── CLAUDE.md                   # AI assistant context for this repo itself
├── agents/                     # 18 individual persona definition files
│   └── council-<name>.md
├── configs/                    # Provider/model routing configuration templates
│   ├── auto-route-defaults.yaml
│   ├── provider-model-slots.example.yaml
│   ├── provider-model-slots.cursor.example.yaml
│   └── provider-model-slots.nim.example.yaml
├── demos/                      # Example prompts and scoring rubrics
│   ├── session-pack.md
│   └── verdict-template.md
├── reports/                    # Ad-hoc research and analysis documents (non-council output)
│   └── ukraine-war-report.md   # Curated Russia-Ukraine War developments report
├── scripts/                    # Validation and detection utilities
│   ├── council-simulation-checklist.sh
│   └── detect-providers.sh
└── install.sh                  # Installation script for all target platforms
```

### Core Components

#### 1. Coordinator Protocol (`SKILL.md`, `SKILL.codex.md`, `SKILL.gemini.md`)
The coordinator is an AI-executed protocol (not software) that:
- Parses invocation flags and selects the appropriate panel
- Runs a multi-step execution sequence with numbered STEPs and `[CHECKPOINT]`/`[VERIFY]` markers
- Enforces three deliberation modes: `full` (3-round), `quick` (2-round), `duo` (2-member dialectic)
- Manages provider routing across Claude, OpenAI, Gemini, Ollama, Cursor CLI, and NVIDIA NIM
- Synthesizes a final verdict via a designated Chairman model

#### 2. Agent Persona Files (`agents/council-*.md`)
Each file defines one council member with YAML frontmatter and structured sections:
- **Identity** — who this persona is
- **Grounding Protocol** — placed immediately after Identity (LLMs weight earlier instructions more heavily); includes specific numeric constraints (e.g., "maximum 2 analogies", "3-level depth limit")
- **Analytical Method** — how this persona thinks
- **What You See** — ≤3 sentences on strengths
- **What You Miss** — ≤3 sentences on blind spots
- **When Deliberating** — behavioral rules for council context
- **Output Format (Council Round 2)** — structured headers: `Disagree`, `Strengthened by`, `Position Update`, `Evidence Label`; Disagree prompt is tailored to each persona's epistemic lens
- **Output Format (Standalone)** — for use outside council context

#### 3. Provider Routing (`configs/`)
YAML configuration templates mapping council members to specific models and providers. Supports:
- `subagent` — Claude subagents
- `codex_exec` — Codex execution
- `gemini_cli` — Gemini CLI
- `ollama_run` — Local Ollama
- `openai_compatible_api` — OpenAI-compatible endpoints
- `cursor_cli` — Cursor agent (model aggregator)
- `nim` — NVIDIA NIM

Auto-routing spreads members across providers for genuine reasoning diversity.

#### 4. Installer (`install.sh`)
Bash script that copies files into platform-specific directories:
- Claude Code: `~/.claude/`
- Codex: `~/.codex/skills/council/`
- Gemini CLI: `~/.gemini/extensions/council-of-high-intelligence/skills/council/`

#### 5. Reports (`reports/`)
A `reports/` directory exists for ad-hoc research documents and curated analyses that are not council deliberation outputs. These are static Markdown documents committed directly to the repository. They do not follow the agent-file conventions and are not installed by `install.sh`. Currently contains:
- `ukraine-war-report.md` — Curated summary of Russia-Ukraine War developments

---

## The 18 Council Members

| Agent | Domain | Default Model Tier |
|---|---|---|
| `council-aristotle` | Categorization & structure | opus |
| `council-socrates` | Assumption destruction | opus |
| `council-sun-tzu` | Adversarial strategy | sonnet |
| `council-ada` | Formal systems & abstraction | sonnet |
| `council-aurelius` | Resilience & moral clarity | opus |
| `council-machiavelli` | Power dynamics & realpolitik | sonnet |
| `council-lao-tzu` | Non-action & emergence | opus |
| `council-feynman` | First-principles reasoning | sonnet |
| `council-torvalds` | Systems engineering & shipping | sonnet |
| `council-musashi` | Discipline & mastery | sonnet |
| `council-watts` | Systems thinking & paradox | sonnet |
| `council-karpathy` | ML engineering & intuition | sonnet |
| `council-sutskever` | AI research & alignment | opus |
| `council-kahneman` | Cognitive bias & decision science | sonnet |
| `council-meadows` | Systems dynamics & leverage | sonnet |
| `council-munger` | Mental models & inversion | opus |
| `council-taleb` | Uncertainty & antifragility | sonnet |
| `council-rams` | Design simplicity & function | sonnet |

---

## Deliberation Protocol

### Three Modes

| Mode | Rounds | Word Limits | Use When |
|---|---|---|---|
| `full` | 3 rounds | Full analysis | Hard, high-stakes decisions |
| `quick` | 2 rounds | 200-word analysis → 75-word position | Tactical questions |
| `duo` | 2 rounds | Dialectic only | Binary or polarity questions |

### Round Structure (Full Mode)

1. **STEP 0** — Panel selection; domain-weight seat (1.5×) designated *before* any positions exist
2. **STEP 1** — Problem Restate Gate: every member rephrases the question; if 3+ restate differently, the question is surfaced as the real problem
3. **STEP 2** — Round 1: independent analysis per member
4. **STEP 3** — Round 2: cross-examination with anonymized peer outputs (`Member A/B/C` labels); members must name a specific flaw in their own Round 1 argument before updating
5. **STEP 4** — Round 3: structured stance voting with machine-parseable output: `STANCE: <option> | CONFIDENCE: … | DEALBREAKER: …`
6. **STEP 5** — Vote tally: `W_option ≥ (2/3) × W_total` for consensus; genuine splits escalate to user
7. **STEP 6** — Chairman synthesis: performed by a named model not on the panel; produces final verdict

### Predefined Triads (20 domains)

`architecture`, `strategy`, `ethics`, `debugging`, `innovation`, `conflict`, `complexity`, `risk`, `shipping`, `product`, `founder`, `ai`, `ai-product`, `ai-safety`, `decision`, `systems`, `uncertainty`, `design`, `economics`, `bias`

### Polarity Pairs (for `--duo` mode)

- architecture/structure: `aristotle` + `lao-tzu`
- shipping/execution: `torvalds` + `musashi`
- strategy/competition: `sun-tzu` + `aurelius`
- ai/ml: `karpathy` + `sutskever`

### Panel Profiles

- `classic` — all 18 members
- `exploration-orthogonal` — 12 members (broad epistemic coverage)
- `execution-lean` — 5 members (torvalds, feynman, sun-tzu, aurelius, ada)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent definitions | Markdown with YAML frontmatter |
| Coordinator protocol | Markdown (AI-executed, not compiled) |
| Configuration | YAML |
| Installation | Bash (`install.sh`) |
| Validation | Bash (`scripts/`) |
| CI/CD | GitHub Actions (`.github/workflows/lint.yml`, `release.yml`) |
| Line endings | Enforced LF for `.sh`, `.yaml`, `.json`, `.md` via `.gitattributes` |

No runtime dependencies beyond the target AI platform (Claude Code, Codex, or Gemini CLI).

---

## Key Files Reference

| File | Purpose |
|---|---|
| `SKILL.md` | Primary coordinator — Claude Code invocation, full execution sequence, all flags, routing |
| `SKILL.codex.md` | Codex coordinator — same protocol adapted for Codex skill system |
| `SKILL.gemini.md` | Gemini CLI coordinator — same protocol adapted for Gemini extensions |
| `CLAUDE.md` | AI assistant context document for *this repo* (conventions, testing requirements) |
| `agents/council-*.md` | Individual persona definitions (18 files) |
| `configs/auto-route-defaults.yaml` | Default provider/model tier assignments and chairman defaults |
| `configs/provider-model-slots.example.yaml` | Template for manual provider/model mapping |
| `configs/provider-model-slots.cursor.example.yaml` | Cursor CLI provider mapping template |
| `configs/provider-model-slots.nim.example.yaml` | NVIDIA NIM provider mapping template |
| `demos/session-pack.md` | Example prompts aligned with active profiles and triads |
| `demos/verdict-template.md` | Scoring rubric and verdict output format |
| `reports/ukraine-war-report.md` | Curated Russia-Ukraine War developments report |
| `install.sh` | Installer for Claude/Codex/Gemini targets |
| `scripts/council-simulation-checklist.sh` | Post-change validation checklist |
| `scripts/detect-providers.sh` | Auto-detects available providers (checks binaries, env vars) |

---

## Coding Conventions

### Agent Files (`agents/council-*.md`)

- **Section order is mandatory:** Identity → Grounding Protocol → Analytical Method → What You See → What You Miss → When Deliberating → Output Format (Council Round 2) → Output Format (Standalone)
- **Grounding Protocol must immediately follow Identity** — LLMs weight earlier instructions more heavily; this placement is intentional
- **"What You See" and "What You Miss":** ≤3 sentences each, no exceptions
- **Grounding protocols use specific numeric constraints** — e.g., "maximum 2 analogies", "3-level depth limit" — not vague guidance like "be concise"
- **Council Round 2 output format** uses structured headers: `Disagree`, `Strengthened by`, `Position Update`, `Evidence Label`
- **"Disagree" prompt is tailored** to each agent's specific epistemic lens
- **No filler sentences** — keep prompts tight

### `SKILL.md` and Coordinator Files

- Coordinator instructions are an **execution sequence** with numbered STEPs and `[CHECKPOINT]`/`[VERIFY]` markers
- Reference tables (triads, profiles, polarity pairs) appear **below** the execution sequence, never mixed into it
- Three modes must always be present: `full`, `quick`, `duo`
- Flag priority is documented explicitly: mode flags → panel flags → routing flags → additive flags

### Configuration Files (`configs/`)

- Files are **templates only** (`.example.yaml` suffix for user-facing configs)
- `auto-route-defaults.yaml` is the canonical defaults file (not an example)
- Provider archetypes must be one of the defined types: `subagent`, `codex_exec`, `gemini_cli`, `ollama_run`, `openai_compatible_api`, `cursor_cli`, `nim`

### Reports (`reports/`)

- Plain Markdown documents; no YAML frontmatter required
- Not subject to agent-file section-order conventions
- Not installed by `install.sh` — repository reference material only
- Should include a datestamp or version note at the top so readers know how current the content is
- File naming: lowercase, hyphenated, descriptive (e.g., `ukraine-war-report.md`)

### Shell Scripts

- Use `set -euo pipefail` at the top of all scripts
- Prefer explicit error handling with user-facing messages to stderr
- Avoid hardcoded counts when files can be discovered dynamically
- Run `shellcheck` before committing installer changes

### General Style

- Keep `demos/session-pack.md` aligned with active profiles and triads whenever either changes
- Docs and installer behavior must stay in sync
- CHANGELOG follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format with Semantic Versioning

---

## Development Workflow

### Setup

```bash
git clone https://github.com/0xNyk/council-of-high-intelligence.git
cd council-of-high-intelligence
```

### Making Changes

```bash
# 1. Sync and branch
git checkout main && git pull origin main
git checkout -b feat/your-change

# 2. Make changes

# 3. Validate — ALWAYS run all three after changes
./scripts/council-simulation-checklist.sh
./install.sh --dry-run
./install.sh --dry-run --codex          # if Codex install was changed

# 4. Lint shell scripts (for install.sh changes)
shellcheck install.sh

# 5. Test at least one mode after protocol changes
# (manually invoke /council with full, quick, or duo mode)

# 6. Commit and PR to main
git add .
git commit -m "feat: clear description of change"
```

### Post-Merge Cleanup

```bash
git fetch origin --prune
git branch -d feat/your-change
```

### Testing Requirements Summary

| Change Type | Required Tests |
|---|---|
| Any change | `./scripts/council-simulation-checklist.sh` + `./install.sh --dry-run` |
| Codex install changes | Also run `./install.sh --dry-run --codex` |
| Protocol changes | Test at least one mode (full/quick/duo) manually |
| Installer changes | Also run `shellcheck install.sh` |
| Agent file changes | Verify section order and constraint specificity |
| Reports (`reports/`) | No automated tests required; verify Markdown renders correctly |

### CI/CD

- `.github/workflows/lint.yml` — runs on PRs (shellcheck, yaml linting)
- `.github/workflows/release.yml` — runs on version tags for release automation

---

## Important Design Decisions

### Why Grounding Protocol Comes Second
LLMs weight earlier instructions more heavily. Placing the Grounding Protocol immediately after Identity (before Analytical Method) ensures behavioral constraints are established before the persona's reasoning style is loaded.

### Why Domain-Weight Seat Is Designated at STEP 0
The 1.5× domain-weight seat is locked to a specific member *before any positions exist* to prevent the coordinator from retroactively choosing the heavyweight after seeing votes — which would introduce a subtle bias toward predetermined outcomes.

### Why Round 2 Uses Anonymized Peer Outputs
Peer outputs in Round 2 are masked behind `Member A/B/C` labels (based on Choi et al., arXiv:2510.07517 and Karpathy `llm-council`) to prevent authority bias — members updating because of *who* said something rather than *what* they said.

### Why Members Must Name a Flaw Before Updating
The anti-conformity directive (Round 2 requires naming a specific flaw in one's own Round 1 argument before updating) defends correct prior positions against social pressure (based on