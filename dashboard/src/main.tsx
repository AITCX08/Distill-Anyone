import { StrictMode } from "react"; import { createRoot } from "react-dom/client"; import { FluentProvider } from "@fluentui/react-components"; import { App } from "./app/App"; import { cyberTheme } from "./theme/cyberTheme"; import "./theme/global.css";
createRoot(document.getElementById("root")!).render(<StrictMode><FluentProvider theme={cyberTheme}><App /></FluentProvider></StrictMode>);
