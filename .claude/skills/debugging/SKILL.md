---
name: debugging
description: A disciplined procedure for finding and fixing bugs: reproduce, gather evidence, rank hypotheses, test one at a time, apply the smallest fix, and prevent regressions. Use this whenever an agent is fixing a bug, error, crash, failing test, broken build, wrong output, hydration mismatch, or "it doesn't work" report in a web app (Next.js, React, Node APIs, or similar), even if the task just pastes an error message or says "fix this."
---

# Debugging

This skill is for an agent fixing a defect. The goal is to find the actual cause, fix it with the smallest correct change, and prove the fix works. The main failure mode to avoid is shotgun debugging: changing several things at once until the symptom disappears, without knowing why.

## Step 1: Plan before changing code

Before editing anything, write this plan.

```
DEBUG PLAN
Symptom: <exact error text or observed vs expected behavior>
Reproduction: <command, URL, or steps that trigger it — or "not yet reproduced">
Scope: <files/modules likely involved, from the stack trace or code search>
Hypotheses (ranked by likelihood):
  1. <cause> — evidence for: <...> — test: <how to confirm or rule out>
  2. <cause> — evidence for: <...> — test: <...>
  3. ...
First test: <hypothesis # and the check to run>
```

Write at least 2 hypotheses. If you only have one, you have not looked enough.

## Step 2: Reproduce

- Reproduce the bug before fixing it. A fix for a bug you never saw is a guess.
- Use the cheapest reproduction: a failing test, a script, a `curl` request, or the dev server with exact steps.
- If you cannot reproduce it after a real attempt, report that with what you tried. Do not invent a fix.

## Step 3: Gather evidence

Read before you change. In order:
1. The full error message and stack trace. Find the first frame in project code, not library code.
2. The code at that location and what calls it.
3. Recent changes: `git log -p --since` or `git diff` on the affected files, if git is available.
4. Runtime values: add temporary logging or use a debugger at the boundary where expected and actual values split.

Common web-app causes worth checking early when they match the symptom:
- **Hydration mismatch**: rendering `Date`, `Math.random()`, `window`, or locale-dependent output on the server and client differently.
- **Server vs client components** (Next.js App Router): hooks or browser APIs in a component missing `"use client"`; passing functions or non-serializable props from server to client.
- **Environment variables**: missing at runtime, or a client-side var without the `NEXT_PUBLIC_` prefix.
- **Caching**: stale data from `fetch` caching, route segment caching, or a stale build; try a clean restart before deep investigation.
- **Async**: missing `await`, unhandled promise rejection, race between effects, stale closure in `useEffect` or event handlers.
- **Data shape**: API returns `null`, an empty array, or a different shape than the types claim.
- **Dependency versions**: lockfile mismatch or a breaking upgrade.

## Step 4: Test hypotheses one at a time

- Test the most likely hypothesis first. Change one variable per test.
- Record each result: `H1: ruled out — <evidence>` or `H1: confirmed — <evidence>`.
- If 3 hypotheses are ruled out, stop and rewrite the plan with new evidence before continuing. Repeating similar guesses wastes time.
- If 5 hypotheses are ruled out with no confirmation, stop and report findings instead of continuing indefinitely.

## Step 5: Fix

- Fix the cause, not the symptom. Wrapping code in `try/catch` to hide the error, adding `?.` everywhere, or adding `// @ts-ignore` is not a fix unless the cause is actually optional data.
- Make the smallest change that fixes the cause. Do not refactor nearby code in the same change.
- If the fix requires a behavior decision the code never defined (for example, what to do when an API returns `null`), choose the safest option, and record it under "Behavior decisions" in the report.
- If the fix changes a function's signature or return shape, search for its callers, update them, and record the change in the report.
- Remove all temporary logging and debug code.

## Step 6: Verify and prevent regression

- Rerun the exact reproduction from Step 2 and confirm the bug is gone.
- Run the related tests and the type check or build.
- If the project has a test setup, add a test that fails without the fix and passes with it. If adding one is not practical, say why.
- Check for the same bug pattern elsewhere: search the codebase for the same mistake and list other locations (fix them only if the task scope allows).

## Output contract

```
DEBUG REPORT
Root cause: <one or two sentences: what was wrong and why it produced the symptom>
Evidence: <what confirmed it>
Fix: <file:line — what changed>
Verification: <reproduction rerun: pass | tests: pass/fail | build: pass/fail>
Regression test: <added at path | not added: reason>
Behavior decisions: <undefined cases resolved by the fix, and the choice made | none>
Interface changes: <signature/return-shape changes and callers updated | none>
Hypotheses ruled out: <list, so nobody re-checks them>
Same pattern elsewhere: <locations or "none found">
Status: fixed | not reproduced | blocked: <reason>
```
