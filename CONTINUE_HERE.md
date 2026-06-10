# ทำต่อที่นี่ (Continue Here)

> อัพเดตล่าสุด: 2026-06-10
> สถานะ: ⚠️ Bot รันอยู่บน GCP แต่ **ไม่เทรดเลย** — มี critical bugs ใน ai_trader.py ที่ต้องแก้ก่อน

---

## สิ่งที่ทำไปแล้ว ✅

- [x] Clone repo จาก GitHub มาที่ local
- [x] ตั้งค่า `/quicksave` command สำหรับ sync ระหว่างเครื่อง
- [x] วิเคราะห์ codebase ด้วย understand-anything → knowledge graph 310 nodes (ภาษาไทย)
- [x] ศึกษา Lunai: v1.4.0 → v2.0.0 upgrade
- [x] สร้าง `Dockerfile` + อัพเดต `docker-compose.yml`
- [x] Deploy บน GCP Singapore (asia-southeast1-b, e2-micro, free tier)
- [x] แก้ bugs ต่างๆ: `_journal`, `_max_var_pct`, `_opt_rsi_oversold`, `_model_bandit`
- [x] Binance เชื่อมได้ — ราคาจริง, ML training ทำงาน
- [x] RTK PreToolUse hook ตั้งค่าแล้ว
- [x] `/impeccable init` → PRODUCT.md + DESIGN.md + .impeccable/design.json
- [x] `/impeccable critique` → Health score 24/40, 13 findings (snapshot ที่ `.impeccable/snapshots/`)
- [x] แก้ side-tab border-left ×3, bounce easing ×2, em dash ×11, reduced-motion support
- [x] **fast-trade analysis** → ดึงเฉพาะแนวคิดดี (FINTA, Optuna, parquet cache, C/C)
- [x] **FINTA bridge** (`src/agent/finta_bridge.py`) — 50+ indicators เสริม
- [x] **Parquet kline cache** (`src/agent/kline_cache.py`) — backtest ไม่ต้อง fetch API ซ้ำ
- [x] **F5.3 Champion/Challenger** (`src/agent/champion_challenger.py`) — tournament 5 strategies
- [x] **F2.4 Optuna optimizer** (`src/agent/param_optimizer.py`) — TPE Bayesian search
- [x] **F2.4 wiring fix** — เพิ่ม `ParamOptimizer()` init + startup `_apply_opt_params()` call ใน ai_trader.py
- [x] **F3.1 Pairs Trading** (`_get_pairs_signal()`) — Engle-Granger cointegration + OU z-score, cache 288 cycles
- [x] **API endpoints**: `GET /api/champion`, `POST /api/champion/tournament`
- [x] **Champion/Challenger UI** — tab ใน Analytics section, leaderboard, Run Tournament button
- [x] **Alt+1–8 keyboard shortcuts** — sidebar nav + kbd badge hints
- [x] **Audit P1 a11y fixes** — role="button" + aria-current บน nav items, chat input focus ring, price card keyboard support
- [x] Docker rebuild → finta 1.3, optuna 4.9.0, pyarrow 24.0.0 install สำเร็จ
- [x] Deploy ล่าสุดบน server → container healthy
- [x] **Model Routing** (`src/agent/model_router.py`) — Haiku สำหรับ BULL/BEAR_TREND, Sonnet สำหรับ CRASH/VOLATILE/RANGING + `GET /api/model-router/stats`

---

## 🚨 BUGS ที่ต้องแก้ก่อน (Bot ไม่เทรดเลยตอนนี้!)

> ตรวจพบโดย Opus code audit — 2026-06-10

### BUG #1 — CRITICAL: `_get_final_signal()` ไม่มี `return` statement
**ไฟล์:** `crypto-ai-trader/src/agent/ai_trader.py` บริเวณ line 569-734
**ปัญหา:** F3.1 commit ทำให้ pairs-signal block ซ้ำสองรอบ และ `return final_sig` หายไป
→ method คืนค่า `None` → caller ทุกตัว crash `AttributeError: 'NoneType'.action`
**แก้:** หา `final_sig` บริเวณท้ายฟังก์ชัน → เพิ่ม `return final_sig` + ลบ dead pairs block ซ้ำ (lines ~712-734)

### BUG #2 — CRITICAL: `self._exit_mgr` ไม่ถูก init
**ไฟล์:** `crypto-ai-trader/src/agent/ai_trader.py` — `__init__`
**ปัญหา:** `ExitManager` มีใน `exit_manager.py` แต่ไม่เคย import/assign ใน `__init__`
→ ATR-based trades เปิดไม่ได้, stop-loss/take-profit ไม่ทำงาน
**แก้:** ใน `__init__` เพิ่ม:
```python
from .exit_manager import ExitManager
self._exit_mgr = ExitManager()
```

### BUG #3 — CRITICAL: `regime` undefined ใน `_check_exit_conditions()`
**ไฟล์:** `crypto-ai-trader/src/agent/ai_trader.py:1091`
**ปัญหา:** `self._exit_mgr.check_exit(trade, price, atr_pct, regime)` — `regime` ไม่ใช่ param หรือ local
**แก้:** เพิ่ม `regime = self._regimes.get(analysis.symbol, "RANGING")` ก่อน call

### BUG #4 — CRITICAL: `self._arb` (ArbitrageEngine) ไม่ถูก init
**ไฟล์:** `crypto-ai-trader/src/api/routes.py:961, 972, 986` + `ai_trader.py` `__init__`
**ปัญหา:** 3 arbitrage endpoints crash `AttributeError`
**แก้:** ใน `AITrader.__init__` เพิ่ม:
```python
from .arbitrage import ArbitrageEngine
self._arb = ArbitrageEngine()
```

### BUG #5 — CRITICAL: `self._attribution_summary()` method ไม่มี
**ไฟล์:** `crypto-ai-trader/src/agent/ai_trader.py:890`
**ปัญหา:** method ถูก call แต่ไม่มีการ define ที่ไหนเลยใน codebase
**แก้:** define method หรือ remove call (ใช้ inline dict แทน)

### BUG #6 — HIGH: `self._signal_attribution` ค้าง `None` ตลอด
**ไฟล์:** `crypto-ai-trader/src/agent/ai_trader.py:97`
**ปัญหา:** `_get_final_signal` สร้าง local `components` dict แต่ไม่เคย assign `self._signal_attribution`
→ ModelBandit reward "rule" เสมอ → learning corrupt
**แก้:** ใน `_get_final_signal` ก่อน `return final_sig` เพิ่ม:
```python
self._signal_attribution = {**components, "chosen": chosen}
```

---

## สิ่งที่ต้องทำต่อ 🚧

### 0. 🔴 แก้ BUGS #1-6 ก่อน (ทำตามลำดับ)
แก้ไฟล์ `crypto-ai-trader/src/agent/ai_trader.py` เป็นหลัก ดูรายละเอียดข้างบน

### 1. 🟡 ใส่ Anthropic API Key (สำคัญ — ทำให้ Claude AI วิเคราะห์ได้)
SSH เข้า server แล้วแก้ `config/settings.yml`:
```bash
gcloud compute ssh kongboonma2@aiterra-server-sg --zone=asia-southeast1-b
nano ~/AI_Create/crypto-ai-trader/config/settings.yml
# หา claude: api_key: "" แล้วใส่ key
docker compose restart
```

### 2. 🟢 Switch เป็น Live Mode (หลังทดสอบ demo ผ่านแล้ว)
แก้ใน settings.yml บน server:
```yaml
trading:
  mode: "live"
```
หรือใช้ POST /api/mode/swap ผ่าน dashboard UI

### 3. 🔵 Audit P2/P3 issues (จาก /impeccable audit)
- Hardcoded `#0a0a0a` บน canvas background → `var(--bg-canvas, #0a0a0a)`
- `z-index:9999` notification → CSS variable `--z-toast`
- Modal `width:360px` → `min(360px, 95vw)`
- รัน `/impeccable audit` อีกครั้งหลังแก้ → expect 15-16/20

### 4. 🔵 ทดสอบ F3.1 Pairs Trading ใน production
- ต้องการ ≥2 symbols ที่มี ≥50 bars ใน `_price_history` (ปกติหลังรัน ~50 cycles)
- ดูที่ logs: `Cointegration cache: X symbols in Y pairs`
- ถ้ามี cointegrated pairs จะเห็น `pairs z=X.XX` ใน reasoning ของ trades

### 5. 🔵 ทดสอบ Champion/Challenger ใน dashboard
- ไปที่ Analytics → Champion tab
- เลือก symbol + days แล้วกด Run Tournament
- ครั้งแรกอาจใช้เวลา 1-2 นาที (fetch 60 วันของ klines)

---

## Server Info (GCP Singapore)

| ค่า | ข้อมูล |
|-----|--------|
| Provider | Google Cloud (Free Tier) |
| Region | asia-southeast1-b (Singapore) |
| Machine | e2-micro (2 vCPU, 1 GB RAM) |
| OS | Ubuntu 22.04 LTS |
| Port | 8888 |
| Public IP | 34.21.139.179 |
| Dashboard | http://34.21.139.179:8888 |
| Path | `~/AI_Create/crypto-ai-trader` |
| Status | ✅ Running (demo mode, Binance จริง) |

---

## API Keys ที่ใส่แล้ว

| Key | สถานะ |
|-----|--------|
| BINANCE_TH_API_KEY | ✅ ใส่แล้ว |
| BINANCE_TH_SECRET_KEY | ✅ ใส่แล้ว |
| ANTHROPIC_API_KEY | ❌ ยังไม่ได้ใส่ (ทำให้ Claude AI + chat ไม่ทำงาน) |

---

## Lunai v2.0.0 Feature Status

| Feature | สถานะ |
|---------|--------|
| F1.x Market Intelligence | ✅ (sentiment, onchain, orderbook, social) |
| F2.3 Trade Journal | ✅ |
| F2.4 Adaptive Meta-Params (Optuna) | ✅ implemented + wired |
| F3.1 Pairs Trading | ✅ implemented (cointegration + z-score) |
| F5.1 Walk-forward Optimizer | ✅ |
| F5.3 Champion/Challenger | ✅ code + API + UI |
| Model Routing (Haiku/Sonnet) | ✅ model_router.py + integrated |
| Anthropic API Key | ❌ ยังไม่ได้ใส่ |

---

## คำสั่งที่ใช้บ่อย

```bash
# SSH เข้า server
gcloud compute ssh kongboonma2@aiterra-server-sg --zone=asia-southeast1-b

# ดู logs
cd ~/AI_Create/crypto-ai-trader && docker compose logs -f --tail=30

# Restart
docker compose restart

# Update + rebuild
cd ~/AI_Create && git pull && cd crypto-ai-trader && docker compose up -d --build
```

---

*ไฟล์นี้สร้างอัตโนมัติโดย Claude เพื่อบันทึกความคืบหน้า*
