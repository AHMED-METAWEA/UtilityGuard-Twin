#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
node --input-type=module - "${1:-http://127.0.0.1:8080}" "$work" <<'JS'
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import {
  htmlReferences, cssReferences, jsReferences, requiredCsp,
} from './frontend/scripts/offline-lib.mjs';

const base = new URL(process.argv[2].replace(/\/+$/, '') + '/');
const work = process.argv[3];
const disclaimer = 'Virtual twin. Not ACUD data and not a survey of any real network. Advisory only: a human approves every action. Not certified for operation of critical infrastructure.';
let failed = false;
let html;
const assets = [];
function assert(ok, message) { if (!ok) throw new Error(message); }
function check(name, run) {
  try { run(); console.log(`PASS ${name}`); }
  catch (error) { failed = true; console.log(`FAIL ${name}: ${error.message}`); }
}
function download(url, name) {
  assert(url.origin === base.origin, `asset leaves base origin: ${url}`);
  const file = join(work, name);
  const headerFile = join(work, `${name}.headers`);
  const status = execFileSync('curl', [
    '--silent', '--show-error', '--max-time', '10', '--path-as-is',
    '--dump-header', headerFile, '--output', file, '--write-out', '%{http_code}',
    url.href,
  ], { encoding: 'utf8' });
  return { status: Number(status), body: readFileSync(file, 'utf8'),
    headers: readFileSync(headerFile, 'utf8'), file };
}
function attributes(tag) {
  return Object.fromEntries([...tag.matchAll(/([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))/g)]
    .map(m => [m[1].toLowerCase(), m[2] ?? m[3] ?? m[4]]));
}
check('page title and CSP', () => {
  const page = download(base, 'index.html');
  assert(page.status === 200, `page HTTP ${page.status}`);
  assert(/^content-type:\s*text\/html\b/im.test(page.headers), 'page is not HTML');
  html = page.body;
  assert(/<title>\s*UtilityGuard Twin\s*<\/title>/i.test(html), 'wrong page title');
  assert(requiredCsp(html).length === 0, requiredCsp(html).join('; '));
});
check('referenced scripts/styles and honesty text', () => {
  assert(html !== undefined, 'page download failed');
  for (const match of html.matchAll(/<(script|link)\b[^>]*>/gi)) {
    const attr = attributes(match[0]);
    const script = match[1].toLowerCase() === 'script';
    const stylesheet = (attr.rel ?? '').toLowerCase().split(/\s+/).includes('stylesheet');
    if ((!script || !attr.src) && !stylesheet) continue;
    const ref = script ? attr.src : attr.href;
    assert(ref, 'asset lacks URL');
    const result = download(new URL(ref, base), `asset-${assets.length}`);
    assert(result.status === 200, `${ref}: HTTP ${result.status}`);
    assert(script ? /^content-type:\s*(?:text|application)\/javascript\b/im.test(result.headers)
      : /^content-type:\s*text\/css\b/im.test(result.headers), `${ref}: wrong content type`);
    assets.push({ ...result, script });
  }
  assert(assets.some(a => a.script) && assets.some(a => !a.script), 'missing script or stylesheet');
  const bundle = assets.filter(a => a.script).map(a => a.body).join('\n');
  assert(bundle.includes('No network loaded'), 'bundle lacks fidelity badge');
  assert(bundle.includes(disclaimer), 'bundle lacks honesty statement');
});
check('health JSON, schema version and disclaimer', () => {
  const health = download(new URL('api/health', base), 'health.json');
  assert(health.status === 200, `health HTTP ${health.status}`);
  assert(/^content-type:\s*application\/json\b/im.test(health.headers), 'health is not JSON');
  execFileSync('python3', ['-m', 'json.tool', health.file], { stdio: 'pipe' });
  const data = JSON.parse(health.body);
  assert(data.schema_version === '1', 'wrong schema_version');
  assert(data.disclaimer === disclaimer, 'wrong health disclaimer');
});
check('unknown API returns problem details', () => {
  const response = download(new URL('api/nope', base), 'problem.json');
  assert(response.status === 404, `unknown API HTTP ${response.status}`);
  assert(/^content-type:\s*application\/problem\+json\b/im.test(response.headers), 'wrong problem media type');
  const data = JSON.parse(response.body);
  assert(data.type === 'about:blank' && data.title === 'Not Found' && data.status === 404, 'wrong problem body');
});
check('downloaded files pass offline gate', () => {
  assert(html !== undefined && assets.some(a => a.script) && assets.some(a => !a.script), 'page or assets unavailable');
  const findings = [...htmlReferences(html), ...requiredCsp(html)];
  for (const asset of assets) findings.push(...(asset.script
    ? jsReferences(asset.body, { bundle: true }) : cssReferences(asset.body)));
  writeFileSync(join(work, 'offline-findings.json'), JSON.stringify(findings));
  assert(findings.length === 0, findings.join('; '));
});
process.exitCode = failed ? 1 : 0;
JS
