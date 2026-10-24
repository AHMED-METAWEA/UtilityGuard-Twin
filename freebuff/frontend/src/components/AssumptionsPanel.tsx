import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import type { AssumptionsPayload } from '../lib/types';
import { EvidenceBadge } from './EvidenceBadge';

interface Props {
  data: AssumptionsPayload | null;
  onSaved: (data: AssumptionsPayload) => void;
}

export function AssumptionsPanel({ data, onSaved }: Props) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDrafts({});
  }, [data?.version]);

  if (!data) return <div className="muted">Loading assumptions…</div>;

  const dirty = Object.keys(drafts).some((key) => {
    const base = data.assumptions[key];
    return base && Number(drafts[key]) !== base.value && drafts[key] !== '';
  });

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const values: Record<string, number> = {};
      for (const [key, raw] of Object.entries(drafts)) {
        if (raw === '') continue;
        const item = data.assumptions[key];
        if (!item) continue;
        const numeric = Number(raw);
        if (Number.isNaN(numeric)) {
          throw new Error(`${key} must be a number`);
        }
        if (numeric !== item.value) values[key] = numeric;
      }
      const updated = await api.updateAssumptions(values);
      onSaved(updated);
      setDrafts({});
    } catch (caught) {
      setError((caught as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="assumptions">
      <div className="assumptions-head">
        <div>
          <h3>
            Assumptions <EvidenceBadge label="ASSUMPTION" />
          </h3>
          <p className="muted small">{data.disclaimer}</p>
          <p className="muted small">
            Version {data.version} · {data.currency}. Ranges feed the triangular Monte Carlo; the value is the mode used for
            deterministic cost lines.
          </p>
        </div>
        <div className="assumptions-actions">
          <button className="btn btn-primary" onClick={save} disabled={!dirty || saving}>
            {saving ? 'Saving…' : 'Save changes'}
          </button>
          {dirty ? (
            <button className="btn btn-subtle" onClick={() => setDrafts({})}>
              Discard
            </button>
          ) : null}
        </div>
      </div>
      {error ? <div className="error-box">{error}</div> : null}
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Assumption</th>
              <th>Value</th>
              <th>Plausible range</th>
              <th>Unit</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(data.assumptions).map(([key, item]) => (
              <tr key={key}>
                <td className="mono small">{key}</td>
                <td>
                  <input
                    className="input"
                    type="number"
                    step="any"
                    value={drafts[key] ?? item.value}
                    min={item.low}
                    max={item.high}
                    onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))}
                  />
                </td>
                <td className="mono small">
                  {item.low} – {item.high}
                </td>
                <td className="muted small">{item.unit}</td>
                <td className="muted small">{item.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Saving stores a local override file with a new revision number. It does not re-run existing decisions: re-open the
        cost comparison to see the effect.
      </p>
    </div>
  );
}
