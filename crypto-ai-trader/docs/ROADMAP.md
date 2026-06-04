# Aiterra v1.1.0 / Lunai — Roadmap: Feature ที่ทำให้ AI ฉลาดขึ้น

> **สถาปัตยกรรมชื่อ:** `Aiterra` = โปรแกรมหลัก (shell/platform) · `Lunai` = AI autotrade engine ที่อยู่ข้างใน
>
> เอกสารนี้คือ **backlog / โจทย์** สำหรับพัฒนา Lunai ให้ตัดสินใจเทรดได้ฉลาดขึ้น
> แต่ละ feature เขียนเป็น "task card" — มี เป้าหมาย / เหตุผล / ไฟล์ที่แตะ / dependency /
> ระดับความยาก / acceptance criteria — หยิบไปทำตามทีหลังได้ทันที
>
> หลักการจัดลำดับ: **Impact ต่อ P&L** มาก่อน **Effort** — เริ่มจากของที่ได้ผลเยอะแต่ทำไม่ยาก

---

## สารบัญ

- [Phase 0 — รากฐานที่มีอยู่แล้ว (อย่าทำซ้ำ)](#phase-0)
- [Phase 1 — Data Edge: ข้อมูลที่ตลาด spot มองไม่เห็น](#phase-1)
- [Phase 2 — Decision Intelligence: สมองตัดสินใจ](#phase-2)
- [Phase 3 — Risk & Portfolio: ความอยู่รอด](#phase-3)
- [Phase 4 — Advanced Signals: เพิ่มความแม่นยำ](#phase-4)
- [Phase 5 — Infra & Ops: ความน่าเชื่อถือ](#phase-5)
- [Prioritization Matrix](#matrix)
- [แผน Sprint ที่แนะนำ](#sprints)

---

<a name="phase-0"></a>
## Phase 0 — รากฐานที่มีอยู่แล้ว ✅ (อย่าทำซ้ำ)

ก่อนเสนอของใหม่ ต้องรู้ว่ามีอะไรแล้ว เพื่อไม่ build ซ้ำ:

| หมวด | สิ่งที่มีแล้ว | ไฟล์ |
|------|-------------|------|
| **Signal funnel** | data → 40+ indicators → regime → model → confidence gate → risk → sizing | `ai_trader.py` |
| **Models** | Rule-based (5 strategy), LightGBM+SHAP, Claude agentic, Hybrid | `strategy_manager.py`, `ml_models.py`, `claude_analyzer.py` |
| **Regime** | ADX-based: BULL/BEAR/RANGING/VOLATILE/CRASH + confidence | `market_regime.py` |
| **RL** | UCB1 bandit, 15 arms = 5 strategy × 5 regime, persist `rl_bandit.pkl` | `rl_trainer.py` |
| **Position sizing** | Kelly (Bayesian prior, fractional 0.25×) + ATR scale + GARCH de-risk + HRP weight | `position_sizer.py`, `hrp_allocator.py` |
| **Risk engine** | High-water mark, drawdown guard, daily-loss circuit breaker, portfolio heat, regime multiplier | `risk_engine.py` |
| **Sentiment / Deriv** | Fear & Greed (alternative.me), Funding rate, Open Interest (contrarian overlay) | `data/sentiment.py` |
| **Technical** | Ichimoku, SuperTrend, StochRSI, Williams%R, CCI, RSI divergence, Aroon, SMC (FVG/OB/BOS/ChoCH/liquidity), 13 chart patterns, Kalman trend, GARCH vol, WorldQuant alphas | `indicators_extra.py`, `smc_detector.py`, `chart_patterns.py`, `quant_features.py` |
| **Learning loop** | per-trade labeling, retrain ทุก 50 trades, seed model cold-start | `trainer.py`, `training_loop.py`, `hourly_trainer.py` |
| **Backtest** | basic/hybrid/autotrade, per-regime + per-pattern breakdown, **walk-forward**, **fee 0.1% + slippage 0.05%** | `backtest.py` |
| **Safety** | dry-run mode, kill switch, allowlist settings, rate limit, localhost bind | `ai_trader.py`, `api/routes.py`, `main.py` |
| **Pairs** | cointegration detection (Engle-Granger) — *ตรวจเจอแล้ว แต่ยังไม่เทรด* | `cointegration.py` |

> 🔑 **ข้อสังเกตสำคัญ:** RL ปัจจุบันเรียนรู้ระดับ *strategy* (DCA/Trend/…) ต่อ regime
> แต่ยัง **ไม่ได้** เรียนรู้ว่า *model* ไหน (rule vs ml vs claude) เก่งกว่ากันต่อ regime/symbol →
> นี่คือช่องว่างหลักที่ Phase 2 จะปิด

---

<a name="phase-1"></a>
## Phase 1 — Data Edge: ข้อมูลที่ตลาด spot มองไม่เห็น

> ปรัชญา: edge ที่ยั่งยืนมาจาก **ข้อมูลที่คนอื่นไม่มี** มากกว่า indicator ที่คำนวณจากราคาเดียวกัน

### F1.1 — On-chain Metrics 🟢 (ผลกระทบสูง)
- **เป้าหมาย:** ดึง exchange net-flow, whale transfers, MVRV/SOPR มาเป็น feature + Claude context
- **เหตุผล:** เงินไหลเข้า exchange จำนวนมาก = แรงขายกำลังมา (signal ที่ราคายังไม่สะท้อน). ปัจจุบันตัดสินจาก OHLCV + funding/OI เท่านั้น
- **ไฟล์:** สร้าง `src/data/onchain.py` (pattern เดียวกับ `sentiment.py`); inject ใน `market_analyzer.py` → `analysis.features`; เพิ่มใน `claude_analyzer.py` system prompt
- **Data source:** CryptoQuant / Glassnode (มี free tier), หรือ Coinglass API
- **Dependency:** ไม่มี (standalone fetcher + cache เหมือน sentiment)
- **Effort:** M (2–3 วัน)
- **Acceptance:**
  - [ ] `onchain.py` คืน `{exchange_netflow, whale_tx_count, mvrv}` cached 5–15 นาที, มี graceful fallback เมื่อ API ล่ม
  - [ ] feature เข้า ML training vector + แสดงใน Claude prompt
  - [ ] backtest ก่อน/หลังเพิ่ม feature → เทียบ Sharpe

### F1.2 — Order Book Microstructure 🟢 (ผลกระทบสูง, ปรับ timing)
- **เป้าหมาย:** อ่าน L2 order book → bid/ask imbalance, large-wall detection, spread
- **เหตุผล:** ปรับจังหวะ entry/exit ให้ดีขึ้นมาก — ตอนนี้ entry ที่ candle close ล้วน ไม่รู้ว่ามีกำแพงขายข้างหน้า
- **ไฟล์:** เพิ่ม `fetch_order_book()` ใน `exchanges/base.py` + ccxt impl; module ใหม่ `src/agent/microstructure.py`; ใช้เป็น **execution filter** ใน `ai_trader._execute_trade()` (ไม่ใช่ signal หลัก)
- **Dependency:** ต้องมี exchange ที่ support `fetchOrderBook` (Binance/OKX มี)
- **Effort:** M (3 วัน)
- **Acceptance:**
  - [ ] คำนวณ imbalance = `bid_vol / (bid_vol + ask_vol)` ที่ depth N
  - [ ] block/delay BUY ถ้าเจอ sell wall ใหญ่ใน ±0.5%
  - [ ] log ผล timing improvement vs baseline

### F1.3 — Social Sentiment 🟡 (ผลกระทบกลาง)
- **เป้าหมาย:** mention volume / sentiment score จาก Twitter+Reddit+ข่าว
- **เหตุผล:** spike ของการพูดถึง = contrarian หรือ momentum signal ขึ้นกับ context
- **ไฟล์:** ขยาย `src/data/sentiment.py` เพิ่ม `social_score()`; source: LunarCrush API หรือ CryptoPanic (news)
- **Dependency:** F1.1 (รวมเป็น "alternative data" layer เดียวกัน)
- **Effort:** M (2–3 วัน)
- **Acceptance:**
  - [ ] sentiment score normalized [-1,1] + 24h mention delta
  - [ ] divergence rule: ราคา new high แต่ social ลด = warning เข้า Claude prompt

### F1.4 — Derivatives Depth (ต่อยอด OI/Funding) 🟡
- **เป้าหมาย:** เพิ่ม long/short ratio, OI skew, liquidation heatmap จากของเดิม
- **เหตุผล:** funding + OI มีแล้ว แต่ยังขาดภาพ positioning เต็ม → liquidation cluster ทำนาย stop-hunt ได้
- **ไฟล์:** ขยาย `data/sentiment.py` (มี `funding_rate`, `open_interest` แล้ว) เพิ่ม `long_short_ratio()`, `liquidation_levels()`; source: Coinglass/Binance futures API
- **Dependency:** ต่อยอดจากของเดิมโดยตรง
- **Effort:** S (1–2 วัน)
- **Acceptance:**
  - [ ] long/short ratio + OI change% เข้า feature dict
  - [ ] liquidation cluster ใกล้เคียงใช้เป็น dynamic SL/TP hint (เชื่อม F2.2)

---

<a name="phase-2"></a>
## Phase 2 — Decision Intelligence: สมองตัดสินใจ

> ใช้ของที่มีอยู่ (RL bandit, Claude, regime) ให้ฉลาดขึ้น โดยไม่ต้องเพิ่ม data

### F2.1 — Ensemble Meta-Learning (model-level bandit) 🟢🟢 (ผลกระทบสูงสุด, ใช้ของเดิม)
- **เป้าหมาย:** ให้ RL bandit เลือกว่า *model ไหน* (rule/ml/claude/hybrid) แม่นที่สุดต่อ regime+symbol — ไม่ใช่แค่ strategy
- **เหตุผล:** ตอนนี้ combine model ด้วย logic คงที่ใน hybrid mode. การให้ระบบ meta-learn ว่า "Claude เก่งใน BULL, ML เก่งใน RANGING" คือ upgrade ที่ใช้ infra ที่มีอยู่แล้ว (UCB1) แค่เปลี่ยนนิยาม arm
- **ไฟล์:** `rl_trainer.py` (เพิ่ม arm dimension หรือ bandit ตัวที่สอง `model_bandit`); `ai_trader.py` ตรง model routing (~line 297–351); persist แยก `rl_model_bandit.pkl`
- **Dependency:** ไม่มี — reuse UCB1 ที่มี
- **Effort:** M (3 วัน)
- **Acceptance:**
  - [ ] bandit ใหม่ arms = model × regime, update ด้วย pnl เหมือน strategy bandit
  - [ ] dashboard แสดง win-rate ต่อ model ต่อ regime
  - [ ] backtest พิสูจน์ว่า meta-selection ≥ best fixed model

### F2.2 — Adaptive Dynamic SL/TP 🟢 (ผลกระทบสูง)
- **เป้าหมาย:** เปลี่ยน TP/SL จาก fixed % เป็น **ATR-based + structure-based trailing** ต่อ regime
- **เหตุผล:** SL คงที่ทำให้โดน stop-hunt ใน VOLATILE และ TP คงที่ทำให้ขายเร็วใน BULL. ใช้ ATR/SMC order block/liquidation level (F1.4) เป็นจุดอ้างอิงจริง
- **ไฟล์:** module ใหม่ `src/agent/exit_manager.py`; เรียกใน `ai_trader._close_trade()` + cycle ที่เช็ค open trade; regime → multiplier table
- **Dependency:** ดีขึ้นถ้ามี F1.4 (liquidation levels) แต่ทำได้เลยด้วย ATR
- **Effort:** M (3 วัน)
- **Acceptance:**
  - [ ] SL = `entry − k×ATR` (k ต่อ regime), trailing เมื่อกำไร > 1×ATR
  - [ ] TP ขยายใน BULL (let-it-run), แคบใน RANGING
  - [ ] backtest เทียบ fixed vs adaptive (Sharpe + max DD)

### F2.3 — Claude Trade Journal / Memory 🟡 (ผลกระทบกลาง, แตกต่าง)
- **เป้าหมาย:** บันทึก "บทเรียน" ต่อ regime/setup แล้วให้ Claude ดึงมา reason ก่อนออก signal
- **เหตุผล:** ตอนนี้ Claude เห็นแค่ recent trades ดิบ ๆ. การสรุปเป็น lesson ("BTC ใน VOLATILE: TP เร็วไป 3 ครั้งติด") ทำให้ reasoning ดีขึ้นแบบ compounding
- **ไฟล์:** ตาราง `trade_journal` ใน `core/database.py`; สร้าง lesson หลังปิดเทรด (สรุปด้วย Claude เอง); retrieval ใน `claude_analyzer.py` prompt
- **Dependency:** ไม่มี
- **Effort:** M (3 วัน)
- **Acceptance:**
  - [ ] journal entry = {regime, setup, outcome, lesson_text} บันทึกอัตโนมัติ
  - [ ] top-k relevant lessons (ตาม regime+symbol) เข้า Claude prompt
  - [ ] ใช้ prompt caching ไม่ให้ token บาน

### F2.4 — Adaptive Meta-Parameters 🟡
- **เป้าหมาย:** ให้ `kelly_fraction`, confidence gate ปรับตาม realized Sharpe / win-rate streak
- **เหตุผล:** parameter คงที่ไม่เหมาะกับทุกสภาพตลาด. ช่วงกำไรต่อเนื่อง → กล้าขึ้นเล็กน้อย; ขาดทุนต่อเนื่อง → หดตัว
- **ไฟล์:** `position_sizer.py` (kelly), `ai_trader.py` (confidence gate); ตัวคูณจาก rolling Sharpe ของ N เทรดล่าสุด
- **Dependency:** ระวังชน F2.2 (อย่าให้ทั้งคู่ปรับ aggressiveness พร้อมกันจน overshoot)
- **Effort:** S–M (2 วัน)
- **Acceptance:**
  - [ ] kelly_fraction ∈ [0.15, 0.35] ปรับตาม rolling Sharpe, มี hard cap
  - [ ] backtest พิสูจน์ว่าไม่เพิ่ม max DD เกิน baseline

---

<a name="phase-3"></a>
## Phase 3 — Risk & Portfolio: ความอยู่รอด

> "เก่งแค่ไหนถ้าระเบิดพอร์ตก็จบ" — กลุ่มนี้ลด tail risk

### F3.1 — Active Pairs Trading 🟡 (ใช้ของที่ detect แล้ว)
- **เป้าหมาย:** ต่อยอด cointegration ที่ "ตรวจเจอแล้วแต่ยังไม่เทรด" → market-neutral long/short
- **เหตุผล:** เพิ่ม return stream ที่ไม่สัมพันธ์กับทิศตลาด (เทรดได้แม้ตลาด sideways)
- **ไฟล์:** `cointegration.py` (มี Engle-Granger แล้ว) → เพิ่ม z-score entry/exit; logic ใหม่ใน `ai_trader.py` หรือ `pairs_trader.py`; ต้องรองรับ short
- **Dependency:** exchange ต้อง support short/margin (ระวัง spot-only exchange)
- **Effort:** L (4–5 วัน)
- **Acceptance:**
  - [ ] entry เมื่อ spread z-score > 2, exit เมื่อ revert < 0.5
  - [ ] half-life filter (อย่าเทรด pair ที่ revert ช้าเกิน)
  - [ ] backtest market-neutral แยกจาก directional

### F3.2 — Portfolio Correlation Guard 🟢 (ผลกระทบสูง, ทำง่าย)
- **เป้าหมาย:** บล็อก position ใหม่ถ้าทำให้ correlation รวมของพอร์ต > threshold
- **เหตุผล:** ถือ BTC+ETH+BNB พร้อมกัน = ไม่ได้ diversify จริง (corr ~0.8+). HRP weight ช่วยเรื่อง sizing แต่ไม่ได้ block การ stack
- **ไฟล์:** `risk_engine.py` (เพิ่ม `check_correlation()`); ใช้ return matrix ที่ HRP มีอยู่แล้วใน `ai_trader._price_history`
- **Dependency:** reuse data ของ `hrp_allocator.py`
- **Effort:** S (1–2 วัน)
- **Acceptance:**
  - [ ] reject BUY ถ้า avg pairwise corr กับ position ที่ถือ > 0.8
  - [ ] override ได้ถ้า conviction สูงมาก (config)

### F3.3 — VaR / CVaR + Monte Carlo Stress 🟡
- **เป้าหมาย:** ประเมิน tail risk เชิงปริมาณ (95% VaR, CVaR) + simulate crash scenario
- **เหตุผล:** circuit breaker เป็น reactive (ตัดหลังขาดทุนแล้ว). VaR เป็น proactive (รู้ก่อนว่าเสี่ยงแค่ไหน)
- **ไฟล์:** `risk_analytics.py` (มีโครงแล้ว) เพิ่ม `historical_var()`, `cvar()`, `monte_carlo_dd()`; แสดงบน dashboard
- **Dependency:** ไม่มี
- **Effort:** M (2–3 วัน)
- **Acceptance:**
  - [ ] 95%/99% VaR + CVaR คำนวณจาก return history
  - [ ] Monte Carlo คาด max DD distribution → เตือนถ้า position ใหม่ดัน VaR เกิน budget

### F3.4 — Model Drift Detection + Auto Re-validate 🟡
- **เป้าหมาย:** ตรวจ model staleness (rolling accuracy/Sharpe ตก) → trigger retrain + OOS validate ก่อน deploy
- **เหตุผล:** retrain ทุก 50 trades แบบ blind. ควร validate ด้วย walk-forward OOS ก่อนเอา model ใหม่มาใช้จริง (มี walk-forward แล้วใน backtest.py — reuse)
- **ไฟล์:** `trainer.py` (retrain path), `hourly_trainer.py`; reuse `backtest.run_walkforward`
- **Dependency:** reuse walk-forward ที่มีแล้ว
- **Effort:** M (3 วัน)
- **Acceptance:**
  - [ ] drift metric = rolling 30-trade accuracy; trigger ถ้าตก > X%
  - [ ] model ใหม่ deploy เฉพาะเมื่อ OOS Sharpe ≥ model เดิม (champion/challenger)

---

<a name="phase-4"></a>
## Phase 4 — Advanced Signals: เพิ่มความแม่นยำ

> ของเสริม — ทำเมื่อ Phase 1–3 นิ่งแล้ว (diminishing returns ต่อความซับซ้อน)

### F4.1 — Harmonic Patterns 🟡
- **เป้าหมาย:** Gartley, Bat, Butterfly, Crab (Fibonacci-based) เพิ่มจาก 13 chart patterns เดิม
- **ไฟล์:** `chart_patterns.py` หรือ `harmonic_patterns.py` ใหม่; ใช้ pivot จาก scipy argrelextrema (มี dependency แล้ว)
- **Effort:** M (3 วัน) — **Acceptance:** detect + Fib ratio validation + confidence เข้า composite score

### F4.2 — Volume Profile / VPOC 🟡
- **เป้าหมาย:** Point of Control, Value Area High/Low, HVN/LVN เป็นแนวรับต้านจาก volume จริง
- **ไฟล์:** `indicators_extra.py` หรือ `volume_profile.py` ใหม่
- **Effort:** M (2–3 วัน) — **Acceptance:** VPOC/VAH/VAL เข้า feature + ใช้เป็น SL/TP reference (เชื่อม F2.2)

### F4.3 — Elliott Wave Auto-Count 🔴 (ยาก, ผลไม่แน่นอน)
- **เป้าหมาย:** นับ wave อัตโนมัติ (ตอนนี้ Claude reason เองในโหมด agentic)
- **ไฟล์:** `elliott_wave.py` ใหม่ — **Effort:** L (5+ วัน, subjective มาก) — **Acceptance:** wave count + invalidation level; ⚠️ ประเมิน ROI ก่อนทำ

### F4.4 — Cross-Asset / Macro Features 🟡
- **เป้าหมาย:** BTC dominance, altseason index, correlation regime (risk-on/off)
- **ไฟล์:** `data/` fetcher ใหม่ + feature inject
- **Effort:** M (2–3 วัน) — **Acceptance:** dominance + altseason เข้า regime/Claude context

---

<a name="phase-5"></a>
## Phase 5 — Infra & Ops: ความน่าเชื่อถือ

> ทำให้ระบบ "เชื่อถือได้และวัดผลได้" — สำคัญตอนสเกล

### F5.1 — Parameter Optimization Framework 🟢 (ต่อยอด walk-forward)
- **เป้าหมาย:** Bayesian optimization (Optuna) จูน indicator periods, kelly_fraction, confidence gate, regime threshold — บน walk-forward ที่มีอยู่
- **เหตุผล:** ตอนนี้ค่าหลายตัว hardcode/manual. ปล่อยให้ data จูนเองบน OOS ป้องกัน overfit
- **ไฟล์:** `backtest.py` (มี `run_walkforward` + grid search แล้ว) → เปลี่ยนเป็น Optuna; CLI/endpoint
- **Effort:** M (3 วัน) — **Acceptance:** optimize บน IS, report บน OOS เท่านั้น; ผลลัพธ์ reproducible (seed)

### F5.2 — Feature Store + Reproducibility 🟡
- **เป้าหมาย:** เก็บ feature snapshot ต่อ decision เพื่อ debug + reproduce + audit
- **ไฟล์:** `core/database.py` (มี `training_records` JSON แล้ว) → จัดให้เป็น structured feature store
- **Effort:** M — **Acceptance:** reconstruct ทุก decision ย้อนหลังได้จาก stored features

### F5.3 — Shadow / Champion-Challenger Trading 🟡
- **เป้าหมาย:** รัน model ใหม่แบบ paper คู่กับ live (dry-run มีแล้ว) เทียบผลก่อน promote
- **ไฟล์:** reuse `_dry_run` infra ใน `ai_trader.py`; log แยก 2 stream
- **Dependency:** F3.4 (drift/validate)
- **Effort:** M — **Acceptance:** challenger ต้องชนะ champion N เทรดก่อนสลับ

### F5.4 — Decision Attribution Logging 🟢 (ทำง่าย, คุ้ม)
- **เป้าหมาย:** log ว่าแต่ละ decision มาจาก signal ไหนบ้าง + น้ำหนักเท่าไร (explainability)
- **เหตุผล:** ตอน debug ขาดทุน ต้องรู้ว่า "ใครพาเข้า" — มี SHAP แล้วสำหรับ ML แต่ยังไม่มีภาพรวม ensemble
- **ไฟล์:** `ai_trader.py` (เก็บ `_last_signal_info` อยู่แล้ว → ขยาย); แสดงบน dashboard
- **Effort:** S (1–2 วัน) — **Acceptance:** ทุกเทรดมี attribution breakdown (rule X%, ml Y%, claude Z%, regime, sentiment)

---

<a name="matrix"></a>
## Prioritization Matrix (Impact × Effort)

```
        ผลกระทบสูง  │  F1.1 On-chain        F2.1 Meta-ensemble
                    │  F1.2 Order book      F2.2 Adaptive SL/TP
                    │  F3.2 Corr guard ⭐   F5.4 Attribution ⭐
        ────────────┼──────────────────────────────────────────
        ผลกระทบกลาง  │  F1.3 Social          F2.3 Trade journal
                    │  F1.4 Deriv depth ⭐  F2.4 Meta-params
                    │  F3.3 VaR/CVaR        F3.4 Drift detect
                    │  F4.1 Harmonic        F5.1 Param-opt
        ────────────┼──────────────────────────────────────────
        ผลกระทบต่ำ/  │  F4.2 Vol profile     F4.4 Macro
        ไม่แน่นอน    │  F4.3 Elliott 🔴      F5.2 Feature store
                    │                       F5.3 Shadow
        ────────────┼──────────────────────────────────────────
                       ทำง่าย (S)      ปานกลาง (M)      ยาก (L)

⭐ = quick win (ผลดี + ทำเร็ว) → หยิบก่อน
🔴 = ประเมิน ROI ก่อน (ยาก, ผลไม่ชัด)
```

---

<a name="sprints"></a>
## แผน Sprint ที่แนะนำ

### Sprint 1 — Quick Wins (สัปดาห์ 1–2) 🎯
ผลกระทบสูง/กลาง + ทำเร็ว, ใช้ infra เดิม:
1. **F3.2 Correlation Guard** (S) — กัน over-concentration ทันที
2. **F5.4 Attribution Logging** (S) — เห็นภาพการตัดสินใจ ช่วย debug ทุกอย่างหลังจากนี้
3. **F1.4 Derivatives Depth** (S) — ต่อยอด funding/OI ที่มีแล้ว

### Sprint 2 — Decision Brain (สัปดาห์ 3–4) 🧠
ยกระดับการตัดสินใจโดยไม่ต้องเพิ่ม data source ใหม่:
1. **F2.1 Meta-Ensemble** (M) — ⭐ ผลกระทบสูงสุด, reuse UCB1
2. **F2.2 Adaptive SL/TP** (M) — ลดโดน stop-hunt + let-winner-run

### Sprint 3 — Data Edge (สัปดาห์ 5–6) 📡
เพิ่มข้อมูลที่ตลาด spot มองไม่เห็น:
1. **F1.1 On-chain** (M)
2. **F1.2 Order Book** (M)

### Sprint 4 — Robustness (สัปดาห์ 7–8) 🛡️
ความอยู่รอดระยะยาว:
1. **F3.4 Drift Detection** (M) — reuse walk-forward
2. **F5.1 Param Optimization** (M) — reuse walk-forward
3. **F3.3 VaR/CVaR** (M)

### Backlog (ทำเมื่อมีเวลา)
F1.3 Social · F2.3 Journal · F2.4 Meta-params · F3.1 Pairs · F4.x Advanced patterns · F5.2/5.3

---

## หลักการสำคัญตลอด roadmap

1. **วัดผลทุก feature ด้วย backtest + walk-forward** — feature ที่ทำให้ Sharpe แย่ลง ให้ถอดออก ไม่ใช่เก็บไว้
2. **เพิ่ม feature ทีละตัว** — เทียบ before/after เสมอ ไม่ batch หลายตัวพร้อมกัน (แยกแยะผลไม่ได้)
3. **ระวัง overfitting** — optimize บน in-sample, report บน out-of-sample เท่านั้น
4. **dry-run ก่อน live เสมอ** — ทุก feature ใหม่ต้องผ่าน paper trade ก่อน
5. **ความซับซ้อนมีต้นทุน** — feature ที่เพิ่ม edge 0.1% แต่เพิ่ม bug surface มาก อาจไม่คุ้ม

---

*อัปเดตล่าสุด: 2026-06-04 · Aiterra v1.1.0 · Lunai (AI engine)*
