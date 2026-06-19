import { createBrowserRouter, Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/app-sidebar";
import Overview from "@/pages/Overview";
import Transactions from "@/pages/Transactions";
import Budgets from "@/pages/Budgets";
import Recurring from "@/pages/Recurring";
import Goals from "@/pages/Goals";
import NetWorth from "@/pages/NetWorth";
import Settings from "@/pages/Settings";
import Insights from "@/pages/Insights";
import Import from "@/pages/Import";

function AppLayout() {
  return (
    <div className="frosted-canvas" style={{ display: "flex", minHeight: "100vh" }}>
      <AppSidebar />
      <main style={{ flex: 1, padding: 24 }}><Outlet /></main>
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
      { path: "budgets", element: <Budgets /> },
      { path: "recurring", element: <Recurring /> },
      { path: "goals", element: <Goals /> },
      { path: "networth", element: <NetWorth /> },
      { path: "import", element: <Import /> },
      { path: "insights", element: <Insights /> },
      { path: "settings", element: <Settings /> },
    ],
  },
]);
