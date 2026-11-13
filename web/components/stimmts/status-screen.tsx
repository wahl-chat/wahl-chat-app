import type { ReactNode } from 'react';
import StimmtsLogo from './stimmts-logo';

type Props = {
  title: string;
  text: ReactNode;
  children?: ReactNode;
};

/** A whole-page message in the game's voice, for every state but play. */
function StatusScreen({ title, text, children }: Props) {
  return (
    <section className="flex animate-stimmts-screen flex-col items-center gap-8 py-14 text-center motion-reduce:animate-none">
      <StimmtsLogo className="text-[32px]" />
      <div className="flex max-w-[36ch] flex-col gap-3">
        <h1 className="font-display text-[28px] font-extrabold leading-tight tracking-[-0.02em]">
          {title}
        </h1>
        <p className="text-muted-foreground">{text}</p>
      </div>
      {children}
    </section>
  );
}

/** While the switch is read: the logo alone, so nothing flashes past. */
export function LoadingScreen() {
  return (
    <div role="status" className="flex justify-center py-14">
      <StimmtsLogo className="animate-pulse text-[32px] motion-reduce:animate-none" />
      <span className="sr-only">Lädt …</span>
    </div>
  );
}

export default StatusScreen;
