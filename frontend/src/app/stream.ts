// The stream-source indicator reads the source from the stream envelope (contracts/v1/
// stream-envelope: payload.stream_source). It defaults to REPLAY and shows LIVE only when an
// envelope says exactly LIVE (Honesty Rule: the source is always visible and never overstated).

import { isRecord, snapshot } from "./snapshot";

export const STREAM_SOURCES = ["REPLAY", "SIMULATED", "LIVE"] as const;
export type StreamSource = (typeof STREAM_SOURCES)[number];

export const DEFAULT_STREAM_SOURCE: StreamSource = "REPLAY";

function isStreamSource(value: unknown): value is StreamSource {
  return typeof value === "string" && (STREAM_SOURCES as readonly string[]).includes(value);
}

/**
 * The source named by the latest envelope; REPLAY when there is none or it is malformed. The
 * envelope is read from a stable copy of its own data, so a value that is inherited, faked by a
 * proxy or produced by a throwing accessor is never taken as a declaration.
 */
export function streamSourceFromEnvelope(envelope: unknown): StreamSource {
  const data = snapshot(envelope);
  if (!isRecord(data) || !isRecord(data.payload)) return DEFAULT_STREAM_SOURCE;
  const source = data.payload.stream_source;
  return isStreamSource(source) ? source : DEFAULT_STREAM_SOURCE;
}
