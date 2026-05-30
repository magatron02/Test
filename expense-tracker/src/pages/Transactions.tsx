import { useState, useMemo } from "react";
import { Plus, Search, Filter } from "lucide-react";
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
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [filter, setFilter] = useState<FilterType>("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    return transactions.filter((t) => {
      if (filter !== "all" && t.type !== filter) return false;
      if (search && !t.note.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [transactions, filter, search]);

  // Group by date
  const grouped = useMemo(() => {
    const map = new Map<string, Transaction[]>();
    filtered.forEach((t) => {
      const key = t.date;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(t);
    });
    return Array.from(map.entries()).sort(([a], [b]) => b.localeCompare(a));
  }, [filtered]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-5 pt-12 pb-4 bg-surface/80 backdrop-blur sticky top-0 z-10">
        <h1 className="text-xl font-bold mb-4">รายการทั้งหมด</h1>

        {/* Search */}
        <div className="flex items-center gap-2 bg-bg rounded-xl px-3 py-2 mb-3">
          <Search size={16} className="text-muted flex-shrink-0" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="ค้นหารายการ..."
            className="flex-1 bg-transparent text-sm focus:outline-none placeholder-white/20"
          />
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2">
          {(["all", "income", "expense"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-1.5 rounded-full text-xs font-medium transition-colors ${
                filter === f
                  ? f === "income"
                    ? "bg-income text-white"
                    : f === "expense"
                    ? "bg-expense text-white"
                    : "bg-primary text-white"
                  : "bg-bg text-muted"
              }`}
            >
              {f === "all" ? "ทั้งหมด" : f === "income" ? "รายรับ" : "รายจ่าย"}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto scrollbar-hide px-5 pb-28">
        {grouped.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Filter size={40} className="text-white/10 mb-3" />
            <p className="text-white/30 text-sm">ไม่พบรายการ</p>
          </div>
        ) : (
          grouped.map(([date, txs]) => (
            <div key={date} className="mb-4">
              <p className="text-xs text-muted mb-2 px-1">
                {format(parseISO(date), "EEEE d MMMM yyyy", { locale: th })}
              </p>
              <div className="flex flex-col gap-2">
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
