# ทำต่อที่นี่ (Continue Here)

> อัพเดตล่าสุด: 2026-06-09
> สถานะ: กำลังวางแผน Deploy บน Cloud ด้วย Docker

---

## สิ่งที่ทำไปแล้ว ✅

- [x] Clone repo จาก GitHub มาที่ `C:\Users\...\Desktop\AI_Create`
- [x] ตั้งค่า `/quicksave` command สำหรับ sync ระหว่างเครื่อง
- [x] วิเคราะห์ codebase ด้วย understand-anything → knowledge graph 310 nodes (ภาษาไทย)
- [x] dashboard ใช้งานได้ที่ `.understand-anything/start-dashboard.bat`
- [x] ศึกษา Lunai: ตอนนี้ v1.4.0 "Resilience" — ซื้อขายเองได้แบบ semi-auto, ต้องมีคนดูอยู่
- [x] dry-run: ไม่ต้องเปิดตลอด ปิดได้ ระบบจำ state ไว้ใน `runtime_state.json`

---

## สิ่งที่ต้องทำต่อ 🚧

### เป้าหมาย: Deploy Aiterra บน Cloud ด้วย Docker

**ปัญหา:** `docker-compose.yml` ปัจจุบันชี้ไปที่ `backend/` (เวอร์ชันเก่า)
โค้ดหลักอยู่ที่ `src/` ซึ่ง**ยังไม่มี Dockerfile**

**งานที่ต้องทำ:**

1. **สร้าง Dockerfile ใหม่** สำหรับ `src/` (Python FastAPI)
2. **อัพเดต `docker-compose.yml`** ให้ใช้ `src/` แทน `backend/`
3. **ตั้งค่า `.env`** (ต้องการ: BINANCE_API_KEY, ANTHROPIC_API_KEY)
4. **เลือก Cloud server**: Oracle Free Tier (ฟรี) หรือ DigitalOcean $6/เดือน
5. **Deploy + ทดสอบ**

---

## โครงสร้างโปรเจค (สำคัญ)

```
AI_Create/
├── crypto-ai-trader/
│   ├── src/                    ← โค้ดหลัก (ใช้งานจริง)
│   │   ├── agent/ai_trader.py  ← Lunai engine
│   │   ├── core/config.py
│   │   └── web/               ← FastAPI app
│   ├── backend/                ← เวอร์ชันเก่า (มี Dockerfile แต่ outdated)
│   ├── docker-compose.yml      ← ต้องแก้ให้ชี้ src/
│   ├── config/
│   │   └── settings.example.yml ← copy เป็น settings.yml แล้วแก้
│   └── backend/.env.example    ← copy เป็น .env แล้วใส่ API keys
└── .understand-anything/
    ├── knowledge-graph.json    ← 310 nodes, 599 edges
    └── start-dashboard.bat     ← เปิด dashboard
```

---

## ข้อมูล API Keys ที่ต้องใช้ (Demo mode)

| Key | จำเป็น | หมายเหตุ |
|-----|--------|----------|
| BINANCE_API_KEY | ✅ | Read-Only permission พอ |
| BINANCE_SECRET_KEY | ✅ | |
| ANTHROPIC_API_KEY | ✅ ถ้าใช้ Claude AI | claude-3-5-sonnet |
| BINANCE_TESTNET | ตั้งเป็น `false` | ใช้ราคาจริง แต่ไม่ trade จริง |

---

## คำสั่งที่ใช้บ่อย

```bash
# Sync ระหว่างเครื่อง
/quicksave

# เปิด knowledge graph dashboard
.understand-anything/start-dashboard.bat

# ดู settings
crypto-ai-trader/config/settings.example.yml
crypto-ai-trader/backend/.env.example
```

---

## ขั้นตอนถัดไปที่คุยกับ Claude ค้างไว้

บอก Claude ว่า: **"ช่วยสร้าง Dockerfile และ docker-compose.yml ใหม่ สำหรับ src/ เพื่อ deploy บน cloud"**

Claude จะสร้าง:
- `crypto-ai-trader/Dockerfile` (สำหรับ `src/`)
- `crypto-ai-trader/docker-compose.yml` (อัพเดต)
- `crypto-ai-trader/.env.template` (template สำหรับ cloud)

---

*ไฟล์นี้สร้างอัตโนมัติโดย Claude เพื่อบันทึกความคืบหน้า*
