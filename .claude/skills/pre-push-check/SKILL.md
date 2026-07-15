---
name: pre-push-check
description: Use right before pushing one or more commits to remote. Trigger when the user says "push it", "is this ready to push?", "run pre-push", or when the pre-push hook asks for Claude verification. Does two heavier checks that pre-commit deliberately skipped: (1) make sure the test suite actually passes, and (2) make sure any code change that affects documented behavior is reflected in `docs/`.
---

# Pre-Push Check

Run right before `git push`. Looks at **all commits that are about to be pushed** (`origin/<branch>..HEAD`) and verifies two things.

Pre-commit stays light. This step is allowed to be slower because pushing is a less frequent action and the cost of pushing a broken build is high.

## 1. When to run

- The user says "push it" / "is this ready to push?" — run this **before** `git push`
- The user explicitly asks "double-check before I push"

If there is nothing to push (`git log origin/<branch>..HEAD` is empty), exit immediately.

## 2. The two checks

### Check 1 — Tests pass

Procedure:

1. Run `python -m pytest tests/`.
2. Wait for the run to finish. Do not assume success from a partial log.
3. Read the final summary:
   - All tests green → pass this check.
   - Failures → list each failing test file + function + the first useful line of the failure. Block the push.
   - Import errors or missing deps → report exactly which module/line and block.
4. If a test was **newly added in the pushed commits** but skipped (`@pytest.mark.skip`, `pytest.skip()`), flag it. Reaching push time with disabled new tests is almost always unintentional.

**Judgment rule**: do not retry on flaky failures automatically. Report the failure and let the user decide.

### Check 2 — Docs stay in sync with code

**Why this matters**: this repo keeps project documentation under `docs/` (ARCHITECTURE.md, PRD.md, ADR.md, etc.) and `CLAUDE.md`. When code changes the documented behavior but the doc is not updated, the doc rots silently.

Procedure:

1. Get the diff for the commits about to be pushed:
   ```bash
   git diff origin/<branch>..HEAD
   ```
2. Identify code changes that **could affect documented behavior**:
   - New / changed / removed API call patterns in `src/rtzr_client.py` (RTZR endpoints, config)
   - Changed module interfaces in `src/` (function signatures, class APIs)
   - Changed data flow (new modules, removed modules, changed pipeline)
   - New environment variables or changed `.env.example`
3. For each such change, check whether the corresponding doc was updated **in the same push**:
   - Module interface changes → must be reflected in `docs/ARCHITECTURE.md`
   - New architectural decisions → must be reflected in `docs/ADR.md`
   - Feature changes → must be reflected in `docs/PRD.md`
   - RTZR API usage changes → must be reflected in `docs/ARCHITECTURE.md` RTZR section
4. For every mismatch found:
   - Point out the code change (file + line) and the doc section that is now stale.
   - **Propose a concrete doc edit** (the exact lines to add / change in the doc file).
   - Ask the user to confirm before applying. Apply only after confirmation.
5. If the docs were already updated in the same push, say so explicitly and move on.

**Judgment rule**: only flag changes that affect **externally observable behavior or architecture**. Internal refactors (renaming a local variable, splitting a helper) do not need doc updates.

## 3. Output format

If both checks pass:

```
✅ pre-push check passed
  - Tests: 12 passed, 0 failed
  - Docs: in sync (no public-surface change, or already updated in this push)
```

If something is off:

```
❌ Tests failing
  - tests/test_segments.py::test_merge_short_utterances
    → AssertionError: expected 3 segments, got 5 at segments.py:42
  - Action: fix and re-run before pushing

⚠️ Docs out of sync
  - Code: added domain parameter to transcribe() in src/rtzr_client.py:55
  - Doc:  docs/ARCHITECTURE.md RTZR config section has no domain parameter
  - Proposed addition (apply? y/N):
        domain 파라미터 추가: "GENERAL" (대면 녹음) 또는 "CALL" (전화 면접)
```

## 4. Do NOT do

- **No secret / commit-message check** — that already ran in pre-commit. Do not re-do it.
- **No automatic code fixes** — fixing failing tests is the user's job.
- **No silent doc edits** — always show the proposed diff and wait for confirmation.
- **No retry on flaky tests** — surface the failure honestly.
- **No scope creep** — do not touch docs that have nothing to do with the pushed changes.

## 5. One-line summary

**Pre-commit was the fast lane. Pre-push is the slow lane — tests must actually pass, and docs must actually match the code.**
