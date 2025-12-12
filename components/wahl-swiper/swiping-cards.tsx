import { useWahlSwiperStore } from '@/components/providers/wahl-swiper-store-provider';
import { Progress } from '@/components/ui/progress';
import { ChevronsRightIcon, HeartIcon, XIcon } from 'lucide-react';
import ThesisCard from './thesis-card';
import WahlSwiperButton from './wahl-swiper-button';

function SwipingCards() {
  const currentThesesStack = useWahlSwiperStore((state) => state.thesesStack);
  const progress = useWahlSwiperStore(
    (state) =>
      ((state.allTheses.length - state.thesesStack.length) /
        state.allTheses.length) *
      100,
  );
  const removeCard = useWahlSwiperStore((state) => state.removeCard);
  const handleBack = useWahlSwiperStore((state) => state.back);

  const handleDislike = () => removeCard('no');
  const handleSkip = () => removeCard('skip');
  const handleLike = () => removeCard('yes');

  return (
    <div className="flex flex-col md:gap-4">
      <Progress value={progress} className="my-4 h-2 w-full" />
      <div className="relative mx-auto flex h-[200px] w-full max-w-80 items-center justify-center [@media(min-height:600px)]:aspect-square [@media(min-height:650px)]:h-auto">
        {currentThesesStack.map((card, index) => (
          <ThesisCard
            key={card.id}
            active={index === currentThesesStack.length - 1}
            removeCard={removeCard}
            card={card}
            canGoBack={progress > 0}
            handleBack={handleBack}
          />
        ))}
      </div>

      <div className="mx-auto mt-6 flex flex-row items-center justify-center gap-4">
        <WahlSwiperButton type="no" onClick={handleDislike} />
        <WahlSwiperButton type="skip" onClick={handleSkip} />
        <WahlSwiperButton type="yes" onClick={handleLike} />
      </div>

      <section className="mx-auto mt-6 flex flex-row flex-wrap justify-center gap-4 text-xs text-muted-foreground">
        <div className="flex flex-row items-center gap-2">
          <XIcon className="size-4 text-red-500" />
          <p>Nein</p>
        </div>
        <div className="flex flex-row items-center gap-2">
          <ChevronsRightIcon className="size-4 text-gray-500" />
          <p>Überspringen</p>
        </div>
        <div className="flex flex-row items-center gap-2">
          <HeartIcon className="size-4 text-green-500" />
          <p>Ja</p>
        </div>
      </section>
    </div>
  );
}

export default SwipingCards;
