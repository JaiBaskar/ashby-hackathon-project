# Design system

How the sampling-site finder looks, and why. Every value lives in `app/globals.css` (`@theme static`, `@theme inline` and the dark-mode block); this file explains them. Components use the tokens through Tailwind utilities (`bg-surface`, `text-ink-muted`, `rounded-md`, `duration-fast`) and never hard-code a color. `app/design-tokens.test.ts` enforces the contrast rules below and fails on any hex value in `app/` or `components/` outside `globals.css`.

## Direction

Calm, clinical precision. The slide image is the hero; the chrome around it stays quiet so the stain colors and the region boxes carry the screen.

- A warm, paper-like neutral base (`canvas`, `surface`) instead of pure white, which reads like a lab bench rather than a template.
- One accent, a clinical teal-green (`accent`). Its hue sits far from both eosin pink and hematoxylin purple, so wherever it appears on top of a slide it never blends into the tissue. It is used for the primary action, the selected state and the best box only.
- No gradients, no glass, no emoji icons, no default Tailwind palette (it's removed with `--color-*: initial`).
- Flat surfaces separated by 1 px `line` borders; shadows only for things that float (the detail panel, popovers).

## Color tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `canvas` | `#F5F4F0` | `#0E1012` | Page background |
| `surface` | `#FFFFFF` | `#16191C` | Cards, panels |
| `surface-sunken` | `#ECEBE6` | `#1E2226` | Wells, the slide's backdrop, empty bar segments |
| `ink` | `#16181A` | `#ECEDEE` | Body text, headings |
| `ink-muted` | `#575B60` | `#A3A8AD` | Secondary text, labels |
| `line` / `line-strong` | `#DCDAD4` / `#B9B6AE` | `#2B3034` / `#454B50` | Borders, dividers / input borders |
| `accent` | `#2DB391` | `#3CC8A5` | Primary button fill, selected state |
| `accent-ink` | `#06231C` | `#04201A` | Text on `accent` |
| `accent-strong` | `#0A6B57` | `#5FD8B8` | Accent used as text or icon on `surface` (links, step indicator) |
| `focus` | `#0A6B57` | `#5FD8B8` | Focus ring |
| `danger` | `#B42318` | `#FF8B7E` | Error text and icons |

Checked by the test, in both themes: `ink` and `ink-muted` on `canvas` and `surface`, `accent-ink` on `accent`, `accent-strong` and `danger` on `surface` are all ≥ 4.5:1; `focus` on `canvas` is ≥ 3:1.

Dark mode follows `prefers-color-scheme` by redefining the chrome tokens on `:root`, so components need no `dark:` variants.

### Tissue classes

For the composition bar and its legend: `class-tumor` `#5B3A8C`, `class-stroma` `#D99AB3`, `class-immune` `#3C5A7A`, `class-necrosis` `#8C6A3F`, `class-normal` `#7FA996`, `class-fat-other` `#CBC6BC`. Tumor and stroma echo hematoxylin and eosin so the bar reads like the slide. Every segment also carries its name and percentage as text, so color is never the only label. The tumor heatmap overlay is drawn by the backend (`HEATMAP_RGB` in `backend/project/regions.py`), not by these tokens.

## Region boxes

Boxes are drawn on top of the stain, so they must stay visible over both eosin pink `#E8B4C8` (luminance ≈ 0.540) and hematoxylin purple `#6B4C9A` (luminance ≈ 0.106), at ≥ 3:1 (WCAG non-text contrast).

**The math rules out one-color boxes.** A single color reaches 3:1 against both only if its luminance is ≤ 0.002, which is near-black: `#000000` gets 3.13:1 on purple, and `#0A0A0A` already fails at 2.95:1. Two distinguishable box styles can't both be near-black.

**So every box is two strokes**, and against each tissue color at least one layer reaches 3:1:

| Box | Outer stroke | Inner stroke | On pink | On purple |
|---|---|---|---|---|
| Best (`region-box-best`) | `box-outline` `#000000`, 2 px | `box-best` `#2DB391` (the accent), **4 px** | outline 11.79:1 | outline 3.13:1 |
| Others (`region-box`) | `box-outline` `#000000`, 2 px | `box-other` `#F4F3EF`, 2 px | outline 11.79:1 | inner 6.05:1, outline 3.13:1 |

The box tokens don't change with the theme: they sit on the slide, not on the chrome.

**The best box stands out without color:** its inner stroke is twice as thick (`--box-stroke-best` 4 px vs. `--box-stroke-other` 2 px, also checked by the test) and it carries a "Best" label next to its rank badge.

Box states (Phase 6): hover thickens nothing but raises the rank badge; keyboard focus adds the `focus` ring outside the outline; the selected box gets an `accent` rank badge. Unselected boxes stay fully visible, never dimmed below the contrast above.

## Type

Two families, both loaded with `next/font/local` from `@fontsource-variable/*` packages, so builds and tests work offline:

- **Newsreader** (`font-display`): page titles and the big numbers in the detail panel. A precise, quiet serif with optical sizes; it gives the product a considered, research-journal voice without decoration.
- **IBM Plex Sans** (`font-sans`, the default): everything else. Engineered and legible at small sizes; use `tabular-nums` for percentages and scores so columns line up.

Scale (6 sizes, set by `--text-*`): `xs` 12/16, `sm` 14/20, `base` 16/24, `lg` 20/28, `xl` 28/36, `display` 44/1.1. Body text is never below `base` on mobile. One `h1` per page. Hierarchy comes from size and weight first, color second.

## Spacing, radii, shadows

- Spacing: Tailwind's 4 px scale (`--spacing: 0.25rem`), unchanged. Space between groups is at least twice the space inside a group.
- Radii: `sm` 4 px (badges, inputs), `md` 8 px (buttons, cards), `lg` 14 px (panels, the slide frame), `full` (pills).
- Shadows: `shadow-raised` for cards that need lifting off the canvas; `shadow-overlay` for the detail panel and popovers. Nothing else casts a shadow.
- Content width: `max-w-6xl` for app screens, `max-w-prose` for text. Layouts must hold at 375 px and 1440 px with no horizontal scroll.

## Motion

Short and calm: `duration-fast` 120 ms (hover, press), `duration-base` 200 ms (panels, screen changes; also the default), `duration-slow` 320 ms (progress between analysis steps). Easing `ease-standard`; `ease-emphasized` only for the detail panel's entrance. `prefers-reduced-motion` sets every duration to 0.

## States

Every interactive element has a visible `:focus-visible` ring (`focus`, 2 px, 2 px offset, set globally in `globals.css`). Disabled controls use the `disabled` attribute plus reduced opacity. Touch targets are at least 44×44 px. Errors use `danger` text plus an icon and a sentence, never color alone.
