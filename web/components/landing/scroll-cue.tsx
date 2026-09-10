import { ChevronDownIcon } from 'lucide-react';

type Props = {
  href: string;
};

/**
 * Tells the visitor the page continues.
 *
 * The hero fills the viewport exactly, so without a cue it reads as the whole
 * page — which is what it used to be. A real anchor rather than a scroll
 * handler: it works without JS, takes keyboard focus, and needs no scroll-mt
 * on the target because the landing page has no sticky header.
 *
 * Sits in the hero's flex flow rather than absolutely positioned, so it cannot
 * overlap the call to action on a short landscape phone.
 */
function ScrollCue({ href }: Props) {
  return (
    <a
      href={href}
      className="relative mx-auto mb-8 flex flex-col items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground md:mb-10"
    >
      Mehr erfahren
      <ChevronDownIcon
        className="size-4 animate-bounce motion-reduce:animate-none"
        aria-hidden="true"
      />
    </a>
  );
}

export default ScrollCue;
