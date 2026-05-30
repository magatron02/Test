import { useState } from "react";
import { Trash2, Download, ChevronRight, DollarSign } from "lucide-react";
import { useStore } from "../store";

const CURRENCIES = [
  { symbol: "฿", label: "บาทไทย (THB)" },
  { symbol: "$", label: "ดอลลาร์ (USD)" },
  { symbol: "€", label: "ยูโร (EUR)" },
  { symbol: "¥", label: "เยน (JPY)" },
];

export default function Settings() {
  const { currency, setCurrency, transactions, deleteTransaction } = useStore();
  const [confirmClear, setConfirmClear] = useState(false);

  const handleExport = () => {
    const csv = [
      ["วันที่", "ประเภท", "หมวดหมู่", "จำนวน", "หมายเหตุ"].join(","),
      ...transactions.map((t) =>
        [t.date, t.type === "income" ? "รายรับ" : "รายจ่าย", t.category, t.amount, `"${t.note}"`].join(",")
      ),
    ].join("\n");

    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `expense-tracker-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleClearAll = () => {
    if (confirmClear) {
      transactions.forEach((t) => deleteTransaction(t.id));
      setConfirmClear(false);
    } else {
      setConfirmClear(true);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-hide pb-28">
      <div className="px-5 pt-12 pb-6">
        <h1 className="text-xl font-bold">ตั้งค่า</h1>
      </div>

      {/* Currency */}
      <div className="px-5 mb-6">
        <p className="text-xs text-muted mb-3 uppercase tracking-wide">สกุลเงิน</p>
        <div className="bg-card rounded-2xl overflow-hidden divide-y divide-white/5">
          {CURRENCIES.map((c) => (
            <button
              key={c.symbol}
              onClick={() => setCurrency(c.symbol)}
              className="w-full flex items-center gap-4 px-4 py-3.5 hover:bg-white/5 transition-colors"
            >
              <div className="w-9 h-9 bg-primary/20 rounded-full flex items-center justify-center text-primary font-bold">
                {c.symbol}
              </div>
              <div className="flex-1 text-left">
                <p className="text-sm font-medium">{c.label}</p>
              </div>
              {currency === c.symbol && (
                <div className="w-5 h-5 rounded-full bg-primary flex items-center justify-center">
                  <div className="w-2 h-2 rounded-full bg-white" />
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Data */}
      <div className="px-5 mb-6">
        <p className="text-xs text-muted mb-3 uppercase tracking-wide">ข้อมูล</p>
        <div className="bg-card rounded-2xl overflow-hidden divide-y divide-white/5">
          <div className="flex items-center px-4 py-3.5">
            <div className="flex-1">
              <p className="text-sm font-medium">รายการทั้งหมด</p>
              <p className="text-xs text-muted">{transactions.length} รายการ</p>
            </div>
            <ChevronRight size={16} className="text-muted" />
          </div>

          <button
            onClick={handleExport}
            className="w-full flex items-center gap-4 px-4 py-3.5 hover:bg-white/5 transition-colors"
          >
            <div className="w-9 h-9 bg-primary/20 rounded-full flex items-center justify-center">
              <Download size={16} className="text-primary" />
            </div>
            <div className="flex-1 text-left">
              <p className="text-sm font-medium">ส่งออกข้อมูล</p>
              <p className="text-xs text-muted">บันทึกเป็นไฟล์ CSV</p>
            </div>
            <ChevronRight size={16} className="text-muted" />
          </button>

          <button
            onClick={handleClearAll}
            className="w-full flex items-center gap-4 px-4 py-3.5 hover:bg-expense/10 transition-colors"
          >
            <div className="w-9 h-9 bg-expense/20 rounded-full flex items-center justify-center">
              <Trash2 size={16} className="text-expense" />
            </div>
            <div className="flex-1 text-left">
              <p className="text-sm font-medium text-expense">
                {confirmClear ? "กดอีกครั้งเพื่อยืนยัน" : "ลบข้อมูลทั้งหมด"}
              </p>
              <p className="text-xs text-muted">ไม่สามารถกู้คืนได้</p>
            </div>
          </button>
        </div>
      </div>

      {/* App info */}
      <div className="px-5">
        <div className="bg-card rounded-2xl px-4 py-4 text-center">
          <p className="text-sm font-semibold mb-1">บัญชีรายรับรายจ่าย</p>
          <p className="text-xs text-muted">v1.0.0</p>
        </div>
      </div>
    </div>
  );
}
