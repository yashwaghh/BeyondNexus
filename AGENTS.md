# PrivacyGate — Agent Operating Manual

**Purpose:** coordinate human and coding agents across iterations without losing project context or confusing a passing unit test with privacy certification. This file describes *roles and instructions*, not background agents that autonomously execute.

## Mandatory first-read sequence

`CONTEXT.md` → `IMPLEMENTATION.md` → `THREAT_MODEL.md` → `PROGRESS.md` → assigned files. Do not assume the latest conversation is an enduring source of truth; persist accepted changes to these files.

## Agents and ownership

### 1. Coordinator / Planner
- Owns iteration scope, milestone acceptance and task dependencies.
- Reads all docs, identifies constraints (8 GB Mac, text-only, local LM Studio).
- Splits tasks into small measurable checkpoints; lists missing evidence.
- Updates `CONTEXT.md` only for confirmed decisions; updates `PROGRESS.md` after each milestone.
- **Never** declare privacy guaranteed, model tested, or extension integrated without evidence.

### 2. Deterministic Detection Engineer
- Owns `privacygate/detectors.py` and `tests/test_detectors.py`.
- Rules: compare format, boundaries, context, checksums, false-positive cases. Do not treat arbitrary digits as a bank account without context.
- Test different textual contexts and mixed whitespace using synthetic data.
- Report known unsupported formats and actual benchmark outcomes.

### 3. Local Model / Fallback Engineer
- Owns `privacygate/model.py` and mock/model interface tests.
- Ensures loopback-only endpoint, correct Gemma 4 model ID, valid JSON and exact-span validation.
- Collects latency/quality evidence locally without storing prompts, full completions or sensitive text.
- **Fail closed** when model required but unavailable. No hosted model fallback.

### 4. Orchestrator / UX Engineer
- Owns `privacygate/pipeline.py` and `privacygate/__main__.py`.
- Enforces rule → uncertainty → model → validation → masking → user gate ordering.
- Never automatically forward results externally. Make limitations and user approval visible.
- For future task-aware work, distinguish required task features from direct identifiers, do not let model bypass deterministic high-risk masking.

### 5. Security Reviewer
- Owns `THREAT_MODEL.md` and adversarial tests.
- Review prompt-injection surfaces, outbound requests, logs, masked strings, residual leaks, line/offset integrity, export APIs and future extension origins.
- Use only synthetic test data. Escalate unsafe defaults to Coordinator.

### 6. Independent Validation Agent (final gate)
- Uses executable `scripts/validate_iteration.py` plus separate live hardware checks.
- Must not rely on a coding agent's claims. Run: `python scripts/validate_iteration.py --record`.
- Check acceptance matrix in `IMPLEMENTATION.md` and verify documented unimplemented items remain unclaimed.
- Verify local-model live tests on developer Mac separately and mark status **UNVERIFIED** until done.
- Returns `PASS`, `FAIL` or `PARTIAL`, with specific unmet gates; no automatic cloud sending or deployment.

## Agent-to-agent handoff format (copy into PROGRESS.md)

```markdown
### YYYY-MM-DD HH:MM TZ — [AGENT] — [TASK]
- Goal:
- Files changed:
- Test command and result:
- Evidence (synthetic only):
- Risks / unfinished:
- Next owner and specific action:
```

## Definition of independent validation

The validator checks `README`, specs, package, tests and availability of contract files, runs unit tests and prints aggregate results. It **does not** run live LM Studio by default; models are on the developer's hardware and are not available inside a generated artifact. A live test requires a developer-run smoke test, timings and manual review of generated spans.

**Iteration cannot be marked complete unless:**
1. Unit test suite passes.
2. Status and fail-closed conditions are working.
3. No hosted endpoint is configured or invoked.
4. Instructions are reproducible and have no hidden prerequisites.
5. Manual tests show expected samples locally.
6. Actual Gemma local inference, if advertised as 'working', has been witnessed and documented.
7. Every known gap is explicit in `PROGRESS.md`.

## Request template for a coding agent

> Read CONTEXT.md, IMPLEMENTATION.md, AGENTS.md, PROGRESS.md and THREAT_MODEL.md. Implement only the assigned item. No real PII, no cloud model calls, no auto-sharing, no undisclosed dependency changes. Add synthetic tests, run validator, append evidence to PROGRESS.md, and explicitly list what remains unverified. Do not alter the core trust boundaries without proposing an ADR.

## Next-iteration policy

No agent builds browser interception or hosted deployment until the Coordinator approves `NEXT_ITERATION.md` and the V1 validator gates are satisfied. It is acceptable to create a plan now, but not to claim this plan is functioning code.
