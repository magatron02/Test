import { useState } from "react";
import { Trash2, Download, Check } from "lucide-react";
import { useStore } from "../store";

const CURRENCIES = [
  { symbol: "฿", label: "บาทไทย",   sub: "THB" },
  { symbol: "$", label: "ดอลลาร์", sub: "USD" },
  { symbol: "€", label: "ยูโร",     sub: "EUR" },
  { symbol: "¥", label: "เยน",      sub: "JPY" },
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
      [...transactions].forEach((t) => deleteTransaction(t.id));
      setConfirmClear(false);
    } else {
      setConfirmClear(true);
    }
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-hide bg-bg pb-28">
      <div className="px-5 pt-12 pb-6">
        <h1 className="text-xl font-bold">Settings</h1>
        <p className="text-xs text-sub mt-0.5">ปรับแต่งแอพพลิเคชัน</p>
      </div>

      {/* Currency */}
      <div className="px-5 mb-6">
        <p className="text-xs text-sub uppercase tracking-widest mb-3">สกุลเงิน</p>
        <div className="bg-card border border-border rounded-2xl overflow-hidden divide-y divide-border">
          {CURRENCIES.map((c) => (
            <button
              key={c.symbol}
              onClick={() => setCurrency(c.symbol)}
              className="w-full flex items-center gap-4 px-4 py-4 hover:bg-card2 transition-colors"
            >
              <div className="w-10 h-10 rounded-full bg-green/10 border border-green/20 flex items-center justify-center text-green font-bold text-base">
                {c.symbol}
              </div>
              <div className="flex-1 text-left">
                <p className="text-sm font-medium">{c.label}</p>
                <p className="text-[11px] text-sub">{c.sub}</p>
              </div>
              {currency === c.symbol && (
                <div className="w-6 h-6 rounded-full bg-green flex items-center justify-center">
                  <Check size={14} className="text-black" strokeWidth={2.5} />
                </div>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Data */}
      <div className="px-5 mb-6">
        <p className="text-xs text-sub uppercase tracking-widest mb-3">ข้อมูล</p>
        <div className="bg-card border border-border rounded-2xl overflow-hidden divide-y divide-border">
          <div className="flex items-center px-4 py-4">
            <div className="flex-1">
              <p className="text-sm font-medium">รายการทั้งหมด</p>
              <p className="text-[11px] text-sub">{transactions.length} รายการในระบบ</p>
            </div>
            <div className="px-3 py-1 bg-green/10 border border-green/20 rounded-full">
              <span className="text-xs text-green font-semibold">{transactions.length}</span>
            </div>
          </div>

          <button
            onClick={handleExport}
            disabled={transactions.length === 0}
            className="w-full flex items-center gap-4 px-4 py-4 hover:bg-card2 transition-colors disabled:opacity-40"
          >
            <div className="w-10 h-10 rounded-full bg-green/10 flex items-center justify-center">
              <Download size={16} className="text-green" />
            </div>
            <div className="flex-1 text-left">
              <p className="text-sm font-medium">ส่งออกข้อมูล</p>
              <p className="text-[11px] text-sub">บันทึกเป็นไฟล์ CSV</p>
            </div>
          </button>

          <button
            onClick={handleClearAll}
            className="w-full flex items-center gap-4 px-4 py-4 hover:bg-expense/5 transition-colors"
          >
            <div className="w-10 h-10 rounded-full bg-expense/10 flex items-center justify-center">
              <Trash2 size={16} className="text-expense" />
            </div>
            <div className="flex-1 text-left">
              <p className={`text-sm font-medium ${confirmClear ? "text-expense" : "text-white"}`}>
                {confirmClear ? "ยืนยันลบข้อมูลทั้งหมด?" : "ลบข้อมูลทั้งหมด"}
              </p>
              <p className="text-[11px] text-sub">ไม่สามารถกู้คืนได้</p>
            </div>
          </button>
        </div>
      </div>

      <div className="px-5">
        <div className="bg-card border border-border rounded-2xl px-4 py-4 text-center">
          <div className="text-2xl mb-1">💰</div>
          <p className="text-sm font-semibold">Expense Tracker</p>
          <p className="text-[11px] text-sub mt-0.5">v1.0.0 — บันทึกข้อมูลในเครื่อง</p>
        </div>
      </div>
    </div>
  );
}
