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
- [x] **Opus design audit** — 9 remaining inconsistencies แก้แล้ว:
  - topbar-slim: remove backdrop-filter, bg → var(--bg-card)
  - price-card: 14px → var(--radius-card)
  - #1a1a1a bar tracks → var(--bg-card2) ทั้งหมด

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

## Deploy Method

| งาน | คำสั่ง |
|-----|--------|
| HTML-only (ไม่ restart) | `gcloud compute scp index.html aiterra-server-sg:/tmp/` → `docker cp /tmp/index.html container:/app/src/web/` |
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
