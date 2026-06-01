import { useStore } from "./store";
import BottomNav from "./components/BottomNav";
import Home from "./pages/Home";
import Transactions from "./pages/Transactions";
import Analytics from "./pages/Analytics";
import Settings from "./pages/Settings";

export default function App() {
  const { activePage } = useStore();

  const renderPage = () => {
    switch (activePage) {
      case "home":         return <Home />;
      case "transactions": return <Transactions />;
      case "analytics":    return <Analytics />;
      case "settings":     return <Settings />;
    }
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg">
      <div className="flex-1 overflow-hidden page-enter">
        {renderPage()}
      </div>
      <BottomNav />
    </div>
  );
}
