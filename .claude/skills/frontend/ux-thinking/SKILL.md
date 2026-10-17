---
name: ux-thinking
description: User-experience rules for web app features: user goals, flows, every UI state (loading, empty, error, success), forms, feedback, copy, and edge cases. Use this whenever an agent builds or reviews a feature a person interacts with — sign-up, onboarding, checkout, search, forms, dashboards, settings, uploads, multi-step flows — or when a task says "make this easier to use," "improve the flow," or "users are confused," even if UX is never mentioned.
---

# UX Thinking

This skill is for an agent building or reviewing interactive features. The goal is a feature a first-time user can complete without help, that never leaves them stuck or guessing. Scope is behavior and flow. Visual styling belongs to `ui-design`.

## Step 1: Plan before editing

Before writing code, write this plan. Do not edit until it is written.

```
UX PLAN
User: <who uses this and what they know when they arrive>
Goal: <the one thing they are trying to finish, in their words>
Entry points: <how they reach this feature>
Happy path: <numbered steps from entry to goal; target 3-5 steps>
States: <for each screen/component: loading, empty, error, success, partial — mark N/A where truly impossible>
Edge cases: <slow network, invalid input, duplicate submit, back button, refresh mid-flow, no permission, very long text>
Success signal: <how the user knows they finished>
```

If the task does not say who the user is, infer it from the codebase and product (README, copy, routes) and state the assumption in the plan. Do not stop to ask unless the answer changes what gets built.

## Step 2: Apply the rules

### Flow
- Count the steps in the happy path. If a step can be removed, merged, or defaulted, do that.
- Ask for information only when it is needed, not all up front.
- Never send the user to a dead end. Every error and empty state offers a next action.
- Preserve user work. Unsaved form input survives validation errors; long forms survive refresh where practical (draft in state or storage).

### States (the most common gap in agent-built UI)
Every view that loads or changes data must handle all of these:
- **Loading**: show a skeleton or spinner within 300ms; keep layout stable so content does not jump in.
- **Empty**: explain what belongs here and give the action that fills it ("No routes yet. Create your first route.").
- **Error**: say what happened in plain language, what the user can do, and offer retry. Never show raw error objects or stack traces.
- **Success**: confirm the action visibly (toast, inline message, or navigation to the result).
- **Partial**: some data loaded, some failed; show what you have and flag what is missing.

In Next.js App Router, use `loading.tsx`, `error.tsx`, and `not-found.tsx` where they fit, plus local state for client-side actions.

### Forms
- Labels are always visible; placeholders are not labels.
- Validate on blur or submit, not on every keystroke while typing.
- Error messages sit next to the field and say how to fix it ("Use at least 8 characters," not "Invalid").
- Disable the submit button and show progress while submitting, to prevent double submits.
- Use the right input types (`email`, `tel`, `number`, `date`) and `autocomplete` attributes.

### Feedback and copy
- Every click gets a response within 100ms (visual press state, spinner, or optimistic update).
- Destructive actions (delete, cancel subscription) need confirmation or undo. Prefer undo for low-stakes actions.
- Button labels name the action ("Save route," not "Submit" or "OK").
- Use the user's words, not internal or database terms.

### Accessibility (behavioral)
- Everything works with keyboard alone, in a logical tab order.
- Modals trap focus and return it to the trigger on close; Escape closes them.
- Status changes (errors, success toasts) are announced with `aria-live` or a library that handles it.

## Step 3: Verify

Walk the flow as the user, in order:
1. Happy path start to finish.
2. Each edge case listed in the plan.
3. Keyboard-only pass if a browser is available.

If you cannot run the app, trace the flow through the code and say that the check was a code trace, not a live run.

## Output contract

```
UX REPORT
Flow: <final happy path, numbered>
States handled: <view: loading/empty/error/success — done or missing>
Edge cases: <each case -> how handled | not handled: reason>
Assumptions: <user/goal assumptions made>
Verification: <live walkthrough | code trace>
Open issues: <or "none">
```

When the task is review only (it says review, audit, critique, or "don't change yet"), list findings ordered by severity as `[high|med|low] <where> <problem a user hits> -> <fix>`, and do not edit files. A "high" finding is one where a user can get stuck, lose data, or not know if an action worked.
