import TopicsFilterableList from '@/components/topics/topics-filterable-list';
import { Button } from '@/components/ui/button';
import {
  getExampleQuestionsShareableChatSession,
  getParties,
} from '@/lib/firebase/firebase-server';
import { buildPartyImageUrl } from '@/lib/utils';
import { ArrowLeftIcon } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';

async function TopicsPage() {
  const exampleQuestionsShareableChatSessions =
    await getExampleQuestionsShareableChatSession();
  const allParties = await getParties();
  const partiesToUse = ['spd', 'cdu', 'gruene', 'afd'];
  const parties = allParties.filter((party) =>
    partiesToUse.includes(party.party_id),
  );

  return (
    <>
      <Button variant="link" asChild className="mt-4 px-0">
        <Link href="/">
          <ArrowLeftIcon className="size-4" />
          Zur Startseite
        </Link>
      </Button>

      <div className="mt-4 flex flex-row gap-2">
        {parties.map((party) => (
          <div
            key={party.party_id}
            className="flex aspect-square items-center justify-center overflow-hidden rounded-full p-2"
            style={{
              backgroundColor: party.background_color,
            }}
          >
            <Image
              src={buildPartyImageUrl(party.party_id)}
              alt={party.name}
              width={40}
              height={40}
              className="object-contain"
            />
          </div>
        ))}
      </div>

      <h1 className="mt-4 text-2xl font-bold">Fragen zu beliebten Themen</h1>
      <p className="text-sm text-muted-foreground">
        Hier findest du Fragen zu den beliebten Themen der Parteien. Klicke auf
        eine Frage um Details zu sehen.
      </p>

      <TopicsFilterableList
        exampleQuestionsShareableChatSessions={
          exampleQuestionsShareableChatSessions
        }
      />
    </>
  );
}

export default TopicsPage;
