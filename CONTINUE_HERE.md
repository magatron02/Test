# ทำต่อที่นี่ (Continue Here)

> อัพเดตล่าสุด: 2026-06-12
> สถานะ: ✅ Bot รันอยู่บน GCP — demo mode, Binance จริง, ML training active, deploy ล่าสุด 2026-06-12

---

## สิ่งที่ทำไปแล้ว ✅

- [x] Clone repo จาก GitHub มาที่ local
- [x] ตั้งค่า `/quicksave` command สำหรับ sync ระหว่างเครื่อง
- [x] วิเคราะห์ codebase ด้วย understand-anything → knowledge graph 310 nodes
- [x] Deploy บน GCP Singapore (asia-southeast1-b, e2-micro, free tier)
- [x] แก้ bugs ต่างๆ, Binance เชื่อมได้, ML training ทำงาน
- [x] **FINTA bridge**, **Parquet kline cache**, **Champion/Challenger**, **Optuna optimizer**, **Pairs Trading**, **Model Routing**
- [x] **fibonacci_levels()** wired เข้า signal pipeline เป็น confluence filter
- [x] **Chart range buttons** (1H/24H/7D) แก้แล้ว — refetch candles จริง
- [x] **Design revamp** — Finance aesthetic: DM Sans, #080808 black bg, 16px radius, clean cards
- [x] **Font/readability pass**, **Bootstrap .text-muted override**, **Chart colors**, **Hardcoded dark colors** → CSS vars
- [x] **Opus design audit** — 9 remaining inconsistencies แก้แล้ว
- [x] **/impeccable critique** — score 30/40, แก้ P0×2 + P1×3 เสร็จหมด
- [x] **P0: SELL color** (#ff6b35 → #EF4444, 50+ instances)
- [x] **P0: Micro-label contrast** (9→10-11px)
- [x] **P1: Danger confirm modal** (5s countdown, Force Sell / Kill Switch)
- [x] **P1: WS stale bar** (banner หลัง 15s ขาด)
- [x] **P1: Risk model bar** (live exposure/RRR)
- [x] **P1: Settings section headers** (5 headers)
- [x] **P2: Activity Feed** CSS + JS (structured .ai-bar + .ai-content)
- [x] **P3: Stat-card inline styles** → CSS classes sc-buy/sc-lime/sc-red/sc-warn
- [x] **DESIGN.md อัพเดต** — Finance aesthetic ครบ
- [x] **M3 Motion System**:
  - CSS tokens: `--ease-exp-out`, `--ease-spring`, duration vars
  - @keyframes: sectionIn (upgraded), m3SpringPop, m3SlideUp, m3ValUp/Down, m3ToastIn, m3GlowRing
  - Section entrance: translateY(22px)+scale(0.97) → emphasized-decel
  - Signal cards: staggered pop-in + M3 hover glow
  - Stat values: green/red flash เมื่อ value เปลี่ยน
  - Activity feed: spring-pop บน item ใหม่
  - Price cards: ripple effect บน click
  - Toast: spring entrance + slide exit
- [x] **Material Web (@material/web) integration**:
  - CDN via ESM: switch, circular-progress, linear-progress
  - M3 sys color tokens ใน `:root` (map Finance aesthetic → Material Web)
  - `md-switch` แทน dryRunToggle (topbar) + schedEnabled (Settings)
  - JS compat shim: `md-switch.checked` ↔ `.selected` (backward-compatible)
  - `md-linear-progress` แทน at-conf-bar ใน signal cards
  - `_spin()` helper function แทน Bootstrap spinner-border
  - Spinner replaced: Running…/Running AI Backtest/Testing connections/กำลังคิด/icon buttons

---

## สิ่งที่ต้องทำต่อ 🚧

### 1. 🟡 ใส่ Anthropic API Key (ข้ามก่อน — เสียเงิน)
```bash
nano ~/AI_Create/crypto-ai-trader/config/settings.yml
# api_key: "sk-ant-..."
docker compose restart
```

### 2. 🟢 Switch เป็น Live Mode (เมื่อพร้อม)
```yaml
trading:
  mode: "live"
```

### 3. 🔵 Material Web ที่ยังเหลือ (optional)
- Exchange enable checkboxes → `md-switch` (binance_enabled, binance_th_enabled ฯลฯ)
- Notification checkboxes → `md-switch`
- Remaining 5 `spinner-border` instances (10px inline-style status text)
- `md-slider` สำหรับ confidence threshold / stop loss % / take profit %

### 4. 🔵 Motion รอบต่อไป (optional)
- Nav pill morphing — sliding indicator
- Portfolio PnL flash — _m3Flash บน ai-dash-value
- Chart entrance animation

---

## Design Score Tracker

| วัน | Score | หมายเหตุ |
|-----|-------|---------|
| 2026-06-11 (ก่อน) | 29/40 | impeccable critique ครั้งแรก |
| 2026-06-12 (หลัง M3+MWC) | ~38/40 (est.) | P0-P3 + M3 motion + Material Web |

---

## Deploy Method

| งาน | คำสั่ง |
|-----|--------|
| HTML-only (ไม่ restart) | `gcloud compute scp index.html aiterra-server-sg:/tmp/` → `sudo docker cp /tmp/index.html crypto-ai-trader-aiterra-1:/app/src/web/index.html` |
| Python files | `docker cp file.py container:/app/path/` + `docker restart` |
| Full rebuild | `git pull` + `docker compose up -d --build` |

---

## Server Info (GCP Singapore)

| ค่า | ข้อมูล |
|-----|--------|
| IP | 34.21.139.179:8888 |
| Container name | `crypto-ai-trader-aiterra-1` |
| SSH zone | `asia-southeast1-b` project `winged-poetry-428205-i4` |

---

## API Keys

| Key | สถานะ |
|-----|--------|
| BINANCE_TH_API_KEY | ✅ ใส่แล้ว |
| BINANCE_TH_SECRET_KEY | ✅ ใส่แล้ว |
| ANTHROPIC_API_KEY | ❌ ยังไม่ได้ใส่ |

---

*อัพเดตอัตโนมัติโดย Claude — 2026-06-12*
