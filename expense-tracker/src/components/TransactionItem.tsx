import { Transaction } from "../types";
import { getCategoryById } from "../store/categories";
import { useStore } from "../store";
import { format, parseISO } from "date-fns";
import { th } from "date-fns/locale";
import { Trash2, Pencil } from "lucide-react";

interface Props {
  transaction: Transaction;
  onEdit: (t: Transaction) => void;
}

export default function TransactionItem({ transaction, onEdit }: Props) {
  const { deleteTransaction, currency } = useStore();
  const cat = getCategoryById(transaction.category);

  return (
    <div className="flex items-center gap-3 px-4 py-3 hover:bg-card2 transition-colors">
      <div
        className="w-10 h-10 rounded-full flex items-center justify-center text-lg flex-shrink-0"
        style={{ backgroundColor: (cat?.color ?? "#444") + "22" }}
      >
        {cat?.icon ?? "💸"}
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{cat?.label ?? transaction.category}</p>
        <p className="text-[11px] text-sub">
          {format(parseISO(transaction.date), "d MMM yyyy", { locale: th })}
          {transaction.note ? ` · ${transaction.note}` : ""}
        </p>
      </div>

      <div className="flex items-center gap-1.5 flex-shrink-0">
        <span
          className={`text-sm font-semibold ${
            transaction.type === "income" ? "text-green" : "text-expense"
          }`}
        >
          {transaction.type === "income" ? "+" : "-"}
          {currency}{transaction.amount.toLocaleString("th-TH")}
        </span>
        <button
          onClick={() => onEdit(transaction)}
          className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-white/10 text-muted transition-colors"
        >
          <Pencil size={12} />
        </button>
        <button
          onClick={() => deleteTransaction(transaction.id)}
          className="w-7 h-7 rounded-lg flex items-center justify-center hover:bg-expense/20 text-muted hover:text-expense transition-colors"
        >
          <Trash2 size={12} />
        </button>
      </div>
    </div>
  );
}
