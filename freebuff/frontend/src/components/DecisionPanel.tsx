import type { Decision, DecisionAction } from '../lib/types';
import { EvidenceBadge, Num } from './EvidenceBadge';

interface Props {
  decision: Decision | null;
  loading: boolean;
  error: string | null;
  onAnalyze: () => void;
  hasIncident: boolean;
}

function money(value: number): string {
  return `CU ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function actionTone(action: DecisionAction, recommended: string): string {
  if (action.action === recommended) return 'action-row action-recommended';
  return 'action-row';
}

export function DecisionPanel({ decision, loading, error, onAnalyze, hasIncident }: Props) {
  if (!hasIncident) {
    return (
      <div className="empty-state">
        <strong>No incident selected</strong>
        <p>Select a detected incident, then ask the decision engine to compare response options.</p>
      </div>
    );
  }
  if (loading) {
    return (
      <div className="empty-state">
        <strong>Running WNTR continuations…</strong>
        <p>
          Each option is a fresh hydraulic simulation from the incident tick, including a leak-size range. This takes about
          10–20 seconds on a laptop.
        </p>
      </div>
    );
  }
  if (error) return <div className="error-box">{error}</div>;
  if (!decision) {
    return (
      <div className="empty-state">
        <strong>Cost comparison not run yet</strong>
        <p>
          The engine simulates monitor / inspect / repair (or pump switch) options and prices them with editable assumptions.
        </p>
        <button className="btn btn-primary" onClick={onAnalyze}>
          Compare response costs
        </button>
      </div>
    );
  }

  const recommended = decision.actions.find((action) => action.action === decision.recommended_action);

  return (
    <div className="decision">
      <div className="recommendation">
        <div>
          <div className="eyebrow">Advisory ranking · MODEL + CALCULATED</div>
          <h3>{decision.recommended_label}</h3>
          <p className="muted small">
            Feasible set: {decision.feasible_ranking.length ? decision.feasible_ranking.join(', ') : 'none'} · horizon{' '}
            {decision.horizon_hours} h
          </p>
        </div>
        <div className="recommendation-saving">
          <span className="muted small">Model-estimated difference vs monitoring</span>
          <div>
            <Num value={decision.savings_vs_monitor} label="CALCULATED" unit="CU" digits={0} />
          </div>
        </div>
      </div>
      <p className="muted small">{decision.savings_note}</p>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Option</th>
              <th>
                Expected cost <EvidenceBadge label="CALCULATED" />
              </th>
              <th>P10–P90</th>
              <th>
                Unserved <EvidenceBadge label="SIMULATION" />
              </th>
              <th>Feasible</th>
            </tr>
          </thead>
          <tbody>
            {decision.actions.map((action) => (
              <tr key={action.action} className={actionTone(action, decision.recommended_action)}>
                <td>
                  <div className="strong">{action.label}</div>
                  <div className="muted small mono">{action.action}</div>
                </td>
                <td className="mono">{money(action.expected_cost)}</td>
                <td className="mono small">
                  {money(action.cost_p10)} – {money(action.cost_p90)}
                </td>
                <td className="mono">
                  {action.remaining_risk.unserved_m3.toFixed(1)} m³
                  <div className="muted small">{action.remaining_risk.affected_nodes} nodes affected</div>
                </td>
                <td>
                  <span className={`pill ${action.constraint_ok && action.within_budget ? 'pill-good' : 'pill-bad'}`}>
                    {action.constraint_ok && action.within_budget ? 'yes' : 'no'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {recommended ? (
        <>
          <h4>
            Cost lines for {recommended.label} <EvidenceBadge label="CALCULATED" />
          </h4>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Line</th>
                  <th>Quantity</th>
                  <th>Unit price</th>
                  <th>Cost</th>
                </tr>
              </thead>
              <tbody>
                {recommended.representative_cost_lines.map((line) => (
                  <tr key={line.line}>
                    <td>{line.line.replace(/_/g, ' ')}</td>
                    <td className="mono">
                      {line.quantity.toFixed(2)} {line.unit}
                      <EvidenceBadge label={line.label} />
                    </td>
                    <td className="mono">
                      {line.unit_price} {line.unit_price_unit}
                      <EvidenceBadge label="ASSUMPTION" />
                    </td>
                    <td className="mono">{money(line.cost)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}

      <h4>
        Break-even thresholds <EvidenceBadge label="CALCULATED" />
      </h4>
      <p className="muted small">
        No failure probability is estimated anywhere. The engine reports the probability at which an action would break even,
        so the reader can judge whether the real chance is plausibly above or below it.
      </p>
      <ul className="break-even">
        {decision.break_even.map((item) => (
          <li key={item.action}>
            <div className="strong">{item.action}</div>
            <div className="mono">
              {item.threshold === null ? 'never pays off in this model' : `P* = ${item.threshold.toFixed(3)}`}
            </div>
            <p className="small muted">{item.text}</p>
          </li>
        ))}
      </ul>

      <h4>
        Sensitivity <EvidenceBadge label="CALCULATED" />
      </h4>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Assumption</th>
              <th>Low → high</th>
              <th>Ranking at low</th>
              <th>Ranking at high</th>
              <th>Flip</th>
            </tr>
          </thead>
          <tbody>
            {decision.sensitivity.map((row) => (
              <tr key={row.assumption}>
                <td className="mono small">{row.assumption}</td>
                <td className="mono small">
                  {row.low} → {row.high} {row.unit}
                </td>
                <td className="small">{row.winner_at_low}</td>
                <td className="small">{row.winner_at_high}</td>
                <td>
                  {row.flips_ranking ? (
                    <span className="pill pill-suspect">flips at {row.flip_value}</span>
                  ) : (
                    <span className="muted small">no</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="decision-notes">
        <p>
          <strong>Constraints.</strong> {decision.constraints.note} Max unserved {decision.constraints.max_unserved_m3} m³
          <EvidenceBadge label="ASSUMPTION" />, budget{' '}
          {decision.constraints.budget === null ? 'not set' : `${decision.constraints.budget} CU`}.
        </p>
        <p>
          <strong>Method.</strong> {decision.method_note}
        </p>
        <p className="warning-text">{decision.advisory}</p>
      </div>
    </div>
  );
}
