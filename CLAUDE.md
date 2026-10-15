# AquaBle

Home Assistant custom integration for Chihiros aquarium LED lights and dosing pumps over Bluetooth Low Energy, plus two Lovelace cards.

## Layout

- `custom_components/aquable/` – the integration
  - `commands/` – BLE frame encoding (`encoder.py`), command sequences (`generators.py`), telemetry parsing (`parsers.py`)
  - `domain/` – dataclasses for light/doser status and schedules
  - `coordinator.py` – polling + BLE connection, `services.py` / `services.yaml` – HA actions
  - `sensor.py` – entities (incl. `*_active_schedules`, live channel brightness)
  - `frontend/` – Lit-based Lovelace cards (plain ES modules, no build step)
- `BLE_Protocol.md` – reverse-engineered protocol reference. **Source of truth for byte layouts**; update it when you learn something new about the hardware.
- `STATUS.md` – known issues and firmware quirks. `CHANGELOG.md` – user-facing changes.
- `scripts/` – diagnosis tools for talking to real devices.

## Local checks

Run all of these before pushing:

```bash
uv sync --group dev
uv run ruff check .
uv run ruff format --check .
for f in custom_components/aquable/frontend/*.js; do node --input-type=module --check < "$f" || echo "FAIL $f"; done
uv run pytest            # once the test suite from #7 exists
```

CI (GitHub Actions) runs the same checks on every PR.

## Conventions

- Python ≥ 3.12, ruff rules `E, F, I, W`, line length 100.
- Match the style of the surrounding code: naming, comment density, idioms.
- Hardware behaviour that is not confirmed by a capture is an **assumption** – say so in code comments, issues and PRs, never present it as fact.
- New or changed HA services need `services.yaml` (and `strings.json` where applicable) entries and a README mention.
- User-visible changes get a `CHANGELOG.md` entry.
- Never put AI model identifiers in commits, PRs, code or docs.

## Issue-driven workflow

All work starts from a GitHub issue on `mmans/AquaBle`. Three Claude Code agents live in `.claude/agents/`:

| Agent | Role |
|---|---|
| `architect` | Discusses features with the maintainer, creates **draft** issues. Never writes code. |
| `dev` | Refines drafts with the maintainer; implements ready issues on a branch. Never opens PRs. |
| `reviewer` | Reviews the branch against the issue; opens the PR when OK, otherwise sends it back. Never pushes code. |

Slash commands in `.claude/commands/` start each step:

| Command | What it does |
|---|---|
| `/brainstorm <idea>` | Architect: discuss a feature, then create draft issues |
| `/refine #<n>` | Dev, refine mode: draft → ready |
| `/next-issue [#<n>]` | Dev, implement mode: ready → in-review (picks the next unblocked issue if no number is given) |

### Issue lifecycle (labels)

```
status:draft ──(dev refine + maintainer OK)──▶ status:ready
status:ready ──(dev starts)──▶ status:in-progress
status:in-progress ──(dev pushes branch)──▶ status:in-review
status:in-review ──(reviewer: changes needed)──▶ status:in-progress
status:in-review ──(reviewer: OK, opens PR)──▶ closed when PR merges
```

Only one `status:*` label per issue at a time. Other labels:

- `type:feature`, `type:scaffolding`, `type:investigation`
- `area:backend`, `area:frontend`, `area:ci`, `area:agents`

Issue bodies use the sections **Context / Goal / Scope / Acceptance criteria / Open questions / Dependencies** (see `.github/ISSUE_TEMPLATE/feature_draft.yml`). Dependencies are written as `Depends on #n`.

### Branches, commits, PRs

- Branch from `main`: `issue-<n>-<short-slug>` (e.g. `issue-11-auto-profile-service`).
- Commit messages are imperative and reference the issue: `Add light_set_auto_profile service (#11)`.
- One issue per branch/PR unless issues are explicitly bundled.
- PR body follows `.github/pull_request_template.md` and contains `Closes #<n>`.

### GitHub CLI cheatsheet

```bash
gh issue list -R mmans/AquaBle --label status:draft
gh issue view <n> -R mmans/AquaBle --comments
gh issue edit <n> -R mmans/AquaBle --remove-label status:draft --add-label status:ready
gh issue edit <n> -R mmans/AquaBle --body-file body.md
gh issue comment <n> -R mmans/AquaBle --body-file comment.md
```
