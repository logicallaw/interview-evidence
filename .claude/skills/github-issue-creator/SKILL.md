---
name: github-issue-creator
description: Convert raw notes, error logs, voice dictation, or screenshots into crisp GitHub-flavored markdown issue reports. Use when the user pastes bug info, error messages, or informal descriptions and wants a structured GitHub issue. Supports images/GIFs for visual evidence.
---

# GitHub Issue Creator

Transform messy input (error logs, voice notes, screenshots) into clean, actionable GitHub issues.

## Template Selection

1. Inspect the repository for issue templates in these supported locations:
   - `.github/ISSUE_TEMPLATE/`
   - `ISSUE_TEMPLATE/`
   - `docs/ISSUE_TEMPLATE/`
2. Ignore `config.yml`. Prefer a relevant Markdown template when one clearly matches the request.
3. If multiple templates plausibly match and the choice changes the required content, ask the user which one to use.
4. If only a YAML issue form matches, mirror its required fields in Markdown without inventing answers.
5. If no repository template matches, use `assets/issue-template.md` from this skill.

## Workflow

1. Generate a concise title from the confirmed facts.
2. Fill the selected template from the user's notes, logs, screenshots, and repository context.
3. Mark unknown required values with explicit placeholders such as `[VERSION]`; never guess them.
4. Remove comments, empty optional sections, and unused placeholders before publishing.
5. Preserve logs verbatim only after removing secrets and sensitive identifiers.

## Output Location

For a draft, create a Markdown file in `/issues/` at the repository root using `YYYY-MM-DD-short-description.md`. When the user asks to publish, pass the completed body file to the `github` skill and create the issue with `gh issue create --body-file`.

## Guidelines

**Be crisp**: No fluff. Every word should add value.

**Extract structure from chaos**: Voice dictation and raw notes often contain the facts buried in casual language. Pull them out.

**Infer missing context**: If user mentions "same project" or "the dashboard", use context from conversation or memory to fill in specifics.

**Placeholder sensitive data**: Use `[PROJECT_NAME]`, `[USER_ID]`, etc. for anything that might be sensitive.

**Match severity to impact**:
- Critical: Service down, data loss, security issue
- High: Major feature broken, no workaround
- Medium: Feature impaired, workaround exists
- Low: Minor inconvenience, cosmetic

**Image/GIF handling**: Reference attachments inline. Format: `![Description](attachment-name.png)`
