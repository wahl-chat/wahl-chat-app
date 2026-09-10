import { INTRO_TEXT, PROCESS_STEPS } from '@/lib/how-to-content';
import {
  MessageCircleQuestionIcon,
  MessageCircleReplyIcon,
  TextSearchIcon,
  WaypointsIcon,
} from 'lucide-react';

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
 * hooks and no 'use client', so it server-renders on the landing page while
 * still being usable from the client HowTo component.
 */
function HowToIntro() {
  return (
    <>
      <p>
        <span className="font-bold underline">wahl.chat</span>{' '}
        {INTRO_TEXT.main.startsWith('wahl.chat ')
          ? INTRO_TEXT.main.slice('wahl.chat '.length)
          : INTRO_TEXT.main}
        <br />
        {INTRO_TEXT.sources}
      </p>

      <p className="mt-4 text-sm font-semibold">Der Prozess ist einfach:</p>

      <ul className="[&_li]:mt-4 [&_li]:text-sm">
        {PROCESS_STEPS.map((step, index) => (
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
