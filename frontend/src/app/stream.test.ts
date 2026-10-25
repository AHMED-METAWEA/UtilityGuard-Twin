import { describe, expect, it } from "vitest";

import { DEFAULT_STREAM_SOURCE, STREAM_SOURCES, streamSourceFromEnvelope } from "./stream";

const envelope = (source: unknown) => ({
  schema_version: "1",
  type: "tick",
  run_id: "run_0042",
  seq: 1,
  payload: { stream_source: source },
});

describe("stream source", () => {
  it("defaults to REPLAY", () => {
    expect(DEFAULT_STREAM_SOURCE).toBe("REPLAY");
    expect(streamSourceFromEnvelope(null)).toBe("REPLAY");
    expect(streamSourceFromEnvelope(undefined)).toBe("REPLAY");
  });

  it.each(STREAM_SOURCES)("reads %s from the envelope", (source) => {
    expect(streamSourceFromEnvelope(envelope(source))).toBe(source);
  });

  it("is exactly the three sources of the contract", () => {
    expect([...STREAM_SOURCES]).toEqual(["REPLAY", "SIMULATED", "LIVE"]);
  });

  it.each(["live", "Live", "LIVE ", " LIVE", "LIVE\n", "REPLAYED", "", "L", 1, true, null, undefined, {}, ["LIVE"]])(
    "shows LIVE only when the envelope says exactly LIVE (%j)",
    (value) => {
      expect(streamSourceFromEnvelope(envelope(value))).toBe("REPLAY");
    },
  );

  it.each([
    ["no payload", { type: "tick" }],
    ["payload null", { payload: null }],
    ["payload a string", { payload: "LIVE" }],
    ["source at the top level", { stream_source: "LIVE" }],
    ["a string", "LIVE"],
    ["an array", ["LIVE"]],
    ["a number", 5],
  ])("ignores a malformed envelope (%s)", (_name, value) => {
    expect(streamSourceFromEnvelope(value)).toBe("REPLAY");
  });
});
