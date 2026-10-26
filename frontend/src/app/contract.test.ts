import { describe, expect, it } from "vitest";

import common from "../../../contracts/v1/common.schema.json";
import tick from "../../../contracts/examples/stream-envelope/tick_replay_with_suspect_sensor.json";
import { STREAM_SOURCES, streamSourceFromEnvelope } from "./stream";

// The shell and the contracts must agree. These tests read the contract files themselves, so a
// change to the stream sources in the contract fails here until the shell follows.
describe("the shell and contracts/v1", () => {
  it("knows exactly the stream sources of the contract", () => {
    expect([...STREAM_SOURCES]).toEqual(common.$defs.stream_source.enum);
  });

  it("reads the source from a real contract example", () => {
    expect(tick.payload.stream_source).toBe("REPLAY");
    expect(streamSourceFromEnvelope(tick)).toBe("REPLAY");
    for (const source of common.$defs.stream_source.enum) {
      const envelope = { ...tick, payload: { ...tick.payload, stream_source: source } };
      expect(streamSourceFromEnvelope(envelope)).toBe(source);
    }
  });

  it("does not turn a rejected envelope into LIVE", () => {
    const rejected = { ...tick, payload: { ...tick.payload, stream_source: "REPLAYED" } };
    expect(streamSourceFromEnvelope(rejected)).toBe("REPLAY");
  });
});
