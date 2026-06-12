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
- [x] **Invalid Date** บน ML MODEL card — แก้ Python ISO timestamp guard แล้ว
- [x] **Design revamp** — Finance aesthetic: DM Sans, #080808 black bg, 16px radius, clean cards
- [x] **Font/readability pass** — body 15px, text-muted #9898AE, border 0.12, stat-label/card-header/regime-badge ใหญ่ขึ้น
- [x] **Bootstrap .text-muted override** → `var(--text-muted) !important`
- [x] **Chart colors** — ApexCharts foreColor/labels/grid ทั้งหมด → #9898AE / rgba(255,255,255,0.08)
- [x] **Hardcoded dark colors** (#444/#555/#666/#888) → var(--text-muted)
- [x] **Topbar symbol display** — แสดง currentSymbol ที่เลือกอยู่
- [x] **Opus design audit** — 9 remaining inconsistencies แก้แล้ว
- [x] **/impeccable critique** — score 30/40, แก้ P0×2 + P1×3 เสร็จหมด
- [x] **P0: SELL color** — แทน #ff6b35 ทั้งหมด (50+ instances) → #EF4444
- [x] **P0: Micro-label contrast** — .at-badge 9→11px, .at-train-badge/kbd-hint 9→10px
- [x] **P1: Bottom stat grid ลบออก**
- [x] **P1: Danger confirm modal** — reusable modal พร้อม 5s countdown สำหรับ Force Sell / Kill Switch
- [x] **P1: WS stale bar** — แสดง banner เมื่อ WebSocket ขาดเกิน 15s
- [x] **P1: Risk model bar** — live-computed exposure/RRR ใน Trading Parameters
- [x] **P1: Settings section headers** — 5 section headers ใน Settings page
- [x] **P2: Activity Feed structured CSS** — .ai-bar color strip + .ai-content layout
- [x] **P2: Activity Feed JS** — addActivity() render ใช้ .ai-bar + .ai-content structure
- [x] **P3: Stat-card inline styles** — 12 instances → CSS classes sc-buy/sc-lime/sc-red/sc-warn
- [x] **DESIGN.md อัพเดต** — เขียนใหม่ทั้งหมดให้ตรงกับ Finance aesthetic
- [x] **M3 Motion System** — Material Design 3 expressive motion ทั้งระบบ:
  - CSS tokens: `--ease-exp-out`, `--ease-spring`, duration vars
  - @keyframes: sectionIn (upgraded), m3SpringPop, m3SlideUp, m3ValUp/Down, m3ToastIn, m3GlowRing, m3Shimmer
  - Utility classes: .m3-card-in, .m3-spring-pop, .m3-slide-up, .m3-val-up/down, .m3-glow, .m3-skeleton
  - Section entrance: translateY(22px)+scale(0.97) → emphasized-decel easing
  - Signal cards: staggered pop-in + M3 hover glow (buy=green, sell=red)
  - Stat values: green/red flash animation เมื่อ value เปลี่ยน (winRate, avgPnl, totalTrades)
  - Activity feed: spring-pop animation บน item ใหม่
  - Price cards: ripple effect บน click
  - Toast: spring entrance + smooth exit
  - Reduced-motion: ครอบคลุมทุก class ใหม่

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

### 3. 🔵 Motion รอบต่อไป (optional)
- Nav pill morphing — sliding indicator ที่เลื่อนตาม active item
- Portfolio PnL flash — _m3Flash บน ai-dash-value เมื่อ PnL เปลี่ยน
- Chart entrance animation — bars draw in เมื่อ chart โหลด
- Skeleton loading states บน cards ที่รอ data

---

## Design Score Tracker

| วัน | Score | หมายเหตุ |
|-----|-------|---------|
| 2026-06-11 (ก่อน) | 29/40 | impeccable critique ครั้งแรก |
| 2026-06-12 (หลัง P0-P3) | ~36/40 (est.) | แก้ P0×2 + P1×3 + P2 + P3 + M3 motion |

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
| Path บน server | ไม่มี git repo — ใช้ docker cp เท่านั้น |
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
