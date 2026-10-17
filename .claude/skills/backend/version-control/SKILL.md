---
name: version-control
description: Handles Git and GitHub work — branching, commits and commit messages, pull requests, merging and rebasing, resolving conflicts, undoing mistakes, .gitignore, tags, and releases. Use whenever the user wants to commit, branch, write a PR, merge, resolve a merge conflict, recover lost work, clean up history, or set up a repo, even if they don't say "version control" (e.g. "save my changes", "I messed up my branch", "push this to GitHub", "how do I undo that").
---

# Version Control (Git + GitHub)

Do the work: run the Git commands, write the commit messages and PR descriptions. Protect the user's work above all else; a lost commit costs far more than an extra confirmation.

## Step 1: Check state first (every time)

Before any change, run and read:
```bash
git status
git branch --show-current
git log --oneline -10
git remote -v
```
Note uncommitted changes, the current branch, and whether it tracks a remote. If there are uncommitted changes and the operation could touch them (checkout, rebase, reset, pull), stop and ask whether to commit or stash them first.

## Step 2: Safety rules

**Ask for explicit confirmation before** any of these, stating what will be lost:
- `git push --force` (always use `--force-with-lease` instead, never plain `--force`)
- `git reset --hard`, `git clean -fd`, `git checkout -- <file>`, `git restore` on modified files
- rebasing or amending commits that are already pushed to a shared branch
- deleting a branch that is not fully merged (`git branch -D`)
- any history rewrite (`filter-repo`, interactive rebase on pushed commits)

**Never**:
- commit directly to `main` when the repo uses pull requests; create a branch.
- commit secrets, `.env` files, credentials, build output (`dist/`, `build/`), dependencies (`node_modules/`, `.venv/`), or OS/editor files. Check `git diff --staged` before committing.
- use `git add .` without first checking `git status` for files that shouldn't be committed.

If a secret was already committed:
- **Not pushed yet**: remove it from the commit (`git rm --cached <file>`, add it to `.gitignore`, `git commit --amend`) before anything is pushed. Check `git log --all -- <file>` returns nothing on any branch.
- **Pushed, or the repo is shared/public**: tell the user to **rotate the secret immediately**, because removing it from history doesn't un-leak it. Then remove it from history only if they want to.

## Step 3: Branching (GitHub flow)

- Branch from an up-to-date default branch: `git switch main && git pull --ff-only && git switch -c <name>`.
- Branch names: `<type>/<short-kebab-description>`, e.g. `feat/route-generation`, `fix/login-redirect`, `chore/update-deps`.
- One branch per feature or fix. Keep branches short-lived; sync with `main` regularly.

## Step 4: Commits

- **Atomic**: one logical change per commit. If a diff mixes a refactor and a feature, split it with `git add -p`.
- **Message format** (Conventional Commits):
  ```
  <type>(<optional scope>): <imperative summary, ≤ 72 chars, no period>

  <body: why this change was made and anything non-obvious; wrap at 72>
  ```
  Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`, `build`, `style`. Add `!` after the type for breaking changes.
- Write the summary from the diff, not the task description. "fix(auth): refresh token before expiry" not "fixed stuff".
- Include a body when the reason isn't obvious from the summary.

## Step 5: Pull requests

When the user is ready to merge, write a PR description:
```markdown
## What
<1–3 sentences on the change>

## Why
<the problem or goal; link the issue: Closes #123>

## How to test
<steps a reviewer can follow>

## Notes
<risks, follow-ups, screenshots for UI changes; omit if none>
```
- Keep PRs small enough to review (aim for under ~400 changed lines; suggest splitting larger ones).
- Default merge strategy: **squash merge** for feature branches (clean `main` history), unless the repo already uses merge commits or rebase merges.
- After merge: delete the branch locally and on the remote.

## Step 6: Syncing and conflicts

- Update a feature branch with `git fetch origin && git rebase origin/main` if the branch is only yours; use `git merge origin/main` if others share it.
- Resolving conflicts:
  1. Run `git status` to list conflicted files.
  2. For each file, read both sides and understand what each change intended. Don't pick one side wholesale unless it's clearly right.
  3. Remove all conflict markers, then run the project's tests/build.
  4. `git add <file>`, then `git rebase --continue` or `git commit`.
  5. If it goes wrong, `git rebase --abort` / `git merge --abort` returns to the starting state.

## Step 7: Undoing mistakes (least destructive first)

| Situation | Command |
|---|---|
| Fix the last commit's message or add a forgotten file (not pushed) | `git commit --amend` |
| Undo last commit, keep changes | `git reset --soft HEAD~1` |
| Undo a commit that's already pushed | `git revert <sha>` |
| Unstage a file | `git restore --staged <file>` |
| Recover a "lost" commit or branch | `git reflog`, then `git switch -c recovered <sha>` |
| Committed to the wrong branch | `git switch -c new-branch`, then reset the old branch (confirm first) |

Always try `git reflog` before telling the user work is gone.

## Step 8: Repo setup and releases

- New repo: add a `.gitignore` for the stack (Node, Python, etc.) plus `.env*` (keep `.env.example`), a README, and commit before the first push.
- Releases: tag with semantic versioning `vMAJOR.MINOR.PATCH` (`git tag -a v1.2.0 -m "..." && git push origin v1.2.0`). Bump MAJOR for breaking changes, MINOR for features, PATCH for fixes.

## Step 9: Report back

After any Git operation, tell the user in 1–3 lines: what changed, the current branch, and whether anything is unpushed. Show the commit message(s) you wrote.
