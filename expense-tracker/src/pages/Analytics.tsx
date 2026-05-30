import { useMemo, useState } from "react";
import {
  PieChart, Pie, Cell, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip,
} from "recharts";
import { useStore } from "../store";
import { getCategoryById } from "../store/categories";
import {
  startOfMonth, endOfMonth, parseISO, isWithinInterval,
  subMonths, format,
} from "date-fns";
import { th } from "date-fns/locale";
import { ArrowDownLeft, ArrowUpRight } from "lucide-react";

export default function Analytics() {
  const { transactions, currency } = useStore();
  const [tab, setTab] = useState<"expense" | "income">("expense");
  const now = new Date();

  const barData = useMemo(() => {
    return Array.from({ length: 6 }, (_, i) => {
      const d = subMonths(now, 5 - i);
      const start = startOfMonth(d);
      const end   = endOfMonth(d);
      const txs   = transactions.filter((t) =>
        isWithinInterval(parseISO(t.date), { start, end })
      );
      return {
        month:   format(d, "MMM", { locale: th }),
        income:  txs.filter((t) => t.type === "income").reduce((s, t)  => s + t.amount, 0),
        expense: txs.filter((t) => t.type === "expense").reduce((s, t) => s + t.amount, 0),
      };
    });
  }, [transactions]);

  const monthTx = useMemo(() => {
    const start = startOfMonth(now);
    const end   = endOfMonth(now);
    return transactions.filter((t) =>
      t.type === tab && isWithinInterval(parseISO(t.date), { start, end })
    );
  }, [transactions, tab]);

  const pieData = useMemo(() => {
    const map = new Map<string, number>();
    monthTx.forEach((t) => map.set(t.category, (map.get(t.category) ?? 0) + t.amount));
    return Array.from(map.entries())
      .map(([cat, value]) => ({
        cat, value,
        label: getCategoryById(cat)?.label ?? cat,
        icon:  getCategoryById(cat)?.icon  ?? "💸",
        color: getCategoryById(cat)?.color ?? "#444",
      }))
      .sort((a, b) => b.value - a.value);
  }, [monthTx]);

  const total = pieData.reduce((s, d) => s + d.value, 0);

  const totalIncome  = useMemo(() => transactions.filter((t) => t.type === "income").reduce((s, t) => s + t.amount, 0),  [transactions]);
  const totalExpense = useMemo(() => transactions.filter((t) => t.type === "expense").reduce((s, t) => s + t.amount, 0), [transactions]);

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-hide bg-bg pb-28">

      {/* Header */}
      <div className="px-5 pt-12 pb-5">
        <h1 className="text-xl font-bold">Analytics</h1>
        <p className="text-xs text-sub mt-0.5">ภาพรวมการเงินของคุณ</p>
      </div>

      {/* Summary pills */}
      <div className="px-5 grid grid-cols-2 gap-3 mb-6">
        <div className="bg-green/10 border border-green/25 rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <ArrowDownLeft size={14} className="text-green" />
            <span className="text-xs text-green/80 font-medium">รายรับทั้งหมด</span>
          </div>
          <p className="text-lg font-bold text-green">
            {currency}{totalIncome.toLocaleString("th-TH")}
          </p>
        </div>
        <div className="bg-expense/10 border border-expense/25 rounded-2xl p-4">
          <div className="flex items-center gap-2 mb-2">
            <ArrowUpRight size={14} className="text-expense" />
            <span className="text-xs text-expense/80 font-medium">รายจ่ายทั้งหมด</span>
          </div>
          <p className="text-lg font-bold text-expense">
            {currency}{totalExpense.toLocaleString("th-TH")}
          </p>
        </div>
      </div>

      {/* Bar chart */}
      <div className="px-5 mb-6">
        <div className="bg-card border border-border rounded-2xl p-4">
          <p className="text-sm font-semibold mb-4">6 เดือนล่าสุด</p>
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={barData} barGap={3} barSize={12}>
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#888" }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.03)" }}
                contentStyle={{ background: "#1C1C1C", border: "1px solid #2A2A2A", borderRadius: 10, fontSize: 12 }}
                formatter={(v: number) => [`${currency}${v.toLocaleString("th-TH")}`, ""]}
              />
              <Bar dataKey="income"  fill="#3DED97" radius={[4,4,0,0]} />
              <Bar dataKey="expense" fill="#FF6B6B" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-5 mt-3">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-green" />
              <span className="text-[11px] text-sub">รายรับ</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-expense" />
              <span className="text-[11px] text-sub">รายจ่าย</span>
            </div>
          </div>
        </div>
      </div>

      {/* Pie */}
      <div className="px-5">
        <div className="bg-card border border-border rounded-2xl p-4">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-semibold">หมวดหมู่เดือนนี้</p>
            <div className="flex bg-bg border border-border rounded-xl p-0.5">
              {(["expense", "income"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                    tab === t
                      ? t === "expense" ? "bg-expense text-white" : "bg-green text-black"
                      : "text-sub"
                  }`}
                >
                  {t === "expense" ? "รายจ่าย" : "รายรับ"}
                </button>
              ))}
            </div>
          </div>

          {pieData.length === 0 ? (
            <div className="py-10 text-center text-sub text-sm">ยังไม่มีข้อมูลเดือนนี้</div>
          ) : (
            <>
              <div className="flex items-center gap-4 mb-5">
                <ResponsiveContainer width={120} height={120}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={35} outerRadius={56} paddingAngle={2} dataKey="value">
                      {pieData.map((d) => <Cell key={d.cat} fill={d.color} />)}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex-1 flex flex-col gap-1.5 min-w-0">
                  {pieData.slice(0, 5).map((d) => (
                    <div key={d.cat} className="flex items-center gap-2 min-w-0">
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: d.color }} />
                      <span className="text-xs truncate flex-1 text-sub">{d.label}</span>
                      <span className="text-xs font-medium flex-shrink-0">
                        {total > 0 ? Math.round((d.value / total) * 100) : 0}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex flex-col gap-3">
                {pieData.map((d) => (
                  <div key={d.cat} className="flex items-center gap-3">
                    <span className="text-base">{d.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between mb-1">
                        <span className="text-xs">{d.label}</span>
                        <span className="text-xs font-semibold">{currency}{d.value.toLocaleString("th-TH")}</span>
                      </div>
                      <div className="h-1 bg-bg rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{ width: `${total > 0 ? (d.value / total) * 100 : 0}%`, background: d.color }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
