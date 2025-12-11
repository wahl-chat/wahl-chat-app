import type { PartyDetails } from '@/lib/party-details';
import { UserIcon, UsersIcon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';

type Props = {
  parties: PartyDetails[];
};

function PartyDetailPopover({ parties }: Props) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="size-7">
          {parties.length > 1 ? <UsersIcon /> : <UserIcon />}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        align="start"
        className="max-h-[70vh] w-72 overflow-y-auto text-xs text-muted-foreground md:w-80"
        collisionPadding={{ right: 12 }}
      >
        {parties.map((party, index) => (
          <div key={party.party_id}>
            <h1 className="text-sm font-bold text-foreground">
              {party.long_name}
            </h1>
            <p className="text-muted-foreground">{party.description}</p>
            <Separator className="my-2" />
            <p>
              Spitzenkandidat*in:{' '}
              <span className="font-bold">{party.candidate}</span>
            </p>
            <p>
              Lerne mehr über die Partei auf{' '}
              <a href={party.website_url} target="_blank" className="underline">
                {party.website_url}
              </a>
            </p>
            <p>
              Oder lese das{' '}
              <a
                href={party.election_manifesto_url}
                target="_blank"
                className="underline"
              >
                Wahlprogramm
              </a>
            </p>
            {index < parties.length - 1 && <Separator className="my-2" />}
          </div>
        ))}
      </PopoverContent>
    </Popover>
  );
}

export default PartyDetailPopover;
