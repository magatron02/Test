# ทำต่อที่นี่ (Continue Here)

> อัพเดตล่าสุด: 2026-06-11
> สถานะ: ✅ Bot รันอยู่บน GCP — demo mode, Binance จริง, ML training active

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
  - `:root` tokens ใหม่ทั้งหมด (bg/card/border/text/font/radius)
  - Sidebar: filled pill active, no left-border, clean bg
  - Cards/buttons/tabs/badges: radius ใหม่ทั้งหมด
  - AT section: Finlandica/hardcoded #000 → CSS vars ทั้งหมด
- [x] **Font/readability pass** — body 15px, text-muted #9898AE, border 0.12, stat-label/card-header/regime-badge ใหญ่ขึ้น
- [x] **Bootstrap .text-muted override** → `var(--text-muted) !important`
- [x] **Chart colors** — ApexCharts foreColor/labels/grid ทั้งหมด → #9898AE / rgba(255,255,255,0.08)
- [x] **Hardcoded dark colors** (#444/#555/#666/#888) ใน inline styles และ JS-rendered HTML → var(--text-muted)
- [x] **Topbar symbol display** — แสดง currentSymbol ที่เลือกอยู่
- [x] **Opus design audit** — 9 remaining inconsistencies แก้แล้ว
- [x] **/impeccable critique** — score 29/40, พบ P0×2 + P1×2
- [x] **P0: SELL color consistency** — แทน `#ff6b35` ทั้งหมด (50+ instances) ด้วย `#EF4444` / `rgba(239,68,68,...)` ทั้งใน CSS, JS, inline styles
- [x] **P0: Micro-label contrast** — `.at-badge` 9→11px, `.at-train-badge` 9→10px, `.kbd-hint` 9→10px, hover opacity 0.55→0.65
- [x] **P1: Bottom duplicate stat grid ลบออก** — Win Rate/Avg PnL/Open Positions/Today PnL ที่ซ้ำถูกลบ
- [x] **DESIGN.md อัพเดต** — เขียนใหม่ทั้งหมดให้ตรงกับ Finance aesthetic ที่ใช้จริงใน code

---

## สิ่งที่ต้องทำต่อ 🚧

### 1. 🟡 ใส่ Anthropic API Key
```bash
# SSH เข้า server แล้ว
nano ~/AI_Create/crypto-ai-trader/config/settings.yml
# api_key: "sk-ant-..."
docker compose restart
```

### 2. 🟡 Deploy code review fixes (Python files) ยังไม่ได้ rebuild
```bash
gcloud compute ssh aiterra-server-sg --zone=asia-southeast1-b
cd ~/AI_Create && git pull
cd crypto-ai-trader && docker compose up -d --build
```
> หมายเหตุ: HTML deploy ทำผ่าน `docker cp` ได้ไม่ต้อง rebuild แต่ Python ต้อง rebuild

### 3. 🟢 Switch เป็น Live Mode
```yaml
trading:
  mode: "live"
```

### 4. 🔵 P2/P3 CSS issues ที่เหลือ (minor)
- `z-index:9999` notification → `var(--z-toast)`
- Modal `width:360px` → `min(360px, 95vw)`

---

## Design Score Tracker

| วัน | Score | หมายเหตุ |
|-----|-------|---------|
| 2026-06-11 (ก่อน) | 29/40 | impeccable critique ครั้งแรก |
| 2026-06-11 (หลัง) | ~35/40 (est.) | แก้ P0×2 + P1×2 แล้ว |

---

## Deploy Method

| งาน | คำสั่ง |
|-----|--------|
| HTML-only (ไม่ restart) | `gcloud compute scp index.html aiterra-server-sg:/tmp/` → `docker cp /tmp/index.html crypto-ai-trader-aiterra-1:/app/src/web/index.html` |
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

*อัพเดตอัตโนมัติโดย Claude — 2026-06-11*
