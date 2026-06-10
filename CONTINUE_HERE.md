# ทำต่อที่นี่ (Continue Here)

> อัพเดตล่าสุด: 2026-06-10
> สถานะ: ✅ App รันบน Singapore + impeccable design system ตั้งค่าแล้ว + critique ผ่าน (8/13 findings แก้แล้ว)

---

## สิ่งที่ทำไปแล้ว ✅

- [x] Clone repo จาก GitHub มาที่ local
- [x] ตั้งค่า `/quicksave` command สำหรับ sync ระหว่างเครื่อง
- [x] วิเคราะห์ codebase ด้วย understand-anything → knowledge graph 310 nodes (ภาษาไทย)
- [x] dashboard local ใช้งานได้ที่ `.understand-anything/start-dashboard.bat`
- [x] ศึกษา Lunai: v1.4.0 "Resilience" — ซื้อขายเองได้แบบ semi-auto
- [x] สร้าง `Dockerfile` + อัพเดต `docker-compose.yml` สำหรับ `src/`
- [x] Deploy บน GCP Singapore (asia-southeast1-b, e2-micro, free tier)
- [x] แก้ bug: `_journal`, `_max_var_pct`, `_max_prob_ruin`, `_opt_rsi_oversold`, `_model_bandit`
- [x] Binance เชื่อมได้ — ราคาจริง, ML training ทำงาน
- [x] ลบ Iowa VM อันเก่าออกแล้ว
- [x] RTK PreToolUse hook เขียนใน `~/.claude/settings.json` แล้ว (ต้อง restart Claude Code ถึงจะโหลด)
- [x] `/impeccable init` — สร้าง `PRODUCT.md` + `DESIGN.md` + `.impeccable/design.json`
- [x] `/impeccable critique` — Health score 24/40, 13 findings (snapshot ที่ `.impeccable/snapshots/`)
- [x] แก้ side-tab border-left ×3 (lines 480, 3039, 4684) → background tint + full border
- [x] แก้ bounce easing ×2 (lines 285, 342) → `cubic-bezier(0.22,1,0.36,1)`
- [x] แก้ em dash prose separators ×11 → `:` / `,`
- [x] เพิ่ม `@media (prefers-reduced-motion: reduce)` ครอบทุก animation

---

## สิ่งที่ต้องทำต่อ 🚧

### 1. 🟡 ใส่ Anthropic API Key (ถ้าต้องการ Claude AI วิเคราะห์)
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

### 3. 🟡 Keyboard shortcuts (P2 จาก critique)
`Alt+1`–`Alt+8` สำหรับ nav sections — เพิ่มใน `crypto-ai-trader/src/web/index.html`
พิจารณา collapse 8 tabs → 5 primary + secondary group

### 4. 🔵 `/impeccable audit` (ถัดไปหลัง polish)
ตรวจ a11y, contrast, responsive — รัน `/impeccable audit crypto-ai-trader/src/web/index.html`

### 5. 🔵 Remaining Lunai v2.0.0 features
- F2.4 Adaptive Meta-Params
- F5.3 Champion/Challenger
- F3.1 Pairs Trading

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
| ANTHROPIC_API_KEY | ❌ ยังไม่ได้ใส่ |

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
