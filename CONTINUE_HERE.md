# ทำต่อที่นี่ (Continue Here)

> อัพเดตล่าสุด: 2026-06-12 (session 3 — polish + bugfix pass)
> สถานะ: ✅ Bot รันอยู่บน GCP — demo mode, Binance จริง, ML training active, deploy ล่าสุด 2026-06-12 (charts fix + motion)

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
- [x] **/impeccable critique** — score 30/40 → ~38/40, แก้ P0×2 + P1×3 เสร็จหมด
- [x] **P0: SELL color** (#ff6b35 → #EF4444), **P0: Micro-label contrast**, **P1: Danger modal**, **P1: WS stale bar**, **P1: Risk model bar**, **P1: Settings headers**, **P2: Activity Feed**, **P3: Stat-card classes**
- [x] **M3 Motion System** — CSS tokens, keyframes (sectionIn, SpringPop, ValUp/Down, ToastIn, GlowRing), section entrance, signal card hover glow, stat flash, activity spring-pop, price card ripple
- [x] **Material Web (@material/web)** — md-switch (×2), md-linear-progress (signal cards), md-circular-progress (spinners), _spin() helper
- [x] **M2 Dark Theme** — `#0D1117` bg, `#192028` card, `rgba(255,255,255,0.12/0.08)` borders, `#00A8E8` accent-only
- [x] **Typography overhaul** — Geist + Geist Mono (fallback Inter + JetBrains Mono), 16px base, floor all micro-labels at 11-12px, tabular-nums ทั้งหมด
- [x] **bklit-ui design language** — frosted glass ApexCharts tooltip (backdrop-blur:14px), area chart gradient fill (0→80→100 stops), Geist Mono in all charts
- [x] **CRITICAL FIX: 4 charts ไม่แสดง** — Portfolio/DailyPnL/Allocation/Feature mount บน `<canvas>` (เหลือจาก Chart.js) → เปลี่ยนเป็น `<div>` แล้วแสดงปกติ
- [x] **นาฬิกาเรียลไทม์** topbar — `#topbarClock` เดินทุกวินาที + แยก lastUpdate (data sync time)
- [x] **Invalid Date ใน Signal Funnel** — รองรับ epoch/ISO timestamp แล้ว
- [x] **Contrast pass** — bg-card #1B242E, border 0.14, text-main 0.93, text-muted 0.68, chart labels 0.55/12px
- [x] **Font pass** — stat-value 2.15rem, hero 3rem, AT section 11→12/13px ทั้งชุด, weight 500-700 ตาม hierarchy
- [x] **Motion #5** — snav sliding indicator (pill morph), PnL flash บน hero, chart entrance fade-in
- [x] **Empty states #6** — signal grid skeleton + "AI กำลังเฝ้าตลาด" feed + attribution hint
- [x] **md-linear-progress track** → rgba(255,255,255,0.08) (M2 spec)

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

### 3. 🔵 Material Web ที่ยังเหลือ (optional — ข้ามไว้ตามสั่ง)
- Exchange enable checkboxes → `md-switch` (binance_enabled, binance_th_enabled ฯลฯ)
- Notification checkboxes → `md-switch`
- Remaining ~5 `spinner-border` instances (inline-style status text)
- `md-slider` สำหรับ confidence threshold / stop loss % / take profit %

### 4. 🔵 UX polish ที่เหลือ (optional)
- Notifications setup — LINE/Telegram (ต้องใช้ token)
- DESIGN.md ยัง stale (อธิบาย DM Sans/#A8FF53 แต่โค้ดจริงเป็น M2/Geist/#00A8E8) — ควร regenerate

---

## Design Score Tracker

| วัน | Score | หมายเหตุ |
|-----|-------|---------|
| 2026-06-11 (ก่อน) | 29/40 | impeccable critique ครั้งแรก |
| 2026-06-12 (หลัง M3+MWC) | ~38/40 (est.) | P0-P3 + M3 motion + Material Web |
| 2026-06-12 (end of day) | ~39-40/40 (est.) | + M2 dark theme + Geist + bklit-ui pass |

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
