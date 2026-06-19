import { createBrowserRouter, Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/app-sidebar";
import { PagePlaceholder } from "@/components/page-placeholder";
import Overview from "@/pages/Overview";
import Transactions from "@/pages/Transactions";
import Budgets from "@/pages/Budgets";
import Recurring from "@/pages/Recurring";
import Goals from "@/pages/Goals";
import NetWorth from "@/pages/NetWorth";

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
      { path: "import", element: <PagePlaceholder title="Import" /> },
      { path: "insights", element: <PagePlaceholder title="AI Insights" /> },
      { path: "settings", element: <PagePlaceholder title="Settings" /> },
    ],
  },
]);
