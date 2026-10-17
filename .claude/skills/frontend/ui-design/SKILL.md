---
name: ui-design
description: Visual design rules for building or changing web UI: layout, spacing, typography, color, hierarchy, component states, and responsive behavior. Use this whenever an agent builds, restyles, or reviews a page, screen, or component in a web app (Next.js, React, Tailwind, or similar), including landing pages, dashboards, forms, modals, and hackathon MVP screens, even if the task only says "make it look good," "clean this up," or "build the page."
---

# UI Design

This skill is for an agent that builds or changes interface code. The goal is UI that is consistent, readable, and intentional instead of generic. Scope is the visual layer: what things look like and how they are arranged. User flows and states belong to `ux-thinking`; code structure belongs to `architecture`.

## Step 1: Plan before editing

Before touching any file, inspect the project and write this plan. Do not edit until it is written.

```
UI PLAN
Target: <files/components to create or change>
Existing system: <design tokens, tailwind.config / CSS vars, component library, fonts found — or "none">
Hierarchy: <the 1 primary element, 2-3 secondary, everything else tertiary>
Layout: <grid/stack structure at mobile and at desktop>
States to style: <default, hover, focus, active, disabled, loading, empty, error — only those that apply>
Verification: <how the result will be checked: screenshot, browser, build only>
```

How to fill "Existing system": search for `tailwind.config.*`, `globals.css`, `@theme`, CSS custom properties, `components/ui/`, and any shadcn/Radix setup. Existing tokens and components win over new ones, because a second system makes the app look inconsistent.

## Step 2: Apply the rules

### Spacing and layout
- Use one spacing scale (Tailwind's default 4px scale or the project's own). No arbitrary values like `mt-[13px]` unless matching a fixed external asset.
- Related items sit closer together than unrelated items. Space between groups is at least 2x the space inside a group.
- Pick one max content width per page type (for example `max-w-6xl` for app pages, `max-w-prose` for text) and center it.
- Build mobile first: base classes for small screens, then `sm:`/`md:`/`lg:` overrides. Check that nothing overflows horizontally at 360px.

### Typography
- At most 2 font families. Use a type scale with no more than 5-6 sizes on a page.
- One h1 per page. Heading sizes must decrease with level.
- Body text 16px minimum on mobile. Line length 45-80 characters for paragraphs.
- Create hierarchy with size and weight first, color second. Do not rely on all caps or color alone.

### Color
- Define colors as tokens (Tailwind theme or CSS variables), not hex values scattered in components.
- One primary accent color used for the main action and key highlights only. If everything is accent-colored, nothing stands out.
- Text contrast: at least 4.5:1 for body text, 3:1 for large text and UI controls. Gray text on gray backgrounds is the most common failure; check it.
- If the project supports dark mode, every new color needs a dark variant. If it does not, do not add dark mode unasked.

### Hierarchy
- Each screen has exactly one primary action, styled as the strongest button. Secondary actions use outline or ghost styles.
- The first thing the eye lands on must be the most important content, not decoration.

### Components and states
- Reuse existing components before writing new ones.
- Every interactive element needs a visible `focus-visible` style. Never remove outlines without a replacement.
- Disabled elements look disabled (reduced opacity or muted color) and use the `disabled` attribute, not only styling.
- Touch targets are at least 44x44px on mobile.
- Images have explicit dimensions or aspect ratios to prevent layout shift (`next/image` in Next.js).

### Avoid generic template styling
These patterns make AI-built UI look interchangeable. Do not use them unless the project already does or the task asks for them:
- Purple-to-blue gradients on hero sections or buttons by default
- Emoji as section icons
- Three identical feature cards with icon, title, and one sentence as the default layout
- Glassmorphism or heavy drop shadows on every card
- Centered text for long paragraphs

Instead, take direction from the product's content and audience. A landslide-hazard app for rangers should feel different from a fashion storefront.

## Step 3: Verify

- Run the build or type check (`npm run build`, `npx tsc --noEmit`, or the project's lint script) and fix errors you introduced.
- If a browser or screenshot tool is available, view the result at about 375px and 1280px wide, and fix overflow, overlap, or cramped spacing.
- If no visual check is possible, say so in the report. Do not claim the UI "looks good" without seeing it.

## Output contract

End with this report so the calling agent or user can act on it:

```
UI REPORT
Changed: <file paths>
Decisions: <key choices, e.g. "reused Button from components/ui; accent = existing --primary">
Checks: build <pass/fail>, visual <done at widths X/Y | not possible: reason>
Contrast issues: <list or "none found">
Open issues: <anything not resolved, or "none">
```

When the task is review only (it says review, audit, critique, or "don't change yet"), replace "Changed" with a findings list ordered by severity: `[high|med|low] <file:line> <problem> -> <fix>`. Do not edit files in review-only mode.
