import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({ plugins: [react()], build: { outDir: "dist", emptyOutDir: true, manifest: true }, test: { environment: "happy-dom", setupFiles: ["./src/test/setup.ts"], exclude: ["e2e/**", "node_modules/**"] } });
