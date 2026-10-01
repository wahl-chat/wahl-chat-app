import { otherTopicsSentence, splitSections } from '@/lib/daily/topics';
import type { DigestSession } from '@/lib/firebase/firebase.types';
import { cn } from '@/lib/utils';
import { ChevronRightIcon, FileTextIcon, ScaleIcon } from 'lucide-react';
import { CARD_INTERACTIVE, CARD_PLACEHOLDER } from './card-styles';
import TopicChip from './topic-chip';

type Props = {
  session: DigestSession;
  selectedTopics: string[];
  onOpen: () => void;
};

export function PlenaryCard({ session, selectedTopics, onOpen }: Props) {
  const { visible, hidden } = splitSections(session.sections, selectedTopics);
  const protocolIds = session.protocols.map((p) => p.protocol_id).join(', ');

  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(CARD_INTERACTIVE, 'flex w-full flex-col gap-3 p-4')}
    >
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <FileTextIcon className="size-3.5" />
        Plenarsitzung
        {protocolIds && <span>· Protokoll {protocolIds}</span>}
      </div>
      {visible.length > 0 ? (
        <ul className="flex flex-col gap-2.5">
          {visible.map((section, i) => (
            <li
              key={`${i}:${section.headline}`}
              className="flex flex-col gap-1"
            >
              <TopicChip topic={section.topic} />
              <span className="text-sm font-semibold leading-snug">
                {section.headline}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          Zu deinen Themen wurde in dieser Sitzung nicht debattiert.
        </p>
      )}
      <p className="text-sm text-muted-foreground">
        {otherTopicsSentence(hidden, session.other_topics)}
      </p>
      <span className="flex items-center gap-1 text-xs font-medium">
        Zusammenfassung lesen <ChevronRightIcon className="size-3.5" />
      </span>
    </button>
  );
}

export function PlenaryPlaceholder({ children }: { children: string }) {
  return (
    <div
      className={cn(
        CARD_PLACEHOLDER,
        'flex flex-col gap-1 p-4 text-sm text-muted-foreground',
      )}
    >
      <span className="flex items-center gap-2 text-xs font-medium">
        <FileTextIcon className="size-3.5" />
        Plenarsitzung
      </span>
      {children}
    </div>
  );
}

export function LegislationTeaser() {
  return (
    <div
      className={cn(
        CARD_PLACEHOLDER,
        'flex flex-col gap-1 p-4 text-sm text-muted-foreground',
      )}
    >
      <span className="flex items-center gap-2 text-xs font-medium">
        <ScaleIcon className="size-3.5" />
        Gesetzesinitiativen
      </span>
      Neu eingebrachte Gesetzentwürfe zeigen wir hier bald ebenfalls.
    </div>
  );
}
