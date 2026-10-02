import { otherTopicsSentence, splitSections } from '@/lib/daily/topics';
import type { DigestSession } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ArrowRightIcon, FileTextIcon, ScaleIcon } from 'lucide-react';
import { CARD_INTERACTIVE, CARD_PLACEHOLDER, MUTED_TEXT } from './card-styles';
import TopicChip from './topic-chip';

type Props = {
  session: DigestSession;
  selectedTopics: string[];
  onOpen: () => void;
};

/** The closing line, set as an editorial pull-quote. */
export function OtherTopicsQuote({ children }: { children: string }) {
  return (
    <p className="border-l-4 border-[var(--daily-ink)] pl-3 font-display text-base italic leading-snug">
      {children}
    </p>
  );
}

export function PlenaryCard({ session, selectedTopics, onOpen }: Props) {
  const { visible, hidden } = splitSections(session.sections, selectedTopics);
  const protocolIds = session.protocols.map((p) => p.protocol_id).join(', ');

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(CARD_INTERACTIVE, 'flex w-full flex-col overflow-hidden')}
    >
      <div className="flex items-center justify-between gap-2 bg-[var(--daily-ink)] px-5 py-2 text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--daily-canvas)]">
        <span className="flex items-center gap-1.5">
          <FileTextIcon className="size-3.5" />
          Plenarsitzung
        </span>
        {protocolIds && <span>Protokoll {protocolIds}</span>}
      </div>

      <div className="flex flex-col gap-4 p-5">
        {visible.length > 0 ? (
          <ol className="flex flex-col gap-4">
            {visible.map((section, i) => (
              <li
                key={`${i}:${section.headline}`}
                className="grid grid-cols-[auto_1fr] gap-x-3"
              >
                <span className="font-display text-3xl font-black leading-none">
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div className="flex flex-col gap-1.5">
                  <TopicChip topic={section.topic} />
                  <span className="font-display text-lg font-bold leading-tight">
                    {section.headline}
                  </span>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className={cn('text-sm', MUTED_TEXT)}>
            Zu deinen Themen wurde in dieser Sitzung nicht debattiert.
          </p>
        )}

        <OtherTopicsQuote>
          {otherTopicsSentence(hidden, session.other_topics)}
        </OtherTopicsQuote>

        <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-[0.14em] underline decoration-2 underline-offset-4">
          Zusammenfassung lesen <ArrowRightIcon className="size-3.5" />
        </span>
      </div>
    </button>
  );
}

function SoonSticker() {
  return (
    <span className="absolute -top-3 right-3 rotate-3 border-2 border-[var(--daily-ink)] bg-[var(--daily-canvas)] px-1.5 py-0.5 text-[10px] font-black uppercase tracking-[0.16em] text-[var(--daily-ink)]">
      Bald
    </span>
  );
}

function Placeholder({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: string;
}) {
  return (
    <div
      className={cn(
        CARD_PLACEHOLDER,
        'relative flex flex-col gap-1.5 p-5 text-sm',
      )}
    >
      <SoonSticker />
      <span className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.16em] text-[var(--daily-ink)]">
        {icon}
        {label}
      </span>
      {children}
    </div>
  );
}

export function PlenaryPlaceholder({ children }: { children: string }) {
  return (
    <Placeholder
      icon={<FileTextIcon className="size-3.5" />}
      label="Plenarsitzung"
    >
      {children}
    </Placeholder>
  );
}

export function LegislationTeaser() {
  return (
    <Placeholder
      icon={<ScaleIcon className="size-3.5" />}
      label="Gesetzesinitiativen"
    >
      Neu eingebrachte Gesetzentwürfe zeigen wir hier bald ebenfalls.
    </Placeholder>
  );
}
