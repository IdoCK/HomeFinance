import { RouterProvider } from "react-router-dom";
import { PersonaProvider } from "@/lib/persona";
import { ThemeProvider } from "@/lib/theme";
import { router } from "@/routes";

export default function App() {
  return (
    <ThemeProvider>
      <PersonaProvider>
        <RouterProvider router={router} />
      </PersonaProvider>
    </ThemeProvider>
  );
}
