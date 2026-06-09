# ทำต่อที่นี่ (Continue Here)

> อัพเดตล่าสุด: 2026-06-10
> สถานะ: App deploy บน GCP สำเร็จ — ทำงานใน demo mode, รอ config สำหรับ live trading

---

## สิ่งที่ทำไปแล้ว ✅

- [x] Clone repo จาก GitHub มาที่ `C:\Users\Lenovo\Desktop\AI\AI_Create`
- [x] ตั้งค่า `/quicksave` command สำหรับ sync ระหว่างเครื่อง
- [x] วิเคราะห์ codebase ด้วย understand-anything → knowledge graph 310 nodes (ภาษาไทย)
- [x] dashboard ใช้งานได้ที่ `.understand-anything/start-dashboard.bat`
- [x] ศึกษา Lunai: ตอนนี้ v1.4.0 "Resilience" — ซื้อขายเองได้แบบ semi-auto, ต้องมีคนดูอยู่
- [x] dry-run: ไม่ต้องเปิดตลอด ปิดได้ ระบบจำ state ไว้ใน `runtime_state.json`
- [x] สร้าง `crypto-ai-trader/Dockerfile` สำหรับ `src/` (Python FastAPI, port 8888)
- [x] อัพเดต `crypto-ai-trader/docker-compose.yml` ให้ชี้ `src/` แทน `backend/`
- [x] ตั้งค่า `config/settings.yml` สำหรับ cloud (host 0.0.0.0, open_browser false, Binance TH)
- [x] Deploy บน GCP e2-micro (us-central1-a, Ubuntu 22.04, free tier)
- [x] แก้ bug 4 ตัว: `_max_var_pct`, `_max_prob_ruin`, `_opt_rsi_oversold`, `_model_bandit`, `_get_pairs_signal`
- [x] App ขึ้นสมบูรณ์: `Application startup complete`, port 8888, demo mode

---

## สิ่งที่ต้องทำต่อ 🚧

### 1. 🔴 เข้าดู Dashboard (ด่วน)
```bash
curl -s ifconfig.me   # หา Public IP ของ server
```
แล้วเปิด browser: `http://<PUBLIC_IP>:8888`

### 2. 🟠 แก้ Binance HTTP 451 (Geo-block จาก US)
ตอนนี้ app ใช้ **simulated price** เพราะ GCP us-central1 (Iowa) ถูก Binance block  
ทางเลือก:
- ย้าย VM ไป `asia-southeast1` (Singapore) — ได้ราคาจริงจาก Binance TH
- หรือใช้ demo mode ต่อไปก่อน (ยังทำงานได้)

### 3. 🟡 ใส่ Anthropic API Key
แก้ใน `config/settings.yml` บน server:
```yaml
ai:
  claude:
    api_key: "sk-ant-..."
```
แล้ว `docker compose restart`

### 4. 🟢 Switch เป็น Live Mode
หลังทดสอบ demo ผ่านแล้ว — เปลี่ยนใน settings.yml:
```yaml
trading:
  mode: "live"
```

---

## โครงสร้างโปรเจค (สำคัญ)

```
AI_Create/
├── crypto-ai-trader/
│   ├── src/                    ← โค้ดหลัก (ใช้งานจริง)
│   │   ├── agent/ai_trader.py  ← Lunai engine
│   │   ├── core/config.py
│   │   └── web/               ← FastAPI app
│   ├── backend/                ← เวอร์ชันเก่า (ไม่ใช้แล้ว)
│   ├── Dockerfile              ← ✅ ใหม่ สำหรับ src/
│   ├── docker-compose.yml      ← ✅ อัพเดตแล้ว ชี้ src/
│   └── config/
│       ├── settings.yml        ← API keys + config (gitignored)
│       └── settings.example.yml
└── .understand-anything/
    ├── knowledge-graph.json    ← 310 nodes, 599 edges
    └── start-dashboard.bat     ← เปิด dashboard
```

---

## Server Info (GCP)

| ค่า | ข้อมูล |
|-----|--------|
| Provider | Google Cloud (Free Tier) |
| Region | us-central1-a (Iowa) |
| Machine | e2-micro (2 vCPU, 1 GB RAM) |
| OS | Ubuntu 22.04 LTS |
| Port | 8888 |
| Path | `~/AI_Create/crypto-ai-trader` |
| Status | ✅ Running (demo mode) |

---

## API Keys ที่ใส่แล้ว

| Key | สถานะ |
|-----|--------|
| BINANCE_TH_API_KEY | ✅ ใส่แล้วใน settings.yml |
| BINANCE_TH_SECRET_KEY | ✅ ใส่แล้วใน settings.yml |
| ANTHROPIC_API_KEY | ❌ ยังไม่ได้ใส่ |

---

## คำสั่งที่ใช้บ่อย (บน server)

```bash
# SSH เข้า server
ssh -i <key>.key kongboonma2@<PUBLIC_IP>

# ดู logs
cd ~/AI_Create/crypto-ai-trader && docker compose logs -f --tail=30

# Restart
docker compose restart

# Update + rebuild
cd ~/AI_Create && git pull && cd crypto-ai-trader && docker compose up -d --build
```

---

*ไฟล์นี้สร้างอัตโนมัติโดย Claude เพื่อบันทึกความคืบหน้า*
