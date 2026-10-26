import { streamSourceFromEnvelope } from "../app/stream";
import { STRINGS } from "../app/strings";

export function StreamSourcePill({ envelope }: { envelope: unknown }) {
  const source = streamSourceFromEnvelope(envelope);
  const connected = envelope !== null && envelope !== undefined;
  return (
    <span className="ug-pill" data-source={source} aria-label={STRINGS.stream.label}>
      <span className="ug-pill-label">{STRINGS.stream.label}</span>
      <strong>{source}</strong>
      {connected ? null : <span className="ug-pill-note">{STRINGS.stream.noStream}</span>}
    </span>
  );
}
