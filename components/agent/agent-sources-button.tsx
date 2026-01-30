'use client';

import { Button } from '@/components/ui/button';
import {
    Tooltip,
    TooltipContent,
    TooltipTrigger,
} from '@/components/ui/tooltip';
import type { Source } from '@/lib/stores/chat-store.types';
import { buildPdfUrl, cn, prettyDate } from '@/lib/utils';
import { BookMarkedIcon } from 'lucide-react';
import { useMemo } from 'react';
import { ChatMessageIcon } from '@/components/chat/chat-message-icon';
import {
    ResponsiveDialog,
    ResponsiveDialogContent,
    ResponsiveDialogDescription,
    ResponsiveDialogHeader,
    ResponsiveDialogTitle,
    ResponsiveDialogTrigger,
} from '@/components/chat/responsive-drawer-dialog';

type Props = {
    sources: Source[];
    messageContent: string;
};

type SourceWithDisplayNumber = Source & { displayNumber: number };

// Regex to match [party_id][N] or [party_id][N, M, ...] format
// e.g., [spd][0], [cdu][1], [spd][0, 1], [cdu][0,1,2]
const REFERENCE_PATTERN = /\[([a-z]+)]\[(\d+(?:,\s*\d+)*)]/g;

// Parse comma-separated indices from a match, e.g., "0, 1" -> [0, 1]
function parseIndices(indicesStr: string): number[] {
    return indicesStr.split(',').map((s) => Number.parseInt(s.trim(), 10));
}

// Group sources by party_id for lookup
function groupSourcesByParty(sources: Source[]): Map<string, Source[]> {
    const grouped = new Map<string, Source[]>();
    for (const source of sources) {
        if (!source.party_id) continue;
        const existing = grouped.get(source.party_id) || [];
        existing.push(source);
        grouped.set(source.party_id, existing);
    }
    return grouped;
}

function AgentSourcesButton({ sources, messageContent }: Props) {
    const [sourcesReferenced, sourcesNotReferenced] = useMemo(() => {
        const sourcesByParty = groupSourcesByParty(sources);
        const referencedKeys = new Set<string>(); // "party_id:index" format
        const orderedSources: SourceWithDisplayNumber[] = [];

        // Find all references in the message (in order of appearance)
        const matches = Array.from(messageContent.matchAll(REFERENCE_PATTERN));
        let displayNumber = 1;

        for (const match of matches) {
            const partyId = match[1];
            const indices = parseIndices(match[2]);

            for (const partyIndex of indices) {
                const key = `${partyId}:${partyIndex}`;

                // Only add if not already seen
                if (!referencedKeys.has(key)) {
                    referencedKeys.add(key);

                    const partySources = sourcesByParty.get(partyId);
                    const source = partySources?.[partyIndex];

                    if (source) {
                        orderedSources.push({
                            ...source,
                            displayNumber: displayNumber++,
                        });
                    }
                }
            }
        }

        // Find sources that weren't referenced
        const notReferenced: SourceWithDisplayNumber[] = [];
        for (const [partyId, partySources] of sourcesByParty.entries()) {
            for (let i = 0; i < partySources.length; i++) {
                const key = `${partyId}:${i}`;
                if (!referencedKeys.has(key)) {
                    notReferenced.push({
                        ...partySources[i],
                        displayNumber: displayNumber++,
                    });
                }
            }
        }

        return [orderedSources, notReferenced];
    }, [messageContent, sources]);

    if (sourcesReferenced.length === 0 && sourcesNotReferenced.length === 0) {
        return null;
    }

    return (
        <ResponsiveDialog>
            <Tooltip>
                <TooltipTrigger asChild>
                    <ResponsiveDialogTrigger asChild>
                        <Button variant="outline" className="h-8 px-2 text-xs">
                            <BookMarkedIcon className="mr-1 size-4" />
                            Quellen
                        </Button>
                    </ResponsiveDialogTrigger>
                </TooltipTrigger>
                <TooltipContent>Quellen</TooltipContent>
            </Tooltip>
            <ResponsiveDialogContent className="flex max-h-[95dvh] flex-col">
                <ResponsiveDialogHeader>
                    <ResponsiveDialogTitle>Quellen</ResponsiveDialogTitle>
                    <ResponsiveDialogDescription>
                        Klicke auf eine Quelle, um sie in einem neuen Fenster zu öffnen.
                    </ResponsiveDialogDescription>
                </ResponsiveDialogHeader>

                <div className={cn('flex grow flex-col overflow-y-auto p-4 md:p-0')}>
                    {sourcesReferenced.length > 0 && (
                        <p className="text-sm font-bold">Im Text referenziert:</p>
                    )}
                    {sourcesReferenced.map((source) => (
                        <SourceItem
                            key={`ref-${source.displayNumber}`}
                            source={source}
                        />
                    ))}
                    {sourcesNotReferenced.length > 0 && (
                        <p
                            className={cn(
                                'text-sm font-bold',
                                sourcesReferenced.length > 0 && 'mt-4'
                            )}
                        >
                            Zusätzlich analysiert:
                        </p>
                    )}
                    {sourcesNotReferenced.map((source) => (
                        <SourceItem
                            key={`notref-${source.displayNumber}`}
                            source={source}
                        />
                    ))}
                </div>
            </ResponsiveDialogContent>
        </ResponsiveDialog>
    );
}

function SourceItem({ source }: { source: SourceWithDisplayNumber }) {
    const onSourceClick = (source: Source) => {
        const url = buildPdfUrl(source);
        return window.open(url.toString(), '_blank');
    };

    return (
        <button
            className="flex flex-row items-center justify-between gap-2 rounded-md p-2 transition-colors hover:bg-muted/50"
            onClick={() => onSourceClick(source)}
            type="button"
        >
            <div className="flex grow flex-col justify-start overflow-hidden">
                <div className="flex grow flex-row items-center gap-2">
                    <div className="inline-flex items-center justify-center rounded-full bg-zinc-300 px-2 py-0.5 text-xs dark:bg-zinc-600">
                        {source.displayNumber}
                    </div>
                    <p className="grow truncate text-start">{source.source}</p>
                </div>
                {source.document_publish_date && (
                    <span className="text-left text-xs text-muted-foreground">
                        Veröffentlicht am:{' '}
                        <span className="font-bold">
                            {prettyDate(source.document_publish_date)}
                        </span>
                    </span>
                )}
            </div>
            <p className="flex h-8 items-center justify-center whitespace-nowrap rounded-md bg-muted px-2 text-xs text-muted-foreground">
                S. {source.page}
            </p>
            {source.party_id && <ChatMessageIcon partyId={source.party_id} />}
        </button>
    );
}

export default AgentSourcesButton;
