---
name: product-sense
description: Decides what to build and what to cut before any code is written: target user, core problem, success metric, MVP scope, priorities, and tradeoffs. Use this whenever an agent receives a feature request, product idea, hackathon or startup MVP brief, vague spec, long feature list, or a choice between features — or when a task says "build an app that," "add a feature for," "what should we build," or "scope this" — even if the request jumps straight to implementation.
---

# Product Sense

This skill is for an agent turning a request into a buildable scope. The goal is to build the smallest thing that solves a real problem for a specific user and can be demonstrated, then stop. Default context is fast builds: hackathons and early-stage startups, where time is the hardest constraint and an unfinished feature is worth less than a finished smaller one.

Run this before `architecture` and before any UI or code work on a new product or feature.

## Step 1: Plan before scoping

Write this first, using only what the request and codebase actually say.

```
PRODUCT PLAN
Request (verbatim summary): <what was asked>
Known constraints: <deadline, team size, stack, judging criteria, existing code>
Unknowns that change scope: <list — or "none">
Assumptions I will make: <for each unknown that does not block work>
```

If an unknown would change what gets built (for example, who the user is, or whether the demo must work offline) and a person is available, ask about that unknown in one batch before Step 2. Otherwise proceed with stated assumptions.

## Step 2: Define the problem

```
PRODUCT BRIEF
User: <one specific person, e.g. "a park ranger checking trail safety each morning" — not "everyone">
Problem: <what is painful or impossible for them today>
Current workaround: <what they do now>
Why now / why us: <what makes this solvable or valuable here>
Success metric: <one measurable outcome, e.g. "ranger gets a risk rating for a trail in under 10 seconds">
Demo moment: <the single 30-second interaction that shows the value>
```

Rules:
- If you cannot name a specific user and problem, the request is a solution looking for a problem. Say so in the brief and propose the most plausible user.
- The success metric measures the user's outcome, not a feature's existence ("users can log in" is not a metric).

## Step 3: Scope with MoSCoW

List every feature in the request plus any required for the demo moment, then sort:

- **Must**: without it the demo moment fails. Keep this list to 3-5 items.
- **Should**: clearly improves the demo but it works without it.
- **Could**: nice, build only if Musts and Shoulds are done.
- **Won't (this version)**: explicitly cut, with a one-line reason.

Cutting rules for fast builds:
- Auth, user accounts, settings pages, and admin panels are Won't unless the core value depends on them. Use a hardcoded demo user instead.
- Prefer seeded or mocked data over a real integration when the integration is not the core value. Say clearly in the output which parts are mocked.
- Prefer one complete flow over three half-built ones.
- Anything that needs approval, payment setup, or third-party review time is Won't for a deadline under a week.

## Step 4: Check for traps

Before finalizing, check each and note any that apply:
- **Scope creep**: Musts exceed 5 items or the estimate exceeds available time.
- **Infrastructure before value**: the plan spends early time on setup (auth, CI, design system) before the core feature works.
- **Unvalidated core**: the riskiest technical piece (an ML model, an external API, real-time data) is scheduled last. Move it first, because if it fails the scope must change.
- **No demo path**: nothing in the Must list produces the demo moment end to end.

## Output contract

```
PRODUCT SCOPE
Brief: <from Step 2>
Must: <ordered by build order, riskiest first>
Should: <...>
Could: <...>
Won't: <item — reason>
Mocked or faked: <what, and how it would become real later>
Risks: <traps from Step 4 and other risks, each with a mitigation>
Build order: <numbered milestones with time budgets; milestone 1 = riskiest piece proven working>
Parallel tracks: <if team size > 1: one track per person, each with its milestones and the interface it shares with others (data shape, API) | solo>
Cut line: <the point at which remaining time forces dropping Should items, and the fallback demo if a Must fails>
Assumptions: <from Step 1>
```

Hand this scope to the next step (architecture or implementation). If a later request adds a feature, re-sort it into this list instead of adding it on top.
