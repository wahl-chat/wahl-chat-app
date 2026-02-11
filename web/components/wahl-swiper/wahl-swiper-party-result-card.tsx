import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { PartyDetails } from '@/lib/party-details';
import { buildPartyImageUrl, cn } from '@/lib/utils';
import type {
  PartiesScoreResult,
  ThesesScoreResult,
} from '@/lib/wahl-swiper/wahl-swiper.types';
import { CheckIcon, MessageSquareIcon, XIcon } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

const WAHL_SWIPER_PARTY_IDS = [
  'afd',
  'cdu',
  'fdp',
  'gruene',
  'linke',
  'spd',
  'bsw',
];

type Props = {
  party: PartyDetails;
  score: PartiesScoreResult[string];
};

function WahlSwiperPartyResultCard({ party, score }: Props) {
  const prettyScore = score.score.toFixed(1);

  const chatLink = `/session?party_id=${party.party_id}`;

  const sortedTheses = score.theses.sort((a, b) => {
    if (a.thesis.topic === b.thesis.topic) {
      return a.thesis.question.localeCompare(b.thesis.question);
    }
    return a.thesis.topic.localeCompare(b.thesis.topic);
  });

  const consensusTheses = sortedTheses.filter((thesis) => thesis.consensus);
  const notConsensusTheses = sortedTheses.filter((thesis) => !thesis.consensus);

  return (
    <AccordionItem
      className="relative flex w-full flex-col overflow-hidden rounded-md border border-border"
      value={party.party_id}
    >
      <AccordionTrigger className="relative flex w-full flex-row items-center p-4">
        <div
          className="absolute left-0 top-0 h-full bg-primary/5"
          style={{
            width: `${score.score}%`,
          }}
        />
        <div className="z-10 flex grow flex-row items-center gap-4">
          <div
            className="flex aspect-square size-[40px] items-center justify-center rounded-full"
            style={{
              backgroundColor: party.background_color,
            }}
          >
            <Image
              src={buildPartyImageUrl(party.party_id)}
              alt={party.name}
              width={30}
              height={30}
            />
          </div>
          <p className="font-medium text-foreground">{party.name}</p>
        </div>
        <h2 className="z-10 mr-2 text-xl font-bold no-underline">
          {prettyScore}%
        </h2>
      </AccordionTrigger>

      <AccordionContent>
        <Separator />

        <div className="flex flex-col gap-2 p-4">
          <h2 className="font-bold">Konsens zwischen {party.name} und dir:</h2>
          <p className="text-sm text-muted-foreground">
            {party.name} stimmt mit dir in{' '}
            <span className="font-bold">
              {consensusTheses.length} von {sortedTheses.length}
            </span>{' '}
            Fragen überein.
          </p>
          <div className="flex w-fit flex-row items-center justify-start gap-2 rounded-md border border-border bg-muted p-2">
            <p className="w-8 text-center text-xl">💡</p>
            <p className="text-sm text-muted-foreground">
              Klicke auf eine Frage für weitere Informationen.
            </p>
          </div>
        </div>

        <div className="grid gap-2">
          <Table>
            <TableHeader className="bg-muted">
              <TableRow>
                <TableHead>Frage</TableHead>
                <TableHead className="min-w-[100px] text-right">
                  Stimme zu
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <span className="mx-4 mt-4 block w-fit rounded-md bg-green-500/10 px-2 py-1 text-xs text-green-500">
                Konsens
              </span>

              {consensusTheses.map((thesis) => (
                <ThesisRow key={thesis.thesis.id} thesis={thesis} />
              ))}

              <span className="mx-4 mt-4 block w-fit rounded-md bg-red-500/10 px-2 py-1 text-xs text-red-500">
                Kein Konsens
              </span>

              {notConsensusTheses.map((thesis) => (
                <ThesisRow key={thesis.thesis.id} thesis={thesis} />
              ))}
            </TableBody>
          </Table>

          <Button variant="secondary" className="mx-4" asChild>
            <Link href={chatLink}>
              <MessageSquareIcon />
              Zum Chat
            </Link>
          </Button>
        </div>
      </AccordionContent>
    </AccordionItem>
  );
}

const ThesisRow = ({ thesis }: { thesis: ThesesScoreResult[number] }) => {
  const searchParams = new URLSearchParams();
  WAHL_SWIPER_PARTY_IDS.forEach((partyId) => {
    searchParams.append('party_id', partyId);
  });
  searchParams.append('q', thesis.thesis.question);

  const link = `/session?${searchParams.toString()}`;

  const agree = thesis.userStance === 'yes';

  return (
    <TableRow>
      <TableCell className="font-semibold">
        <Link href={link} target="_blank" className="hover:underline">
          {thesis.thesis.question}
        </Link>
      </TableCell>
      <TableCell className="flex items-center justify-end">
        <div
          className={cn(
            'flex flex-row items-center justify-center rounded-full p-2 w-fit aspect-square',
            agree && 'text-green-500 bg-green-500/10',
            !agree && 'text-red-500 bg-red-500/10',
          )}
        >
          {agree ? (
            <CheckIcon className="size-4" />
          ) : (
            <XIcon className="size-4" />
          )}
        </div>
      </TableCell>
    </TableRow>
  );
};

export default WahlSwiperPartyResultCard;
