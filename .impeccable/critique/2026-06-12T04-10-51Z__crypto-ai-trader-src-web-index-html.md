---
target: crypto-ai-trader/src/web/index.html
total_score: 30
p0_count: 2
p1_count: 3
timestamp: 2026-06-12T04-10-51Z
slug: crypto-ai-trader-src-web-index-html
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Excellent: WS dot, mode badge, agent status, AT scan line |
| 2 | Match System / Real World | 4 | Finance-native language throughout |
| 3 | User Control and Freedom | 3 | AT signal grid lacks dismiss; no undo on parameter changes |
| 4 | Consistency and Standards | 3 | Inline styles bypass CSS var system on tinted stat-cards |
| 5 | Error Prevention | 2 | Force Sell All no confirmation; Live Mode no pre-flight warning |
| 6 | Recognition Rather Than Recall | 3 | Signal badges excellent; Trading Parameters needs unit labels + tooltips |
| 7 | Flexibility and Efficiency | 3 | Keyboard hints in sidebar; no bulk ops, no settings presets |
| 8 | Aesthetic and Minimalist Design | 4 | Finance terminal cohesive; no gradient abuse; micro-interactions tight |
| 9 | Error Recovery | 2 | WS disconnect shows dot only; async failures render "รอข้อมูล..." forever |
| 10 | Help and Documentation | 2 | No tooltips on Trading Parameters; "Jesse-style IS/OOS", "Kelly fraction" undefined |
| **Total** | | **30/40** | **Good** |

## Anti-Patterns Verdict
CLEAN. No hero-metric templates, no identical card grids, no SaaS aesthetics, no gradient text, no side-stripe borders.
Detector: layout-transition x8 (acceptable for progress bars), em-dash x68 (false positive — data placeholders not prose).

## Priority Issues

[P0] Force Sell All no confirmation — Fix: modal with 5s countdown + confirmation text
[P0] Live Mode no pre-flight warning — Fix: 3-step activation flow with checklist modal
[P1] Settings IA flat — Fix: 5 named sections with sticky jump-nav
[P1] Trading Parameters 7 inputs no context — Fix: Risk Model Snapshot card + tooltips
[P1] WS disconnect no stale data alert — Fix: 15s alert bar + dim stats + amber timestamps
[P2] Signal grid unpredictable layout — Fix: locked breakpoints 4/3/2 cols
[P2] Activity Feed unstructured — Fix: flex rows with color bar
[P3] Inline styles on tinted stat-cards — Fix: CSS modifier classes

## Persona Red Flags
Alex: No settings presets; kbd-hints not discoverable; no multi-symbol backtest compare
Sam: Live Mode button no ARIA description; Kill Switch no focus ring; border rgba too faint in high-contrast
Dao: Today PnL requires scroll; Demo/Live buried in Settings; Kelly/Jesse undefined in Thai context

## Minor Observations
chart-container fixed 300px; input-group-text size mismatch; Firefox scrollbar unstyled; mobile hides aiModelSelect with no fallback
