import { Home, List, BarChart2, Settings, type LucideIcon } from "lucide-react";
import { useStore } from "../store";
import { Page } from "../types";

const tabs: { id: Page; label: string; Icon: LucideIcon }[] = [
  { id: "home",         label: "หน้าหลัก",  Icon: Home },
  { id: "transactions", label: "รายการ",    Icon: List },
  { id: "analytics",   label: "วิเคราะห์", Icon: BarChart2 },
  { id: "settings",    label: "ตั้งค่า",   Icon: Settings },
];

export default function BottomNav() {
  const { activePage, setActivePage } = useStore();

  return (
    <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] bg-surface border-t border-white/5 z-40 safe-area-bottom">
      <div className="flex">
        {tabs.map(({ id, label, Icon }) => {
          const active = activePage === id;
          return (
            <button
              key={id}
              onClick={() => setActivePage(id)}
              className="flex-1 flex flex-col items-center gap-0.5 py-2.5 transition-colors"
            >
              <Icon
                size={22}
                className={active ? "text-primary" : "text-muted"}
              />
              <span className={`text-[10px] font-medium ${active ? "text-primary" : "text-muted"}`}>
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
