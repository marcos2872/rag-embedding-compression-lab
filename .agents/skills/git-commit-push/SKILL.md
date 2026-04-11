---
name: git-commit-push
description: "Analyze staged/unstaged Git changes, generate a Conventional Commits summary and description, execute the commit, push to the remote repository, and optionally create a GitHub Pull Request. Use when: committing code, generating commit messages, pushing to Git, creating conventional commit messages from diffs, saving changes, preparing a Git commit with summary and body, opening a pull request, creating a PR after push."
argument-hint: "Optionally specify: commit type override (feat, fix, refactor…), scope override (backend, frontend…), target branch, or '--pr' to also create a Pull Request"
---

# Git Commit, Push & Pull Request — Conventional Commits Generator

Analyze the current Git working tree (staged and unstaged changes), generate a well-structured commit message following the **Conventional Commits** specification, execute `git commit`, `git push` to the remote repository, and optionally create a **GitHub Pull Request** via the `gh` CLI.

## When to Use

- After making code changes that need to be committed and pushed
- When you want an automated, well-crafted conventional commit message derived from the actual diff
- When you want to commit, push, **and open a Pull Request** in a single flow
- Before a code review, to ensure clean commit history with meaningful messages
- Any time the user says "commit", "push", "save my changes", "create a PR", "open a pull request", or similar

## Inputs

| Input | Required | Default | Example |
|-------|----------|---------|---------|
| Branch name | No | current branch | `feat/new-upload` |
| Commit type override | No | auto-detected from diff | `feat`, `fix`, `refactor` |
| Scope override | No | auto-detected from paths | `backend`, `frontend`, `costs` |
| Push after commit | No | `true` | `false` |
| Amend last commit | No | `false` | `true` |
| Additional context | No | — | `"This fixes the login timeout bug"` |
| Create Pull Request | No | `false` (ask if user mentions PR) | `true` |
| PR base branch | No | `main` | `main`, `dev` |
| PR reviewers | No | — | `username1,username2` |
| PR labels | No | auto-detected from type | `enhancement`, `bug` |
| PR draft | No | `false` | `true` |

## Conventional Commits Specification

This project follows [Conventional Commits v1.0.0](https://www.conventionalcommits.org/).

### Message Format

```
<type>(<scope>): <summary>
                                        ← blank line
<body>
                                        ← blank line
<footer(s)>
```

### Allowed Types

| Type | When to Use |
|------|-------------|
| `feat` | A new feature or capability |
| `fix` | A bug fix |
| `refactor` | Code restructuring without behavior change |
| `docs` | Documentation-only changes |
| `style` | Formatting, whitespace — no logic change |
| `test` | Adding or updating tests |
| `chore` | Tooling, configs, dependency bumps |
| `ci` | CI/CD pipeline changes (GitHub Actions, Docker, Nginx) |
| `perf` | Performance improvements |
| `build` | Build system or external dependency changes |
| `revert` | Reverting a previous commit |

### Scope Detection — Path-to-Scope Map

Derive the scope from the **directories** where changes were made.
Use the directory structure declared in the project's **AGENTS.md** as the primary reference.

**Generic heuristics (adapt to the project's actual layout):**

| Changed Path Pattern | Scope |
|---------------------|-------|
| Domain / business logic layer | `domain` |
| Application / use-case layer | `application` |
| Infrastructure / adapters layer | `infra` |
| HTTP handlers / controllers / routers | module name (e.g. `auth`, `users`, `orders`) |
| Database models / migrations | `models` or `migration` |
| Frontend components / UI | `ui` |
| Frontend pages / routes | `pages` |
| Frontend API client layer | `api` |
| Frontend hooks | `hooks` |
| Tests | `tests` |
| CI/CD (`.github/workflows/`, `Dockerfile`) | `ci` |
| Agent configs (`.agents/**`) | `agents` |
| Documentation (`docs/**`) | `docs` |
| Changes in multiple unrelated areas | use the dominant one, or **omit scope** |

**Sub-directory refinement:** When changes are concentrated inside a single feature or module, use that feature name as scope (e.g., `auth`, `checkout`, `dashboard`).

### Summary Line Rules

- **Imperative mood**: "add", "fix", "update" — NOT "added", "fixes", "updated"
- **≤ 72 characters** for the entire first line (`type(scope): summary`)
- **Lowercase** first word after the colon
- **No trailing period**
- Be specific: `fix null pointer on product clone` not `fix bug`

### Body Rules

- Separated from summary by **one blank line**
- Lines wrapped at **100 characters**
- Explain **what** changed and **why** — not how (the diff shows how)
- Use bullet points (`-`) for multiple changes
- Group by service tag when changes span multiple services

### Footer Rules

- `BREAKING CHANGE: <description>` for non-backward-compatible changes (also mark summary with `!`: `feat(backend)!: ...`)
- `Refs: #<issue>` for related issues or Azure DevOps work items
- `Co-authored-by: Name <email>` for pair programming

## Procedure

### Step 1 — Assess Repository State

Run all three commands to build a full picture:

1. `git status` — identify staged files, unstaged modifications, untracked files, and any merge conflicts.
2. `git branch --show-current` — identify the active branch.
3. `git log --oneline -5` — recent commit history for contextual continuity.

**Stop conditions:**
- If the working tree is completely clean → inform the user: *"Nothing to commit — working tree is clean."* and stop.
- If there are **merge conflicts** → list conflicted files and instruct the user to resolve them before committing. Stop.
- If on a **detached HEAD** → warn the user and suggest `git checkout -b <name>` before proceeding.

### Step 2 — Stage Files

Decide what to stage:

| Scenario | Action |
|----------|--------|
| User said "commit everything" / "commit all" | `git add -A` |
| There are already staged files and nothing else changed | Proceed with current staging |
| There are unstaged/untracked files | **Ask the user**: stage all (`git add -A`), stage specific files, or proceed with only already-staged files |

After staging, run `git diff --cached --name-only` to confirm the final staged file list.

### Step 3 — Analyze the Diff

1. Run `git diff --cached --stat` — high-level summary: files changed, insertions (+), deletions (-).
2. Run `git diff --cached` — full diff of all staged changes.
3. **If the diff exceeds ~500 lines**, analyze incrementally:
   - Use the `--stat` output to identify files
   - Run `git diff --cached -- <file>` for each important file
   - Prioritize business logic files over auto-generated or config files
4. For **each changed file**, extract:
   - **What** changed (new class, modified method, new component, deleted file, config change, migration, etc.)
   - **Why** it changed (new feature, bug fix, refactor, dependency update, etc.)
   - **Which service/domain** it belongs to (using the path-to-scope map)

### Step 4 — Determine Commit Type and Scope

#### 4a — Auto-detect Type

Apply these heuristics **in priority order** (first match wins):

| Priority | Signal | Type |
|----------|--------|------|
| 1 | `revert` in branch name or user instruction | `revert` |
| 2 | New files with business logic, endpoints, components, migrations | `feat` |
| 3 | Changes fixing defects, null checks, error handling, wrong behavior | `fix` |
| 4 | Structural changes with no behavior difference | `refactor` |
| 5 | Only test files (`*Test.java`, `*.test.ts`, `*.spec.ts`) | `test` |
| 6 | Only documentation (`.md`, Javadoc, comments, Swagger annotations) | `docs` |
| 7 | Only CI/CD (`.github/workflows/`, `Dockerfile`, `docker-compose*`) | `ci` |
| 8 | Only build/config (`build.gradle`, `package.json`, `next.config`, `tsconfig`) | `build` |
| 9 | Only formatting, whitespace, semicolons, import ordering | `style` |
| 10 | Caching, query optimization, lazy loading, memoization | `perf` |
| 11 | Dependency updates, tooling, `.gitignore`, linting config | `chore` |

#### 4b — Auto-detect Scope

Use the path-to-scope map from above. If changes touch exactly **one domain sub-package**, use that domain (e.g., `costs`) instead of the service name.

#### 4c — Override

If the user explicitly provided a type or scope, use their value.

#### 4d — Multiple Scopes

If changes span 3+ unrelated scopes → omit the scope entirely: `feat: add template setup wizard and slide preview`.

### Step 5 — Check for Unrelated Changes (Split Suggestion)

If the diff contains **clearly unrelated logical changes** (e.g., a bug fix in an auth module AND a new feature in the UI layer):

1. **Suggest splitting** into separate commits for a cleaner history.
2. Present a proposed split plan based on the actual changed files:
   ```
   Commit 1: fix(auth): handle expired token on refresh
     - <path to auth file>

   Commit 2: feat(ui): add new feature component
     - <path to UI file>
   ```
3. **Ask the user** whether to split or commit together. If together, summarize the overall intent in a single message.

### Step 6 — Generate Commit Message

#### 6a — Summary Line

```
<type>(<scope>): <imperative verb> <concise description>
```

Examples:
- `feat(templates): add slide preview endpoint`
- `fix(domain): handle empty placeholder in table renderer`
- `refactor(infra): extract LLM retry logic into base client`
- `ci: add ruff lint step to PR workflow`

#### 6b — Body

**For single-service changes:**
```
<Why this change was needed — 1-2 sentences>

- <Specific change 1>
- <Specific change 2>
- <Specific change 3>
```

**For multi-layer changes:**
```
<Overall motivation — 1-2 sentences>

- [domain] <what and why>
- [backend] <what and why>
- [frontend] <what and why>
```

**For database migrations:**
```
Add Alembic migration: <description>

- <Table/column changes>
- <Data migration notes if any>
- <Rollback considerations>
```

#### 6c — Footer

- Add `BREAKING CHANGE: <description>` if any public API, database schema, or shared DTO changed in a non-backward-compatible way.
- Add `Refs: #<number>` for related issues/work items.

### Step 7 — Present Message and Wait for Confirmation

Display the complete commit message to the user in a clear visual block:

```
┌─────────────────────────────────────────────────────────┐
│  feat(auth): add token refresh endpoint                 │
│                                                         │
│  Allow clients to obtain a new access token using a     │
│  valid refresh token without re-authenticating.         │
│                                                         │
│  - Add POST /auth/refresh route                         │
│  - Rotate refresh token on every use                    │
│  - Revoke old token after successful rotation           │
│                                                         │
│  Refs: #42                                              │
└─────────────────────────────────────────────────────────┘
```

Also display:
- **Files:** N files staged (list them briefly)
- **Branch:** `<current-branch>`
- **Action:** Commit + Push to `origin/<current-branch>` (or "Commit only" if push=false)

**⚠️ WAIT for explicit user confirmation before executing.** If the user requests changes, adjust the message and present again.

### Step 8 — Execute Commit

After confirmation:

1. Write the message to a temp file (preserves multi-line formatting reliably):
   ```bash
cat <<'COMMITMSG' > /tmp/pi-commit-msg.txt
<type>(<scope>): <summary>

<body>

<footer>
COMMITMSG
```

2. Execute the commit:
   ```bash
   git commit -F /tmp/pi-commit-msg.txt
   ```

3. If amend was requested:
   ```bash
   git commit --amend -F /tmp/pi-commit-msg.txt
   ```

4. Clean up:
   ```bash
   rm -f /tmp/pi-commit-msg.txt
   ```

5. Verify success:
   ```bash
   git log --oneline -1
   ```

### Step 9 — Push to Remote

If push is enabled (default):

1. Determine if upstream exists:
   ```bash
   git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null
   ```

2. Push accordingly:
   - **Has upstream:** `git push`
   - **No upstream:** `git push -u origin <current-branch>`

3. **If push fails (non-fast-forward):**
   - Inform the user the remote has diverged.
   - Suggest: `git pull --rebase origin <branch>` then retry.
   - Only suggest `git push --force-with-lease` if the user explicitly requests force-push.

4. Verify push:
   ```bash
   git log --oneline origin/<branch>..<branch>
   ```
   (Should show 0 commits ahead after a successful push.)

### Step 10 — Create Pull Request (optional)

If the user requested a Pull Request (said "PR", "pull request", or provided `--pr`), **or** if the current branch is a feature/fix branch and the push succeeded, **ask the user** whether they'd like to open a PR.

#### 10a — Prerequisites

1. Confirm `gh` CLI is available: `which gh`.
2. Confirm authentication: `gh auth status`.
   - If not authenticated → instruct the user to run `gh auth login` and stop.
3. Confirm push completed successfully (Step 9).
4. Confirm the current branch is **not** the base branch itself (do not PR `dev` into `dev`).

#### 10b — Determine PR Base Branch

Use this project's branching strategy to auto-detect the base:

| Current Branch Pattern | Default Base | Triggers |
|------------------------|-------------|----------|
| `feat/*`, `fix/*`, `refactor/*`, `chore/*`, `test/*`, `docs/*` | `main` | Default integration branch |
| Any other | `main` | Safe default |

If the user explicitly provided a base branch, use their value instead.

#### 10c — Check for Existing PR

Before creating, check if a PR already exists for this branch:

```bash
gh pr list --head <current-branch> --base <base-branch> --state open --json number,title,url
```

- If an **open PR already exists** → show its URL and ask if the user wants to update it or skip.
- If no open PR → proceed to create.

#### 10d — Generate PR Title and Body

**PR Title:** Reuse the commit summary line (the first line of the commit message):
```
feat(templates): add slide preview endpoint
```

**PR Body:** Generate a structured Markdown body:

```markdown
## Description

<Expanded version of the commit body — what changed and why>

## Changes

- <Bullet list of key changes, grouped by layer if multi-layer>

## Type of Change

- [ ] New feature (`feat`)
- [ ] Bug fix (`fix`)
- [ ] Refactor (`refactor`)
- [ ] Documentation (`docs`)
- [ ] Tests (`test`)
- [ ] Chore / Config (`chore`, `build`, `ci`)
- [ ] Performance (`perf`)

> Check the one that applies (auto-checked based on commit type).

## Layers Affected

> List the layers/modules changed, based on the project structure declared in AGENTS.md.

- [ ] Domain / business logic
- [ ] Application / use cases
- [ ] Infrastructure / adapters
- [ ] Backend / API handlers
- [ ] Frontend / UI
- [ ] Database / migrations
- [ ] CI / Agents / Config

> Check all that apply (auto-checked based on changed files).

## Testing

- [ ] Unit tests added/updated
- [ ] Manual testing performed locally
- [ ] No breaking changes to existing APIs

## Related

- Refs: #<issue-number> (if any)
```

Auto-check the applicable checkboxes based on the commit type and changed files.

#### 10e — Present PR for Confirmation

Display the PR details:

```
┌─────────────────────────────────────────────────────────┐
│  Pull Request                                           │
│                                                         │
│  Title:  feat(templates): add slide preview endpoint    │
│  Base:   main  ←  feat/slide-preview                    │
│  Draft:  No                                             │
│  Labels: enhancement                                    │
│                                                         │
│  Body: (see generated description above)                │
└─────────────────────────────────────────────────────────┘
```

**⚠️ WAIT for user confirmation before creating.** If the user requests changes, adjust and present again.

#### 10f — Create the PR

After confirmation, write the PR body to a temp file and execute:

```bash
cat <<'PRBODY' > /tmp/pi-pr-body.md
<generated PR body>
PRBODY

gh pr create \
  --base <base-branch> \
  --head <current-branch> \
  --title "<PR title>" \
  --body-file /tmp/pi-pr-body.md \
  <--draft if requested> \
  <--reviewer user1,user2 if provided> \
  <--label label1,label2 if applicable>

rm -f /tmp/pi-pr-body.md
```

**Label mapping from commit type:**

| Commit Type | GitHub Label |
|-------------|-------------|
| `feat` | `enhancement` |
| `fix` | `bug` |
| `docs` | `documentation` |
| `perf` | `performance` |
| `ci`, `build` | `ci/cd` |
| `refactor`, `style`, `chore`, `test` | *(no label or use type name)* |

> Only apply labels that **actually exist** in the repository. Run `gh label list --json name` first to check. If a label doesn't exist, skip it silently.

#### 10g — Verify PR Creation

After creating:

```bash
gh pr view --json number,title,url,state
```

Confirm the PR was created and capture its URL and number.

### Step 11 — Report

Present the final summary:

**With PR:**
```
Committed, pushed, and PR created

  Commit:   a1b2c3d feat(templates): add slide preview endpoint
  Branch:   feat/slide-preview
  Remote:   origin/feat/slide-preview
  Files:    4 files changed, 187 insertions(+), 12 deletions(-)
  PR:       #42 — https://github.com/<org>/<repo>/pull/42
  Base:     main <- feat/slide-preview
```

**Without PR:**
```
Committed and pushed successfully

  Commit:   a1b2c3d feat(templates): add slide preview endpoint
  Branch:   feat/slide-preview
  Remote:   origin/feat/slide-preview
  Files:    4 files changed, 187 insertions(+), 12 deletions(-)
```

**Commit only (no push, no PR):**
```
Committed (not pushed)

  Commit:   a1b2c3d feat(templates): add slide preview endpoint
  Branch:   feat/slide-preview
  Files:    4 files changed, 187 insertions(+), 12 deletions(-)

  Run `git push` when ready.
```

## Edge Cases

### Pull Request Already Exists

If `gh pr list --head <branch>` returns an open PR, inform the user and show the link. Do not create a duplicate. Offer to update the existing PR body if desired.

### PR to Same Branch

If the current branch equals the base branch (e.g., on `dev` trying to PR into `dev`) → skip PR creation and inform the user.

### gh CLI Not Authenticated

If `gh auth status` fails → print clear instructions: `gh auth login --web` and stop. Do not attempt to create the PR.

### Labels Don't Exist

If the auto-detected label doesn't exist in the repo, skip it silently. Never fail the PR creation because of a missing label.

### Multiple Logical Changes

If the diff contains **clearly unrelated logical changes** (e.g., a bug fix in the auth module AND a new feature in the UI layer):

1. **Suggest splitting** into separate commits for a cleaner history.
2. Present a proposed split plan based on the actual file paths in the diff:
   ```
   Commit 1: fix(auth): handle expired token on refresh
     - <path to auth file>

   Commit 2: feat(ui): add new component
     - <path to UI file>
   ```
3. **Ask the user** whether to split or commit together.

### Merge Conflicts

If `git status` shows merge conflicts → list conflicted files and instruct the user to resolve them before committing. Stop.

### Empty Diff

If `git diff --cached` is empty after staging → warn the user and suggest checking their changes.

### Detached HEAD

If on a detached HEAD → warn the user and suggest `git checkout -b <name>` before proceeding.

### Large Binary Files

If the diff includes large binary files, mention them in the commit body but note they won't appear in the diff analysis.

## Restrictions

- **NEVER commit secrets**, API keys, passwords, or `.env*` files. If detected in staged files → **WARN the user and refuse** to commit until removed or `.gitignore`d.
- **NEVER force-push** without explicit user authorization.
- **NEVER amend** a commit that has already been pushed (unless user explicitly requests force-push).
- **NEVER create a PR without user confirmation** — always present the title, base, and body first.
- **NEVER create a duplicate PR** — always check for existing open PRs on the same head→base pair.
- **ALWAYS follow Conventional Commits** format.
- **ALWAYS present the full commit message for review** before executing.
- **ALWAYS use imperative mood** in the summary line.
- **ALWAYS verify** the commit was created successfully before attempting to push.
- **ALWAYS verify** the push succeeded before attempting to create a PR.

## Quality Criteria

- [ ] Commit type correctly reflects the nature of the changes
- [ ] Scope accurately identifies the affected service or domain module
- [ ] Summary line is ≤ 72 characters, imperative mood, lowercase after colon
- [ ] Body explains what changed and why (not how)
- [ ] No secrets or sensitive data in staged files
- [ ] Unrelated changes were flagged for potential splitting
- [ ] Commit was verified with `git log`
- [ ] Push was successful or explicitly skipped by user preference
- [ ] Message follows Conventional Commits format
- [ ] PR base branch follows the project branching strategy
- [ ] PR title matches the commit summary line
- [ ] PR body includes description, change list, type checkbox, and affected services
- [ ] No duplicate PR was created
- [ ] PR URL was reported to the user

## Output

A Git commit created and pushed to the remote repository with a well-structured Conventional Commits message, optionally followed by a GitHub Pull Request — plus a summary report of the full operation.
