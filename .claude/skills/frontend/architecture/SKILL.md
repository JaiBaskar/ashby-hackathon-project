---
name: architecture
description: Structural decisions for web apps: folder layout, server vs client boundaries, data flow, where state lives, API and database design, third-party services, and how new code fits existing code. Use this whenever an agent starts a new project, adds a significant feature, introduces a library or service, designs an API or data model, refactors structure, or faces a "where should this code go" decision in a web app (Next.js, React, Node, or similar), even if the task only says "set up the project" or "add X."
---

# Architecture

This skill is for an agent making structural decisions. The goal is a codebase where a new contributor (human or agent) can find any piece of logic quickly, and where the next feature does not require rewriting the last one. Default context is fast builds on a modern TypeScript web stack (Next.js App Router, Tailwind, a hosted database), but follow the project's actual stack when it differs.

Prefer the simplest structure that handles the known requirements. Do not design for scale or features nobody asked for.

## Step 1: Plan before creating or moving files

Inspect first, then write this plan. Do not create or move files until it is written.

```
ARCHITECTURE PLAN
Existing state: <framework + version, router type, folder layout, data layer, state libs, auth, deploy target — or "new project">
Conventions found: <naming, file colocation, import aliases, lint rules>
Change requested: <what needs to be added or restructured>
Components of the change: <new routes, components, server logic, data models, external services>
Data the change needs: <fields/inputs required; mark any the current data model lacks>
Decisions needed: <each open structural choice>
```

How to inspect: read `package.json`, the framework config (`next.config.*`), `tsconfig.json` (paths/aliases), the top two levels of the source tree, and one existing feature end to end. Existing conventions win, because mixed conventions make the codebase harder to navigate than any single imperfect one. Change a convention only when the task asks for it.

## Step 2: Make decisions

For each decision in the plan, record it like this:

```
DECISION: <question>
Options: <2-3 realistic options>
Choice: <option>
Why: <one or two sentences tied to the actual requirements>
Revisit if: <condition that would change this choice>
```

### Default choices

Use these only for a new project, or for a question where the existing codebase has no convention. Before applying any default, compare it with "Conventions found" in the plan. If the project already does it differently (for example, server modules sit in `lib/` with `import "server-only"` instead of `lib/server/`), follow the project and do not apply the default.

**Structure (Next.js App Router)**
- Routes in `app/`. Colocate route-only components in the route folder; put shared components in `components/`.
- Shared UI primitives in `components/ui/`. Feature components grouped by feature (`components/routes/`, `components/map/`), not by type.
- Server-only logic (database, secrets, external APIs) in `lib/server/` or files marked with `import "server-only"`.
- Shared types in `types/` or next to the module that owns them.

**Server vs client**
- Components are server components by default. Add `"use client"` only to the smallest component that needs state, effects, or browser APIs.
- Fetch data on the server when possible; pass plain serializable data to client components.
- Secrets and privileged calls never reach client code. Only `NEXT_PUBLIC_` variables are allowed in client bundles.

**Data flow and state**
- Server data: fetch in server components, or use server actions or route handlers for mutations. On the client, use a data-fetching library (TanStack Query or SWR) rather than hand-written `useEffect` fetching.
- UI state: keep it in the nearest component that needs it; lift only when a sibling needs it.
- Shareable state (filters, tabs, selected item) goes in the URL search params so it survives refresh and links.
- Add a global store (Zustand, Context) only when 3+ distant components share state that is not server data.

**APIs and data**
- Validate every external input at the boundary (route handler, server action, form) with a schema library such as Zod; derive TypeScript types from the schema.
- One module per external service that wraps its client, so swapping or mocking it touches one file.
- Model the database around the core entities from the product scope; avoid speculative tables.
- For hackathon builds, prefer a managed backend (Supabase, Firebase, Convex, or a hosted Postgres) over a self-run server.

**Dependencies**
- Before adding a library, check whether the platform or an existing dependency already covers it.
- Prefer widely used, maintained libraries. Record each new dependency as a DECISION.

## Step 3: Implement the structure

- Create the skeleton (folders, empty modules with exported signatures, types) before filling in logic, so the shape can be checked early.
- Keep files focused: one main responsibility per file. Split a file when it mixes unrelated concerns, not at an arbitrary line count.
- Use the project's import alias (for example `@/`) consistently.

## Step 4: Verify

- Run the type check and build. Fix errors you introduced.
- Confirm no server-only module is imported by a client component (search `"use client"` files for server imports).
- Trace one request or user action through the new structure end to end and confirm each layer has one clear owner. Check that a server-fetched value reaches its client component as a serializable prop, not through an import of a server module.
- List every new file and confirm its location matches an existing convention or a recorded DECISION.

## Output contract

```
ARCHITECTURE REPORT
Structure: <tree of new/changed folders and key files, with a few words each>
Decisions: <each DECISION block from Step 2>
Boundaries: <what runs on server, what on client, where secrets live>
Data flow: <source -> transform -> UI, for the main feature>
New dependencies: <name — why | none>
Checks: types <pass/fail>, build <pass/fail>
Follow-ups: <deferred structural work and the trigger for doing it>
```
