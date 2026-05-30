import { useState, useMemo } from "react";
import { Plus, TrendingUp, TrendingDown, Wallet } from "lucide-react";
import { useStore } from "../store";
import TransactionItem from "../components/TransactionItem";
import TransactionModal from "../components/TransactionModal";
import { Transaction } from "../types";
import { format, startOfMonth, endOfMonth, parseISO, isWithinInterval } from "date-fns";
import { th } from "date-fns/locale";

export default function Home() {
  const { transactions, currency } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Transaction | null>(null);

  const now = new Date();
  const monthStart = startOfMonth(now);
  const monthEnd = endOfMonth(now);

  const monthlyTx = useMemo(
    () =>
      transactions.filter((t) =>
        isWithinInterval(parseISO(t.date), { start: monthStart, end: monthEnd })
      ),
    [transactions]
  );

  const income = useMemo(
    () => monthlyTx.filter((t) => t.type === "income").reduce((s, t) => s + t.amount, 0),
    [monthlyTx]
  );
  const expense = useMemo(
    () => monthlyTx.filter((t) => t.type === "expense").reduce((s, t) => s + t.amount, 0),
    [monthlyTx]
  );
  const balance = income - expense;

  const recent = transactions.slice(0, 10);

  const fmt = (n: number) =>
    n.toLocaleString("th-TH", { minimumFractionDigits: 0, maximumFractionDigits: 2 });

  return (
    <div className="flex flex-col h-full">
      {/* Header gradient */}
      <div className="bg-gradient-to-b from-primary/30 to-bg px-5 pt-12 pb-6">
        <p className="text-sm text-white/60 mb-1">
          {format(now, "MMMM yyyy", { locale: th })}
        </p>
        <p className="text-xs text-white/40 mb-3">ยอดคงเหลือเดือนนี้</p>
        <div className="flex items-baseline gap-1 mb-6">
          <span className="text-4xl font-bold">{currency}</span>
          <span
            className={`text-4xl font-bold ${
              balance >= 0 ? "text-white" : "text-expense"
            }`}
          >
            {fmt(Math.abs(balance))}
          </span>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-income/15 border border-income/30 rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp size={16} className="text-income" />
              <span className="text-xs text-income font-medium">รายรับ</span>
            </div>
            <p className="text-xl font-bold text-income">
              {currency}{fmt(income)}
            </p>
          </div>
          <div className="bg-expense/15 border border-expense/30 rounded-2xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown size={16} className="text-expense" />
              <span className="text-xs text-expense font-medium">รายจ่าย</span>
            </div>
            <p className="text-xl font-bold text-expense">
              {currency}{fmt(expense)}
            </p>
          </div>
        </div>
      </div>

      {/* Transactions */}
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 pb-28">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-sm text-white/80">รายการล่าสุด</h3>
          {transactions.length > 10 && (
            <button
              onClick={() => useStore.getState().setActivePage("transactions")}
              className="text-xs text-primary"
            >
              ดูทั้งหมด
            </button>
          )}
        </div>

        {recent.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <Wallet size={48} className="text-white/10 mb-3" />
            <p className="text-white/30 text-sm">ยังไม่มีรายการ</p>
            <p className="text-white/20 text-xs mt-1">กดปุ่ม + เพื่อเพิ่มรายการแรก</p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {recent.map((t) => (
              <TransactionItem
                key={t.id}
                transaction={t}
                onEdit={(tx) => { setEditing(tx); setShowModal(true); }}
              />
            ))}
          </div>
        )}
      </div>

      {/* FAB */}
      <button
        onClick={() => { setEditing(null); setShowModal(true); }}
        className="fixed bottom-20 right-4 w-14 h-14 bg-primary rounded-full flex items-center justify-center shadow-lg shadow-primary/40 active:scale-95 transition-transform z-30"
      >
        <Plus size={26} />
      </button>

      {showModal && (
        <TransactionModal
          onClose={() => { setShowModal(false); setEditing(null); }}
          editing={editing}
        />
      )}
    </div>
  );
}
