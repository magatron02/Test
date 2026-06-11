---
name: Aiterra v2.0.0
description: Personal AI crypto trading system — live signals, ML training, portfolio intelligence
register: product
colors:
  bg-dark:      "#080808"
  bg-card:      "#111111"
  bg-card2:     "#181818"
  bg-canvas:    "#080808"
  border:       "rgba(255,255,255,0.12)"
  border2:      "rgba(255,255,255,0.08)"
  text-main:    "#F2F2FC"
  text-muted:   "#9898AE"
  accent:       "#A8FF53"
  accent-buy:   "#22C55E"
  accent-red:   "#EF4444"
  accent-blue:  "#60A5FA"
  accent-yellow: "#FACC15"
  accent-purple: "#A78BFA"
typography:
  body:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.5
  headline:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 700
    lineHeight: 1.3
  label:
    fontFamily: "DM Sans, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 600
    letterSpacing: "0.4px"
  mono:
    fontFamily: "Space Mono, Courier New, monospace"
    fontSize: "0.82rem"
    fontWeight: 400
rounded:
  card:   "16px"
  sm:     "10px"
  pill:   "100px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#000000"
    rounded: "{rounded.sm}"
    padding: "6px 16px"
    typography: "DM Sans 700"
  button-buy:
    backgroundColor: "rgba(34,197,94,0.15)"
    textColor: "{colors.accent-buy}"
    border: "1px solid rgba(34,197,94,0.3)"
    rounded: "{rounded.sm}"
  button-sell:
    backgroundColor: "rgba(239,68,68,0.15)"
    textColor: "{colors.accent-red}"
    border: "1px solid rgba(239,68,68,0.3)"
    rounded: "{rounded.sm}"
  card:
    backgroundColor: "{colors.bg-card}"
    border: "1px solid {colors.border}"
    rounded: "{rounded.card}"
    padding: "0"
  card-header:
    backgroundColor: "{colors.bg-card2}"
    borderBottom: "1px solid {colors.border}"
    padding: "10px 16px"
    fontSize: "0.78rem"
    fontFamily: "DM Sans"
    fontWeight: 600
    textColor: "{colors.text-main}"
  nav-pill-active:
    backgroundColor: "{colors.text-main}"
    textColor: "#080808"
    rounded: "{rounded.pill}"
    padding: "5px 16px"
    fontWeight: 700
  nav-pill-inactive:
    backgroundColor: "transparent"
    textColor: "{colors.text-muted}"
    rounded: "{rounded.pill}"
    padding: "5px 16px"
  signal-badge-buy:
    backgroundColor: "rgba(57,217,138,0.12)"
    textColor: "{colors.accent-buy}"
    border: "1px solid rgba(57,217,138,0.25)"
    rounded: "{rounded.pill}"
    fontFamily: "Space Mono"
    fontSize: "0.62rem"
  signal-badge-sell:
    backgroundColor: "rgba(239,68,68,0.12)"
    textColor: "{colors.accent-red}"
    border: "1px solid rgba(239,68,68,0.25)"
    rounded: "{rounded.pill}"
    fontFamily: "Space Mono"
    fontSize: "0.62rem"
---

# Design System: Aiterra v2.0.0 — Finance Aesthetic

## 1. Overview

**Aesthetic: Finance Terminal**

Clean, dense, and readable. The design is modeled after professional trading terminals — Bloomberg, TradingView dark mode — rather than SaaS dashboards or glassmorphic app UI. Every pixel serves data legibility.

The background is near-void (`#080808`), cards are solid (`#111111`), and typography is DM Sans throughout. The only decoration is the Neural Lime accent (`#A8FF53`) which marks active states and the AI's output signal. Everything else is structure.

**Key Characteristics:**
- Near-black solid surfaces, no glassmorphism, no backdrop-blur
- DM Sans for all UI text (body + headlines); Space Mono for all numeric/identifier data
- 16px card radius (modern finance feel, not sharp-edged terminal)
- `#F2F2FC` primary text (near-white, slightly blue-cool); `#9898AE` muted text
- Two signal colors only: `#22C55E` buy/positive, `#EF4444` sell/negative
- Accent `#A8FF53` Neural Lime for active states, primary actions, AI output

## 2. Color Tokens

All tokens defined as CSS variables in `:root`.

| Token | Value | Use |
|-------|-------|-----|
| `--bg-dark` | `#080808` | Page background, canvas |
| `--bg-card` | `#111111` | Card/panel background |
| `--bg-card2` | `#181818` | Card headers, secondary bg, input bg |
| `--border` | `rgba(255,255,255,0.12)` | Primary borders |
| `--border2` | `rgba(255,255,255,0.08)` | Secondary borders, chart grid lines |
| `--text-main` | `#F2F2FC` | All primary text |
| `--text-muted` | `#9898AE` | Secondary labels, card headers, muted info |
| `--accent` | `#A8FF53` | Neural Lime — active states, primary actions, AI output |
| `--accent-buy` | `#22C55E` | BUY signal, positive PnL, success states |
| `--accent-red` | `#EF4444` | SELL signal, negative PnL, danger states |
| `--accent-blue` | `#60A5FA` | Informational highlights |
| `--accent-yellow` | `#FACC15` | Caution/volatile regime |
| `--accent-purple` | `#A78BFA` | Secondary informational |

### Signal Color Rules

- `--accent-buy` (#22C55E) — BUY badges, positive numbers, success buttons, bull regime
- `--accent-red` (#EF4444) — SELL badges, negative numbers, danger buttons, bear regime, candlestick down
- `--accent` (#A8FF53) — active nav pill fill, active UI states, primary button, AI signal output
- Never use `#ff6b35` (old Signal Orange) — deprecated, replaced by `--accent-red`

## 3. Typography

Two font families, three semantic roles:

| Role | Font | Size | Weight | Use |
|------|------|------|--------|-----|
| Body/UI | DM Sans | 15px base | 400 | All UI text, labels, prose |
| Headline/Stat | DM Sans | varies | 600–700 | Section headings, card headers, stat values |
| Mono/Data | Space Mono | 0.82rem | 400 | Prices, rates, percentages, timestamps, tickers |

**The Machine Layer Rule.** Every number, rate, identifier, timestamp, and price renders in Space Mono. Font choice encodes data type.

**No Finlandica. No Noto Sans.** These were the v1 fonts — they are no longer in use.

### Size Scale

- Stat values (large): `1.5–2rem`, DM Sans 700
- Card headers: `0.78rem`, DM Sans 600, `--text-muted`
- Body text: `0.9rem` (0.875rem), DM Sans 400
- Labels/badges: `0.65–0.72rem`, DM Sans or Space Mono
- Micro-labels minimum: `10px` — never below 10px for any functional label

## 4. Surfaces & Elevation

No glassmorphism. All surfaces are solid.

| Layer | Background | Use |
|-------|-----------|-----|
| Canvas | `#080808` | Page background |
| Card | `#111111` | `.card`, `.stat-card`, `.price-card` |
| Card header | `#181818` | `.card-header`, input backgrounds |
| Hover tint | `rgba(255,255,255,0.03)` | Row hover, interactive card hover |

Cards have `1px solid rgba(255,255,255,0.12)` border and `border-radius: 16px`.

No `backdrop-filter`, no `rgba()` semi-transparent card backgrounds, no `::before` top-accent glow lines.

## 5. Components

### Navigation

Left sidebar (`280px`), `#111111` background, `1px solid rgba(255,255,255,0.12)` right border.

- **Active pill**: `background: var(--text-main)`, `color: #080808`, `font-weight: 700`, `border-radius: 100px`, full-width pill
- **Inactive**: transparent bg, `--text-muted` text, hover gets `rgba(255,255,255,0.05)` bg tint
- No left-border accent stripe

### Cards

```css
background: var(--bg-card);
border: 1px solid var(--border);
border-radius: var(--radius-card); /* 16px */
```

Card headers use `--bg-card2` background and `--text-muted` color at `0.78rem` DM Sans 600.

### Buttons

- **Primary**: `--accent` bg, `#000` text, DM Sans 700
- **Buy**: `rgba(34,197,94,0.15)` bg, `--accent-buy` text, green border
- **Sell/Danger**: `rgba(239,68,68,0.15)` bg, `--accent-red` text, red border
- **Ghost**: transparent, `--text-muted` text, `--border` border

### Signal Badges

Space Mono, `0.62rem`, pill radius, uppercase, letter-spacing `0.8px`.

- BUY: `rgba(57,217,138,0.12)` bg, `--accent-buy` text, green border
- SELL: `rgba(239,68,68,0.12)` bg, `--accent-red` text, red border
- HOLD: `rgba(102,102,102,0.12)` bg, `--text-muted` text, gray border

### Charts (ApexCharts)

```javascript
chart: { background: 'transparent', foreColor: '#9898AE', fontFamily: "'Space Mono',monospace" }
grid: { borderColor: 'rgba(255,255,255,0.08)', strokeDashArray: 3 }
// Candlestick
colors: { upward: '#A8FF53', downward: '#EF4444' }
```

## 6. Do's and Don'ts

### Do:
- Render all numeric data in Space Mono
- Use `--accent-buy` (#22C55E) for BUY and positive outcomes
- Use `--accent-red` (#EF4444) for SELL and negative outcomes
- Use `--accent` (#A8FF53) only for active states and primary actions
- Keep cards solid (`#111111`) — no glassmorphism
- Use `--text-main` (#F2F2FC) for primary text, `--text-muted` (#9898AE) for secondary
- Floor all functional labels at 10px minimum
- Use CSS variables, never hardcoded color hex in JS render functions

### Don't:
- Use `#ff6b35` (old Signal Orange) — deprecated
- Use Finlandica or Noto Sans — both removed from v2
- Add `backdrop-filter` or semi-transparent card backgrounds
- Use `#000000` pure black for backgrounds — use `#080808`
- Use gradient text (`background-clip: text`)
- Hardcode `#444`, `#555`, `#666`, `#888` — use `var(--text-muted)`
- Set labels below 10px font size
