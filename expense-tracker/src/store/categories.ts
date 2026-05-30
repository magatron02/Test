import { Category } from "../types";

export const CATEGORIES: Category[] = [
  { id: "salary",      label: "เงินเดือน",   icon: "💼", type: "income",  color: "#10b981" },
  { id: "business",    label: "ธุรกิจ",       icon: "🏢", type: "income",  color: "#06b6d4" },
  { id: "investment",  label: "การลงทุน",    icon: "📈", type: "income",  color: "#8b5cf6" },
  { id: "gift_in",     label: "ของขวัญ",     icon: "🎁", type: "income",  color: "#f59e0b" },
  { id: "other_in",    label: "รายรับอื่นๆ", icon: "💰", type: "income",  color: "#84cc16" },

  { id: "food",        label: "อาหาร",        icon: "🍜", type: "expense", color: "#ef4444" },
  { id: "transport",   label: "เดินทาง",      icon: "🚗", type: "expense", color: "#f97316" },
  { id: "shopping",    label: "ช้อปปิ้ง",     icon: "🛍️", type: "expense", color: "#ec4899" },
  { id: "entertainment", label: "บันเทิง",   icon: "🎮", type: "expense", color: "#a855f7" },
  { id: "health",      label: "สุขภาพ",       icon: "🏥", type: "expense", color: "#06b6d4" },
  { id: "housing",     label: "ที่พัก/บ้าน",  icon: "🏠", type: "expense", color: "#3b82f6" },
  { id: "education",   label: "การศึกษา",    icon: "📚", type: "expense", color: "#14b8a6" },
  { id: "bills",       label: "ค่าบริการ",   icon: "📱", type: "expense", color: "#64748b" },
  { id: "other_out",   label: "รายจ่ายอื่นๆ", icon: "💸", type: "expense", color: "#94a3b8" },
];

export const getCategoryById = (id: string) =>
  CATEGORIES.find((c) => c.id === id);

export const getCategoriesByType = (type: "income" | "expense") =>
  CATEGORIES.filter((c) => c.type === type || c.type === "both");
