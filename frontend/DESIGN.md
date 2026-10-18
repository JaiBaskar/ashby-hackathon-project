# Design system

How the sampling-site finder looks, and why. Every value lives in `app/globals.css` (`@theme static`, `@theme inline` and the dark-mode block); this file explains them. Components use the tokens through Tailwind utilities (`bg-surface`, `text-ink-muted`, `rounded-md`, `duration-fast`) and never hard-code a color. `app/design-tokens.test.ts` enforces the contrast rules below and fails on any hex value in `app/` or `components/` outside `globals.css`.

## Direction: the bench

The app should feel like it came out of a pathology lab, not a template. Every choice below comes from the bench: the stain, the glass slide, the marker pen, the scope.

- **Chrome in stain colors.** Hematoxylin indigo (`accent`) is the ink for actions and selection; eosin rose (`eosin`) is the one highlight (the logo's label end, the current-page mark, a sequencing badge). The page itself is a faintly violet glass-white (`canvas`).
- **Annotations in marker ink.** On the slide, boxes are black plus teal or white, like the marker pens pathologists dot on glass. Those colors can't blend into stained tissue, and the chrome colors never appear on top of the slide.
- **The stage.** The slide always sits on a dark "scope" background (`stage`), in both themes, like a whole-slide viewer, so the stain is the brightest thing on screen. The header uses the same band.
- **Glass-slide motifs:** the logo is a slide with a frosted label end; codes, states and case labels sit on mono "label" chips (`Chip`).
- **Numbers are instrument readouts:** every percentage, score, size and ID uses IBM Plex Mono with tabular figures (`.num` or `font-mono`), so columns line up and they read as measurements.
- **Copy in the lab's words:** case, block, macrodissect, tumor fraction, sequencing threshold. No marketing hero, no "How it works", no exclamation marks.
- No gradients, no glass blur, no emoji, no default Tailwind palette (removed with `--color-*: initial`).

## Color tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| `canvas` | `#F4F3F8` | `#0F0E15` | Page background |
| `surface` | `#FFFFFF` | `#18161F` | Panels, tables |
| `surface-sunken` | `#EAE8F1` | `#211E2B` | Wells, hover rows, empty bar segments |
| `ink` / `ink-muted` | `#1B1730` / `#5C5870` | `#EEEDF3` / `#A8A4B7` | Text / secondary text |
| `line` / `line-strong` | `#DEDBE7` / `#B8B3C8` | `#2C2938` / `#464157` | Dividers / control borders |
| `accent` | `#3D2F86` | `#A99BF5` | Primary button fill, selected rows (hematoxylin) |
| `accent-ink` | `#FFFFFF` | `#16112F` | Text on `accent` |
| `accent-strong` / `focus` | `#4B3BA3` | `#B9ADFF` | Accent as text or icon; focus ring |
| `eosin` / `eosin-strong` | `#D9467A` / `#B4295F` | `#F07AA5` / `#F28DB3` | Highlight fill / highlight as text |
| `ok` / `warn` | `#1D7350` / `#8A5300` | `#5ED3A2` / `#F0B54C` | Meets / below the sequencing threshold |
| `danger` | `#B42318` | `#FF8B7E` | Errors |
| `stage`, `stage-raised`, `stage-line` | `#110F18`, `#1C1926`, `#2E2A3B` | same | The slide stage and header |
| `stage-ink` / `stage-muted` / `stage-focus` | `#ECEAF3` / `#A6A1B6` / `#B9ADFF` | same | Text and focus ring on the stage |

Checked by `app/design-tokens.test.ts`, in both themes: `ink` and `ink-muted` on `canvas` and `surface`, `accent-ink` on `accent`, `accent-strong` on `surface` and `canvas`, `danger`, `eosin-strong`, `ok` and `warn` on `surface`, and `stage-ink`/`stage-muted` on the stage are all ≥ 4.5:1; `focus` on `canvas` and `stage-focus` on `stage` are ≥ 3:1. The stage tokens must not change in dark mode (also tested). Tinted backgrounds use the same tokens at low opacity (`bg-ok/10`), never new colors.

Dark mode follows `prefers-color-scheme` by redefining the chrome tokens on `:root`, so components need no `dark:` variants.

### Tissue classes

For the composition bar and its legend: `class-tumor` `#5B3A8C`, `class-stroma` `#D99AB3`, `class-immune` `#3C5A7A`, `class-necrosis` `#8C6A3F`, `class-normal` `#7FA996`, `class-fat-other` `#CBC6BC`. Tumor and stroma echo hematoxylin and eosin so the bar reads like the slide. Every segment also carries its name and percentage as text, so color is never the only label. The tumor (deep orange) and necrosis (blue) heatmap overlays are drawn by the backend (`HEATMAP_RGB` in `backend/project/regions.py`), not by these tokens; their keys in `SlideStage.tsx` (`HEATMAP_KEYS`) mirror those tints and sit on `slide-glass`.

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

Two families, loaded with `next/font/local` from pinned `@fontsource` packages, so builds and tests work offline:

- **Instrument Sans** (`font-sans`, also `font-display`): everything you read. Compact, slightly technical, and with enough character in its curves that headings don't need a serif to have a voice. Headings use tight tracking (set on `--text-xl` and `--text-display`).
- **IBM Plex Mono** (`font-mono`, or the `.num` class): every number, percentage, size, score, ID and chip. Mono with tabular figures makes the region table read like an instrument printout.

Scale (6 sizes, `--text-*`): `xs` 12/16, `sm` 14/20, `base` 16/24, `lg` 20/28, `xl` 28/34, `display` 52/1.02. Body text is never below `base` on mobile. One `h1` per page.

## Spacing, radii, shadows

- Spacing: Tailwind's 4 px scale, unchanged. Space between groups is at least twice the space inside a group.
- Radii are small, like glass and instruments: `sm` 3 px (chips, inputs), `md` 6 px (buttons), `lg` 10 px (panels, the stage), `full` (only for the progress bar and dots).
- Shadows: `shadow-raised` for things lifted off the canvas; `shadow-overlay` for dialogs and the inspector. Panels are mostly separated by 1 px `line` borders, not shadows.
- Content width: app screens use up to `90rem`, so the slide gets the room; text stays at `max-w-prose`. Layouts must hold at 375 px and 1440 px with no horizontal page scroll.

## Motion

Motion only where it tells you something; never as decoration.

- `animate-enter` (320 ms): a screen or panel arriving.
- `animate-drop`: region boxes land on the slide one after another, in rank order, so the eye follows the ranking.
- `animate-sweep` and `animate-tile`: on the analyzing screen, a scan line passes over your image and tiles light up as they are scored.
- Score readouts update as a box is resized (the numbers are re-measured live).
- Durations `fast` 120 ms, `base` 200 ms, `slow` 320 ms; easing `ease-standard`, `ease-emphasized` for the box drop.
- `prefers-reduced-motion` sets every duration to 0 and switches all animations off.

## States

Every interactive element has a visible `:focus-visible` ring (`focus`, 2 px, 2 px offset, set globally in `globals.css`; `stage-focus` inside `.on-stage`). Disabled controls use the `disabled` attribute plus reduced opacity. Touch targets are at least 44×44 px. Errors use `danger` text plus an icon and a sentence, never color alone.
