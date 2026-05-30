import { create } from "zustand";
import { persist } from "zustand/middleware";
import { Transaction, Page } from "../types";

interface AppState {
  transactions: Transaction[];
  activePage: Page;
  currency: string;
  addTransaction: (t: Omit<Transaction, "id" | "createdAt">) => void;
  updateTransaction: (id: string, t: Partial<Omit<Transaction, "id" | "createdAt">>) => void;
  deleteTransaction: (id: string) => void;
  setActivePage: (p: Page) => void;
  setCurrency: (c: string) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      transactions: [],
      activePage: "home",
      currency: "฿",

      addTransaction: (t) =>
        set((s) => ({
          transactions: [
            {
              ...t,
              id: crypto.randomUUID(),
              createdAt: new Date().toISOString(),
            },
            ...s.transactions,
          ],
        })),

      updateTransaction: (id, t) =>
        set((s) => ({
          transactions: s.transactions.map((tx) =>
            tx.id === id ? { ...tx, ...t } : tx
          ),
        })),

      deleteTransaction: (id) =>
        set((s) => ({
          transactions: s.transactions.filter((tx) => tx.id !== id),
        })),

      setActivePage: (p) => set({ activePage: p }),
      setCurrency: (c) => set({ currency: c }),
    }),
    { name: "expense-tracker-store" }
  )
);
