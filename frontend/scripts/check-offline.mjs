// Offline-first check (Master Spec P10): the shell must not reach out to the network.
// Run after `vite build`. Scans the page, the sources and the build output for anything that
// points outside the application (see offline-lib.mjs) and fails with a list. It cannot prove
// that a running browser makes no request; it makes the common ways of doing so fail the build.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { cssReferences, htmlReferences, isScannedSource, jsReferences, requiredCsp } from "./offline-lib.mjs";

const root = join(fileURLToPath(new URL(".", import.meta.url)), "..");
const problems = [];

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

function scan(path, { bundle }) {
  const text = readFileSync(path, "utf8");
  const rel = path.replace(root + "/", "");
  const ext = extname(path);
  const found =
    ext === ".html" || ext === ".svg"
      ? htmlReferences(text)
      : ext === ".css"
        ? cssReferences(text)
        : ext === ".js" || ext === ".mjs" || ext === ".ts" || ext === ".tsx"
          ? jsReferences(text, { bundle })
          : [];
  for (const item of found) problems.push(`${rel}: ${item}`);
  // TypeScript sources may also hold CSS-in-strings or markup; the page scan covers index.html.
}

scan(join(root, "index.html"), { bundle: false });
for (const file of walk(join(root, "src"))) {
  if (isScannedSource(file)) scan(file, { bundle: false });
}
let built = [];
try {
  built = walk(join(root, "dist"));
} catch {
  problems.push("dist/ not found: run `npm run build` first");
}
for (const file of built) scan(file, { bundle: true });
const builtIndex = join(root, "dist", "index.html");
if (built.includes(builtIndex)) {
  for (const item of requiredCsp(readFileSync(builtIndex, "utf8"))) problems.push(`dist/index.html: ${item}`);
}

if (problems.length > 0) {
  console.error(`offline check FAILED (${problems.length}):`);
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}
console.log(`offline check OK: index.html, src and ${built.length} built files, no reference outside the application`);
