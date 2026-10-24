import type { EvidenceLabel } from '../lib/types';

const MEANINGS: Record<EvidenceLabel, string> = {
  SIMULATION: 'WNTR simulation output from the virtual network.',
  SENSOR_SIM: 'Simulated measurement: WNTR truth plus noise and any injected sensor fault.',
  MODEL: 'Output of a documented rule or model in this app (detector, quality layer, decision ranking).',
  ASSUMPTION: 'A user-editable placeholder input, not measured or verified data.',
  CALCULATED: 'Derived arithmetically from the other values; the formula is shown where space allows.',
  INSUFFICIENT_EVIDENCE: 'The data cannot support a trustworthy value. Nothing is guessed.',
};

const SHORT: Record<EvidenceLabel, string> = {
  SIMULATION: 'sim',
  SENSOR_SIM: 'sensor',
  MODEL: 'model',
  ASSUMPTION: 'assume',
  CALCULATED: 'calc',
  INSUFFICIENT_EVIDENCE: 'no evidence',
};

export function EvidenceBadge({ label }: { label: EvidenceLabel }) {
  return (
    <span
      className={`ev ev-${label.toLowerCase().replace(/_/g, '-')}`}
      title={`${label}: ${MEANINGS[label]}`}
    >
      {SHORT[label]}
    </span>
  );
}

interface NumProps {
  value: number | string | null | undefined;
  label: EvidenceLabel;
  unit?: string;
  digits?: number;
  className?: string;
  title?: string;
}

export function Num({ value, label, unit, digits = 1, className, title }: NumProps) {
  const text =
    value === null || value === undefined || Number.isNaN(value)
      ? '—'
      : typeof value === 'number'
        ? value.toFixed(digits)
        : value;
  return (
    <span className={`num ${className ?? ''}`} title={title}>
      <span className="num-value">
        {text}
        {unit ? <span className="num-unit">{unit}</span> : null}
      </span>
      <EvidenceBadge label={text === '—' ? 'INSUFFICIENT_EVIDENCE' : label} />
    </span>
  );
}
