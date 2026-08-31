# UI / Frontend Style Guide Prompt

> A single, extremely detailed prompt that fully describes the visual style of the product.
> Paste this into any AI coding/design tool to reproduce the exact look and feel.
> Stack: **React 19 + Vite + TypeScript + Tailwind CSS v4 + shadcn/ui (Radix primitives)**.

---

## 1. OVERALL VISUAL LANGUAGE

You are styling a **dark-first, monochrome SaaS product** ("karen"). The visual identity is:

- **Dark mode is the primary theme.** Light mode exists but is derived and secondary.
- **Monochrome + a single quiet accent.** Neutrals carry the interface; one accent is used
  sparingly for the single primary action and live-status signals. Never more than **2 chromatic colors** in the whole palette.
- **Flat "floating card" surfaces.** The UI is built as quiet panels that float on a darker
  backdrop. No glassmorphism, no neumorphism, no glossy gradients. Every surface is flat.
- **Edges are the decoration.** Instead of drop shadows, depth is communicated through
  **hairline 1px borders** (`--color-border`) and subtle background temperature shifts between layers.
- **Shadows are banned.** `box-shadow: none` everywhere. You never use shadow to create depth.
- **Generous whitespace.** Sections breathe with `clamp(4rem, 10vw, 7.5rem)` rhythm.
- **One primary CTA per viewport.** Everything else is quiet, secondary, tertiary.
- **Motion is subtle and purposeful.** Short, easing curves (`cubic-bezier(.16,1,.3,1)`),
  small translate/opacity drifts. No bouncy or flashy animation.

The overall mood: **premium, calm, technical, editorial.** Like a developer tool or a
high-end financial dashboard — trustworthy, dense but not cluttered.

---

## 2. COLOR SYSTEM

### 2.1 Principles

- Work with semantic tokens only inside components — **never raw hex in component CSS.**
- Two-tier token model: **primitive tokens** (raw values) feed **semantic tokens**.
- Text/background must meet **WCAG AA (4.5:1** normal, **3:1** large/UI).
- Saturation is kept low; large surfaces are neutral, only small accents get saturation.
- Dark background is **never pure black for panels** — pure black is only the outermost
  backdrop. Panels sit at `#151515`–`#1c1c1c`.
- In dark mode, bright saturated colors "glow"; avoid them on large areas.

### 2.2 Layer color map (dark mode — the canonical theme)

The UI is organized as a **stack of layers**, dark to light (outer → inner):

| Layer | Token | Dark value | Role |
|-------|-------|-----------|------|
| Outer backdrop (canvas) | `--color-backdrop` | `#000000` | the page background behind everything |
| Workspace surface | `--color-panel` | `#151515` | floating cards, sidebar's content area |
| Elevated surface | `--color-panel-elevated` | `#1c1c1c` | inputs, hover fills |
| Inner card surface | `--color-bg-secondary` | `#1a1a1a` | card body, elevated inner surfaces |
| Hover / chip tint | `--color-bg-tertiary` | `#222222` | chips, row hovers |
| Innermost (table header) | `--color-recessed` | `#0b0b0b` | recessed wells |

### 2.3 Text color map (dark)

| Token | Dark value | Role |
|-------|-----------|------|
| `--color-fg` | `#f5f5f5` | primary text |
| `--color-fg-secondary` | `#9a9a9e` | secondary text, labels, captions |
| `--color-fg-tertiary` | `#5c5c60` | tertiary text, eyebrows, meta |
| `--color-disabled` | `#4a4a4e` | disabled, em-dashes, empty states |

### 2.4 Border map (dark)

| Token | Dark value | Role |
|-------|-----------|------|
| `--color-border` | `#222222` | **subtle** — card edges, section dividers |
| `--color-border-light` | `#2a2a2a` | **strong** — inputs, divider lines |

### 2.5 Accent & interactive

| Token | Dark value | Role |
|-------|-----------|------|
| `--color-accent` | `#e4e4e7` | interactive accent — light pill fills |
| `--color-accent-contrast` | `#0a0a0a` | text on accent |
| `--color-active-bg` | `#1f1f1f` | nav active pill — subtle lift |
| `--color-active-fg` | `#ffffff` | nav active text |

### 2.6 Semantic status colors (dark)

```css
--color-success: #22c55e;  /* validations, positive live states */
--color-warning: #e8a33d;  /* pending, warnings */
--color-danger:  #ef4444;  /* errors, destructive */
--color-blue:    #3b82f6;  /* info */
```

**Rule:** color is never the *only* signal. Every status also carries an icon, label, or
shape. A red badge must also say the word.

### 2.7 The single accent

Use **one** accent to draw attention to exactly one thing per viewport. Prefer making the
primary action a **solid light pill** (`--color-accent` + `--color-accent-contrast`) — in a
monochrome dark UI, the light pill is the loud, guaranteed-focus element. Reserve saturated
green (`--color-success`) for **live status** pulses.

### 2.8 Example: the complete theme block (Tailwind v4 `@theme`)

```css
@import "tailwindcss";

@custom-variant dark (&:where(.dark, .dark *));

@theme {
  /* --- primitives (raw surfaces) --- */
  --color-backdrop:      #000000;
  --color-panel:         #151515;
  --color-panel-elevated:#1c1c1c;
  --color-bg:            #000000;
  --color-bg-secondary:  #1a1a1a;
  --color-bg-tertiary:   #222222;
  --color-recessed:      #0b0b0b;

  /* --- text --- */
  --color-fg:            #f5f5f5;
  --color-fg-secondary:  #9a9a9e;
  --color-fg-tertiary:   #5c5c60;
  --color-disabled:      #4a4a4e;

  /* --- borders (1px hairlines, no shadows) --- */
  --color-border:        #222222;
  --color-border-light:  #2a2a2a;

  /* --- interactive / accent --- */
  --color-accent:        #e4e4e7;
  --color-accent-contrast:#0a0a0a;
  --color-accent-dark:   #d0d0d4;
  --color-accent-light:  #2b2b2e;
  --color-active-bg:     #1f1f1f;
  --color-active-fg:     #ffffff;

  /* --- semantic status --- */
  --color-success: #22c55e;
  --color-warning: #e8a33d;
  --color-danger:  #ef4444;
  --color-blue:    #3b82f6;

  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  --radius: 14px;
}

/* Light mode is the DERIVED, secondary theme — same structure, inverted temperatures */
:root:not(.dark) {
  --color-backdrop:      #f4f4f6;
  --color-panel:         #ffffff;
  --color-panel-elevated:#ffffff;
  --color-bg:            #f4f4f6;
  --color-bg-secondary:  #ffffff;
  --color-bg-tertiary:   #f1f1f3;
  --color-recessed:      #f6f6f8;

  --color-fg:            #16171c;
  --color-fg-secondary:  #6b6c74;
  --color-fg-tertiary:   #9a9ba3;
  --color-disabled:      #b0b0b6;

  --color-border:        #e4e4e7;
  --color-border-light:  #d4d4d8;

  --color-accent:        #16171c;   /* light mode flips: dark pill on light bg */
  --color-accent-contrast:#ffffff;
  --color-active-bg:     #16171c;
  --color-active-fg:     #ffffff;

  --color-success: #16a34a;
  --color-warning: #e8a33d;
  --color-danger:  #dc2626;
  --color-blue:    #2563eb;
}
```

---

## 3. LAYERS & DEPTH

Depth is **flat and border-driven**, never shadow-driven.

### 3.1 Layer stack

```
                    ┌─────────────────────────────┐
  outer backdrop    │  --color-backdrop           │  darkest
                    │   ┌───────────────────────┐ │
  side surface      │   │  --color-panel        │ │  sidebar / floating panel
                    │   │  ┌─────────────────┐  │ │
  inner surface     │   │  │ --color-bg-secondary│ │  card body
                    │   │  │  ┌─────────────┐ │  │ │
  elevated surface  │   │  │  │--color-bg-tertiary│ │  inputs / chips / hover
                    │   │  │  └─────────────┘ │  │ │
                    │   │  └─────────────────┘  │ │
                    │   └───────────────────────┘ │
                    └─────────────────────────────┘
```

Each step down the stack is **one temperature step lighter** (in dark mode) and is usually
bounded by a **1px `--color-border`**.

### 3.2 The "soft card" recipe

The default surface primitive. This is the single most reused style:

```css
.soft-card {
  border: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  border-radius: 14px;                 /* --radius */
  box-shadow: none;                    /* NEVER shadows */
}
```

Used in JSX like:

```tsx
<div className="soft-card p-5">
  <h3 className="text-sm font-semibold text-fg">Pipeline</h3>
  {/* ... */}
</div>
```

### 3.3 Borders are the only divider tool

- Card edges: `1px solid var(--color-border)` (subtle).
- Inputs & strong dividers: `1px solid var(--color-border-light)`.
- Dividers between rows: `border-b border-border`.

```tsx
<div className="divide-y divide-border">
  <ListRow /> <ListRow /> <ListRow />
</div>
```

### 3.4 Radius

Single global radius token: **`14px`** for any card/panel. Inputs and small controls may
drop to `8–10px`. Use pill (`rounded-full`) for chips, badges, and status dots.

---

## 4. TYPOGRAPHY

- **Font:** `Inter` — loaded via Google Fonts with weights `400/500/600/700`.
- **Body minimum:** `16px`. Labels may be `13–14px`. Don't go below.
- **Hierarchy** is expressed via weight + size + color, in that order of importance.
- **Max 3 font sizes within one viewport area.** Display type is at least **3x** body.
- Normal text must hit **4.5:1** contrast; large text **3:1**.

### 4.1 Type scale

| Role | Size | Weight | Color token |
|------|------|--------|-------------|
| Display (page hero) | `clamp(2.5rem, 6vw, 4.5rem)` | 700 | `fg` |
| Section title (h2) | `1.5–2rem` | 600 | `fg` |
| Card title (h3) | `0.9375–1rem` | 600 | `fg` |
| Body / labels | `0.875–1rem` | 400–500 | `fg` |
| Meta / captions | `0.8125rem` | 400 | `fg-secondary` |
| Eyebrow (kicker) | `0.75rem` | 600, `letter-spacing:.12em`, `uppercase` | `fg-tertiary` |

### 4.2 The eyebrow pattern (very karen)

Small, uppercase, letter-spaced label above a section title:

```css
.eyebrow {
  color: var(--color-fg-tertiary);
  font-size: .75rem;
  font-weight: 600;
  letter-spacing: .12em;
  text-transform: uppercase;
}
```

```tsx
<span className="eyebrow">Live Grading</span>
<h2 className="mt-2 text-2xl font-semibold text-fg">How your work scores</h2>
```

### 4.3 Typographic hero example

```tsx
<section className="max-w-3xl">
  <span className="eyebrow">Karen</span>
  <h1 className="mt-4 text-[clamp(2.5rem,6vw,4.5rem)] font-bold leading-[1.05] tracking-tight text-fg">
    Work that ships,<br />graded in real time.
  </h1>
  <p className="mt-5 max-w-xl text-base leading-relaxed text-fg-secondary">
    A quiet, monochrome command center for your pipeline. Dark first.
  </p>
  <button className="mt-8 btn-primary">Get started</button>
</section>
```

---

## 5. BORDERS, CORNERS & EDGES — THE DESIGN SYSTEM'S "DECORATION"

Because there are no shadows, **borders and corners carry all the visual weight**. Get these right.

### 5.1 Border usage rule

- **`--color-border`** (subtle) → the *default* edge for any floating card, panel, or row.
- **`--color-border-light`** (strong) → interactive *inputs*, `focus` outlines, and anything
  that must read as interactive or collapsible.
- **Never** a thick border. Everything is a **hairline 1px**.

### 5.2 Focus ring (accessibility)

Focus must be obvious without shadows. Use a 2px ring in the accent with an offset gap:

```css
:focus-visible {
  outline: 2px solid var(--color-accent);
  outline-offset: 2px;
}

/* smoother for inputs */
input:focus-visible {
  outline: none;
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 18%, transparent);
}
```

### 5.3 Input styling

Flat, bordered, no shadow. Elevated surface behind it:

```css
.input {
  height: 2.5rem;
  padding: 0 .75rem;
  border: 1px solid var(--color-border-light);
  border-radius: 10px;
  background: var(--color-panel-elevated);
  color: var(--color-fg);
  font-size: .875rem;
  transition: border-color .18s ease, box-shadow .18s ease;
}
.input:hover { border-color: var(--color-fg-tertiary); }
.input:focus-visible {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-accent) 18%, transparent);
}
.input::placeholder { color: var(--color-fg-tertiary); }
.input:disabled { color: var(--color-disabled); border-color: var(--color-border); }
```

```tsx
<label className="flex flex-col gap-1.5">
  <span className="text-xs font-medium text-fg-secondary">Repository URL</span>
  <input className="input" placeholder="https://github.com/..." />
</label>
```

### 5.4 Error state

```css
.input[aria-invalid="true"], .field-error {
  border-color: var(--color-danger);
}
.field-error-msg {
  color: var(--color-danger);
  font-size: .75rem;
}
```

```tsx
<p className="field-error-msg flex items-center gap-1.5">
  <AlertCircle className="h-3.5 w-3.5" /> This field is required.
</p>
```

---

## 6. BUTTONS & INTERACTIVE ELEMENTS

### 6.1 Button scale — flat pill system

One accent (primary), one quiet (secondary), one tertiary (ghost).

```css
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: .5rem;
  height: 2.5rem; padding: 0 1rem;
  border-radius: 9999px;                 /* FULL pill */
  border: 1px solid transparent;         /* hairline, kept for consistency */
  font-size: .875rem; font-weight: 500;
  cursor: pointer; white-space: nowrap;
  transition: background-color .18s ease, border-color .18s ease, color .18s ease, transform .12s ease;
}
.btn:active { transform: translateY(1px); }

/* PRIMARY — the ONLY loud button. Solid light pill (monochrome dark theme). */
.btn-primary {
  background: var(--color-accent);
  color: var(--color-accent-contrast);
  box-shadow: none;
}
.btn-primary:hover { background: var(--color-accent-dark); }

/* SECONDARY — bordered quiet button */
.btn-secondary {
  background: transparent;
  border-color: var(--color-border-light);
  color: var(--color-fg);
}
.btn-secondary:hover { background: var(--color-bg-tertiary); }

/* TERTIARY / GHOST — text button */
.btn-ghost {
  background: transparent;
  color: var(--color-fg-secondary);
}
.btn-ghost:hover { background: var(--color-bg-tertiary); color: var(--color-fg); }

/* DANGER */
.btn-danger {
  background: transparent;
  border-color: color-mix(in srgb, var(--color-danger) 40%, transparent);
  color: var(--color-danger);
}
.btn-danger:hover { background: color-mix(in srgb, var(--color-danger) 12%, transparent); }

/* SIZES */
.btn-sm { height: 2rem; padding: 0 .75rem; font-size: .8125rem; }
.btn-lg { height: 3rem; padding: 0 1.5rem; font-size: 1rem; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
```

```tsx
<div className="flex items-center gap-2">
  <button className="btn btn-primary">Deploy</button>
  <button className="btn btn-secondary">Save as draft</button>
  <button className="btn btn-ghost">Cancel</button>
</div>
```

### 6.2 Chips / tags (filter pills)

Small, bordered or tinted, fully rounded:

```css
.chip {
  display: inline-flex; align-items: center; gap: .375rem;
  height: 1.625rem; padding: 0 .625rem;
  border-radius: 9999px;
  border: 1px solid var(--color-border);
  background: var(--color-bg-secondary);
  color: var(--color-fg-secondary);
  font-size: .75rem; font-weight: 500;
}
.chip-active {
  background: var(--color-accent);
  color: var(--color-accent-contrast);
  border-color: var(--color-accent);
}
```

```tsx
<div className="flex flex-wrap gap-2">
  <span className="chip chip-active">All</span>
  <span className="chip">Queued</span>
  <span className="chip">Running</span>
  <span className="chip">Failed</span>
</div>
```

### 6.3 Live-status badge with pulsing dot

```css
@keyframes karen-pulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }
.karen-pulse { animation: karen-pulse 1.4s ease-in-out infinite; }
```

```tsx
<span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-bg-secondary px-2.5 py-0.5 text-xs font-medium text-fg-secondary">
  <span className="karen-pulse h-1.5 w-1.5 rounded-full bg-success" aria-hidden="true" />
  Grading live
</span>
```

---

## 7. NAVIGATION & LAYOUT

### 7.1 Sidebar

Flat, spans full height on the `--color-backdrop` / `--color-sidebar` layer, **no shadow**,
hairline right border. Active item is a **subtle lifted pill** (`--color-active-bg`).

```css
.sidebar {
  width: 260px;
  background: var(--color-sidebar);
  border-right: 1px solid var(--color-border);
}
.nav-item {
  display: flex; align-items: center; gap: .75rem;
  width: 100%; height: 2.25rem; padding: 0 .75rem;
  border-radius: 10px;
  color: var(--color-fg-secondary);
  font-size: .875rem; font-weight: 500;
  transition: background-color .16s ease, color .16s ease;
}
.nav-item:hover { background: var(--color-pill-hover-bg); color: var(--color-fg); }
.nav-item-active {
  background: var(--color-active-bg);
  color: var(--color-active-fg);
}
```

```tsx
<aside className="sidebar sticky top-0 h-screen flex-col p-3 hidden md:flex">
  <nav className="flex flex-col gap-1">
    <a href="/pipeline" className={active === 'pipeline' ? 'nav-item nav-item-active' : 'nav-item'}>
      <GitBranch className="h-4 w-4" /> Pipeline
    </a>
    <a href="/branches" className="nav-item">
      <GitFork className="h-4 w-4" /> Branches
    </a>
  </nav>
</aside>
```

### 7.2 Page shell + section rhythm

```css
.page-shell { max-width: 1560px; margin: 0 auto; padding: 0 1.5rem; }
.section-space { margin-top: clamp(4rem, 10vw, 7.5rem); }
```

```tsx
<main className="page-shell py-8">
  <header className="flex items-center justify-between">
    <div>
      <span className="eyebrow">Overview</span>
      <h1 className="mt-1 text-2xl font-semibold text-fg">Dashboard</h1>
    </div>
    <button className="btn btn-primary">New run</button>
  </header>

  <section className="section-space grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
    <StatCard /><StatCard /><StatCard /><StatCard />
  </section>
</main>
```

### 7.3 Card grid (bento-style)

12-column base, broken deliberately — never uniform 50/50:

```tsx
<section className="section-space grid grid-cols-12 gap-4">
  <div className="soft-card p-5 col-span-12 lg:col-span-7">
    <GradingTrend />   {/* large chart card */}
  </div>
  <div className="soft-card p-5 col-span-12 lg:col-span-5">
    <RecentCommits />
  </div>
</section>
```

---

## 8. DATA TABLES & DENSE PANELS

### 8.1 Table

Recessed header (`--color-recessed`), hairline dividers, horizontal scroll for density,
thin custom scrollbar.

```css
.table {
  width: 100%; border-collapse: collapse; font-size: .875rem;
}
.table thead th {
  background: var(--color-recessed);
  color: var(--color-fg-secondary);
  text-align: left; font-weight: 500;
  padding: .625rem .75rem;
  border-bottom: 1px solid var(--color-border);
  white-space: nowrap;
}
.table tbody td {
  padding: .75rem;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-fg);
}
.table tbody tr:hover td { background: var(--color-bg-tertiary); }
.table tbody tr:last-child td { border-bottom: none; }
```

```tsx
<div className="soft-card overflow-hidden">
  <div className="scroll-thin overflow-x-auto">
    <table className="table">
      <thead>
        <tr><th>Commit</th><th>Author</th><th>Score</th><th>Status</th></tr>
      </thead>
      <tbody>
        <tr>
          <td className="font-mono text-xs">a3f2c1</td>
          <td>mira@acme</td>
          <td className="font-medium">0.87</td>
          <td><StatusBadge status="passed" /></td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
```

### 8.2 Custom thin scrollbar (dense panels)

```css
.scroll-thin {
  scrollbar-width: thin;
  scrollbar-color: var(--color-border) transparent;
}
.scroll-thin::-webkit-scrollbar { width: 6px; height: 6px; }
.scroll-thin::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 9999px; }
.scroll-thin::-webkit-scrollbar-track { background: transparent; }
```

---

## 9. DASHBOARD / STAT CARDS

A tight stat card consistent with the flat + hairline language:

```tsx
function StatCard({ label, value, delta, tone = 'default' }: StatCardProps) {
  return (
    <div className="soft-card flex flex-col gap-1 p-5">
      <span className="text-xs font-medium text-fg-secondary">{label}</span>
      <span className="text-2xl font-semibold tracking-tight text-fg">{value}</span>
      <span className={`text-xs font-medium ${tone === 'up' ? 'text-success' : tone === 'down' ? 'text-danger' : 'text-fg-tertiary'}`}>
        {delta}
      </span>
    </div>
  );
}
```

---

## 10. MOTION & ANIMATION

Purposeful, subtle, easing `cubic-bezier(.16, 1, .3, 1)` (expo-out). Opacity + small
translate. Never auto-loop except for live pulses.

```css
@keyframes rise {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fade-slide-up {
  from { opacity: 0; transform: translateY(16px); }
  to   { opacity: 1; transform: translateY(0); }
}
.animate-rise  { animation: rise .65s both cubic-bezier(.16,1,.3,1); }
.animate-rise-delay { animation: rise .65s .12s both cubic-bezier(.16,1,.3,1); }
.animate-fade-up { animation: fade-slide-up .5s cubic-bezier(.16,1,.3,1) both; }
```

```tsx
<section className="animate-rise">
  <h1 className="text-5xl font-bold">Dashboard</h1>
</section>
```

**Motion rules:**
- Prefer translate/opacity over layout properties.
- Keep under ~400ms.
- Respect `prefers-reduced-motion`: disable decorative motion.
- Hover is a `transition` over `background-color`/`border-color`/`color`, not new keyframes.

---

## 11. GLOBAL KEYFRAMES & UTILITIES (reference)

```css
@keyframes float { 0%,100% { transform: translateY(0) rotate(-2deg); } 50% { transform: translateY(-14px) rotate(1deg); } }
@keyframes glow { 0%,100% { opacity: .48; } 50% { opacity: .9; } }
@keyframes marquee { from { transform: translateX(0); } to { transform: translateX(-50%); } }
@keyframes check-pop { 0% { transform: scale(.4); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }

.animate-float   { animation: float 6s ease-in-out infinite; }
.animate-glow    { animation: glow 4s ease-in-out infinite; }
.animate-marquee { animation: marquee 34s linear infinite; }
.animate-marquee:hover { animation-play-state: paused; }
```

---

## 12. ANTI-PATTERNS — NEVER DO THESE

- ❌ **Drop shadows** to create depth (`box-shadow` on cards). Banned. Use borders.
- ❌ **Glassmorphism / neumorphism / glossy gradients.** No frosted glass, no inner bevels.
- ❌ **More than 2 chromatic colors.** The palette is monochrome + one accent.
- ❌ **Color as the only status signal.** Always add icon/text/shape.
- ❌ **Saturated colors on large areas.** Only small accents.
- ❌ **A gradient, purple-pink-orange hero.** Oversaturated and generic.
- ❌ **4+ font families.** Use Inter only (optionally one mono for code).
- ❌ **Body text under 16px.**
- ❌ **Stock-photo mixes / inconsistent imagery.**
- ❌ **Auto-carousels and scroll-hijacking.**
- ❌ **Magic numbers** — every value references a token.
- ❌ **Mixed icon styles** — one set (Lucide), consistent weight.

---

## 13. CONCISE STYLE SUMMARY (paste-me one-liners)

> **Colors:** dark-first monochrome; pure-black outer backdrop, `#151515`–`#1c1c1c` panels,
> hairline `#222222`/`#2a2a2a` borders; text `#f5f5f5` / `#9a9a9e` / `#5c5c60`; one light-pill
> accent (`#e4e4e7`) + green `#22c55e` for live status.

> **Borders:** all 1px hairlines, `--color-border` (subtle) for cards, `--color-border-light`
> (stronger) for inputs/focus. Borders are the ONLY depth cue.

> **Layers:** backdrop → panel → bg-secondary → bg-tertiary → recessed, stacked one
> temperature step apart, each bounded by the 1px border.

> **Shadows:** none, ever.

> **Radius:** `14px` default cards, `10px` inputs, `9999px` pills/chips/badges.

> **Type:** Inter 400–700; body 16px+; eyebrow = 12px uppercase `letter-spacing:.12em`
> `fg-tertiary`; hierarchy via weight→size→color.

> **Buttons:** primary = solid light pill (the only loud thing), secondary = bordered quiet,
> tertiary = ghost. One primary CTA per viewport.

> **Motion:** subtle rise/fade-up, expo-out `cubic-bezier(.16,1,.3,1)`, <400ms, no auto-loop
> except live pulses, respect reduced-motion.

---

## 14. HOW TO USE THIS PROMPT

1. **Paste Section 1** (Overall visual language) into any AI design tool to set intent.
2. **Paste Sections 2–3** when setting up design tokens / CSS (colors, layers, depth).
3. **Use Sections 4–9** as the exact CSS + JSX recipes for components.
4. **Reference Section 12** as the hard "no" list iteratively while reviewing output.
5. When a tool asks for "style constraints," paste **Section 13** — it is the distilled,
   copy-paste summary of everything above.
