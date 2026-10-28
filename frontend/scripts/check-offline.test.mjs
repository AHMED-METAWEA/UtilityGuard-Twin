// The offline check must catch the ways found in review of the first version (and more).
import { describe, expect, it } from "vitest";

import { readFileSync } from "node:fs";

import { cssReferences, htmlReferences, isScannedSource, jsReferences, leavesTheApplication } from "./offline-lib.mjs";

describe("leavesTheApplication", () => {
  it.each([
    "https://example.invalid/x", "http://example.invalid", "//example.invalid/pixel", " //example.invalid ",
    "ws://example.invalid", "wss://example.invalid", "ftp://example.invalid", "javascript:alert(1)",
    "data:text/html,<p>", "HTTPS://EXAMPLE.INVALID", "'//example.invalid/x'",
  ])("is true for %s", (value) => expect(leavesTheApplication(value)).toBe(true));
  it.each(["", "./a.js", "/assets/a.js", "assets/a.css", "#clip", "../x.png", "http://localhost:5173/x", "//127.0.0.1/x", "mailto:a@b"])(
    "is false for %j", (value) => expect(leavesTheApplication(value)).toBe(false));
});

describe("css", () => {
  it.each([
    "a{background:url(//example.invalid/pixel)}", "@import url(https://example.invalid/a.css);",
    '@import "//example.invalid/a.css";', "@import 'https://example.invalid/a.css';",
    'a{background:url("https://example.invalid/x.png")}', "a{background:URL( //example.invalid/x )}",
    "a{background:url(data:image/png;base64,AAAA)}",
  ])("flags %s", (css) => expect(cssReferences(css).length).toBeGreaterThan(0));
  it.each(["a{background:url(#clip)}", "a{background:url(./a.png)}", "/* url(https://example.invalid) */ a{color:red}", "@import './b.css';"])(
    "passes %s", (css) => expect(cssReferences(css)).toEqual([]));
});

describe("html", () => {
  it.each([
    '<link rel="stylesheet" href="https://example.invalid/a.css">', '<link rel="preconnect" href="https://example.invalid">',
    '<link rel="dns-prefetch" href="//example.invalid">', '<script src="//example.invalid/a.js"></script>',
    '<img src="x" srcset="https://example.invalid/a.png 2x">', '<img srcset="a.png 1x, //example.invalid/b.png 2x">',
    '<svg><use xlink:href="https://example.invalid/s.svg#a"></use></svg>', '<meta http-equiv="refresh" content="0; url=https://example.invalid">',
    '<a href="javascript:alert(1)">x</a>', '<form action="https://example.invalid/post"></form>',
    '<div style="background:url(//example.invalid/x)"></div>', '<style>@import url(https://example.invalid/a.css);</style>',
    '<script>fetch("/api")</script>', "<iframe src='https://example.invalid'></iframe>", '<video poster="//example.invalid/p.png"></video>',
    '<script>import("//example.invalid/a.js")</script>', '<link rel=stylesheet href=https://example.invalid/a.css>',
  ])("flags %s", (html) => expect(htmlReferences(html).length).toBeGreaterThan(0));
  it.each([
    '<script type="module" src="./assets/a.js"></script>', '<link rel="stylesheet" href="./assets/a.css">',
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><use xlink:href="#a"></use></svg>',
    "<!-- <script src=\"https://example.invalid/a.js\"></script> --><p>ok</p>", '<a href="#/health">x</a>',
  ])("passes %s", (html) => expect(htmlReferences(html)).toEqual([]));
});

describe("javascript", () => {
  it.each([
    'fetch("/x")', "globalThis['fetch']('/x')", 'window["fetch"]("/x")', "new XMLHttpRequest()", "new WebSocket('wss://x')",
    "navigator.sendBeacon('/x')", "new EventSource('/x')", "importScripts('/x.js')", "navigator.serviceWorker.register('/sw.js')",
    'import("//example.invalid/a.js")', 'import("https://example.invalid/a.js")', 'const u = "https://example.invalid/a"',
    'const u = "//example.invalid/a"', "const u = `//example.invalid/a`",
  ])("flags %s", (js) => expect(jsReferences(js).length).toBeGreaterThan(0));
  it.each([
    'import("./chunk.js")', 'const ns = "http://www.w3.org/2000/svg"', 'const s = "http://localhost:5173/"', "const a = 1; // comment",
    'const t = "prefetch"',
  ])("passes %s", (js) => expect(jsReferences(js)).toEqual([]));
  it("allows only the exact React message string in a bundle", () => {
    const message = 'var u="https://reactjs.org/docs/error-decoder.html?invariant="+e';
    expect(jsReferences(message, { bundle: true })).toEqual([]);
    expect(jsReferences(message, { bundle: false }).length).toBeGreaterThan(0);
    expect(jsReferences('var u="https://reactjs.org/other"', { bundle: true }).length).toBeGreaterThan(0);
  });
  it("lets only the recorded-run client call fetch, for a path, never a URL or another API", () => {
    expect(jsReferences('fetch(path)', { apiClient: true })).toEqual([]);
    expect(jsReferences('fetch(path)', { bundle: true, apiClient: true })).toEqual([]);
    expect(jsReferences('fetch(path)', {}).length).toBeGreaterThan(0); // any other app code
    expect(jsReferences('new XMLHttpRequest()', { apiClient: true }).length).toBeGreaterThan(0);
    expect(jsReferences('new WebSocket(u); fetch(p)', { apiClient: true })).toEqual(["js network api WebSocket"]);
    expect(jsReferences('fetch("https://example.invalid/a")', { apiClient: true }).length).toBeGreaterThan(0);
  });

  it("tolerates a network API name only in a built vendor chunk, never a URL there", () => {
    expect(jsReferences('fetch(a)', { bundle: true, vendor: true })).toEqual([]);
    expect(jsReferences('fetch(a)', { bundle: true }).length).toBeGreaterThan(0);
    expect(jsReferences('fetch(a)', { vendor: true }).length).toBeGreaterThan(0); // source is always strict
    expect(jsReferences('fetch("https://example.invalid/a")', { bundle: true, vendor: true }).length).toBeGreaterThan(0);
  });
  it("allows only the exact loaders.gl worker template and luma.gl doc links in a bundle", () => {
    const template = "var u=`https://unpkg.com/@loaders.gl/${e.module}${n}/dist/${r}`";
    expect(jsReferences(template, { bundle: true })).toEqual([]);
    expect(jsReferences(template, { bundle: false }).length).toBeGreaterThan(0);
    expect(jsReferences("var u=`https://unpkg.com/@loaders.gl/core/dist/x.js`", { bundle: true }).length).toBeGreaterThan(0);
    expect(jsReferences("var o={CDN:`https://unpkg.com/@loaders.gl`,worker:!0}", { bundle: true })).toEqual([]);
    expect(jsReferences("var o={CDN:`https://unpkg.com/other`}", { bundle: true }).length).toBeGreaterThan(0);
    expect(jsReferences('var d="https://en.wikipedia.org/wiki/Find_first_set#CLZ"', { bundle: true })).toEqual([]);
    expect(jsReferences('var d="https://en.wikipedia.org/wiki/Other"', { bundle: true }).length).toBeGreaterThan(0);
  });
});

describe("which source files are scanned", () => {
  it.each(["src/main.tsx", "src/app/App.tsx", "src/app/stream.ts", "src/ui/tokens.css", "src/generated/index.ts", "src/x.svg", "src/x.html"])(
    "scans %s", (path) => expect(isScannedSource(path)).toBe(true));
  it.each(["src/generated/stream-envelope.d.ts", "src/vite-env.d.ts", "src/app/App.test.tsx", "src/app/x.test.ts", "src/data.json", "src/readme.md"])(
    "does not scan %s", (path) => expect(isScannedSource(path)).toBe(false));
  it("the generated declarations do mention network words in schema descriptions, which is why they are skipped", () => {
    const text = readFileSync("src/generated/stream-envelope.d.ts", "utf8");
    expect(jsReferences(text).length).toBeGreaterThan(0);
    expect(isScannedSource("src/generated/stream-envelope.d.ts")).toBe(false);
  });
});
