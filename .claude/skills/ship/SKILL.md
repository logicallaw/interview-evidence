---
name: ship
description: >-
  이슈 생성 → 브랜치 → 커밋 → PR → 체크리스트 검증 → 머지의 전체 shipping
  워크플로우를 실행한다. "/ship" 또는 "ship it"으로 호출한다.
  단독 GitHub 작업(이슈 조회, PR 확인, CI 로그 등)도 지원한다.
allowed-tools: Bash
---

# Ship

이슈 생성부터 머지까지의 전체 shipping 워크플로우를 실행한다.

## Type Map

이슈 제목 prefix, 라벨, 브랜치 prefix, 커밋 prefix를 통합한다.

| type     | 이슈 제목    | 라벨            | 브랜치             | 커밋                  |
| -------- | ------------ | --------------- | ------------------ | --------------------- |
| feat     | `[Feature]`  | `feat`          | `feat/#N-slug`     | `feat(#N/scope):`     |
| fix      | `[Fix]`      | `fix`           | `fix/#N-slug`      | `fix(#N/scope):`      |
| docs     | `[Docs]`     | `documentation` | `docs/#N-slug`     | `docs(#N/scope):`     |
| chore    | `[Chore]`    | `chore`         | `chore/#N-slug`    | `chore(#N/scope):`    |
| refactor | `[Refactor]` | `refactor`      | `refactor/#N-slug` | `refactor(#N/scope):` |
| test     | `[Test]`     | `test`          | `test/#N-slug`     | `test(#N/scope):`     |

## 공통 설정

- **할당자**: `--assignee @me` (모든 이슈, PR에 자동 적용)
- **프로젝트**: `--project "Interview Evidence MVP"` (이슈, PR 모두)
- **라벨**: type map에서 자동 결정. 라벨이 없으면 `gh label create`로 먼저 생성.
- **이슈 템플릿**: `.github/ISSUE_TEMPLATE/`에서 type에 매칭되는 템플릿 사용
- **PR 템플릿**: `.github/pull_request_template.md` 사용
- **참조 컨벤션**: 이전 이슈(`gh issue list`)와 PR(`gh pr list`)의 제목·본문 스타일을 참고

## 6단계 워크플로우

각 단계는 승인 게이트가 있으며, 사용자 승인 없이 실행하지 않는다.

### Phase 1 — Issue

1. `gh issue list --state all --limit 5`로 기존 이슈 제목 컨벤션 확인
2. `.github/ISSUE_TEMPLATE/`에서 type에 맞는 템플릿 선택
3. 템플릿을 채워 이슈 초안 작성 (영어 섹션 제목, 한국어 본문)
4. 초안을 사용자에게 제시 → **승인 대기**
5. 승인 후 `gh issue create --title "..." --body-file /tmp/issue.md --assignee @me --label <label> --project "Interview Evidence MVP"`

### Phase 2 — Branch

1. `git checkout main && git pull origin main`
2. type map에 따라 브랜치명 결정: `<type>/#<issue-number>-<slug>`
3. `git checkout -b <branch>`

### Phase 3 — Commit

1. 코드 변경 완료 후, `git status`와 `git diff`로 변경 내용 확인
2. type map에 따라 커밋 메시지 결정: `<type>(#<issue>/<scope>): 한국어 설명`
3. 커밋 분할이 필요하면 분할 계획 제시 → **승인 대기**
4. **`pre-commit-check` 스킬을 참조하여** 시크릿 누출과 메시지 품질 확인
5. 승인 후 staging + commit 실행
6. 커밋 후 `git log --oneline -5` 표시

### Phase 4 — PR

1. `gh pr list --state all --limit 5`로 기존 PR 제목 컨벤션 확인
2. `.github/pull_request_template.md` 로드
3. PR 제목: `<type>(#<issue>): 한국어 설명` (70자 이하)
4. 본문: Summary, Related issue (`Closes #N`), Changes, Verification, Checklist 작성
5. 초안을 사용자에게 제시 → **승인 대기**
6. **`pre-push-check` 스킬을 참조하여** 테스트 통과와 문서 동기화 확인
7. `git push -u origin <branch>`
8. `gh pr create --title "..." --body-file /tmp/pr.md --assignee @me --label <label> --project "Interview Evidence MVP"`

### Phase 5 — Verify

1. `gh issue view <N> --json body`로 이슈의 Acceptance criteria 체크리스트 로드
2. 각 항목을 코드와 테스트 결과로 검증
3. 검증 결과를 사용자에게 보고 → **승인 대기**
4. 승인 후 이슈 본문의 `- [ ]`를 `- [x]`로 갱신: `gh issue edit <N> --body-file /tmp/issue-updated.md`

### Phase 6 — Merge

1. PR 머지: `gh pr merge <pr-number> --merge --delete-branch`
2. `git checkout main && git pull origin main`
3. 테스트 실행: `python -m pytest`
4. 이슈 자동 종료 확인 (`Closes #N`이 PR에 있으므로)
5. 최종 상태 보고

## 상태 감지 (중간 진입)

워크플로우 중간에서 재개할 수 있도록 현재 상태를 자동 감지한다:

- 이슈 번호가 주어지면 → 해당 이슈의 브랜치/PR 존재 여부 확인
- 브랜치가 이미 있으면 → Phase 3(커밋)부터
- PR이 이미 있으면 → Phase 5(검증)부터
- 미커밋 변경이 있으면 → Phase 3(커밋)부터

## 단독 GitHub 작업

워크플로우 외에 다음 단독 작업도 지원한다:

```bash
# 이슈
gh issue list/view/comment/close

# PR
gh pr list/view/checks/diff/comment

# CI
gh run list/view --log-failed

# API
gh api repos/{owner}/{repo}/...

# 인증
gh auth status
```

`--body-file`을 사용해 백틱, 셸 스니펫, 사용자 텍스트가 포함된 본문을 전달한다.

## 안전 규칙

- `CLAUDE.md`의 Git Workflow (섹션 6), PR & Merge (섹션 7), Approval Workflow (섹션 9) 규칙을 모두 따른다.
- Force push 금지. `--no-verify` 금지 (사용자 명시 요청 제외).
- `.env`, 시크릿 파일 staging 금지.
- 기본 머지 전략: merge commit. squash는 사용자 명시 요청 시에만.
- 모든 생성 작업(이슈, 커밋, PR)은 초안 제시 후 승인을 받아야 실행.
- `git add` 또는 `git commit`을 사용자 승인 전에 실행하지 않는다.
- 커밋 메시지는 HEREDOC으로 전달한다.
- 커밋 실패 시 amend가 아닌 새 커밋을 생성한다.
