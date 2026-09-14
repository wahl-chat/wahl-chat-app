import LandingSection from '@/components/landing/landing-section';
import LandingStats from '@/components/landing/landing-stats';
import { SITE_LINKS } from '@/lib/site-links';
import { ArrowUpRightIcon } from 'lucide-react';
import Link from 'next/link';

const WAYS_TO_HELP = [
  {
    ...SITE_LINKS.donate,
    label: 'Mit einer Spende helfen',
    description: 'Den Betrieb und die KI finanzieren.',
  },
  {
    ...SITE_LINKS.github,
    label: 'Gemeinsam weiterentwickeln',
    description: 'Den Code ansehen und mitmachen.',
  },
  {
    href: 'mailto:info@wahl.chat',
    label: 'Mit uns ins Gespräch kommen',
    description: 'Ideen, Feedback oder Lust mitzuhelfen?',
  },
];

function LandingCommunity({ electionCount }: { electionCount: number }) {
  return (
    <LandingSection
      gridPosition="top-right"
      eyebrow="Gemeinsam möglich"
      title="Viele Fragen. Eine offene Idee."
      description="wahl.chat ist ein Open-Source-Projekt für alle, die Politik besser verstehen möchten. Unser Code ist öffentlich. Mit deiner Unterstützung können wir das Angebot weiterentwickeln."
    >
      <LandingStats electionCount={electionCount} />
      <div className="grid border-t border-border/70 px-5 sm:px-6 md:grid-cols-3">
        {WAYS_TO_HELP.map(({ href, label, description }) => (
          <Link
            key={href}
            href={href}
            className="group flex flex-col gap-2 border-b border-border/70 py-4 text-muted-foreground transition-colors hover:text-foreground focus-visible:text-foreground last:border-0 md:border-b-0 md:px-4 md:first:pl-0 md:last:pr-0"
          >
            <span className="flex items-start justify-between gap-3 text-sm font-medium">
              {label}
              <ArrowUpRightIcon
                className="size-4 shrink-0 opacity-40 transition-[transform,opacity] duration-300 ease-out group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:opacity-100 group-focus-visible:-translate-y-0.5 group-focus-visible:translate-x-0.5 group-focus-visible:opacity-100 motion-reduce:transform-none motion-reduce:transition-none"
                aria-hidden="true"
              />
            </span>
            <span className="text-xs leading-relaxed text-muted-foreground">
              {description}
            </span>
          </Link>
        ))}
      </div>
    </LandingSection>
  );
}

export default LandingCommunity;
