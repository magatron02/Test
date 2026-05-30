import { useState, useMemo } from "react";
import { Plus, Search } from "lucide-react";
import { useStore } from "../store";
import TransactionItem from "../components/TransactionItem";
import TransactionModal from "../components/TransactionModal";
import { Transaction, TransactionType } from "../types";
import { format, parseISO } from "date-fns";
import { th } from "date-fns/locale";

type FilterType = "all" | TransactionType;

export default function Transactions() {
  const { transactions } = useStore();
  const [showModal, setShowModal] = useState(false);
  const [editing,   setEditing]   = useState<Transaction | null>(null);
  const [filter,    setFilter]    = useState<FilterType>("all");
  const [search,    setSearch]    = useState("");

  const filtered = useMemo(() => {
    return transactions.filter((t) => {
      if (filter !== "all" && t.type !== filter) return false;
      if (search) {
        const q = search.toLowerCase();
        return t.note.toLowerCase().includes(q) || t.category.includes(q);
      }
      return true;
    });
  }, [transactions, filter, search]);

  const grouped = useMemo(() => {
    const map = new Map<string, Transaction[]>();
    filtered.forEach((t) => {
      if (!map.has(t.date)) map.set(t.date, []);
      map.get(t.date)!.push(t);
    });
    return Array.from(map.entries()).sort(([a], [b]) => b.localeCompare(a));
  }, [filtered]);

  const FILTERS = [
    { id: "all" as FilterType,     label: "ทั้งหมด" },
    { id: "income" as FilterType,  label: "รายรับ" },
    { id: "expense" as FilterType, label: "รายจ่าย" },
  ];

  return (
    <div className="flex flex-col h-full bg-bg">
      {/* Sticky header */}
      <div className="px-5 pt-12 pb-4 bg-bg sticky top-0 z-10">
        <h1 className="text-xl font-bold mb-4">Transaction History</h1>

        <div className="flex items-center gap-2 bg-surface border border-border rounded-2xl px-4 py-3 mb-4">
          <Search size={15} className="text-muted flex-shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="ค้นหารายการ..."
            className="flex-1 bg-transparent text-sm focus:outline-none placeholder-muted"
          />
        </div>

        <div className="flex gap-2">
          {FILTERS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setFilter(id)}
              className={`px-4 py-1.5 rounded-full text-xs font-semibold transition-all ${
                filter === id
                  ? id === "income"
                    ? "bg-green text-black"
                    : id === "expense"
                    ? "bg-expense text-white"
                    : "bg-white text-black"
                  : "bg-surface border border-border text-sub"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 pb-28">
        {grouped.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <p className="text-5xl mb-3">🔍</p>
            <p className="text-sub text-sm">ไม่พบรายการ</p>
          </div>
        ) : (
          grouped.map(([date, txs]) => (
            <div key={date} className="mb-5">
              <div className="flex items-center gap-3 mb-2">
                <p className="text-[11px] text-sub whitespace-nowrap">
                  {format(parseISO(date), "EEEE d MMMM yyyy", { locale: th })}
                </p>
                <div className="flex-1 h-px bg-border" />
                <p className="text-[11px] text-sub whitespace-nowrap">
                  {txs.length} รายการ
                </p>
              </div>
              <div className="bg-card border border-border rounded-2xl overflow-hidden divide-y divide-border">
                {txs.map((t) => (
                  <TransactionItem
                    key={t.id}
                    transaction={t}
                    onEdit={(tx) => { setEditing(tx); setShowModal(true); }}
                  />
                ))}
              </div>
            </div>
          ))
        )}
      </div>

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
