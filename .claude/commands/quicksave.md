---
description: Save and push all changes to GitHub (sync between computers)
---

## ขั้นตอน Quicksave

### 1. อัพเดต CONTINUE_HERE.md ก่อน

อัพเดตไฟล์ `CONTINUE_HERE.md` ให้สะท้อนสถานะล่าสุด:
- วันที่ปัจจุบัน
- สถานะงานที่เพิ่งทำเสร็จ → ย้ายไป ✅
- งานที่ค้างอยู่ → อัพเดตให้ตรง
- ขั้นตอนถัดไปที่ต้องทำต่อ → เขียนให้ชัดเจน ราวกับว่าคนอื่นจะมาอ่านต่อ

### 2. Push ขึ้น GitHub

```bash
cd "C:\Users\Lenovo\Desktop\AI\AI_Create"
git add -A
git commit -m "quicksave: บันทึกความคืบหน้า $(date '+%Y-%m-%d %H:%M')" --allow-empty
git push origin main
```

หลังรันแล้ว แจ้งผลการ push ให้ทราบ ถ้า push ถูก reject (คอมเครื่องอื่น push ไปก่อน) ให้รัน:
```bash
git pull --rebase origin main
git push origin main
```
