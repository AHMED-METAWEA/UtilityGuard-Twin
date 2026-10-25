// Bypasses of the first offline check that resolve to an external host in a browser.
import { describe, expect, it } from "vitest";

import { htmlReferences, jsReferences, leavesTheApplication, requiredCsp } from "./offline-lib.mjs";

describe("URL normalisation like a browser", () => {
  it.each([
    "/\\example.invalid/x", "\\\\example.invalid/x", "ht\ntps://example.invalid/x", "ht\ttps://example.invalid", "https&#58;//example.invalid/x",
    "https&colon;//example.invalid/x", "&#104;ttps://example.invalid", "HtTpS://example.invalid/x", " \u0001https://example.invalid", "https:\\\\example.invalid",
    "java\nscript:alert(1)", "///example.invalid/x", "https:///example.invalid/x", " javascript:alert(1)", "JaVaScRiPt:alert(1)", "&#106;avascript:alert(1)",
  ])("treats %j as leaving the application", (value) => expect(leavesTheApplication(value)).toBe(true));
});

describe("html", () => {
  it.each([
    '<img src="/\\example.invalid/x">', '<img src="ht&#10;tps://example.invalid/x">', '<img src="https&#58;//example.invalid/x">',
    '<a href="HtTpS://example.invalid">x</a>', '<img src="https://www.w3.org/tracker.png">', '<base href="https://example.invalid/">',
    '<object data="https://example.invalid/x"></object>', '<embed src="//example.invalid/x">', '<form formaction="//example.invalid"></form>',
  ])("flags %s", (html) => expect(htmlReferences(html).length).toBeGreaterThan(0));
  it.each([
    '<svg xmlns="http://www.w3.org/evil/tracker.png"></svg>', '<svg xmlns="https://www.w3.org/2000/svg/../tracker"></svg>',
    '<svg xmlns:x="http://www.w3.org/1999/xlink/extra"></svg>', '<svg xmlns="https://example.invalid/ns"></svg>',
  ])("flags a namespace declaration that is not a known namespace: %s", (html) =>
    expect(htmlReferences(html).length).toBeGreaterThan(0));
  it("still passes namespace declarations", () => {
    expect(htmlReferences('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"></svg>')).toEqual([]);
  });
});

describe("javascript strings are normalised like URLs", () => {
  it.each([
    'new Image().src="HtTpS://example.invalid/x"', 'new Image().src="https://www.w3.org/tracker.png"', 'a = "/\\\\example.invalid/x"',
    'a = "\\x68ttps://example.invalid/x"', 'a = "\\u0068ttps://example.invalid/x"', "a = `https://example.invalid/x`", 'a = "ht\\ntps://example.invalid"',
  ])("flags %s", (js) => expect(jsReferences(js).length).toBeGreaterThan(0));
  it.each([
    'const ns = "http://www.w3.org/2000/svg"', 'const x = "http://www.w3.org/1999/xlink"', 'const n = "http://www.w3.org/1998/Math/MathML"',
    'const a = "a//b"', 'const re = "^//"', 'const s = "//"',
  ])("passes %s", (js) => expect(jsReferences(js)).toEqual([]));
});

describe("content security policy of the built page", () => {
  const good = "default-src 'self'; connect-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'";
  const page = (csp) => `<html><head><meta http-equiv="Content-Security-Policy" content="${csp}"></head></html>`;
  it("accepts a strict policy", () => expect(requiredCsp(page(good))).toEqual([]));
  it.each([
    ["no policy", "<html></html>"],
    ["unsafe-inline", page(good.replace("script-src 'self'", "script-src 'self' 'unsafe-inline'"))],
    ["unsafe-eval", page(good.replace("script-src 'self'", "script-src 'self' 'unsafe-eval'"))],
    ["a remote host", page(good.replace("connect-src 'self'", "connect-src 'self' https://example.invalid"))],
    ["a wildcard", page(good.replace("img-src 'self'", "img-src *"))],
    ["no default-src", page(good.replace("default-src 'self'; ", ""))],
    ["objects allowed", page(good.replace("object-src 'none'", "object-src 'self'"))],
    ["no base-uri", page(good.replace("base-uri 'self'; ", ""))],
    ["no form-action", page(good.replace("; form-action 'self'", ""))],
    ["data: scripts", page(good.replace("script-src 'self'", "script-src 'self' data:"))],
  ])("rejects %s", (_n, html) => expect(requiredCsp(html).length).toBeGreaterThan(0));
});
