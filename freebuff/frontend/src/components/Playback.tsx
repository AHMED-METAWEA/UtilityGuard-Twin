interface Props {
  tick: number;
  ticks: number;
  playing: boolean;
  speed: number;
  simTime: string | null;
  status: string;
  onToggle: () => void;
  onSpeed: (speed: number) => void;
  onSeek: (tick: number) => void;
}

const SPEEDS = [
  { value: 300, label: '5 min/s' },
  { value: 1800, label: '30 min/s' },
  { value: 3600, label: '1 h/s' },
  { value: 7200, label: '2 h/s' },
];

export function Playback({
  tick,
  ticks,
  playing,
  speed,
  simTime,
  status,
  onToggle,
  onSpeed,
  onSeek,
}: Props) {
  const timeLabel = simTime ? simTime.replace('T', ' ').slice(0, 16) : '—';
  return (
    <div className="playback">
      <button className="btn btn-primary" onClick={onToggle} disabled={status !== 'ready'}>
        {playing ? '❚❚ Pause' : '▶ Play'}
      </button>
      <div className="playback-time">
        <div className="playback-clock">{timeLabel}</div>
        <div className="playback-sub">
          tick {tick} / {ticks} · replayed simulation
        </div>
      </div>
      <input
        className="scrubber"
        type="range"
        min={0}
        max={Math.max(0, ticks)}
        value={tick}
        onChange={(event) => onSeek(Number(event.target.value))}
        disabled={status !== 'ready'}
        aria-label="Seek simulation tick"
      />
      <select
        className="select"
        value={speed}
        onChange={(event) => onSpeed(Number(event.target.value))}
        aria-label="Playback speed"
      >
        {SPEEDS.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
    </div>
  );
}
