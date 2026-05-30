import { useState, useEffect } from "react";
import { X } from "lucide-react";
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

  const [type, setType] = useState<TransactionType>(editing?.type ?? "expense");
  const [amount, setAmount] = useState(editing ? String(editing.amount) : "");
  const [category, setCategory] = useState(editing?.category ?? "");
  const [note, setNote] = useState(editing?.note ?? "");
  const [date, setDate] = useState(editing?.date ?? format(new Date(), "yyyy-MM-dd"));

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

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-[430px] bg-surface rounded-t-2xl p-5 pb-8 animate-[slideUp_0.25s_ease-out]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold">
            {editing ? "แก้ไขรายการ" : "เพิ่มรายการ"}
          </h2>
          <button onClick={onClose} className="p-1 rounded-full hover:bg-white/10">
            <X size={20} />
          </button>
        </div>

        {/* Type toggle */}
        <div className="flex bg-bg rounded-xl p-1 mb-5">
          {(["expense", "income"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setType(t)}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                type === t
                  ? t === "expense"
                    ? "bg-expense text-white"
                    : "bg-income text-white"
                  : "text-muted"
              }`}
            >
              {t === "expense" ? "รายจ่าย" : "รายรับ"}
            </button>
          ))}
        </div>

        {/* Amount */}
        <div className="mb-4">
          <label className="text-xs text-muted mb-1.5 block">จำนวนเงิน (บาท)</label>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.00"
            className="w-full bg-bg text-3xl font-bold text-center py-3 rounded-xl border border-white/10 focus:outline-none focus:border-primary placeholder-white/20"
            autoFocus
          />
        </div>

        {/* Category */}
        <div className="mb-4">
          <label className="text-xs text-muted mb-1.5 block">หมวดหมู่</label>
          <div className="grid grid-cols-4 gap-2">
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setCategory(cat.id)}
                className={`flex flex-col items-center gap-1 p-2 rounded-xl border transition-colors ${
                  category === cat.id
                    ? "border-primary bg-primary/20"
                    : "border-white/10 bg-bg"
                }`}
              >
                <span className="text-xl">{cat.icon}</span>
                <span className="text-[10px] text-center leading-tight">{cat.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Note */}
        <div className="mb-4">
          <label className="text-xs text-muted mb-1.5 block">หมายเหตุ</label>
          <input
            type="text"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="เพิ่มหมายเหตุ..."
            className="w-full bg-bg px-4 py-2.5 rounded-xl border border-white/10 focus:outline-none focus:border-primary text-sm placeholder-white/20"
          />
        </div>

        {/* Date */}
        <div className="mb-6">
          <label className="text-xs text-muted mb-1.5 block">วันที่</label>
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-full bg-bg px-4 py-2.5 rounded-xl border border-white/10 focus:outline-none focus:border-primary text-sm"
          />
        </div>

        {/* Submit */}
        <button
          onClick={handleSubmit}
          disabled={!amount || !category}
          className={`w-full py-3.5 rounded-xl font-semibold text-white transition-opacity ${
            type === "expense" ? "bg-expense" : "bg-income"
          } disabled:opacity-40`}
        >
          {editing ? "บันทึกการแก้ไข" : "เพิ่มรายการ"}
        </button>
      </div>
    </div>
  );
}
