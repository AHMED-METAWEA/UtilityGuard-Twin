// Finds references to anything outside the application in HTML, CSS and JavaScript text.
// Master Spec P10: the shell must work offline, so nothing may point at another host, load a
// script or style from elsewhere, or call the network. Used by check-offline.mjs after a build
// and by its own tests (check-offline.test.mjs), which feed it the bypasses found in review.

const LOOPBACK = /^(?:https?:)?\/\/(?:localhost|127\.0\.0\.1)(?::\d+)?(?:[/?#]|$)/i;
// The XML namespaces that appear as constants in HTML, SVG and React. Exact URLs only: a path
// under w3.org (a tracking pixel, say) is not a namespace.
const NAMESPACES = new Set([
  "http://www.w3.org/2000/svg", "http://www.w3.org/1999/xlink", "http://www.w3.org/1999/xhtml",
  "http://www.w3.org/1998/Math/MathML", "http://www.w3.org/XML/1998/namespace", "http://www.w3.org/2000/xmlns/",
]);
// Message text inside react-dom 18 (never fetched or run as a URL). Exact prefixes only.
const INERT_IN_BUNDLE = [
  /^https:\/\/reactjs\.org\/docs\/error-decoder\.html\?invariant=/,
  /^javascript:throw new Error\('React has blocked a javascript: URL as a security precaution\.'\)$/,
];

const NAMED_ENTITIES = {
  colon: ":", sol: "/", bsol: "\\", tab: "\t", newline: "\n", amp: "&", lt: "<", gt: ">", quot: '"', apos: "'",
  period: ".", comma: ",", lpar: "(", rpar: ")", semi: ";", num: "#", quest: "?", equals: "=", plus: "+", percnt: "%",
  excl: "!", lsqb: "[", rsqb: "]", lbrace: "{", rbrace: "}", commat: "@", dollar: "$", ast: "*", hyphen: "-", lowbar: "_",
};

function decodeEntities(text) {
  return String(text)
    .replace(/&#x([0-9a-f]+);?/gi, (_, h) => String.fromCodePoint(Math.min(parseInt(h, 16), 0x10ffff)))
    .replace(/&#(\d+);?/g, (_, d) => String.fromCodePoint(Math.min(parseInt(d, 10), 0x10ffff)))
    .replace(/&([a-z]+);/gi, (m, name) => NAMED_ENTITIES[name.toLowerCase()] ?? m);
}

/** What a browser makes of a URL string: entities decoded, tabs and newlines dropped, leading
 *  control characters and spaces trimmed, backslashes read as slashes. */
export function browserUrl(value) {
  return decodeEntities(value)
    .replace(/[\t\n\r]/g, "")
    .replace(/^[\u0000-\u0020]+|[\u0000-\u0020]+$/g, "")
    .replace(/\\/g, "/")
    .replace(/^['"]|['"]$/g, "")
    .trim();
}

/** Does a URL-valued attribute or CSS url() argument leave the application? */
export function leavesTheApplication(value, { namespaces = false } = {}) {
  const v = browserUrl(value);
  if (v === "" || v === "//") return false; // a bare "//" names no host
  if (LOOPBACK.test(v)) return false;
  if (namespaces && NAMESPACES.has(v.replace(/\/$/, "")) ) return false;
  return /^(?:[a-z][a-z0-9+.-]*:)?\/\//i.test(v) || /^(?:javascript|data|vbscript|blob|file):/i.test(v);
}

function stripCssComments(css) {
  return css.replace(/\/\*[\s\S]*?\*\//g, " ");
}

export function cssReferences(css) {
  const found = [];
  const text = stripCssComments(css);
  for (const m of text.matchAll(/@import\s+(?:url\(\s*)?(["']?)([^"')\s;]+)\1/gi)) {
    if (leavesTheApplication(m[2])) found.push(`css @import ${m[2]}`);
  }
  for (const m of text.matchAll(/url\(\s*(["']?)([^"')]*)\1\s*\)/gi)) {
    if (leavesTheApplication(m[2])) found.push(`css url(${m[2]})`);
  }
  return found;
}

const NETWORK_API =
  /(?:\b|["'`\[])(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts|SharedWorker|ServiceWorker|serviceWorker)(?:\b|["'`\]])/;

function unescapeJs(text) {
  return text
    .replace(/\\\r?\n/g, "")
    .replace(/\\u\{([0-9a-f]+)\}/gi, (_, h) => String.fromCodePoint(Math.min(parseInt(h, 16), 0x10ffff)))
    .replace(/\\u([0-9a-f]{4})/gi, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\x([0-9a-f]{2})/gi, (_, h) => String.fromCharCode(parseInt(h, 16)))
    .replace(/\\([nrt])/g, (_, c) => ({ n: "\n", r: "\r", t: "\t" })[c])
    .replace(/\\(.)/g, "$1");
}

export function jsReferences(js, { bundle = false } = {}) {
  const found = [];
  const inert = (text) => bundle && INERT_IN_BUNDLE.some((re) => re.test(text));
  // Every string literal, read as a browser would read it as a URL (escapes, case, backslashes).
  for (const m of js.matchAll(/(["'`])((?:\\[\s\S]|(?!\1)[^\\\n])*?)\1/g)) {
    const text = unescapeJs(m[2]);
    if (inert(text)) continue;
    if (leavesTheApplication(text, { namespaces: true })) found.push(`js url ${text.slice(0, 80)}`);
  }
  // URLs written outside quotes cannot be told from prose; any absolute one is reported.
  for (const m of js.matchAll(/https?:\/\/[^\s"'`<>)\\]+/gi)) {
    const url = m[0];
    if (LOOPBACK.test(url) || NAMESPACES.has(url.replace(/\/$/, "")) || inert(url)) continue;
    if (!found.some((f) => f.includes(url.slice(0, 40)))) found.push(`js url ${url}`);
  }
  for (const m of js.matchAll(/\bimport\s*\(\s*(["'`])([^"'`]+)\1/g)) {
    if (leavesTheApplication(unescapeJs(m[2]))) found.push(`js dynamic import ${m[2]}`);
  }
  const api = js.match(NETWORK_API);
  if (api) found.push(`js network api ${api[1]}`);
  return [...new Set(found)];
}

const URL_ATTRIBUTES = new Set([
  "src", "href", "srcset", "poster", "action", "formaction", "data", "xlink:href", "ping",
  "background", "cite", "longdesc", "manifest", "imagesrcset", "archive", "codebase",
]);

export function htmlReferences(html) {
  const found = [];
  const text = html.replace(/<!--[\s\S]*?-->/g, " ");
  for (const tag of text.matchAll(/<([a-z][\w:-]*)\b([^>]*)>/gi)) {
    const [, name, attrs] = tag;
    for (const attr of attrs.matchAll(/([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))/g)) {
      const key = attr[1].toLowerCase();
      const value = attr[2] ?? attr[3] ?? attr[4] ?? "";
      if (key === "xmlns" || key.startsWith("xmlns:")) {
        if (leavesTheApplication(value, { namespaces: true })) found.push(`html <${name}> ${key}=${value}`);
        continue;
      }
      if (key === "style") {
        found.push(...cssReferences(`x{${value}}`).map((r) => `html style: ${r}`));
      } else if (key === "srcset" || key === "imagesrcset") {
        for (const part of value.split(",")) {
          if (leavesTheApplication(part.trim().split(/\s+/)[0] ?? "")) found.push(`html ${name} ${key} ${part.trim()}`);
        }
      } else if (key === "content" && /http-equiv\s*=\s*["']?refresh/i.test(attrs)) {
        const target = decodeEntities(value).match(/url\s*=\s*(.+)$/i);
        if (target && leavesTheApplication(target[1])) found.push(`html meta refresh ${target[1]}`);
      } else if (URL_ATTRIBUTES.has(key) && leavesTheApplication(value)) {
        found.push(`html <${name}> ${key}=${value}`);
      }
    }
  }
  for (const m of text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/gi)) {
    found.push(...cssReferences(m[1]).map((r) => `html <style>: ${r}`));
  }
  for (const m of text.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)) {
    if (m[1].trim() !== "") found.push(...jsReferences(m[1]).map((r) => `html <script>: ${r}`));
  }
  return found;
}

/** SVG files are HTML-like (xlink:href, href, style). */
export const svgReferences = htmlReferences;

/**
 * The built page must carry a strict Content-Security-Policy (a meta tag), the runtime backstop
 * for what static scanning cannot see (constructed URLs, decoded strings): with it a browser
 * refuses any request to another origin. Returns the problems found, empty when it is strict.
 */
export function requiredCsp(html) {
  const tag = html.match(/<meta\b[^>]*http-equiv\s*=\s*["']?content-security-policy["']?[^>]*>/i);
  if (!tag) return ["no Content-Security-Policy meta tag"];
  const content = tag[0].match(/content\s*=\s*"([^"]*)"|content\s*=\s*'([^']*)'/i);
  if (!content) return ["Content-Security-Policy has no content"];
  const policy = new Map();
  for (const part of (content[1] ?? content[2]).split(";")) {
    const [name, ...sources] = part.trim().split(/\s+/);
    if (name) policy.set(name.toLowerCase(), sources);
  }
  const problems = [];
  const only = (directive, allowed) => {
    const sources = policy.get(directive);
    if (!sources) return problems.push(`CSP lacks ${directive}`);
    for (const source of sources) {
      if (!allowed.includes(source)) problems.push(`CSP ${directive} allows ${source}`);
    }
    if (sources.length === 0) problems.push(`CSP ${directive} is empty`);
  };
  only("default-src", ["'self'"]);
  only("script-src", ["'self'"]);
  only("style-src", ["'self'"]);
  only("img-src", ["'self'"]);
  only("connect-src", ["'self'"]);
  only("object-src", ["'none'"]);
  only("base-uri", ["'self'"]);
  only("form-action", ["'self'"]);
  return problems;
}
