import { defineConfig } from "vitest/config";
import type { Plugin } from "vite";

// A strict Content-Security-Policy for the built page: scripts, styles and images from the same
// origin only, no inline script, no other origin for any request, no plugins, no other base or
// form target. The dev server needs inline code for hot reload, so it is added at build time.
const CSP =
  "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; " +
  "object-src 'none'; worker-src 'none'; base-uri 'self'; form-action 'self'";

const contentSecurityPolicy: Plugin = {
  name: "ug-content-security-policy",
  apply: "build",
  transformIndexHtml: {
    order: "post",
    handler: (html) => html.replace("<head>", `<head>\n    <meta http-equiv="Content-Security-Policy" content="${CSP}" />`),
  },
};

// Relative base: the built shell works offline, from any path, with no server-side rewriting.
export default defineConfig({
  base: "./",
  plugins: [contentSecurityPolicy],
  build: {
    target: "es2022",
    sourcemap: false,
    outDir: "dist",
    emptyOutDir: true,
    // The preload polyfill calls fetch(); modern browsers do not need it, and the shell makes no request.
    modulePreload: { polyfill: false },
    // Third-party code goes to vendor-* chunks. The offline check reads app code strictly and, in
    // vendor chunks only, tolerates the NAME of a network API (deck.gl's loaders carry fetch and a
    // worker loader that the app never calls); URLs are still refused everywhere, and the CSP
    // (connect-src 'self', worker-src 'none') plus the Playwright run prove no request is made.
    rolldownOptions: { output: { codeSplitting: { groups: [{ name: "vendor", test: /node_modules/ }] } } },
  },
  server: { host: "127.0.0.1" },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}", "scripts/**/*.test.mjs"],
    css: false,
  },
});
