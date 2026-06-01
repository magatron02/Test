import { useState, useMemo } from "react";
import { Plus, ArrowDownLeft, ArrowUpRight, ChevronRight } from "lucide-react";
import { useStore } from "../store";
import { getCategoryById } from "../store/categories";
import TransactionModal from "../components/TransactionModal";
import { Transaction } from "../types";
import {
  format, startOfMonth, endOfMonth, parseISO, isWithinInterval,
} from "date-fns";
import { th } from "date-fns/locale";

export default function Home() {
  const { transactions, currency, setActivePage } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing]     = useState<Transaction | null>(null);
  const [activeTab, setActiveTab] = useState<"income" | "expense">("income");

  const now        = new Date();
  const monthStart = startOfMonth(now);
  const monthEnd   = endOfMonth(now);

  const monthTx = useMemo(
    () => transactions.filter((t) =>
      isWithinInterval(parseISO(t.date), { start: monthStart, end: monthEnd })
    ),
    [transactions]
  );

  const totalIncome  = useMemo(() => monthTx.filter((t) => t.type === "income").reduce((s, t) => s + t.amount, 0), [monthTx]);
  const totalExpense = useMemo(() => monthTx.filter((t) => t.type === "expense").reduce((s, t) => s + t.amount, 0), [monthTx]);
  const balance      = totalIncome - totalExpense;

  const allIncome  = useMemo(() => transactions.filter((t) => t.type === "income").reduce((s, t) => s + t.amount, 0), [transactions]);
  const allExpense = useMemo(() => transactions.filter((t) => t.type === "expense").reduce((s, t) => s + t.amount, 0), [transactions]);

  const recent = transactions.slice(0, 8);

  const fmt = (n: number) =>
    n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-hide bg-bg pb-28">

      {/* ── Top bar ── */}
      <div className="flex items-center justify-between px-5 pt-12 pb-2">
        <div className="w-9 h-9 rounded-full bg-card2 border border-border overflow-hidden flex items-center justify-center text-lg">
          👤
        </div>
        <p className="text-xs text-sub font-medium tracking-wide">Total Balance</p>
        <button
          onClick={() => { setEditing(null); setShowModal(true); }}
          className="w-9 h-9 rounded-full border border-green/40 flex items-center justify-center text-green hover:bg-green/10 transition-colors"
        >
          <Plus size={18} />
        </button>
      </div>

      {/* ── Balance ── */}
      <div className="px-5 pt-2 pb-6 text-center">
        <p className="text-[42px] font-bold tracking-tight leading-none mb-1">
          {currency}{fmt(balance < 0 ? 0 : balance)}
        </p>
        <p className="text-sub text-xs">
          {format(now, "MMMM yyyy", { locale: th })}
        </p>

        {/* Tabs */}
        <div className="flex gap-3 justify-center mt-5">
          <button
            onClick={() => setActiveTab("income")}
            className={`flex items-center gap-1.5 px-5 py-2 rounded-full text-sm font-semibold transition-all ${
              activeTab === "income"
                ? "bg-green text-black shadow-green"
                : "border border-green/30 text-green/70"
            }`}
          >
            <ArrowDownLeft size={14} />
            Income
          </button>
          <button
            onClick={() => setActiveTab("expense")}
            className={`flex items-center gap-1.5 px-5 py-2 rounded-full text-sm font-semibold transition-all ${
              activeTab === "expense"
                ? "bg-expense text-white"
                : "border border-expense/30 text-expense/70"
            }`}
          >
            <ArrowUpRight size={14} />
            Spending
          </button>
        </div>
      </div>

      {/* ── Budget Overview ── */}
      <div className="px-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold">Budget Overview</p>
          <button
            onClick={() => setActivePage("analytics")}
            className="text-xs text-sub flex items-center gap-0.5"
          >
            See all <ChevronRight size={12} />
          </button>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {/* Income card */}
          <div className="bg-card rounded-2xl p-4 border border-border">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-full bg-green/15 flex items-center justify-center">
                <ArrowDownLeft size={15} className="text-green" />
              </div>
              <span className="text-xs text-sub">Income</span>
            </div>
            <p className="text-base font-bold text-green leading-tight">
              {currency} {fmt(allIncome)}
            </p>
            <p className="text-[10px] text-sub mt-1">รายรับทั้งหมด</p>
          </div>

          {/* Expense card */}
          <div className="bg-card rounded-2xl p-4 border border-border">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-8 h-8 rounded-full bg-expense/15 flex items-center justify-center">
                <ArrowUpRight size={15} className="text-expense" />
              </div>
              <span className="text-xs text-sub">Spending</span>
            </div>
            <p className="text-base font-bold text-expense leading-tight">
              {currency} {fmt(allExpense)}
            </p>
            <p className="text-[10px] text-sub mt-1">รายจ่ายทั้งหมด</p>
          </div>
        </div>
      </div>

      {/* ── Transactions ── */}
      <div className="px-5">
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-semibold">Transactions</p>
          <button
            onClick={() => setActivePage("transactions")}
            className="text-xs text-sub flex items-center gap-0.5"
          >
            See all <ChevronRight size={12} />
          </button>
        </div>

        {recent.length === 0 ? (
          <div className="bg-card rounded-2xl border border-border py-12 flex flex-col items-center gap-3">
            <p className="text-4xl">💸</p>
            <p className="text-sub text-sm">ยังไม่มีรายการ</p>
            <button
              onClick={() => setShowModal(true)}
              className="mt-1 px-5 py-2 bg-green text-black text-xs font-semibold rounded-full"
            >
              เพิ่มรายการแรก
            </button>
          </div>
        ) : (
          <div className="bg-card rounded-2xl border border-border overflow-hidden divide-y divide-border">
            {recent.map((t) => {
              const cat = getCategoryById(t.category);
              return (
                <button
                  key={t.id}
                  onClick={() => { setEditing(t); setShowModal(true); }}
                  className="w-full flex items-center gap-3 px-4 py-3 hover:bg-card2 transition-colors text-left"
                >
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center text-lg flex-shrink-0"
                    style={{ backgroundColor: (cat?.color ?? "#444") + "22" }}
                  >
                    {cat?.icon ?? "💸"}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{cat?.label ?? t.category}</p>
                    <p className="text-[11px] text-sub">
                      {format(parseISO(t.date), "d MMM yyyy", { locale: th })}
                      {t.note ? ` · ${t.note}` : ""}
                    </p>
                  </div>
                  <span
                    className={`text-sm font-semibold flex-shrink-0 ${
                      t.type === "income" ? "text-green" : "text-expense"
                    }`}
                  >
                    {t.type === "income" ? "+" : "-"}
                    {currency}{t.amount.toLocaleString("th-TH")}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* FAB */}
      <button
        onClick={() => { setEditing(null); setShowModal(true); }}
        className="fixed bottom-20 right-4 w-14 h-14 bg-green text-black rounded-full flex items-center justify-center shadow-green active:scale-95 transition-transform z-30"
      >
        <Plus size={24} strokeWidth={2.5} />
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
