import DataSources from '@/components/landing/data-sources';
import LandingFaq from '@/components/landing/landing-faq';
import { INTRO_TEXT } from '@/lib/how-to-content';
import { ArrowUpRightIcon, ChevronDownIcon } from 'lucide-react';
import Link from 'next/link';

const STEPS = [
  {
    title: 'Du fragst.',
    description:
      'Was beschäftigt dich? Stelle deine Frage und wähle die Parteien, deren Positionen du vergleichen möchtest.',
  },
  {
    title: 'Du bekommst Antworten.',
    description:
      'wahl.chat findet passende Informationen in den Dokumenten der Parteien und verlinkt die Quellen zu jeder Antwort.',
  },
  {
    title: 'Du bildest dir deine Meinung.',
    description:
      'Vergleiche die Positionen, prüfe die Originalquellen und frage nach, wenn du mehr wissen möchtest.',
  },
];

type Props = {
  sourcesHref?: string;
};

function LandingExplainer({ sourcesHref }: Props) {
  return (
    <section
      id="was-ist-wahl-chat"
      aria-labelledby="explainer-heading"
      className="w-full px-5 pb-6 md:pb-8"
    >
      <div className="mx-auto max-w-5xl overflow-hidden rounded-3xl border border-border/70 bg-muted/20">
        <div className="grid gap-4 p-5 sm:p-6 md:grid-cols-2 md:gap-8">
          <div>
            <p className="text-xs font-medium uppercase tracking-widest text-muted-foreground">
              So funktioniert wahl.chat
            </p>
            <h2
              id="explainer-heading"
              className="mt-4 text-balance text-3xl font-semibold leading-tight tracking-[-0.035em] md:text-4xl"
            >
              Weniger durchlesen.
              <br />
              Mehr durchblicken.
            </h2>
          </div>
          <div className="space-y-4 text-sm leading-relaxed text-muted-foreground">
            <p>
              wahl.chat hilft dir, die Positionen der Parteien im Gespräch zu
              verstehen. Die Antworten basieren auf Dokumenten zur ausgewählten
              Wahl und enthalten Links zu den Originalquellen.
            </p>
            <Link
              href="/how-to"
              className="inline-flex items-center gap-2 font-medium text-foreground transition-colors hover:text-muted-foreground"
            >
              Mehr zur Funktionsweise{' '}
              <ArrowUpRightIcon className="size-4" aria-hidden="true" />
            </Link>
          </div>
        </div>
        <ol className="grid gap-5 px-5 pb-5 sm:px-6 sm:pb-6 md:grid-cols-3 md:gap-0">
          {STEPS.map(({ title, description }, index) => (
            <li
              key={title}
              className="border-t border-border pt-4 md:px-4 md:first:pl-0 md:last:pr-0"
            >
              <span className="text-xs font-medium tabular-nums text-muted-foreground">
                0{index + 1}
              </span>
              <h3 className="mb-2 mt-4 text-lg font-medium tracking-tight">
                {title}
              </h3>
              <p className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            </li>
          ))}
        </ol>
        <div className="border-t border-border/70 bg-background/60 px-5 sm:px-6">
          {sourcesHref && (
            <details className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 py-4 text-sm font-medium [&::-webkit-details-marker]:hidden">
                Welche Quellen stecken dahinter?
                <ChevronDownIcon
                  className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                  aria-hidden="true"
                />
              </summary>
              <div className="pb-7">
                <p className="mb-5 text-sm leading-relaxed text-muted-foreground">
                  {INTRO_TEXT.sources}
                </p>
                <DataSources sourcesHref={sourcesHref} />
              </div>
            </details>
          )}
          <LandingFaq />
        </div>
      </div>
    </section>
  );
}

export default LandingExplainer;
