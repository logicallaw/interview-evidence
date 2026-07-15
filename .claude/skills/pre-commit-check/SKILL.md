---
name: pre-commit-check
description: Use right before creating a commit to give the staged diff (`git diff --cached`) a lightweight human-reviewer pass. Trigger when the user says "commit this", "is this safe to commit?", "run pre-commit", or when the pre-commit hook asks for Claude verification. Only checks the two things that lint cannot: (1) secret / sensitive-data leaks and (2) commit-message quality. Stays lightweight on purpose — this is a quick second look, not a full review.
---

# Pre-Commit Check

Run right before a commit is created. Looks **only at staged changes** and verifies two things.

## 1. When to run

- The user says "commit this" / "is this safe to commit?" — run this **before** creating the commit
- The user explicitly asks "take a quick look at what's staged"

If there are no staged changes (`git diff --cached --quiet` returns true), exit immediately and do nothing.

## 2. The two checks

### Check 1 — Secret / sensitive-data leak

**Why this matters**: this project handles RTZR API credentials and Hugging Face tokens. These must never appear in commits.

Procedure:

1. Run `git diff --cached` and read the full staged diff.
2. Block the commit and report if any of the following appear:
   - **RTZR credentials**: `RTZR_CLIENT_ID` or `RTZR_CLIENT_SECRET` with hardcoded real values (not empty placeholders in `.env.example`)
   - **HF tokens**: `HF_TOKEN` with a real value, or strings matching `hf_...` pattern
   - **Named secrets with hardcoded values**: `apiKey = "..."`, `password = "..."`, `secret = "..."`, `token = "..."` where the value is real. Placeholder values like `"your-key-here"`, `""` are fine.
   - **`.env`-style files getting staged**: `.env`, `.env.prod`, `.env.local` — almost always a mistake.
   - **JWT / access-token shapes**: long base64 strings starting with `eyJ...`, or known prefixes like `sk-...`, `ghp_...`, `AKIA...`.
   - **Personal data**: real-looking emails, phone numbers, national IDs (clearly fake test fixtures are fine).
   - **Real interview recordings or transcripts**: actual interview content with real names or identifiable information.
3. When something is found, point to the exact file and line and let the user unstage it themselves. **Do not unstage automatically.**

**Judgment rule**: if in doubt, ask the user. A false positive costs a few seconds; a leaked secret costs much more.

### Check 2 — Commit message quality

**Why this matters**: this repo uses conventional prefixes (`feat:`, `fix:`, `docs:`, `refactor:`, ...).

Procedure:

1. Take the commit message (final or draft) the user wants to use.
2. Run `git log --oneline -10` to confirm the prefix style currently in use — match it exactly.
3. Compare the message against the staged diff and check:
   - **Wrong prefix**: e.g. `docs:` used for what is actually a new feature (`feat:`) or a bug fix (`fix:`).
   - **Too vague**: one-word messages like `update`, `fix`, `wip`.
   - **Mismatch with the diff**: the message says "add export" but the diff also touches RTZR client logic.
4. If something is off, **do not block** — propose 1 or 2 better messages and let the user pick.

**Judgment rule**: if the message is obviously fine, just pass it. Do not nitpick.

## 3. Output format

Keep the report short. If both checks pass, one line:

```
✅ pre-commit check passed (no secrets, commit message OK)
```

If something is off, 1–3 lines per check:

```
❌ Possible secret leak
  - .env:1 contains RTZR_CLIENT_ID with a real value
  - Action: unstage .env, add it to .gitignore

⚠️ Commit message suggestion
  - Current: "docs: add search module"
  - Suggested: "feat: add semantic search module" (the diff adds new functionality)
```

## 4. Do NOT do

- **No tests** — that belongs in pre-push. This step must stay fast.
- **No automatic fixes** — unstaging secrets or rewriting the message is the user's decision.
- **No style nitpicks** — naming, function length, comment style belong to the full `review` command, not here.

## 5. One-line summary

**This skill checks context — only two things, secrets and message, kept short.**
