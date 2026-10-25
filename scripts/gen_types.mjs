/**
 * Generate contracts/v1 TypeScript declarations offline with the pinned tool.
 * Usage: node scripts/gen_types.mjs [output-directory] (default: frontend/src/generated).
 * make gen-types writes committed declarations; check_contract_drift.sh uses a temp directory.
 * Each schema is an isolated module. The index exports every declaration explicitly;
 * common definitions win unprefixed names, then schema filename order breaks ties.
 * Repeated names get a schema prefix, keeping inlined dependencies collision-free.
 * These structural types do not replace JSON Schema runtime validation.
 */
import { mkdir, readdir, writeFile } from 'node:fs/promises';
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
const modules = new Map();
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
  await writeFile(path.join(outputDir, `${stem}.d.ts`), declaration);
}

// Reserve all original names before allocating aliases, so an alias cannot hide
// a declaration introduced by another schema. Fail clearly on any alias collision.
const reserved = new Set([...modules.values()].flat());
const exported = new Set();
const index = [header('contracts/v1/*.schema.json'), ''];
const order = [...modules.keys()].sort((a, b) =>
  a === b ? 0 : a === 'common' ? -1 : b === 'common' ? 1 : a < b ? -1 : 1);
for (const stem of order) {
  const prefix = stem.split('-').map((part) => part[0].toUpperCase() + part.slice(1)).join('');
  const specifiers = modules.get(stem).map((name) => {
    let alias = name;
    if (exported.has(name)) {
      alias = `${prefix}${name}`;
      if (reserved.has(alias) || exported.has(alias)) {
        throw new Error(`Public type alias collision: ${alias} from ${stem}`);
      }
    }
    exported.add(alias);
    return alias === name ? name : `${name} as ${alias}`;
  });
  index.push(`export type {\n  ${specifiers.join(',\n  ')},\n} from './${stem}';`, '');
}
await writeFile(path.join(outputDir, 'index.ts'), normalize(index.join('\n')));
console.log(`Generated ${schemas.length} schema modules and index.ts.`);
