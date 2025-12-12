import { useChatVotingDetails } from '@/components/providers/chat-voting-details-provider';
import type { Vote } from '@/lib/socket.types';

type Props = {
  vote: Vote;
};

function ChatVotingBehaviorDetailJustification({ vote }: Props) {
  const { selectedPartyId } = useChatVotingDetails();

  const party = vote.voting_results.by_party.find(
    (party) => party.party === selectedPartyId,
  );

  if (!party || !party.justification) return null;

  return (
    <>
      <h2 className="pb-2 pt-4 text-base font-bold">Begründung</h2>
      <p className="text-sm text-muted-foreground">{party.justification}</p>
    </>
  );
}

export default ChatVotingBehaviorDetailJustification;
