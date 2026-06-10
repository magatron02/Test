---
name: Aiterra v2.0.0
description: Personal AI crypto trading system — live signals, ML training, portfolio intelligence
colors:
  bg-void: "#000000"
  bg-surface: "#0c0c0c"
  bg-raised: "#0d0d0d"
  border-dim: "#222222"
  border-subtle: "#2a2a2a"
  ink-primary: "#ffffff"
  ink-muted: "#666666"
  neural-lime: "#A8FF53"
  neural-lime-bright: "#C6FF80"
  signal-green: "#39d98a"
  signal-orange: "#ff6b35"
  signal-alert: "#ff4d6d"
  signal-caution: "#ffc107"
typography:
  display:
    fontFamily: "Finlandica, sans-serif"
    fontSize: "1.65rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.5px"
  headline:
    fontFamily: "Finlandica, sans-serif"
    fontSize: "1.15rem"
    fontWeight: 700
    lineHeight: 1.3
  title:
    fontFamily: "Finlandica, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: "Noto Sans, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Space Mono, monospace"
    fontSize: "0.65rem"
    fontWeight: 400
    letterSpacing: "1.2px"
  data:
    fontFamily: "Space Mono, monospace"
    fontSize: "0.82rem"
    fontWeight: 400
rounded:
  sharp: "2px"
  sm: "3px"
  md: "4px"
  lg: "14px"
  pill: "100px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  content: "36px"
components:
  button-primary:
    backgroundColor: "{colors.neural-lime}"
    textColor: "#000000"
    rounded: "{rounded.md}"
    padding: "8px 16px"
    typography: "Finlandica 700"
  button-primary-hover:
    backgroundColor: "{colors.neural-lime-bright}"
    textColor: "#000000"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-success:
    backgroundColor: "{colors.signal-green}"
    textColor: "#000000"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-danger:
    backgroundColor: "{colors.signal-orange}"
    textColor: "#000000"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.md}"
    padding: "5px 14px"
  button-ghost-hover:
    backgroundColor: "rgba(168,255,83,0.06)"
    textColor: "{colors.neural-lime}"
    rounded: "{rounded.md}"
    padding: "5px 14px"
  nav-pill:
    backgroundColor: "{colors.bg-surface}"
    textColor: "{colors.ink-muted}"
    rounded: "{rounded.pill}"
    padding: "6px 16px"
  nav-pill-active:
    backgroundColor: "{colors.ink-primary}"
    textColor: "#000000"
    rounded: "{rounded.pill}"
    padding: "6px 16px"
  input-field:
    backgroundColor: "{colors.bg-raised}"
    textColor: "{colors.ink-primary}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
---

# Design System: Aiterra v2.0.0

## 1. Overview

**Creative North Star: "The Sentient Engine"**

Aiterra's visual system is built around one idea: an AI that never sleeps. The screen is not a dashboard you check once; it is the face of a system that is actively running, trading, and learning right now. Every visual element either carries live data or conveys the state of the engine. There is no decoration that is not also information.

The aesthetic is pure functional darkness. Black is not a mood choice; it is the canvas that makes signals legible. The Neural Lime accent exists precisely because it is the least natural color in the financial world, making every actionable element immediately distinguishable from data. The system reads like instrument glass at night: everything that matters glows; everything else recedes.

Typography is a three-role system: Finlandica for human-readable labels and headings (the interface layer), Noto Sans for Thai and English prose (the explanation layer), and Space Mono for all numeric and identifier data (the machine layer). This separation is not aesthetic; it is semantic. A number in the wrong font is a warning sign.

**Key Characteristics:**
- Pure black void canvas with glassmorphic card surfaces
- One accent color (Neural Lime) reserved for primary actions, active states, and the AI's output signal
- Three semantic fonts, each with exactly one role
- Motion conveys state: every animation signals that something changed, not that the page loaded
- Data density is a feature, not a problem to solve

## 2. Colors: The Signal Palette

Black void with one electrified accent and a semantic signal vocabulary.

### Primary
- **Neural Lime** (`#A8FF53`): The AI's voice. Used for primary actions (buttons, active nav pills, active tabs), the primary BUY/neutral indicator, links, accent glows, and the chat FAB. Its rarity against the void background is its power. Never used decoratively.
- **Neural Lime Bright** (`#C6FF80`): Hover variant. Appears only on hover states of Neural Lime elements. Not used as a standalone color.

### Secondary
- **Signal Green** (`#39d98a`): The BUY signal color. Used exclusively for positive trade outcomes, BUY badges, success buttons, and the WebSocket connected pulse. Semantically distinct from Neural Lime: Neural Lime is the AI's active state; Signal Green is a positive market outcome.
- **Signal Orange** (`#ff6b35`): The SELL signal color. Used for SELL badges, negative PnL, danger buttons, and the BEAR regime badge. Never used where a neutral warning is intended.

### Tertiary
- **Signal Alert** (`#ff4d6d`): CRASH regime only. Carries an animated pulse to signal emergency market conditions. The only pulsing color in the system; its animation is a feature, not decoration.
- **Signal Caution** (`#ffc107`): Volatile regime badge. Informational warning; no animation.

### Neutral
- **Void** (`#000000`): The body background. Not a dark gray; not a tinted near-black. Pure void.
- **Surface** (`#0c0c0c` at 60% opacity with blur): Card and panel backgrounds via glassmorphism. The 40% transparency lets the void breathe through, preventing cards from feeling like opaque boxes.
- **Raised** (`#0d0d0d`): Card headers, secondary backgrounds, input backgrounds. Slightly lighter than surface but not enough to feel like a step; it is a whispering distinction.
- **Border Dim** (`#222222`): Primary borders. Barely visible; their job is structure, not decoration.
- **Border Subtle** (`#2a2a2a`): Secondary borders on inputs and inner separations.
- **Ink Primary** (`#ffffff`): All primary text. Full white, never gray-shifted, never dimmed.
- **Ink Muted** (`#666666`): Secondary labels, inactive nav items, form labels. At 4.5:1 on void this is borderline; never use for body prose, only short labels.

### Named Rules

**The One Signal Rule.** Neural Lime appears on active, primary, and AI-output elements only. If it appears on something inactive, neutral, or decorative, that element is misclassified. Rarity is the point.

**The Semantic Separation Rule.** Signal Green is a positive market outcome. Neural Lime is an active system state. They are different things. Never substitute one for the other.

## 3. Typography: The Three Layers

**Display/UI Font:** Finlandica (italic available, wght 400–700)
**Body/Prose Font:** Noto Sans (Thai + Latin, wght 300–700)
**Data/Mono Font:** Space Mono (wght 400/700)

**Character:** Finlandica's slightly condensed proportions and high x-height make it readable at small sizes in dense interfaces. Paired with Noto Sans for body prose (the only font that handles Thai script correctly at small weights), and Space Mono for the machine layer — prices, rates, identifiers, timestamps.

### Hierarchy

- **Display** (Finlandica 700, 1.65rem, lh 1.15, ls -0.5px): Stat values in portfolio cards. Large numbers that need visual weight.
- **Headline** (Finlandica 700, 1.15rem, lh 1.3): Brand name, section page titles.
- **Title** (Finlandica 600, 0.9rem, lh 1.4): Price card symbols, component headings.
- **Body** (Noto Sans 400, 14px, lh 1.55): Activity feed text, alert copy, form labels (prose). Thai and English mixed content. Max line length 65–75ch.
- **Label / Card Header** (Space Mono 400, 0.65rem, ls 1.2px, uppercase): Card header titles, stat labels below numbers. Uppercase is permitted for labels ≤4 words in this font only.
- **Data / Prices** (Space Mono 400, 0.82rem): All numeric data: prices, PnL values, win rates, timestamps, ticker symbols, API keys.

### Named Rules

**The Machine Layer Rule.** Every number, rate, identifier, timestamp, and price renders in Space Mono. If a number appears in Finlandica or Noto Sans, it is wrong. The font choice encodes the data type.

**The Thai-Latin Contract.** Noto Sans handles both scripts. Any Thai body text in Finlandica or Space Mono will render incorrectly at some sizes. Prose is always Noto Sans.

## 4. Elevation: The Fog Layer

This system uses tonal glassmorphism rather than traditional shadows. Depth is conveyed through transparency and blur, not shadow casting. Cards float above the void by letting the void bleed through, not by casting light downward.

Base rule: surfaces are semi-transparent, never opaque. The void is always visible through the card layer. This creates a sense of depth without heaviness.

### Shadow Vocabulary

- **Void Bleed** (`background: rgba(12,12,12,0.6); backdrop-filter: blur(20px)`): Standard card. The transparency is structural: it conveys that the card is a lens, not a box.
- **Stat Surface** (`rgba(12,12,12,0.55)` at `blur(18px)`): Slightly thinner than card. Stat cards are lighter weight; they should feel like data readouts, not containers.
- **Accent Glow** (`box-shadow: 0 6px 28px rgba(168,255,83,0.13)`): Applied to interactive cards on hover. The accent color bleeds outward; the card activates.
- **Button Glow** (`box-shadow: 0 0 22px rgba(168,255,83,0.28)`): Primary button hover. Signals that the action is ready.
- **Chat Depth** (`box-shadow: 0 20px 70px rgba(0,0,0,0.8)`): Chat panel. The deepest shadow in the system; it establishes the chat panel as a modal layer above everything else.
- **Top Accent Line** (`::before` gradient from transparent to `rgba(168,255,83,0.12)` to transparent): A 1px horizontal line at the top of every card. This is the system's signature: the card breathes Neural Lime from its crown.

### Named Rules

**The Fog Layer Rule.** All cards are semi-transparent. No card has an opaque background. If a design calls for an opaque panel, it is either a fullscreen modal (the chat panel precedent) or a mistake.

**The Flat-at-Rest Rule.** Shadows appear only in response to state (hover, active, focus). At rest, a card has only its top-accent line and its transparent background. No ambient shadows on resting elements.

## 5. Components

### Navigation

The topnav is the cockpit. It persists across all views, sticky at 62px height, with blur backdrop. Navigation is pill-shaped: inactive pills are ghost with muted text; the active pill is white with black text — the highest contrast possible on a dark background.

- **Topnav background:** `rgba(0,0,0,0.80)` + `blur(24px)`. Not fully opaque; the page scrolls behind it.
- **Pill container:** `rgba(255,255,255,0.04)` with `rgba(255,255,255,0.07)` border.
- **Active pill:** white background (`#fff`), black text, weight 700. No color, just inversion.
- **Hover pill:** text shifts to Ink Primary. No background change.

### Buttons

Four button classes, each semantically distinct:

- **Primary** (Neural Lime bg, black text, Finlandica 700): For the AI's primary action calls. Hover: Neural Lime Bright + accent glow. Active: scale(0.96).
- **Success** (Signal Green bg, black text): For BUY / open long actions specifically.
- **Danger** (Signal Orange bg, black text): For SELL / close / stop-loss actions specifically.
- **Ghost** (transparent bg, Border Subtle border, muted text): Secondary and destructive-secondary actions. Hover: accent tint background, Neural Lime text.

All buttons: 4px radius, Finlandica 700, active scale transform `scale(0.96)` for tactile click feedback.

### Cards / Containers

The system's signature component. Every card is a glassmorphic lens over the void.

- **Corner Style:** Sharp (4px radius). Not rounded.
- **Background:** `rgba(12,12,12,0.6)` + `backdrop-filter: blur(20px)`.
- **Border:** `1px solid rgba(255,255,255,0.05)` — barely visible, structural only.
- **Top Accent Line:** `::before` pseudo-element, 1px gradient from transparent → `rgba(168,255,83,0.12)` → transparent, 70% width centered.
- **Card Header:** `#0d0d0d` background, 1px border-bottom, Space Mono uppercase 0.82rem, muted text.
- **Internal Padding:** 16px (card-body), 11px 16px (card-header).
- **Hover:** `translateY(-2px)` + border shifts toward accent, ambient glow appears. Only on interactive cards (price-card, stat-card).

### Inputs / Fields

- **Background:** `#0d0d0d` (Raised surface).
- **Border:** 1px `#2a2a2a` (Border Subtle).
- **Radius:** 4px.
- **Focus:** Border shifts to Neural Lime; `box-shadow: 0 0 0 2px rgba(168,255,83,0.12)`.
- **Placeholder:** `#666666` (Ink Muted). This is the minimum acceptable; do not dim further.
- **Input labels:** Space Mono, 0.7rem, uppercase, muted. These are identifiers, not prose.

### Badges and Chips

Two badge systems, semantically distinct:

- **Signal badges** (BUY/SELL/HOLD): Transparent background tint, colored border. Space Mono 0.62rem, letter-spacing 0.8px, uppercase. 3px radius.
- **Regime badges** (BULL/BEAR/RANGE/VOL/CRASH): Same structure. CRASH is the only badge with a pulse animation — reserved for emergency conditions only.
- **Pattern pills:** 100px radius (pill shape), mono font. More rounded than badges to signal they are filters/tags rather than states.

### The Chat FAB

Signature component: Neural Lime floating action button, fixed bottom-right, 52px circle, with `box-shadow: 0 4px 20px rgba(168,255,83,0.4)` ambient glow at rest. On hover: `scale(1.1)` + intensified glow. This is the only element in the system with an ambient glow at rest — it signals AI availability at all times.

The chat panel itself: 360px wide, `rgba(10,10,10,0.95)` with `blur(28px)`, 14px border-radius, shadow `0 20px 70px rgba(0,0,0,0.8)`.

### Tables

- Headers: Space Mono, 0.65rem, uppercase, muted. The machine layer signals this is data.
- Rows: 0.82rem, Noto Sans, full white text. Hover: `rgba(168,255,83,0.04)` tint — barely perceptible but present.
- Border: `#222222`, not removed.

## 6. Do's and Don'ts

### Do:

- **Do** render all numeric data in Space Mono. Prices, rates, percentages, timestamps — no exceptions.
- **Do** use Neural Lime only for active states, primary actions, and AI-signal outputs. Its rarity is functional.
- **Do** keep cards semi-transparent with backdrop blur. Every card is a lens; opacity kills the depth system.
- **Do** add the `::before` top-accent glow line to every card. It is the system's visual signature.
- **Do** animate on state change only. Hover lifts and glows signal interactivity; they are not decoration.
- **Do** use Signal Green for BUY and positive outcomes, Signal Orange for SELL and negative outcomes, and never mix them.
- **Do** use Finlandica for UI labels and navigation; Noto Sans for Thai or multi-line body prose.
- **Do** include `:focus-visible` ring (2px Neural Lime glow) on all interactive elements.
- **Do** add `@media (prefers-reduced-motion: reduce)` for every animation. Replace transforms with instant opacity transitions.

### Don't:

- **Don't** use a SaaS metric dashboard aesthetic: white backgrounds, bland card grids, cream neutrals, or generic B2B layout patterns. This system must be unrecognizable as an HR tool.
- **Don't** use Neural Lime decoratively, or on inactive/neutral elements. If it appears on something the user isn't acting on, it is wrong.
- **Don't** use glassmorphism on components that aren't cards or overlays. The blur effect is the card system; applying it to buttons or labels dilutes the hierarchy.
- **Don't** use gradient text (`background-clip: text`). Use a single solid color. Emphasis through weight or size.
- **Don't** put numbers in Finlandica or Noto Sans. The machine layer exists precisely to distinguish data from labels.
- **Don't** animate layout properties. Only transform and opacity. No width/height/margin animations.
- **Don't** add uppercase tracking to prose or body copy. Uppercase is for Space Mono labels (≤4 words) and signal badges only.
- **Don't** use arbitrary z-index values (no 999 or 9999). Use the semantic scale: nav (200), notification (300), chat panel (8999), chat FAB (9000).
- **Don't** make cards opaque. Semi-transparency is structural, not decorative.
- **Don't** add a second floating action button. The chat FAB with its ambient glow is a signature; a second FAB competes with it.
