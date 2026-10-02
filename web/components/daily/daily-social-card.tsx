import InstagramIcon from '@/components/icons/instagram-icon';
import LinkedInIcon from '@/components/icons/linkedin-icon';
import XIcon from '@/components/icons/x-icon';
import { socialMediaConfig } from '@/lib/contact-config';
import { cn } from '@/lib/utils';
import { CARD_SURFACE, PRESSABLE } from './card-styles';

const CHANNELS = [
  {
    href: socialMediaConfig.instagram,
    label: 'Instagram',
    Icon: InstagramIcon,
  },
  { href: socialMediaConfig.linkedin, label: 'LinkedIn', Icon: LinkedInIcon },
  { href: socialMediaConfig.x, label: 'X', Icon: XIcon },
];

/** Where else to follow wahl.chat; sits beside the newsletter CTA. */
function DailySocialCard() {
  return (
    <div
      className={cn(
        CARD_SURFACE,
        'flex items-center justify-between gap-4 p-4 md:flex-col md:items-start md:justify-center md:gap-3 md:px-5',
      )}
    >
      <p className="font-display text-xl font-black leading-tight md:text-2xl">
        Auch auf …
      </p>
      <ul className="flex items-center gap-3">
        {CHANNELS.map(({ href, label, Icon }) => (
          <li key={label}>
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`wahl.chat auf ${label}`}
              className={cn(
                PRESSABLE,
                // White tile in both themes: the brand icons are drawn for a
                // light background (the X mark is ink-coloured).
                'flex size-11 items-center justify-center rounded-[4px] border-2 border-[var(--daily-ink)] bg-white shadow-[3px_3px_0_0_var(--daily-ink)]',
              )}
            >
              <Icon className="size-6 text-[#1A1A1A]" />
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default DailySocialCard;
