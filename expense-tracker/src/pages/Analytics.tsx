import { useMemo, useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
} from "recharts";
import { useStore } from "../store";
import { getCategoryById } from "../store/categories";
import {
  startOfMonth, endOfMonth, parseISO, isWithinInterval,
  subMonths, format,
} from "date-fns";
import { th } from "date-fns/locale";

export default function Analytics() {
  const { transactions, currency } = useStore();
  const [tab, setTab] = useState<"expense" | "income">("expense");

  const now = new Date();

  // Last 6 months bar data
  const barData = useMemo(() => {
    return Array.from({ length: 6 }, (_, i) => {
      const d = subMonths(now, 5 - i);
      const start = startOfMonth(d);
      const end = endOfMonth(d);
      const txs = transactions.filter((t) =>
        isWithinInterval(parseISO(t.date), { start, end })
      );
      return {
        month: format(d, "MMM", { locale: th }),
        income: txs.filter((t) => t.type === "income").reduce((s, t) => s + t.amount, 0),
        expense: txs.filter((t) => t.type === "expense").reduce((s, t) => s + t.amount, 0),
      };
    });
  }, [transactions]);

  // Pie data this month
  const monthTx = useMemo(() => {
    const start = startOfMonth(now);
    const end = endOfMonth(now);
    return transactions.filter((t) =>
      t.type === tab &&
      isWithinInterval(parseISO(t.date), { start, end })
    );
  }, [transactions, tab]);

  const pieData = useMemo(() => {
    const map = new Map<string, number>();
    monthTx.forEach((t) => {
      map.set(t.category, (map.get(t.category) ?? 0) + t.amount);
    });
    return Array.from(map.entries())
      .map(([cat, value]) => ({
        cat,
        value,
        label: getCategoryById(cat)?.label ?? cat,
        icon: getCategoryById(cat)?.icon ?? "💸",
        color: getCategoryById(cat)?.color ?? "#6b7280",
      }))
      .sort((a, b) => b.value - a.value);
  }, [monthTx]);

  const total = pieData.reduce((s, d) => s + d.value, 0);

  const fmt = (n: number) =>
    n >= 1000
      ? (n / 1000).toFixed(1) + "k"
      : n.toFixed(0);

  return (
    <div className="flex flex-col h-full overflow-y-auto scrollbar-hide pb-28">
      <div className="px-5 pt-12 pb-4">
        <h1 className="text-xl font-bold mb-1">วิเคราะห์</h1>
        <p className="text-xs text-muted">ภาพรวม 6 เดือนล่าสุด</p>
      </div>

      {/* Bar chart */}
      <div className="px-5 mb-6">
        <div className="bg-card rounded-2xl p-4">
          <p className="text-sm font-medium mb-3">รายรับ / รายจ่าย</p>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={barData} barGap={2} barSize={14}>
              <XAxis dataKey="month" tick={{ fontSize: 10, fill: "#6b7280" }} axisLine={false} tickLine={false} />
              <YAxis hide />
              <Tooltip
                contentStyle={{ background: "#1e1e2e", border: "none", borderRadius: 8, fontSize: 12 }}
                formatter={(v: number) => [`${currency}${v.toLocaleString("th-TH")}`, ""]}
              />
              <Bar dataKey="income" fill="#10b981" radius={[4, 4, 0, 0]} />
              <Bar dataKey="expense" fill="#ef4444" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex gap-4 mt-2">
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-income" />
              <span className="text-xs text-muted">รายรับ</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-expense" />
              <span className="text-xs text-muted">รายจ่าย</span>
            </div>
          </div>
        </div>
      </div>

      {/* Pie chart */}
      <div className="px-5">
        <div className="bg-card rounded-2xl p-4">
          <div className="flex items-center justify-between mb-4">
            <p className="text-sm font-medium">หมวดหมู่เดือนนี้</p>
            <div className="flex bg-bg rounded-lg p-0.5">
              {(["expense", "income"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                    tab === t
                      ? t === "expense" ? "bg-expense text-white" : "bg-income text-white"
                      : "text-muted"
                  }`}
                >
                  {t === "expense" ? "รายจ่าย" : "รายรับ"}
                </button>
              ))}
            </div>
          </div>

          {pieData.length === 0 ? (
            <div className="py-8 text-center text-white/20 text-sm">ยังไม่มีข้อมูล</div>
          ) : (
            <>
              <div className="flex items-center gap-4">
                <ResponsiveContainer width={130} height={130}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={38}
                      outerRadius={60}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {pieData.map((d) => (
                        <Cell key={d.cat} fill={d.color} />
                      ))}
                    </Pie>
                  </PieChart>
                </ResponsiveContainer>

                <div className="flex-1 flex flex-col gap-2 min-w-0">
                  {pieData.slice(0, 5).map((d) => (
                    <div key={d.cat} className="flex items-center gap-2 min-w-0">
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: d.color }} />
                      <span className="text-xs truncate flex-1">{d.label}</span>
                      <span className="text-xs text-muted flex-shrink-0">
                        {total > 0 ? Math.round((d.value / total) * 100) : 0}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4 flex flex-col gap-2">
                {pieData.map((d) => (
                  <div key={d.cat} className="flex items-center gap-3">
                    <span className="text-base">{d.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between mb-1">
                        <span className="text-xs">{d.label}</span>
                        <span className="text-xs font-medium">
                          {currency}{d.value.toLocaleString("th-TH")}
                        </span>
                      </div>
                      <div className="h-1.5 bg-bg rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${total > 0 ? (d.value / total) * 100 : 0}%`,
                            background: d.color,
                          }}
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
