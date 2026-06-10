# Lunai — Release Roadmap 🌙

> **Lunai** คือ AI autotrade engine ที่อยู่ภายใน **Aiterra** (โปรแกรมหลัก)
> เอกสารนี้คือ **แผน release ตามเวอร์ชั่น** ของ Lunai — จับ feature แต่ละตัวลงเวอร์ชั่น
> พร้อมธีม, เป้าหมายวัดผล (KPI), และเกณฑ์ผ่านก่อนปล่อย (release gate)
>
> 📋 รายละเอียดแต่ละ feature (สเปก/ไฟล์/acceptance) อยู่ใน [`ROADMAP.md`](./ROADMAP.md) — อ้างอิงด้วยรหัส `F1.1`, `F2.1`, …
> เอกสารนี้ตอบคำถาม **"ปล่อยอะไร เวอร์ชั่นไหน และวัดความสำเร็จยังไง"**

---

## 🎯 North Star — Lunai มีไว้ทำอะไร

> **"AI ที่เทรดเองได้อย่างมีวินัย เรียนรู้จากผลจริงตลอดเวลา และอยู่รอดในตลาดทุกสภาพ"**

3 เสาหลักที่ทุกเวอร์ชั่นต้องไม่ทำให้แย่ลง:

| เสา | ความหมาย | ตัววัดหลัก |
|-----|----------|-----------|
| **Edge** | ตัดสินใจดีกว่าสุ่ม/buy-and-hold อย่างมีนัยสำคัญ | Sharpe ratio, Profit Factor |
| **Survival** | ไม่ระเบิดพอร์ตในเหตุการณ์รุนแรง | Max Drawdown, Calmar |
| **Learning** | เก่งขึ้นเมื่อมีข้อมูลมากขึ้น | Win-rate trend, OOS stability |

---

## 📐 Versioning Philosophy (Semantic)

| ระดับ | เมื่อไหร่ | ตัวอย่าง |
|-------|---------|---------|
| **MAJOR** (x.0.0) | เปลี่ยนสถาปัตยกรรมการตัดสินใจ / เพิ่ม trading paradigm ใหม่ | v1 → v2 (เพิ่ม market-neutral) |
| **MINOR** (1.x.0) | เพิ่ม capability ใหม่ที่ backward-compatible | v1.0 → v1.1 (เพิ่ม data/decision) |
| **PATCH** (1.0.x) | แก้บั๊ก, จูน parameter, ไม่เพิ่ม capability | v1.0.0 → v1.0.1 |

**กฎเหล็ก:** ทุก MINOR/MAJOR ต้องผ่าน [Release Gate](#release-gate) ก่อนขึ้น live เสมอ

---

## 🗺️ Release Timeline — ภาพรวม

```
v1.0.0 ──► v1.1.0 ──► v1.2.0 ──► v1.3.0 ──► v1.4.0 ──────────► v2.0.0
Foundation  Awareness  Judgment  Perception  Resilience       Autonomy
(ปัจจุบัน)   มองเห็น+    ตัดสินใจ   เห็นสิ่งที่    อยู่รอด+         เทรดเอง
            อธิบายได้    ดีขึ้น     spot ไม่เห็น  ตรวจสอบตัวเอง   หลายกลยุทธ์
```

| เวอร์ชั่น | ธีม | Features | เป้าหมายหลัก | ระยะ |
|----------|-----|----------|-------------|------|
| **v1.0.0** ✅ | Foundation | (มีอยู่แล้ว) | baseline ที่เทรดได้จริง | — |
| **v1.1.0** ✅ | Awareness | F3.2, F5.4, F1.4 | เห็นความเสี่ยง + อธิบายการตัดสินใจได้ | — |
| **v1.2.0** ✅ | Judgment | F2.1, F2.2 | เลือก model + จัดการ exit ฉลาดขึ้น | — |
| **v1.3.0** ✅ | Perception | F1.1, F1.2, F1.3 | ข้อมูลที่ตลาด spot มองไม่เห็น | — |
| **v1.3.0** ✅ | Perception | F1.1, F1.2, F1.3 | ข้อมูลที่ตลาด spot มองไม่เห็น | — |
| **v1.4.0** ✅ | Resilience | F3.4, F5.1, F3.3 | self-validate + tail-risk control | — |
| **v2.0.0** | Autonomy | F3.1, F5.3, ~~F2.3~~, F2.4 | multi-strategy + self-managing | 3–5 สัปดาห์ |
| _backlog_ | Advanced | F4.1–F4.4, F5.2 | ของเสริม ทำเมื่อ ROI คุ้ม | — |

---

## v1.0.0 — "Foundation" ✅ (ปัจจุบัน)

**ธีม:** ฐานที่เทรดได้จริง มี safety ครบ

**สิ่งที่มีในเวอร์ชั่นนี้:**
- Signal funnel: 40+ indicators → regime → model → confidence gate → risk → sizing
- 4 models: Rule-based (5 strategy), LightGBM+SHAP, Claude agentic, Hybrid
- RL UCB1 bandit (strategy × regime), Kelly sizing + ATR/GARCH/HRP
- Risk engine: drawdown guard, daily-loss circuit breaker, portfolio heat
- Sentiment: Fear & Greed, Funding rate, Open Interest
- Backtest: walk-forward + fee/slippage, per-regime/pattern breakdown
- Safety: dry-run, kill switch, allowlist, rate limit, localhost bind

**KPI baseline:** เก็บค่าจริงจาก dry-run/paper เพื่อใช้เป็นจุดอ้างอิงทุกเวอร์ชั่นถัดไป
> ⚠️ ก่อนเริ่ม v1.1 ต้อง **lock baseline** — รัน dry-run ≥ 2 สัปดาห์ บันทึก Sharpe / Max DD / Win-rate / Profit Factor

---

## v1.1.0 — "Awareness" 👁️ ✅ (implemented)

**ธีม:** Lunai เห็นความเสี่ยงรอบตัว และอธิบายได้ว่าทำไมถึงเทรด

**ทำไมเวอร์ชั่นนี้ก่อน:** quick wins ที่ใช้ infra เดิม + `F5.4` ทำให้ debug ทุกเวอร์ชั่นถัดไปง่ายขึ้น (เห็นว่าใครพาเข้าเทรด)

| Feature | สิ่งที่ได้ | Effort | สถานะ |
|---------|-----------|--------|-------|
| `F3.2` Correlation Guard | กัน over-concentration (ไม่ stack BTC+ETH+BNB ที่ corr 0.8+) | S | ✅ |
| `F5.4` Attribution Logging | ทุกเทรดบอกได้ว่ามาจาก signal ไหน น้ำหนักเท่าไร | S | ✅ |
| `F1.4` Derivatives Depth | long/short ratio, taker flow, OI change | S | ✅ |

**สิ่งที่ลงจริง (commit นี้):**
- `F3.2` — `RiskEngine.check_correlation()` + Pearson helper; wired เข้า BUY gate ใน `ai_trader._check_risk_limits` ผ่าน `_check_correlation_guard()`; config `risk.max_correlation` (0.80) + เปิด/ปิดได้
- `F5.4` — `_get_final_signal` เก็บ attribution ของทุก sub-signal (ml/rule/claude/multi_model + RL strategy + regime + confidence gate); แสดงใน dashboard `last_signal.attribution`, ใส่ใน `trade_executed` broadcast, และ persist สรุปสั้นลง trade reasoning
- `F1.4` — `sentiment.py` เพิ่ม `get_long_short_ratio()`, `get_taker_ratio()`, OI-change tracking + pure `derivatives_bias()` scorer; โผล่ใน `/api/sentiment` block ใหม่ `derivatives`
- **Tests:** +14 unit tests (`test_derivatives_bias.py`, `test_correlation_guard.py`) — รวมทั้งหมด 42 ผ่านหมด

> ⚠️ **เลื่อนไป v1.2:** liquidation-cluster hint (เชื่อม `F2.2` adaptive SL/TP) — Binance ไม่มี public endpoint ฟรี; deriv feature injection เข้า ML hot-path เลื่อนเพื่อกัน latency regression

**🎯 เป้าหมายวัดผล:**
- Max Drawdown ลดลง ≥ 10% จาก baseline (จาก correlation guard)
- ทุกเทรดมี attribution breakdown ครบ 100% ✅ (โครงพร้อม — รอวัดผลจริงใน paper)
- ไม่มี regression: Sharpe ไม่ต่ำกว่า baseline

**🚪 Exit gate:** ผ่าน [Release Gate](#release-gate) + correlation guard บล็อกได้จริงใน paper test
> ⏳ ยังต้องทำก่อนปิด gate: lock baseline (dry-run ≥ 2 สัปดาห์) → วัด Max DD / attribution coverage จริง

---

## v1.2.0 — "Judgment" 🧠 ✅ (implemented)

**ธีม:** Lunai ตัดสินใจดีขึ้น — เลือก model ที่เหมาะกับสถานการณ์ + จัดการ exit เป็น

| Feature | สิ่งที่ได้ | Effort | สถานะ |
|---------|-----------|--------|-------|
| `F2.1` Meta-Ensemble ⭐ | RL เลือกว่า model ไหน (rule/ml/claude) เก่งต่อ regime+symbol | M | ✅ |
| `F2.2` Adaptive SL/TP | SL/TP เป็น ATR/structure-based แทน fixed % + trailing | M | ✅ |

**สิ่งที่ลงจริง:**
- `F2.1` — `ModelBandit` (UCB1, arms = model×regime = 15) เพิ่มใน `rl_trainer.py`; persist `rl_model_bandit.pkl`; wired เข้า hybrid path ใน `_get_final_signal()` แทน hard-coded fallback; reward update ใน `_close_trade()`;  `model_bandit_stats` โผล่ใน dashboard
- `F2.2` — `ExitManager` (`src/agent/exit_manager.py`): ATR-based SL (k×ATR per regime), R:R table (BULL=3×, RANGING=2×, VOLATILE=1.5×, CRASH=1.5×), ATR trailing (activate at N×ATR profit); `attach_exits()` wired เข้า `_execute_trade()` ทับ fixed-%; `check_exit()` เป็น primary path ใน `_check_exit_conditions()`; fallback fixed-% ยังอยู่สำหรับ edge cases
- `_signal_attribution` เพิ่ม field `bandit_model` — บันทึกว่า ModelBandit เลือก model ไหน
- **Tests:** +19 tests (`test_exit_manager.py` × 12, `test_model_bandit.py` × 7) — รวมทั้งหมด **61 ผ่านหมด**

**ทำไมสำคัญ:** นี่คือ upgrade สมองที่ใช้ของเดิม (UCB1) — ผลกระทบต่อ P&L สูงสุดโดยไม่ต้องเพิ่ม data

**🎯 เป้าหมายวัดผล:**
- Profit Factor เพิ่ม ≥ 15% (meta-selection ชนะ best fixed model)
- Win-rate ใน VOLATILE regime ดีขึ้น (จาก adaptive SL ลดโดน stop-hunt)
- Avg winning trade เพิ่มขึ้น (จาก let-winner-run ใน BULL)

**🚪 Exit gate:** backtest พิสูจน์ meta-ensemble ≥ best single model บน **OOS** (ไม่ใช่ in-sample)

---

## v1.3.0 — "Perception" 📡 ✅ (implemented)

**ธีม:** Lunai เห็นสิ่งที่ตลาด spot มองไม่เห็น — edge จากข้อมูล ไม่ใช่แค่ราคา

| Feature | สิ่งที่ได้ | Effort | สถานะ |
|---------|-----------|--------|-------|
| `F1.1` On-chain Metrics | active addresses, tx count, hash rate growth (BTC) | M | ✅ |
| `F1.2` Order Book Microstructure | bid/ask imbalance, wall detection (support/resistance) | M | ✅ |
| `F1.3` Social Sentiment | news keyword sentiment scoring via CryptoCompare | M | ✅ |

**สิ่งที่ลงจริง:**
- `F1.2` — `src/data/orderbook.py`: pure `analyze_order_book(bids, asks)` → imbalance, wall detection, spread_bps, signal (BULLISH/NEUTRAL/BEARISH); async `get_order_book(symbol)` จาก Binance public depth endpoint (ไม่ต้องการ API key); cache 30s
- `F1.1` — `src/data/onchain.py`: pure `onchain_bias(addr_change, tx_change, hr_change)` → (label, score); async `get_btc_onchain()` จาก blockchain.com/stats (BTC เท่านั้น, ไม่ต้องการ key); `get_onchain(symbol)` fallback gracefully สำหรับ non-BTC; cache 10 min
- `F1.3` — `src/data/social.py`: pure `social_sentiment_score(articles, hint)` → keyword count + ratio scoring; async `get_news_sentiment(symbol)` จาก CryptoCompare news API (free, no key); cache 5 min
- `SentimentSnapshot` เพิ่ม fields: ob_imbalance, ob_signal, onchain_label/score, social_label/score/article_count
- `get_snapshot()` — รวม 8 sources พร้อมกัน (asyncio.gather); graceful fallback ทุก source
- `/api/sentiment` — ส่งคืน blocks ใหม่ order_book, onchain, social
- **Tests:** +27 tests (`test_orderbook.py` × 10, `test_onchain.py` × 9, `test_social.py` × 8) — รวมทั้งหมด **88 ผ่านหมด**

**🎯 เป้าหมายวัดผล:**
- เพิ่ม feature ทีละตัว เทียบ Sharpe before/after — เก็บเฉพาะตัวที่ทำให้ดีขึ้น
- Entry timing ดีขึ้น (slippage จริง vs คาดการณ์ ลดลง จาก order book filter)
- On-chain feature ติด top-10 SHAP importance (พิสูจน์ว่ามีประโยชน์จริง)

**🚪 Exit gate:** feature ใดที่ไม่เพิ่ม OOS Sharpe → **ถอดออก** ไม่เก็บไว้เพิ่ม complexity

---

## v1.4.0 — "Resilience" 🛡️ ✅ (implemented)

**ธีม:** Lunai ตรวจสอบตัวเองได้ และอยู่รอดในเหตุการณ์รุนแรง

| Feature | สิ่งที่ได้ | Effort | สถานะ |
|---------|-----------|--------|-------|
| `F3.3` VaR / CVaR + Monte Carlo | tail-risk เชิงปริมาณ (proactive แทน reactive) | M | ✅ |
| `F3.4` Drift Detection + Auto Re-validate | จับ model เสื่อม → retrain อัตโนมัติ | M | ✅ |
| `F5.1` Param Optimization | walk-forward grid search (RSI/ATR/confidence) | M | ✅ |

**สิ่งที่ลงจริง:**
- `F3.3` — `src/agent/var_engine.py`: pure functions `var_cvar(returns, confidence)`, `monte_carlo_maxdd(returns, n_paths, horizon)`, `summarize()`; bootstrap sampling สำหรับ path simulation; wired เข้า `RiskEngine.summary()` ใต้ key `tail_risk`; `_daily_returns` history rolling 365 วัน
- `F3.4` — `src/agent/drift_detector.py`: PSI-based drift detection; pure `psi(expected, actual, buckets)` + `detect_feature_drift()`; `DriftDetector` class ที่ record baseline หลัง training และ check ทุก 50 predictions; trigger retrain อัตโนมัติเมื่อ PSI > 0.20; wired เข้า `AITrainer.train()` (baseline), `predict()` (accumulate + check), `stats` (drift summary)
- `F5.1` — `src/agent/param_optimizer.py`: walk-forward splits + exhaustive grid search ไม่ต้อง Optuna; tune RSI thresholds, ATR multiplier, confidence gate; persist `best_params.json` ใน `models_dir`; `ParamOptimizer` class load-on-startup; `_simulate_returns()` simulation objective
- **Tests:** +39 tests (`test_var_engine.py` × 11, `test_drift_detector.py` × 12, `test_param_optimizer.py` × 16) — รวมทั้งหมด **138 ผ่านหมด**

**🎯 เป้าหมายวัดผล:**
- Model ใหม่ deploy เฉพาะเมื่อ OOS Sharpe ≥ ตัวเดิม (champion/challenger)
- 95% VaR คำนวณได้ + เตือนก่อน position ดัน risk เกิน budget
- Monte Carlo max-DD distribution สอดคล้องกับ realized DD (model สมจริง)

**🚪 Exit gate:** simulate crash scenario (เช่น -30% ใน 1 วัน) → circuit breaker + VaR ทำงานถูกต้อง

---

## v2.0.0 — "Autonomy" 🚀 (MAJOR)

**ธีม:** Lunai กลายเป็น engine หลายกลยุทธ์ที่จัดการตัวเอง — ไม่ใช่แค่ directional bot

> เป็น MAJOR เพราะเพิ่ม **trading paradigm ใหม่** (market-neutral) + ระบบ promote model อัตโนมัติ

| Feature | สิ่งที่ได้ | Effort |
|---------|-----------|--------|
| `F3.1` Active Pairs Trading | cointegration → market-neutral long/short (return ไม่ขึ้นกับทิศตลาด) | L |
| `F5.3` Shadow / Champion-Challenger | รัน model ใหม่ paper คู่ live, promote อัตโนมัติเมื่อชนะ | M |
| `F2.3` Trade Journal / Memory | Lunai สรุปบทเรียนเอง + ดึงมา reason (learning แบบ compounding) | M |
| `F2.4` Adaptive Meta-Parameters | kelly/confidence ปรับตาม rolling Sharpe เอง | M |

**🎯 เป้าหมายวัดผล:**
- Pairs strategy มี return stream ที่ correlation ต่ำกับ directional (< 0.3)
- Champion/challenger สลับ model ได้เองโดยไม่ต้องคนสั่ง
- Lunai เทรดได้กำไรแม้ในตลาด sideways (ที่ directional bot ทำไม่ได้)

**🚪 Exit gate:** market-neutral + directional รวมกันให้ Calmar สูงกว่า directional เดี่ยว

---

<a name="release-gate"></a>
## 🚪 Release Gate — เกณฑ์ผ่านก่อนปล่อยทุกเวอร์ชั่น

ทุก MINOR/MAJOR ต้องผ่าน **ทั้งหมด** ก่อนขึ้น live:

- [ ] **Backtest** ครอบคลุม ≥ 180 วัน ผ่าน ≥ 2 regime (รวมช่วง crash)
- [ ] **Walk-forward OOS:** Sharpe ≥ baseline — optimize บน in-sample, รายงานบน out-of-sample เท่านั้น
- [ ] **ไม่ regression:** Max Drawdown ไม่แย่กว่า baseline
- [ ] **Dry-run / paper** ≥ 2 สัปดาห์ ไม่มี critical bug
- [ ] **Attribution logs** ตรวจแล้ว — ทุก decision อธิบายได้
- [ ] **Safety verified:** kill switch + circuit breaker + correlation guard ทำงานจริง
- [ ] **Single-feature isolation:** เพิ่ม feature ทีละตัว วัด before/after แยกได้

> ❌ ถ้าข้อใดไม่ผ่าน → ไม่ขึ้น live, กลับไปแก้ หรือถอด feature นั้นออก

---

## 📊 KPI Framework — วัดความสำเร็จของ Lunai ยังไง

| Metric | นิยาม | ทำไมสำคัญ | ทิศทางที่ดี |
|--------|-------|----------|-----------|
| **Sharpe Ratio** | return / volatility | edge ที่ปรับความเสี่ยงแล้ว (เสาหลัก) | ↑ สูงขึ้น |
| **Max Drawdown** | ดิ่งจาก peak มากสุด | ความอยู่รอด | ↓ ต่ำลง |
| **Calmar Ratio** | return / max DD | กำไรเทียบความเจ็บ | ↑ สูงขึ้น |
| **Profit Factor** | gross profit / gross loss | คุณภาพ edge | ↑ > 1.5 |
| **Win Rate** | % เทรดที่กำไร | ความสม่ำเสมอ | ↑ (ดูคู่ R:R) |
| **Recovery Factor** | net profit / max DD | ฟื้นตัวเร็วแค่ไหน | ↑ สูงขึ้น |
| **OOS Stability** | Sharpe(OOS) / Sharpe(IS) | ไม่ overfit | → ใกล้ 1.0 |

**กฎทอง:** เปรียบเทียบทุกเวอร์ชั่นกับ **baseline v1.0.0** เสมอ — feature ที่ทำให้ Sharpe แย่ลง = ถอดออก

---

## ⚠️ Risk Register — ความเสี่ยงของ roadmap

| ความเสี่ยง | ผลกระทบ | การรับมือ |
|-----------|---------|----------|
| Overfitting จากเพิ่ม feature เยอะ | model ดีใน backtest แต่เจ๊งจริง | OOS-only reporting, single-feature isolation |
| Complexity creep | bug surface บาน, debug ยาก | release gate เข้ม, ถอด feature ที่ไม่คุ้ม |
| Data source ล่ม (on-chain/social API) | signal หาย, ตัดสินใจพลาด | graceful fallback ทุก fetcher (มี pattern แล้วใน sentiment.py) |
| Feature ใหม่ปรับ aggressiveness พร้อมกัน | overshoot risk (F2.2 + F2.4 ชนกัน) | ปล่อยคนละเวอร์ชั่น, วัดทีละตัว |
| Exchange ไม่ support short (F3.1) | pairs trading ทำไม่ได้ | เช็ค capability ก่อน, fallback spot-only |

---

## 🧭 หลักการตลอด roadmap

1. **วัดผลทุก feature** — Sharpe แย่ลง = ถอด ไม่ใช่เก็บ
2. **เพิ่มทีละตัว** — แยกแยะผลได้ ไม่ batch
3. **OOS เท่านั้น** — optimize in-sample, report out-of-sample
4. **dry-run ก่อน live** — ทุกเวอร์ชั่น
5. **ความซับซ้อนมีต้นทุน** — edge 0.1% แต่ bug เยอะ = ไม่คุ้ม

---

*อัปเดตล่าสุด: 2026-06-04 · Lunai v1.4.0 (engine) ภายใน Aiterra v1.4.0 (platform)*
*Feature spec: [`ROADMAP.md`](./ROADMAP.md)*
