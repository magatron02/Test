# Microstructure — Yellow Feature Plan
> ได้ concept มาจาก [binance_l3_est](https://github.com/OctopusTakopi/binance_l3_est)
> บันทึก: 2026-06-05 — รอทำในรอบถัดไป

---

## F-MICRO-5: CTR / OTR True Metrics (ความซับซ้อน: สูง)

### คืออะไร
- **CTR** (Cancellation-to-Trade Ratio) — สัดส่วน qty ที่ถูก cancel เทียบกับ qty ที่ trade จริง  
  → ค่าสูง = สัญญาณ spoofing (วางแล้วยกเลิก)
- **OTR** (Order-to-Trade Ratio) — สัดส่วน order ใหม่ต่อ trade ที่เกิดขึ้น  
  → วัดความหนาแน่นของ liquidity provision

### ทำไมยังไม่ทำ
ccxt และ Binance REST ให้ L2 snapshot เท่านั้น — ไม่มี event stream ระดับ order  
ต้องการ **Binance WebSocket individual order events** หรือ **SBE stream** (ที่ repo ต้นทางใช้ Rust)

### แนวทางที่จะทำ
```
Option A: WebSocket diff stream
  - Subscribe to <symbol>@depth (update stream, 100ms)
  - Track orders ที่หายไปจาก book โดยไม่มี trade match
  - ctr = disappeared_qty / traded_qty ต่อ window 1 นาที

Option B: Approx จาก L2 snapshot diff
  - เก็บ snapshot ทุก 1 วิ → เทียบ qty ที่หายไป vs OHLCV volume
  - ความแม่นยำต่ำกว่า Option A แต่ implement ง่ายกว่า
  - ใช้ self._ob_history ที่มีอยู่แล้วได้เลย
```

### Files ที่ต้องแก้
- `src/exchanges/base.py` — เพิ่ม `subscribe_depth_stream()` abstract
- `src/exchanges/binance_client.py` — implement WebSocket depth stream
- `src/agent/market_analyzer.py` — เพิ่ม `ctr_approx`, `otr_approx` fields
- `src/agent/trainer.py` — เพิ่ม `ctr_approx`, `otr_approx` ใน `GBM_FEATURE_KEYS`
- `src/web/index.html` — แสดงใน Microstructure panel

---

## F-MICRO-6: K-Means Participant Clustering (ความซับซ้อน: กลาง)

### คืออะไร
จัด cluster ของ order ตามขนาด (size) เพื่อแยกประเภทผู้เล่น:
- Cluster เล็ก = รายย่อย / retail
- Cluster กลาง = fund / institution
- Cluster ใหญ่ = whale

### แนวทางที่จะทำ
```python
# ใน market_analyzer.py หรือ file ใหม่ microstructure_extra.py
from sklearn.cluster import MiniBatchKMeans

def cluster_participants(bids: list, asks: list, n_clusters: int = 5) -> dict:
    qtys = [q for _, q in bids + asks if q > 0]
    if len(qtys) < n_clusters * 2:
        return {}
    X = np.array(qtys).reshape(-1, 1)
    km = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, n_init=3)
    km.fit(X)
    centroids = sorted(km.cluster_centers_.flatten())
    labels = ["micro", "small", "medium", "large", "whale"][:n_clusters]
    return dict(zip(labels, centroids))
```

### Output → ML features
```python
"cluster_whale_pct"  # % ของ orders ที่อยู่ใน whale cluster
"cluster_retail_pct" # % ของ orders ที่อยู่ใน micro/small cluster
"cluster_ratio"      # whale_pct / retail_pct
```

### Files ที่ต้องแก้
- `src/agent/market_analyzer.py` — เพิ่ม `cluster_participants()` + fields
- `src/agent/trainer.py` — เพิ่ม cluster features ใน `GBM_FEATURE_KEYS`
- `src/web/index.html` — แสดง cluster breakdown ใน Microstructure panel

---

## F-MICRO-7: L2→L3 Queue Reconstruction (ความซับซ้อน: สูง)

### คืออะไร
ประมาณ queue priority ของ order แต่ละ level จาก L2 snapshots:
- Level ที่อยู่มานาน = "senior" (มาก่อน → execute ก่อน)
- Level ใหม่ = "junior"
- ช่วยประมาณว่า order ที่ level นั้นจะ execute เมื่อไหร่

### แนวทางที่จะทำ
```
1. Track ว่า price level แต่ละ level อยู่มากี่ snapshot แล้ว
   _level_age[symbol][price_level] = age_in_snapshots

2. ถ้า level qty ลดลง (partial fill) → record ว่า order เริ่ม execute
   → estimate time_to_fill = age × snapshot_interval

3. Output:
   - bid_queue_depth_ticks: กี่ level ก่อนถึงราคาตลาด
   - top_bid_age_bars: level ที่ดีที่สุดอยู่มากี่ bar แล้ว
   - partial_fill_rate: สัดส่วน level ที่ถูก partial fill ต่อ cycle
```

### Files ที่ต้องแก้
- `src/agent/ai_trader.py` — เพิ่ม `_level_age` dict tracking ใน `analyze_symbol()`
- `src/agent/market_analyzer.py` — เพิ่ม `bid_queue_depth`, `top_bid_age` fields
- `src/agent/trainer.py` — เพิ่ม queue features ใน `GBM_FEATURE_KEYS`

---

## สรุปลำดับการทำ

| ลำดับ | Feature | Effort | Impact |
|---|---|---|---|
| 1 | F-MICRO-6 K-Means Clustering | ~2 ชม. | กลาง |
| 2 | F-MICRO-5 OTR/CTR (Option B approx) | ~3 ชม. | สูง |
| 3 | F-MICRO-5 OTR/CTR (Option A WebSocket) | ~1 วัน | สูงมาก |
| 4 | F-MICRO-7 L2→L3 Queue | ~1 วัน | กลาง |

แนะนำ: ทำ **F-MICRO-6** ก่อน เพราะง่ายสุดและได้ ML feature ทันที
