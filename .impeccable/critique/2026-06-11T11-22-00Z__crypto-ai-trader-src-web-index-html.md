---
target: crypto-ai-trader/src/web/index.html
total_score: 29
p0_count: 2
p1_count: 2
timestamp: 2026-06-11T11-22-00Z
slug: crypto-ai-trader-src-web-index-html
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Excellent |
| 2 | Match System / Real World | 3 | Thai/EN mixing unsystematic |
| 3 | User Control and Freedom | 3 | STOP+Force Sell lacks confirm |
| 4 | Consistency and Standards | 2 | SELL color split (#ff6b35 vs #EF4444) |
| 5 | Error Prevention | 3 | Destructive sell needs confirm |
| 6 | Recognition Rather Than Recall | 3 | Status dots color-only |
| 7 | Flexibility and Efficiency | 4 | Keyboard nav, sidebar shortcuts |
| 8 | Aesthetic and Minimalist Design | 2 | Bottom clone grid; eyebrow monoculture |
| 9 | Error Recovery | 2 | Generic toast errors |
| 10 | Help and Documentation | 3 | Chat FAB accessible |
| Total | | 29/40 | Good |

## Anti-Patterns Verdict
Not AI slop. 80% expert cockpit, 20% generator residue (eyebrow monoculture, bottom 4-clone stat grid, gradient logo orbs).
Detector: 8x layout-transition (width on progress bars, mostly intentional), 68 em-dashes (false positive — data placeholders).

## Priority Issues
P0: SELL color inconsistency (#ff6b35 vs #EF4444 across screens) — trader muscle-memory hazard
P0: Tiny muted micro-labels below legibility floor (9px at opacity 0.55)
P1: Bottom 4-identical stat card grid duplicates Win Rate and Today PnL already shown above
P1: Uppercase-mono-eyebrow on 7 different label classes — flat hierarchy
P2: STOP + Force Sell All has no visible confirm guard
