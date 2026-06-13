---
name: Aiterra v2.0.0
description: Personal AI crypto trading system — live signals, ML training, portfolio intelligence
register: product
colors:
  bg-dark:       "#060708"
  bg-deep:       "#030304"
  bg-card:       "rgba(255,255,255,0.055)"
  bg-card2:      "rgba(255,255,255,0.028)"
  bg-solid:      "#0c0e11"
  border:        "rgba(255,255,255,0.10)"
  border2:       "rgba(255,255,255,0.055)"
  text-main:     "rgba(255,255,255,0.95)"
  text-muted:    "rgba(255,255,255,0.64)"
  text-dim:      "rgba(255,255,255,0.50)"
  ink:           "rgba(255,255,255,0.95)"
  on-ink:        "#07080a"
  accent:        "#9db8b0"
  accent-buy:    "#34d399"
  accent-red:    "#f87171"
  accent-blue:   "#5eead4"
  accent-yellow: "#fbbf24"
  accent-purple: "#c4b5fd"
  glass-blur:    "26px"
  glass-hi:      "rgba(255,255,255,0.13)"
typography:
  root-font-size: "17px"
  body:
    fontFamily: "Geist, Noto Sans Thai, Inter, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  headline:
    fontFamily: "Geist, Noto Sans Thai, Inter, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 600
    lineHeight: 1.3
  mono:
    fontFamily: "Geist Mono, JetBrains Mono, Courier New, monospace"
    fontSize: "0.9rem"
    fontWeight: 400
  stat-value:
    fontSize: "2.15rem"
    fontWeight: 700
    letterSpacing: "-0.75px"
rounded:
  card:   "16px"
  sm:     "10px"
  pill:   "100px"
---

# Design System: Aiterra v2.0.0 — DeFi Luxe / Frosted Glass

## 1. Overview

**Aesthetic: Dark Luxe Trading Terminal**

Pure-black canvas lit by soft ambient glow; data sits on frosted-glass panels that refract the light behind them. Modeled on premium DeFi landing-page craft (frosted glass, luminous fog, large refined display type, white pill nav) adapted to a dense single-operator trading dashboard. Interactive lead is monochrome white; one cool luminous tone (sage-silver) carries links / charts / AI-alive; green & red are reserved strictly for trade signals, so they pop against the monochrome field.

**Key Characteristics:**
- Near-black canvas `#060708` over a **top-lit base gradient** (`#11151a → #030304`) so the field has dimension, plus fixed radial **ambient glow** (silver-sage bloom top, sage corner, vignette frame) drifting slowly, plus a **film-grain** overlay
- **Frosted glass surfaces** — translucent white-alpha bg + `backdrop-filter: blur(26px) saturate(140%)` + top-edge sheen highlight; the glow shows THROUGH the glass
- Geist + Geist Mono (Vercel); `html { font-size: 17px }` base scale
- Large refined display: stat-value 2.45rem / hero 2.9rem, weight 600, tight tracking (−1.2 to −1.6px)
- Text: `rgba(255,255,255,0.95)` main / `0.64` muted / `0.50` dim — all ≥4.5:1 on black
- Borders: hairline white-alpha (`0.10` / `0.055`), never color-tinted
- **Monochrome interactive**: active nav = white pill + dark text (sliding indicator); `#9db8b0` sage-silver accent for links/focus/charts/live-pulse only
- `#34d399` BUY / `#f87171` SELL — the only chroma in the data field
- `font-variant-numeric: tabular-nums` on all data/money elements
- Motion: ease-out-expo entrances, soft 24s ambient drift, M3 spring on signals

## 2. Color Tokens

CSS variables defined in `:root`.

| Token | Value | Use |
|-------|-------|-----|
| `--bg-dark` | `#060708` | Page canvas (near-black) |
| `--bg-deep` | `#030304` | Deepest well behind glow |
| `--bg-card` | `rgba(255,255,255,0.055)` | Frosted glass surface (2dp) |
| `--bg-card2` | `rgba(255,255,255,0.028)` | Sunken glass — headers, inputs (1dp) |
| `--bg-solid` | `#0c0e11` | Opaque fallback — dropdowns, menus, dense tables |
| `--border` | `rgba(255,255,255,0.10)` | Primary hairline dividers |
| `--border2` | `rgba(255,255,255,0.055)` | Secondary dividers, input borders |
| `--text-main` | `rgba(255,255,255,0.95)` | High-emphasis text |
| `--text-muted` | `rgba(255,255,255,0.64)` | Medium-emphasis labels |
| `--text-dim` | `rgba(255,255,255,0.50)` | Low-emphasis mono micro-labels (≥4.5:1) |
| `--ink` | `rgba(255,255,255,0.95)` | Monochrome action surface (white pill) |
| `--on-ink` | `#07080a` | Text on white pill |
| `--accent` | `#9db8b0` | Sage-silver — links, focus, chart line, AI-alive pulse |
| `--accent-buy` | `#34d399` | BUY signal, positive PnL |
| `--accent-red` | `#f87171` | SELL signal, negative PnL |
| `--accent-blue` | `#5eead4` | Secondary informational |
| `--accent-yellow` | `#fbbf24` | Caution / volatile regime |
| `--accent-purple` | `#c4b5fd` | Secondary informational |
| `--glass-blur` | `26px` | Card backdrop blur |
| `--glass-hi` | `rgba(255,255,255,0.13)` | Glass top-edge highlight |

### Background System (fixed, behind everything)

Layers under content (`z-index:0`); app chrome rides at `z-index:1`:

1. **Base gradient** (on `body`): `radial-gradient(150% 100% at 50% -10%, #0d1014 → #030304)` — top-lit dimension so the canvas is never flat black; also the fallback if the image fails.
2. **Background image** (`body::before`, fixed, `cover`): a monochrome photo served from `/static/img/`, heavily dimmed by stacked overlays so it never washes out the UI.
   - **Dashboard** = `bg-dashboard.jpg` (greyscale nebula): dim `linear-gradient(rgba(6,7,8,0.72) → rgba(4,4,5,0.84))` + vignette `radial(transparent 46% → rgba(0,0,0,0.7))`. Keep it dark.
   - **Landing** = `bg-landing.jpg` (white line-art poster): lighter dim `rgba(6,7,8,0.40 → 0.56)` + vignette + faint sage glow.
   - No blur filter and no transform animation on this layer (perf: animating a blurred full-screen layer re-rasterizes every frame).
3. **Film grain** (`body::after`): fine SVG fractal-noise, `baseFrequency:1.1`, tiled at `130px`, `opacity:0.11`, `mix-blend-mode:screen` (screen makes grain visible on near-black; soft-light vanishes on black). Grain lives ONLY on the background, never on cards/buttons.

**Performance rules** (learned the hard way): backdrop-filter blur on glass = `15px` (not 26px); no `background-attachment:fixed`; no animated blur filter. These three are what keep scroll/transitions smooth.

### Signal Color Rules

- Interactive lead is **monochrome**: active nav pill = `--ink` (white) + `--on-ink` (near-black). Primary button = sage-silver `--accent`.
- `--accent-buy` (#34d399) — BUY badges, positive numbers, bull regime
- `--accent-red` (#f87171) — SELL badges, negative numbers, bear regime
- `--accent` (#9db8b0) — links, focus rings, chart line, live-pulse dot ONLY (not a surface)
- **Forbidden:** `#00A8E8` (old Fresh Sky cyan), `#A8FF53` (Neural Lime), `#ff6b35` (Signal Orange)

## 3. Typography

Two font families. `html { font-size: 17px }` — all rem values scale from this.

| Role | Font | Size | Weight | Use |
|------|------|------|--------|-----|
| Body/UI | Geist | 1rem (17px) | 400 | All UI text, prose |
| Headline | Geist | 0.95rem | 600–700 | Card headers, section titles |
| Stat value | Geist | 2.15rem | 700 | Portfolio value, main KPIs |
| Hero value | Geist | 3rem | 700 | Dashboard hero number |
| Mono/Data | Geist Mono | 0.9rem | 400–700 | Prices, rates, timestamps, tickers |

**Fallback chain:** Geist → Noto Sans Thai → Inter → sans-serif
**Mono fallback:** Geist Mono → JetBrains Mono → Courier New

### Size Floor

- Minimum for any functional label: **11px**
- Micro-labels (uppercase, mono): 0.72rem ≈ 12px
- Dense card internals: 12–13px (never below 11px)

### Machine Layer Rule

Every number, rate, identifier, timestamp, and price renders in Geist Mono with `font-variant-numeric: tabular-nums`. Font choice encodes data type — prose = Geist, data = Geist Mono.

### letter-spacing

- Geist body/headline: `-0.1px` to `0`
- Mono uppercase labels: `0.5–0.8px`
- Stat values: `-0.75px`

### Typography Scale (actual CSS values)

```css
.stat-value      { font-size: 2.45rem; font-weight: 600; letter-spacing: -1.2px; }
#totalValue      { font-size: 2.9rem;  font-weight: 600; letter-spacing: -1.6px; }
.stat-label      { font-size: 0.78rem; font-weight: 500; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.9px; }
.badge-signal    { font-size: 0.72rem; }
.card-header     { font-size: 1rem; font-weight: 600; letter-spacing: -0.3px; }
.table td, th    { font-size: 0.9rem; padding: 9px 12px; }
.table thead th  { font-size: 0.74rem; letter-spacing: 0.8px; }
.btn-sm          { font-size: 0.82rem; }
.tab-btn         { font-size: 0.85rem; }
.form-label      { font-size: 0.72rem; letter-spacing: 0.6px; }
```

## 4. Surfaces & Elevation — Frosted Glass

Surfaces are **translucent glass**: the ambient glow refracts through them. Radius is generous (`--radius-card: 20px`). The blur is the committed brand material, not decoration — it only works because there is light (the ambient glow) behind it.

```css
.card, .stat-card {
  background: rgba(255,255,255,0.055);
  backdrop-filter: blur(26px) saturate(140%);
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 20px;
  box-shadow: inset 0 1px 0 var(--glass-hi),   /* crisp top edge */
              0 16px 40px rgba(0,0,0,0.42);      /* float */
}
/* top-edge sheen that sells the glass */
.card::before {
  content:''; position:absolute; inset:0; border-radius:inherit;
  background: linear-gradient(180deg, rgba(255,255,255,0.075) 0%, transparent 26%);
}
```

**Opaque exceptions:** dropdowns / `<select>` menus use `--bg-solid` (`#0c0e11`) so popups stay legible. ApexCharts tooltip: `rgba(8,10,12,0.80)` + `blur(16px)`.

Glass nests one level only (page glass → inner glass). Avoid deeper nesting; let inner content sit on the parent glass.

## 5. Components

### Navigation (sidebar)

Left rail `.sidebar` — frosted glass (`rgba(255,255,255,0.022)` + `blur(24px)`), hairline right border. `.topnav` is hidden (legacy).

- **Active item**: white **sliding indicator** pill (`--ink`, `inset 0 1px 0 rgba(255,255,255,0.5)`) that morphs between items with `transform`/`height` over `0.38s --ease-exp-out`. Active label + icon flip to `--on-ink` (near-black); kbd-hint flips to dark-on-white.
- **Inactive**: `--text-muted`, hover → white-alpha `0.05` bg + `--text-main`.
- Fallback (no-JS first paint): active item gets solid `--ink` bg directly.

### Cards

```css
background: var(--bg-card);            /* translucent glass */
backdrop-filter: blur(var(--glass-blur)) saturate(140%);
border: 1px solid var(--border);
border-radius: var(--radius-card);     /* 20px */
box-shadow: inset 0 1px 0 var(--glass-hi), 0 16px 40px rgba(0,0,0,0.42);
```

Card headers: transparent bg, `--text-main` at 1rem Geist 600, `letter-spacing:-0.3px`, `border-bottom: 1px solid var(--border)`.

### Stat Cards

```css
.stat-card { padding: 18px; box-shadow: 0 4px 24px rgba(0,0,0,0.15); }
.stat-card.sc-buy  { background: rgba(57,217,138,0.06); border-color: rgba(57,217,138,0.18); }
.stat-card.sc-lime { background: rgba(0,168,232,0.06);  border-color: rgba(0,168,232,0.18); }
.stat-card.sc-red  { background: rgba(239,68,68,0.06);  border-color: rgba(239,68,68,0.18); }
```

### Buttons

| Type | Background | Text | Border |
|------|-----------|------|--------|
| Primary | `--accent` (#00A8E8) | `#00171F` | — |
| Buy | `rgba(34,197,94,0.15)` | `--accent-buy` | green |
| Sell/Danger | `rgba(239,68,68,0.15)` | `--accent-red` | red |
| Ghost | transparent | `--text-muted` | `--border2` |

All buttons: `border-radius: 10px`, Geist 700, `transition: transform 0.1s + box-shadow 0.15s`.

### Signal Badges

Geist Mono, `0.72rem`, `border-radius: 100px`, `font-weight: 700`, `letter-spacing: 0.5px`.

| Type | Background | Text | Border |
|------|-----------|------|--------|
| BUY | `rgba(57,217,138,0.12)` | `--accent-buy` | `rgba(57,217,138,0.25)` |
| SELL | `rgba(239,68,68,0.12)` | `--accent-red` | `rgba(239,68,68,0.25)` |
| HOLD | `rgba(102,102,102,0.12)` | `--text-muted` | `rgba(102,102,102,0.25)` |

### Charts (ApexCharts)

```javascript
chart: {
  background: 'transparent',
  foreColor: 'rgba(255,255,255,0.40)',
  fontFamily: "'Geist Mono','JetBrains Mono',monospace",
}
grid: { borderColor: 'rgba(255,255,255,0.07)', strokeDashArray: 4 }
// Candlestick
colors: { upward: '#00A8E8', downward: '#EF4444' }
// Area fill
fill: { type:'gradient', gradient:{ shadeIntensity:1, opacityFrom:0.28, opacityTo:0, stops:[0,80,100] } }
// Axis labels
labels: { style: { colors: 'rgba(255,255,255,0.40)', fontSize: '11px' } }
```

**Tooltip (frosted glass, bklit-ui style):**

```css
.apexcharts-tooltip {
  background: rgba(13,17,23,0.82) !important;
  backdrop-filter: blur(14px) !important;
  border: 1px solid rgba(255,255,255,0.10) !important;
  border-radius: 12px !important;
  box-shadow: 0 12px 40px rgba(0,0,0,0.55), 0 0 0 0.5px rgba(255,255,255,0.06) !important;
}
.apexcharts-tooltip-title {
  background: rgba(255,255,255,0.04) !important;
  border-bottom: 1px solid rgba(255,255,255,0.08) !important;
  font-family: var(--font-mono) !important;
  font-size: 11px !important;
  font-variant-numeric: tabular-nums !important;
  color: rgba(255,255,255,0.45) !important;
}
```

## 6. Motion System (M3-inspired)

### Easing Tokens

```css
--ease-exp-out: cubic-bezier(0.05, 0.7, 0.1, 1.0);   /* most entrances */
--ease-spring:  cubic-bezier(0.34, 1.56, 0.64, 1);    /* pop-in, spring */
--dur-xs: 80ms;  --dur-sm: 150ms;  --dur-md: 250ms;
--dur-lg: 350ms; --dur-xl: 450ms;
```

### Keyframes

| Name | Use |
|------|-----|
| `sectionIn` | Section tab entrance — translateY(22px)+scale(0.97) → 0 |
| `m3SpringPop` | Signal card / feed item pop-in |
| `m3SlideUp` | Staggered list item entrance |
| `m3ValUp` / `m3ValDown` | Stat value green/red flash on change |
| `m3ToastIn` | Toast spring entrance from right |
| `m3GlowRing` | Pulse glow ring on interactive elements |
| `m3Shimmer` | Skeleton loading state |

### Interaction Rules

- Section entrance: `sectionIn` 350ms `--ease-exp-out`
- Signal cards: staggered `m3SpringPop` with `--stagger` index × 55ms
- Stat values: `_m3Stat(id, val)` → flash green (up) or red (down) on change
- Price cards: `_m3Ripple()` on click — radial gradient at cursor position
- Sidebar nav: sliding indicator pill morphs between items (absolutely positioned)
- All animations wrapped in `@media (prefers-reduced-motion: reduce)` — instant or no-op

## 7. Material Web Components (@material/web)

Loaded via ESM CDN. M3 sys color tokens mapped to M2 dark theme.

| Component | Used for |
|-----------|---------|
| `md-switch` | dryRunToggle (topbar), schedEnabled (Settings) |
| `md-linear-progress` | Signal card confidence bar (track: `rgba(255,255,255,0.08)`) |
| `md-circular-progress` | All loading spinners via `_spin()` helper |

## 8. Light Mode

Secondary theme; the glass/glow system is tuned for dark. `[data-theme="light"]` overrides:

| Token | Light Value | Note |
|-------|------------|------|
| `--bg-dark` | `#F2F3F8` | — |
| `--bg-card` | `#FFFFFF` | opaque (blur becomes a no-op over solid) |
| `--bg-card2` | `#ECEDF5` | — |
| `--border` | `rgba(0,0,0,0.08)` | — |
| `--text-main` | `#0D0D1A` | — |
| `--text-muted` | `#8888A8` | — |
| `--ink` | `#11131a` | nav pill flips to **dark** pill |
| `--on-ink` | `#ffffff` | white text on dark pill |

Also: `body::before` glow dimmed to `opacity:0.32`, `body::after` grain off, active nav kbd-hint flips light-on-dark.

## 9. Do's and Don'ts

### Do:
- Render all numeric/price data in Geist Mono with `tabular-nums`
- Use `--accent-buy` (#34d399) for BUY / positive, `--accent-red` (#f87171) for SELL / negative — the only chroma in the data field
- Keep interactive lead **monochrome**: active nav = white pill; reserve `--accent` sage-silver for links/focus/charts/live-pulse only
- Treat the **ambient glow as the light source** — glass reads as glass only because the glow sits behind it; don't remove one without the other
- Keep glass nesting to one level; opaque (`--bg-solid`) for dropdowns/menus
- `--text-main` (0.95) primary, `--text-muted` (0.64) secondary, `--text-dim` (0.50) micro-labels — all ≥4.5:1
- Floor functional labels at 11px

### Don't:
- Use `#00A8E8` old cyan, `#A8FF53` Neural Lime, or `#ff6b35` Signal Orange — all removed
- Use `--accent` as a fill/surface — it is a luminous accent, not a background
- Use DM Sans, Space Mono, or Finlandica — removed
- Stack glass on glass on glass (more than one nested blur level)
- Use colored borders as structural dividers (hairline white-alpha only)
- Let signal green/red leak into non-signal UI — it dilutes the 200ms read
- Set labels below 11px
