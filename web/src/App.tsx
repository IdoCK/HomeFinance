import { RouterProvider } from "react-router-dom";
import { PersonaProvider } from "@/lib/persona";
import { ThemeProvider } from "@/lib/theme";
import { CurrencyProvider } from "@/lib/currency";
import { router } from "@/routes";

export default function App() {
  return (
    <ThemeProvider>
      <PersonaProvider>
        <CurrencyProvider>
          <RouterProvider router={router} />
        </CurrencyProvider>
      </PersonaProvider>
    </ThemeProvider>
  );
}
