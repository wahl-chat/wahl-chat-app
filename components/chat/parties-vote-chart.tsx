import { useChatVotingDetails } from '@/components/providers/chat-voting-details-provider';
import { useParties } from '@/components/providers/parties-provider';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import type { Vote } from '@/lib/socket.types';
import { useMemo } from 'react';
import VoteChart from './vote-chart';

type Props = {
  vote: Vote;
};

function PartiesVoteChart({ vote }: Props) {
  const { selectedPartyId, setSelectedPartyId } = useChatVotingDetails();

  const parties = useParties();
  const byParty = vote.voting_results.by_party;

  const partyNamesAndKeys = useMemo(() => {
    return byParty.map((party) => ({
      key: party.party,
      name:
        party.party === 'fraktionslose'
          ? 'Fraktionslose'
          : (parties?.find((p) => p.party_id === party.party)?.name ??
            party.party),
    }));
  }, [byParty, parties]);

  const selectedPartyData = useMemo(() => {
    return byParty.find((party) => party.party === selectedPartyId);
  }, [byParty, selectedPartyId]);

  if (!selectedPartyData) {
    return null;
  }

  return (
    <section className="flex flex-1 flex-col items-center justify-center gap-4">
      <VoteChart
        voteResults={selectedPartyData}
        memberCount={selectedPartyData.members}
      />

      <div className="flex grow flex-col items-center justify-center">
        <Select
          defaultValue={selectedPartyId}
          value={selectedPartyId}
          onValueChange={setSelectedPartyId}
        >
          <SelectTrigger className="h-8 w-[130px] rounded-lg">
            <SelectValue placeholder="Wähle eine Partei" />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {partyNamesAndKeys.map((party) => (
                <SelectItem key={party.key} value={party.key}>
                  {party.name}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
      </div>
    </section>
  );
}

export default PartiesVoteChart;
