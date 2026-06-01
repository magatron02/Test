export type TransactionType = "income" | "expense";

export interface Transaction {
  id: string;
  type: TransactionType;
  amount: number;
  category: string;
  note: string;
  date: string;
  createdAt: string;
}

export type Page = "home" | "transactions" | "analytics" | "settings";

export interface Category {
  id: string;
  label: string;
  icon: string;
  type: TransactionType | "both";
  color: string;
}
