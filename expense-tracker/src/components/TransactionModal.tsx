import { useState, useEffect } from "react";
import { X, CheckCircle } from "lucide-react";
import { useStore } from "../store";
import { getCategoriesByType } from "../store/categories";
import { Transaction, TransactionType } from "../types";
import { format } from "date-fns";

interface Props {
  onClose: () => void;
  editing?: Transaction | null;
}

export default function TransactionModal({ onClose, editing }: Props) {
  const { addTransaction, updateTransaction } = useStore();

  const [type,     setType]     = useState<TransactionType>(editing?.type ?? "expense");
  const [amount,   setAmount]   = useState(editing ? String(editing.amount) : "");
  const [category, setCategory] = useState(editing?.category ?? "");
  const [note,     setNote]     = useState(editing?.note ?? "");
  const [date,     setDate]     = useState(editing?.date ?? format(new Date(), "yyyy-MM-dd"));

  const categories = getCategoriesByType(type);

  useEffect(() => {
    if (!editing) setCategory("");
  }, [type, editing]);

  const handleSubmit = () => {
    const num = parseFloat(amount.replace(/,/g, ""));
    if (!num || num <= 0 || !category) return;
    if (editing) {
      updateTransaction(editing.id, { type, amount: num, category, note, date });
    } else {
      addTransaction({ type, amount: num, category, note, date });
    }
    onClose();
  };

  const isIncome = type === "income";
  const accentColor = isIncome ? "#3DED97" : "#FF6B6B";

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="sheet-up relative w-full max-w-[430px] bg-surface rounded-t-3xl border-t border-border px-5 pt-5 pb-8">

        {/* Handle */}
        <div className="w-10 h-1 bg-border rounded-full mx-auto mb-5" />

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-bold">{editing ? "แก้ไขรายการ" : "เพิ่มรายการใหม่"}</h2>
          <button onClick={onClose} className="w-8 h-8 rounded-full bg-card2 flex items-center justify-center">
            <X size={16} />
          </button>
        </div>

        {/* Type toggle */}
        <div className="flex bg-bg rounded-xl p-1 mb-5 border border-border">
          {(["expense", "income"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={`flex-1 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                type === t
                  ? t === "income"
                    ? "bg-green text-black"
                    : "bg-expense text-white"
                  : "text-sub"
              }`}
            >
              {t === "income" ? "รายรับ" : "รายจ่าย"}
            </button>
          ))}
        </div>

        {/* Amount */}
        <div
          className="rounded-2xl border p-4 mb-4 transition-colors"
          style={{ borderColor: accentColor + "44", backgroundColor: accentColor + "08" }}
        >
          <p className="text-xs mb-1" style={{ color: accentColor + "aa" }}>จำนวนเงิน (บาท)</p>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="w-full bg-transparent text-4xl font-bold focus:outline-none placeholder-white/10"
            style={{ color: accentColor }}
            autoFocus
          />
        </div>

        {/* Category */}
        <div className="mb-4">
          <p className="text-xs text-sub mb-2">หมวดหมู่</p>
          <div className="grid grid-cols-4 gap-2">
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setCategory(cat.id)}
                className={`flex flex-col items-center gap-1 p-2.5 rounded-xl border transition-all ${
                  category === cat.id
                    ? "border-green/60 bg-green/10"
                    : "border-border bg-card"
                }`}
              >
                <span className="text-xl">{cat.icon}</span>
                <span className="text-[9px] text-center leading-tight text-sub">{cat.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Note & Date */}
        <div className="grid grid-cols-2 gap-3 mb-5">
          <div>
            <p className="text-xs text-sub mb-1.5">หมายเหตุ</p>
            <input
              type="text"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="เพิ่มโน้ต..."
              className="w-full bg-card border border-border px-3 py-2.5 rounded-xl text-sm focus:outline-none focus:border-green/50 placeholder-muted"
            />
          </div>
          <div>
            <p className="text-xs text-sub mb-1.5">วันที่</p>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full bg-card border border-border px-3 py-2.5 rounded-xl text-sm focus:outline-none focus:border-green/50"
            />
          </div>
        </div>

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={!amount || !category}
          className="w-full py-4 rounded-2xl font-bold text-sm flex items-center justify-center gap-2 disabled:opacity-30 transition-opacity"
          style={{ backgroundColor: accentColor, color: isIncome ? "#000" : "#fff" }}
        >
          <CheckCircle size={18} />
          {editing ? "บันทึกการแก้ไข" : "เพิ่มรายการ"}
        </button>
      </div>
    </div>
  );
}
