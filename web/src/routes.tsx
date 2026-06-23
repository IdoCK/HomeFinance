import { createBrowserRouter, Outlet, useLocation } from "react-router-dom";
import { AppSidebar } from "@/components/app-sidebar";
import Overview from "@/pages/Overview";
import Transactions from "@/pages/Transactions";
import Analysis from "@/pages/Analysis";
import Budgets from "@/pages/Budgets";
import Recurring from "@/pages/Recurring";
import Goals from "@/pages/Goals";
import NetWorth from "@/pages/NetWorth";
import Settings from "@/pages/Settings";
import Insights from "@/pages/Insights";
import Import from "@/pages/Import";
import Events from "@/pages/Events";

function AppLayout() {
  const loc = useLocation();
  return (
    <div className="frosted-canvas" style={{ minHeight: "100vh", padding: 16 }}>
      {/* Rounded floating frame on the canvas (reference .frame). */}
      <div
        style={{
          display: "flex",
          minHeight: "calc(100vh - 32px)",
          background: "var(--fl-frame)",
          borderRadius: 22,
          overflow: "hidden",
          boxShadow: "0 24px 60px -34px rgba(22,24,29,.33)",
        }}
      >
        <AppSidebar />
        <main style={{ flex: 1, minWidth: 0, padding: "18px 24px 28px" }}>
          <div className="fl-page" key={loc.pathname}>
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "transactions", element: <Transactions /> },
      { path: "analysis", element: <Analysis /> },
      { path: "budgets", element: <Budgets /> },
      { path: "recurring", element: <Recurring /> },
      { path: "goals", element: <Goals /> },
      { path: "networth", element: <NetWorth /> },
      { path: "events", element: <Events /> },
      { path: "import", element: <Import /> },
      { path: "insights", element: <Insights /> },
      { path: "settings", element: <Settings /> },
    ],
  },
]);
