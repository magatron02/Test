# ทำต่อที่นี่ (Continue Here)

> อัพเดตล่าสุด: 2026-06-12 (session 2 — N'legion, end of day)
> สถานะ: ✅ Bot รันอยู่บน GCP — demo mode, Binance จริง, ML training active, deploy ล่าสุด 2026-06-12 bklit-ui pass

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
- [x] **bklit-ui design language** — frosted glass ApexCharts tooltip (backdrop-blur:14px), area chart gradient fill (0→80→100 stops), axis labels 11px / 0.40 opacity, Geist Mono in all charts

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

### 3. 🟡 Minor CSS fix ที่ค้าง
- `--md-linear-progress-track-color: rgba(0,168,232,0.12)` → `rgba(255,255,255,0.08)` (M2 spec, line ~91 ใน :root)

### 4. 🔵 Material Web ที่ยังเหลือ (optional)
- Exchange enable checkboxes → `md-switch` (binance_enabled, binance_th_enabled ฯลฯ)
- Notification checkboxes → `md-switch`
- Remaining ~5 `spinner-border` instances (inline-style status text)
- `md-slider` สำหรับ confidence threshold / stop loss % / take profit %

### 5. 🔵 Motion รอบต่อไป (optional)
- Nav pill morphing — sliding indicator
- Portfolio PnL flash — `_m3Flash` บน ai-dash-value
- Chart entrance animation (area fade-in on load)

### 6. 🔵 UX polish (optional)
- Empty states — signal cards / activity feed เมื่อยังไม่มีข้อมูล
- Notifications setup — LINE/Telegram

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
