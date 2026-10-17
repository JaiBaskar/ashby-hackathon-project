---
name: ci-cd
description: Builds and fixes CI/CD pipelines with GitHub Actions — workflows that lint, test, and build on every push and pull request, plus deploy jobs, caching, secrets, environments, and database services for tests. Use whenever the user wants to automate tests or deploys, add or debug a `.github/workflows` file, set up checks on pull requests, deploy on merge, or fix a failing Actions run, even if they don't say "CI/CD" (e.g. "run my tests automatically", "deploy when I push to main", "why is my workflow red").
---

# CI/CD with GitHub Actions

Do the work: write the workflow files, and list exactly what the user must configure in GitHub (secrets, environments, branch protection). Base every command on what the repo actually contains.

## Step 1: Inspect the repo (before writing anything)

1. Detect the language and package manager from lockfiles: `package-lock.json` (npm), `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `requirements.txt` / `poetry.lock` / `uv.lock`, `go.mod`, `Cargo.lock`, etc.
2. Find the real commands: `scripts` in `package.json`, `Makefile` targets, `pyproject.toml` tool config, existing README instructions. **Use those commands. Never invent a `lint` or `test` step the project doesn't have**; if one is missing, say so and offer to add it.
3. Read any existing files in `.github/workflows/` and extend them rather than creating duplicates.
4. Identify the runtime version from `.nvmrc`, `.python-version`, `engines`, `go.mod`, or similar. Pin CI to it.
5. Identify the deploy target (Vercel, Render, Fly.io, AWS, GCP, Docker registry, etc.) if deployment is requested. If it's unknown, ask.

## Step 2: CI workflow rules (`.github/workflows/ci.yml`)

- **Triggers**: `pull_request` and `push` to the default branch. Add `workflow_dispatch` for manual runs.
- **Concurrency**: cancel superseded runs on the same ref:
  ```yaml
  concurrency:
    group: ${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: true
  ```
- **Permissions**: set `permissions: contents: read` at the top level; grant more only on the specific job that needs it.
- **Actions versions**: use official actions at their current major version (`actions/checkout@v4`, `actions/setup-node@v4`, `actions/setup-python@v5`). Pin third-party actions to a full commit SHA with a comment naming the version.
- **Caching**: use the setup action's built-in cache (`cache: npm`, `cache: pip`) before reaching for `actions/cache`.
- **Install**: use the lockfile-respecting command (`npm ci`, `pnpm install --frozen-lockfile`, `pip install -r requirements.txt`, `uv sync --frozen`).
- **Jobs**: separate jobs for lint, test, and build when each takes more than a minute; otherwise one job with ordered steps is fine. Fast checks run first.
- **Timeouts**: every job sets `timeout-minutes` (default 15).
- **Matrix**: only when the project actually supports multiple versions/OSes (e.g., a published library). Apps test on the one version they deploy on.
- **Databases in tests**: use a `services:` container (e.g., `postgres:16`) with a health check, and pass the connection string via `env`. Run migrations before tests.

## Step 3: CD (deploy) rules

- Deploy only from the default branch on `push` (or on a published release/tag), never from `pull_request`.
- The deploy job uses `needs:` on every CI job so a failing test blocks the deploy.
- Use a GitHub **environment** (`environment: production`) so secrets are scoped and the user can add required reviewers.
- Prefer OIDC (`permissions: id-token: write`) over long-lived cloud keys when the provider supports it (AWS, GCP, Azure).
- For platforms that auto-deploy from GitHub themselves (Vercel, Render, Netlify), say so and don't duplicate the deploy in Actions unless the user wants Actions to gate it.

## Step 4: Secrets

- Never hardcode tokens, passwords, or keys in workflow files. Reference them as `${{ secrets.NAME }}`.
- Never `echo` a secret or pass it as a command-line argument where it could be logged; pass it via `env`.
- Workflows triggered by `pull_request` from forks don't receive secrets; don't design CI that requires them for basic tests.
- Do not use `pull_request_target` with a checkout of the PR's code.

## Step 5: Debugging a failing run

1. Ask for (or read) the failing job's log and find the first error, not the last.
2. Classify it: dependency install, missing secret/env var, version mismatch between local and CI, missing service, flaky test, or a real failure.
3. Reproduce the failing command locally with the same runtime version when possible.
4. Fix the root cause. Don't add `continue-on-error: true` or skip tests to make the run green unless the user explicitly asks, and say what it hides if they do.

## Step 6: Produce output

1. **Workflow file(s)** in full, with short comments on non-obvious lines.
2. **Setup checklist** for the user to do in GitHub: each secret name and where its value comes from, environments to create, and recommended branch protection (require the CI check to pass before merging to `main`).
3. **What runs when**: one line per trigger (e.g., "Every PR: lint + test. Push to main: lint + test + deploy.").

## Step 7: Check before finishing

- [ ] Every command exists in the repo's scripts/config.
- [ ] Runtime version matches the project's pinned version.
- [ ] Top-level `permissions` is read-only.
- [ ] Every job has `timeout-minutes`.
- [ ] Deploy job `needs` all CI jobs and only runs on the default branch.
- [ ] No secret values appear in any file.
- [ ] YAML is valid (run `actionlint` if available; otherwise parse it).
