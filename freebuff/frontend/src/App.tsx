import { Dashboard } from './pages/Dashboard';

export function App() {
  return (
    <>
      <Dashboard />
      <footer className="footer">
        <span>Virtual utility twin. Hypothetical network, simulated data.</span>
        <span className="muted">
          Advisory prototype · no real utility data · costs in placeholder CU · not for operational use
        </span>
      </footer>
    </>
  );
}
