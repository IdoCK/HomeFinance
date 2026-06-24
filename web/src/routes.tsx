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
import Studio from "@/pages/Studio";
import Guide from "@/pages/Guide";

function AppLayout() {
  const loc = useLocation();
  return (
    // Full-bleed shell: the app fills the window (no floating card frame). The
    // sidebar and the main content are independent scroll regions, so scrolling
    // a long page never moves the nav rail and vice-versa.
    <div className="frosted-canvas" style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <AppSidebar />
      <main style={{ flex: 1, minWidth: 0, height: "100vh", overflowY: "auto", padding: "18px 24px 28px" }}>
        {/* minWidth:0 lets wide children (tables) shrink + scroll inside instead
            of forcing the page wider than the window. maxWidth keeps line lengths
            sane on very wide monitors. */}
        <div className="fl-page" key={loc.pathname} style={{ minWidth: 0, maxWidth: 1200, margin: "0 auto" }}>
          <Outlet />
        </div>
      </main>
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
      { path: "studio", element: <Studio /> },
      { path: "import", element: <Import /> },
      { path: "insights", element: <Insights /> },
      { path: "settings", element: <Settings /> },
      { path: "guide", element: <Guide /> },
    ],
  },
]);
