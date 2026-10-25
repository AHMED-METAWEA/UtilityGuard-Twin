/**
 * Generate contracts/v1 TypeScript declarations offline with the pinned tool.
 * Usage: node scripts/gen_types.mjs [output-directory] (default: frontend/src/generated).
 * make gen-types writes committed declarations; check_contract_drift.sh uses a temp directory.
 * Each schema is an isolated module. The index exports every declaration explicitly;
 * a schema that embeds another (by a $ref to its file) comes after it, so an embedded type keeps
 * its home name; common definitions come first, then filename order breaks ties.
 * A repeated name with an identical body is exported once; one with a different body gets a
 * schema prefix, so inlined dependencies stay collision-free.
 * These structural types do not replace JSON Schema runtime validation.
 */
import { mkdir, readFile, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { compileFromFile } from './types/node_modules/json-schema-to-typescript/dist/src/index.js';

const root = fileURLToPath(new URL('../', import.meta.url));
const schemaDir = path.join(root, 'contracts/v1');
const outputDir = path.resolve(process.argv[2] ?? path.join(root, 'frontend/src/generated'));
if (process.argv.length > 3) throw new Error('Usage: node scripts/gen_types.mjs [output-directory]');
const schemas = (await readdir(schemaDir)).filter((name) => name.endsWith('.schema.json')).sort();
if (!schemas.length) throw new Error('No contracts/v1/*.schema.json files found');
const header = (source) => `/**\n * Generated from ${source} by json-schema-to-typescript.\n * DO NOT MODIFY: edits are lost. Run make gen-types.\n */`;
const normalize = (text) => text.replace(/\r\n?/g, '\n').trimEnd() + '\n';

// Split a generated module into its declarations by name. A declaration runs from its `export`
// line to the JSDoc comment of the next one, so two modules can be compared body by body.
function declarations(text) {
  const starts = [...text.matchAll(/^export (?:type|interface|enum) (\w+)/gm)];
  return new Map(starts.map((match, i) => {
    const end = i + 1 < starts.length ? starts[i + 1].index : text.length;
    const body = text.slice(match.index, end).replace(/\/\*\*(?:(?!\*\/)[\s\S])*\*\/\s*$/, '').trimEnd();
    return [match[1], body];
  }));
}
const modules = new Map();
const declarationTexts = new Map(); // stem -> Map(name -> declaration without its leading comment)
await mkdir(outputDir, { recursive: true });
for (const schema of schemas) {
  const stem = schema.slice(0, -'.schema.json'.length);
  const declaration = normalize(await compileFromFile(path.join(schemaDir, schema), {
    bannerComment: header(`contracts/v1/${schema}`),
    unreachableDefinitions: true,
    $refOptions: { resolve: { http: false } },
    style: { endOfLine: 'lf' },
  }));
  const names = [...declaration.matchAll(/^export (?:type|interface|enum) (\w+)/gm)]
    .map((match) => match[1]).sort();
  if (!names.length) throw new Error(`No declarations generated for ${schema}`);
  modules.set(stem, names);
  declarationTexts.set(stem, declarations(declaration));
  await writeFile(path.join(outputDir, `${stem}.d.ts`), declaration);
}

// Reserve all original names before allocating aliases, so an alias cannot hide
// a declaration introduced by another schema. Fail clearly on any alias collision.
const reserved = new Set([...modules.values()].flat());
const exported = new Set();
const firstBody = new Map();
const index = [header('contracts/v1/*.schema.json'), ''];
// Dependencies first: a schema that references another schema file is placed after it, so a
// type embedded in a dependent module (Fault inside run-manifest) is exported from its home module.
const dependsOn = new Map();
for (const stem of modules.keys()) {
  const text = await readFile(path.join(schemaDir, `${stem}.schema.json`), 'utf8');
  const refs = [...text.matchAll(/"\$ref":\s*"([\w-]+)\.schema\.json/g)].map((m) => m[1]);
  dependsOn.set(stem, new Set(refs.filter((ref) => ref !== stem && modules.has(ref))));
}
const order = [];
const remaining = new Set(modules.keys());
while (remaining.size) {
  const ready = [...remaining].filter((stem) => [...dependsOn.get(stem)].every((d) => !remaining.has(d))).sort();
  if (!ready.length) throw new Error(`Circular $ref between schemas: ${[...remaining].join(', ')}`);
  order.push(ready[0]);
  remaining.delete(ready[0]);
}
for (const stem of order) {
  const prefix = stem.split('-').map((part) => part[0].toUpperCase() + part.slice(1)).join('');
  const specifiers = modules.get(stem).flatMap((name) => {
    let alias = name;
    if (exported.has(name)) {
      // The same declaration repeated inside a dependent module (Fault inside run-manifest) is
      // not exported again: its first export is the public name.
      if (firstBody.get(name) === declarationTexts.get(stem).get(name)) return [];
      alias = `${prefix}${name}`;
      if (reserved.has(alias) || exported.has(alias)) {
        throw new Error(`Public type alias collision: ${alias} from ${stem}`);
      }
    } else {
      firstBody.set(name, declarationTexts.get(stem).get(name));
    }
    exported.add(alias);
    return [alias === name ? name : `${name} as ${alias}`];
  });
  if (!specifiers.length) continue;
  index.push(`export type {\n  ${specifiers.join(',\n  ')},\n} from './${stem}';`, '');
}
await writeFile(path.join(outputDir, 'index.ts'), normalize(index.join('\n')));
console.log(`Generated ${schemas.length} schema modules and index.ts.`);
