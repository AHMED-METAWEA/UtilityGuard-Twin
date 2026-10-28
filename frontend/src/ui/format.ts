import { UI_STRINGS } from "./strings";
/** Locale independent; digits requests fixed decimals, including trailing zeroes. */
export function formatValue(value: number | string | boolean | null, digits?: number): string {
  if (value === null) return UI_STRINGS.missing;
  if (typeof value === "boolean") return value ? UI_STRINGS.true : UI_STRINGS.false;
  if (typeof value !== "number") return value;
  if (!Number.isFinite(value)) throw new Error("Metric requires a finite number");
  let formatted = digits === undefined ? String(value) : value.toFixed(digits);
  if (Math.abs(value) < 10000) return formatted;
  // Expand positive exponents before grouping (toFixed also uses them at 1e21).
  if (formatted.includes("e+")) {
    const [coefficient, exponent] = formatted.split("e+");
    const [whole, fraction = ""] = coefficient!.split(".");
    formatted = whole + fraction + "0".repeat(Number(exponent) - fraction.length);
    if (digits !== undefined && digits > 0) formatted += "." + "0".repeat(digits);
  }
  const [integer, fraction] = formatted.split(".");
  return integer!.replace(/\B(?=(\d{3})+(?!\d))/g, "\u2009") + (fraction === undefined ? "" : `.${fraction}`);
}
