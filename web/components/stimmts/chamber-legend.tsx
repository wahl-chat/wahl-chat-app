import VoteDot from './vote-dot';

type Props = {
  /** Rings while the player's tips are on the chamber, filled dots after. */
  kind: 'guess' | 'votes';
  unaffiliated: number;
};

const GUESSES = [
  { kind: 'yes', label: 'Tipp Ja' },
  { kind: 'no', label: 'Tipp Nein' },
  { kind: 'abstain', label: 'Tipp Enthaltung' },
] as const;

const VOTES = [
  { kind: 'yes', label: 'Ja' },
  { kind: 'no', label: 'Nein' },
  { kind: 'abstain', label: 'Enthaltung' },
  { kind: 'absent', label: 'Abwesend' },
] as const;

/** The key under the chamber: colour never works without its word. */
function ChamberLegend({ kind, unaffiliated }: Props) {
  const items =
    kind === 'guess'
      ? GUESSES
      : unaffiliated > 0
        ? [...VOTES, { kind: 'unaffiliated', label: 'fraktionslos' } as const]
        : VOTES;
  return (
    <ul className="flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {items.map((item) => (
        <li key={item.label} className="inline-flex items-center gap-1.5">
          <VoteDot kind={item.kind} ring={kind === 'guess'} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

export default ChamberLegend;
