import { getHowToContent } from '@/lib/how-to-content';
import {
  MessageCircleQuestionIcon,
  MessageCircleReplyIcon,
  TextSearchIcon,
  WaypointsIcon,
} from 'lucide-react';
import { useLocale } from 'next-intl';

// Fewer icons than steps: the last step has never had one. Kept as-is rather
// than invented, so this stays a move and not a redesign.
const PROCESS_STEP_ICONS = [
  <MessageCircleQuestionIcon key="icon1" className="absolute left-0 top-0" />,
  <TextSearchIcon key="icon2" className="absolute left-0 top-0" />,
  <MessageCircleReplyIcon key="icon3" className="absolute left-0 top-0" />,
  <WaypointsIcon key="icon4" className="absolute left-0 top-0" />,
];

/**
 * What wahl.chat is, plus the five steps of how an answer comes about.
 *
 * Shared by /how-to and the landing page so the explanation exists once. No
 * 'use client' and only next-intl's `useLocale`, which works on both sides, so
 * it server-renders on the landing page while still being usable from the
 * client HowTo component.
 */
function HowToIntro() {
  const { introText, processSteps, labels } = getHowToContent(useLocale());
  return (
    <>
      <p>
        <span className="font-bold underline">wahl.chat</span>{' '}
        {introText.main.startsWith('wahl.chat ')
          ? introText.main.slice('wahl.chat '.length)
          : introText.main}
        <br />
        {introText.sources}
      </p>

      <p className="mt-4 text-sm font-semibold">{labels.processHeading}</p>

      <ul className="[&_li]:mt-4 [&_li]:text-sm">
        {processSteps.map((step, index) => (
          <li key={step} className="relative pl-10">
            {PROCESS_STEP_ICONS[index]}
            {step}
          </li>
        ))}
      </ul>
    </>
  );
}

export default HowToIntro;
