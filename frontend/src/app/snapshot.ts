// Untrusted data (a loaded network, a stream envelope) is accepted only as INERT DATA and is
// then read from a fresh plain copy, never through the object it arrived in.
//
// Inert means: plain objects and arrays, strings, finite numbers, booleans and null, nothing
// else. Every property is a data property (an accessor is rejected without being called), is
// enumerable, and has a string key; custom prototypes, symbol keys, serialisation hooks such as
// toJSON, cycles, very deep or very large values and non-plain types (Date, Map, class
// instances) are all rejected. What passes is exactly what JSON.stringify would show, which is
// what a JSON parser at the API boundary produces. A Proxy is detected by structuredClone and
// rejected. Anything rejected is UNREADABLE and callers fall back to the conservative answer.
//
// Not covered: a Proxy trap that never returns. Code in the same page can always hang the page;
// the defence against hostile data is to receive it as JSON text and parse it once.

export const UNREADABLE: unique symbol = Symbol("unreadable");
type Unreadable = typeof UNREADABLE;

const MAX_DEPTH = 8;
const MAX_KEYS = 256;
const MAX_ARRAY = 5000;
const MAX_STRING = 10_000;

function copy(value: unknown, depth: number): unknown | Unreadable {
  if (value === null || typeof value === "boolean") return value;
  if (typeof value === "number") return Number.isFinite(value) ? value : UNREADABLE;
  if (typeof value === "string") return value.length <= MAX_STRING ? value : UNREADABLE;
  if (typeof value !== "object" || depth > MAX_DEPTH) return UNREADABLE;
  if (Object.getOwnPropertySymbols(value).length > 0) return UNREADABLE;
  const names = Object.getOwnPropertyNames(value);
  const proto: unknown = Object.getPrototypeOf(value);
  if (Array.isArray(value)) {
    if (proto !== Array.prototype || value.length > MAX_ARRAY || names.length !== value.length + 1) {
      return UNREADABLE;
    }
    const items: unknown[] = [];
    for (let index = 0; index < value.length; index += 1) {
      const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
      if (descriptor === undefined || !("value" in descriptor) || !descriptor.enumerable) return UNREADABLE;
      const item = copy(descriptor.value, depth + 1);
      if (item === UNREADABLE) return UNREADABLE;
      items.push(item);
    }
    return items;
  }
  if ((proto !== Object.prototype && proto !== null) || names.length > MAX_KEYS) return UNREADABLE;
  const out: Record<string, unknown> = Object.create(null) as Record<string, unknown>;
  for (const name of names) {
    const descriptor = Object.getOwnPropertyDescriptor(value, name);
    if (descriptor === undefined || !("value" in descriptor) || !descriptor.enumerable) return UNREADABLE;
    const item = copy(descriptor.value, depth + 1);
    if (item === UNREADABLE) return UNREADABLE;
    out[name] = item;
  }
  return out;
}

export function snapshot(value: unknown): unknown | Unreadable {
  try {
    const result = copy(value, 0);
    if (result === UNREADABLE) return UNREADABLE;
    if (typeof value === "object" && value !== null) structuredClone(value); // rejects a Proxy
    return result;
  } catch {
    return UNREADABLE;
  }
}

/** A plain object (not an array, not a boxed value, no custom prototype). */
export function isRecord(value: unknown): value is Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const proto: unknown = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}
