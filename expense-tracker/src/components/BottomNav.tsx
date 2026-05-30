import { Home, List, BarChart2, Settings, type LucideIcon } from "lucide-react";
import { useStore } from "../store";
import { Page } from "../types";

const tabs: { id: Page; label: string; Icon: LucideIcon }[] = [
  { id: "home",         label: "Home",      Icon: Home },
  { id: "transactions", label: "History",   Icon: List },
  { id: "analytics",   label: "Analytics", Icon: BarChart2 },
  { id: "settings",    label: "Settings",  Icon: Settings },
];

export default function BottomNav() {
  const { activePage, setActivePage } = useStore();

  return (
    <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] z-40">
      <div className="mx-3 mb-3 bg-surface border border-border rounded-2xl flex overflow-hidden">
        {tabs.map(({ id, label, Icon }) => {
          const active = activePage === id;
          return (
            <button
              key={id}
              onClick={() => setActivePage(id)}
              className={`flex-1 flex flex-col items-center gap-1 py-3 transition-colors ${
                active ? "text-green" : "text-muted hover:text-sub"
              }`}
            >
              <Icon size={20} strokeWidth={active ? 2.2 : 1.8} />
              <span className={`text-[10px] font-medium ${active ? "text-green" : "text-muted"}`}>
                {label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
