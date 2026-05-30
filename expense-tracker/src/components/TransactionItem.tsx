import { Trash2, Pencil } from "lucide-react";
import { Transaction } from "../types";
import { getCategoryById } from "../store/categories";
import { useStore } from "../store";
import { format, parseISO } from "date-fns";
import { th } from "date-fns/locale";

interface Props {
  transaction: Transaction;
  onEdit: (t: Transaction) => void;
}

export default function TransactionItem({ transaction, onEdit }: Props) {
  const { deleteTransaction, currency } = useStore();
  const cat = getCategoryById(transaction.category);

  return (
    <div className="flex items-center gap-3 bg-card rounded-xl px-4 py-3">
      {/* Icon */}
      <div
        className="w-11 h-11 rounded-full flex items-center justify-center text-xl flex-shrink-0"
        style={{ backgroundColor: (cat?.color ?? "#6b7280") + "22" }}
      >
        {cat?.icon ?? "💸"}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="font-medium text-sm truncate">{cat?.label ?? transaction.category}</p>
        <p className="text-xs text-muted truncate">
          {transaction.note || format(parseISO(transaction.date), "d MMM yyyy", { locale: th })}
        </p>
        {transaction.note && (
          <p className="text-[10px] text-muted/60">
            {format(parseISO(transaction.date), "d MMM yyyy", { locale: th })}
          </p>
        )}
      </div>

      {/* Amount */}
      <div className="flex items-center gap-2 flex-shrink-0">
        <span
          className={`font-semibold text-sm ${
            transaction.type === "income" ? "text-income" : "text-expense"
          }`}
        >
          {transaction.type === "income" ? "+" : "-"}
          {currency}{transaction.amount.toLocaleString("th-TH", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}
        </span>

        <button
          onClick={() => onEdit(transaction)}
          className="p-1.5 rounded-lg hover:bg-white/10 text-muted transition-colors"
        >
          <Pencil size={13} />
        </button>
        <button
          onClick={() => deleteTransaction(transaction.id)}
          className="p-1.5 rounded-lg hover:bg-expense/20 text-muted hover:text-expense transition-colors"
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  );
}
