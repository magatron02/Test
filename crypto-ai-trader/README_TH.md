# Lunai v1.0.0

โปรแกรม AI เทรด Crypto อัตโนมัติ แบบ Portable — copy folder ไปเครื่องไหนก็ใช้ได้

---

## วิธีเริ่มใช้งาน (Windows)

### ครั้งแรก
1. ดับเบิลคลิก **`INSTALL.bat`** — ติดตั้ง Python dependencies (ใช้เวลา ~3-7 นาที)
2. ดับเบิลคลิก **`START.bat`** — เปิดโปรแกรม (browser จะเปิดขึ้นมาอัตโนมัติ)

### ครั้งต่อไป
- ดับเบิลคลิก **`START.bat`** แค่นั้นพอ

---

## วิธีอัพเดตเวอร์ชันใหม่ (ข้อมูลเดิมไม่หาย)

เมื่อได้ไฟล์ zip เวอร์ชันใหม่:

1. **แตก zip ทับโฟลเดอร์เดิม** — เลือก **"Replace the files in the destination"**
2. ดับเบิลคลิก **`UPDATE.bat`** — อัพเดต dependencies

ข้อมูลต่อไปนี้ **ไม่ถูกแตะต้อง** เพราะไม่ได้อยู่ใน zip:

| ไฟล์ | เก็บอะไร |
|------|---------|
| `config\settings.yml` | API keys / LINE / Telegram token ทั้งหมด |
| `data\trades.db` | ประวัติการเทรด |
| `models\signal_model.pkl` | โมเดล AI ที่เทรนไว้ |

> โมเดล AI: ครั้งแรกจะใช้ `signal_model.seed.pkl` ที่แถมมา จากนั้นระบบจะเทรนต่อทุกชั่วโมง
> และเซฟเป็น `signal_model.pkl` ของคุณเอง — อัพเดตเวอร์ชันใหม่จะไม่ทับโมเดลนี้

---

## โหมดการทำงาน

| โหมด | คำอธิบาย |
|------|-----------|
| **Demo Mode** | เทรดด้วย virtual money ใช้ข้อมูลตลาดจริง — เพื่อเทรน AI |
| **Live Mode** | เทรดด้วยเงินจริง (ต้องตั้งค่า Exchange + API key ก่อน) |

---

## วิธีเปิด Live Mode (เทรดเงินจริง)

> ⚠️ Live Mode ใช้เงินจริง — แนะนำให้รัน Demo จนกว่า AI จะเทรนพอแล้วค่อยเปิด

1. ไปที่ **Settings → Exchange API Keys** เลือก exchange ที่ใช้ (Binance / Binance TH / Bitkub / OKX)
2. ใส่ **API Key + API Secret** (OKX ต้องมี Passphrase ด้วย) แล้วติ๊ก **Enable** → กด **Save & Test**
3. ที่การ์ด **Trading Mode** เลือก exchange ใน **Live Exchange** ให้ตรงกัน
   - แถบ "พร้อมเทรดจริงผ่าน …" จะเป็นสีเขียวเมื่อตั้งค่าครบ
4. กดปุ่ม **Live Mode** → ยืนยัน → ระบบสลับเป็นเงินจริงทันที (ไม่ต้อง restart)
5. กลับมา Demo เมื่อไหร่ก็กดปุ่ม **Demo Mode** ได้เลย

> - Binance / OKX เทรดคู่ **USDT** · Bitkub / Binance TH เทรดคู่ **THB** (ระบบจะอ่านยอดเงินตามสกุลของ exchange ให้อัตโนมัติ)
> - ต้องปิด position ที่เปิดค้างใน Live ก่อน ถึงจะสลับ mode ได้ (กันลืม position เงินจริง)

---

## การตั้งค่า AI Model

เปิดหน้า **Settings** แล้วเลือก:

| โมเดล | คำอธิบาย |
|--------|-----------|
| **Hybrid** (แนะนำ) | รวม Rule-based + ML + Claude |
| **Rule-based** | ใช้ Technical Indicators ล้วนๆ |
| **ML Model** | ใช้ Random Forest ที่ train จาก demo trades |
| **Claude API** | ใช้ Claude วิเคราะห์ตลาด (ต้องมี API key) |

---

## Exchanges ที่รองรับ

- **Binance** — Global exchange
- **Binance TH** — เวอร์ชันไทย
- **Bitkub** — Exchange ไทย รองรับ THB
- **OKX** — Global exchange

ใส่ API key ในหน้า Settings ก่อนใช้ Live Mode

---

## ระบบ AI Learning (Demo Mode)

1. ระบบเทรด Demo ด้วยข้อมูล Binance จริง
2. บันทึกทุก trade พร้อม indicators (RSI, MACD, BB, EMA, ATR, VWAP)
3. เมื่อ trade ปิด บันทึกผลกำไร/ขาดทุน
4. เมื่อครบ **50 trades** → train RandomForest model อัตโนมัติ
5. Model เรียนรู้ pattern → ช่วยปรับ signal ให้แม่นยำขึ้น

ยิ่งเทรด Demo มาก AI ยิ่งฉลาดขึ้น!

---

## Indicators ที่ใช้

| Indicator | การใช้งาน |
|-----------|-----------|
| RSI (14) | Overbought/Oversold |
| MACD (12/26/9) | Trend direction + crossover |
| EMA (9/21/50) | Trend + momentum |
| Bollinger Bands (20) | Mean reversion signals |
| ATR (14) | Volatility measurement |
| VWAP | Price vs volume average |

---

## โครงสร้างไฟล์

```
crypto-ai-trader/
├── START.bat           ← เปิดโปรแกรม
├── SETUP.bat           ← ติดตั้งครั้งแรก
├── CREATE_SHORTCUT.bat ← สร้าง Desktop shortcut
├── config/
│   └── settings.yml   ← ตั้งค่าทั้งหมด (API keys ฯลฯ)
├── data/
│   └── trades.db      ← ข้อมูลทั้งหมด (SQLite)
├── models/
│   └── signal_model.pkl ← ML model ที่ train แล้ว
└── src/               ← Source code
```

---

## การย้ายไปเครื่องอื่น

1. Copy ทั้ง folder ไปเครื่องใหม่
2. รัน `SETUP.bat` ใหม่ครั้งเดียว
3. รัน `START.bat` ได้เลย
- `data/trades.db` และ `models/signal_model.pkl` ติดไปด้วย
- ประวัติการเทรดและ AI model จะยังอยู่ครบ

---

## แจ้งเตือน

- **LINE Notify**: ใส่ token ในหน้า Settings
- **Telegram**: ใส่ Bot token + Chat ID ในหน้า Settings
