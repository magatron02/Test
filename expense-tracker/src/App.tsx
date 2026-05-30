import { useStore } from "./store";
import BottomNav from "./components/BottomNav";
import Home from "./pages/Home";
import Transactions from "./pages/Transactions";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";
import { Page } from "./types";

const PAGES: Record<Page, React.ReactNode> = {
  home: <Home />,
  transactions: <Transactions />,
  analytics: <Analytics />,
  settings: <Settings />,
};

export default function App() {
  const { activePage } = useStore();

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg">
      <div className="flex-1 overflow-hidden page-enter">
        {PAGES[activePage]}
      </div>
      <BottomNav />
    </div>
  );
}
