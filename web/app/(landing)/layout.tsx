import LandingFooter from '@/components/landing/landing-footer';
import LandingHeader from '@/components/landing/landing-header';
import { getNextUpcomingElection } from '@/lib/elections';
import { getContexts } from '@/lib/firebase/firebase-server';

type Props = {
  children: React.ReactNode;
};

/**
 * Shell for the landing page.
 *
 * / uses its own compact header and footer around the server-rendered landing
 * content. The shared application header depends on an election context, while
 * this page lets the visitor choose that context before entering the chat.
 */
async function LandingLayout({ children }: Props) {
  const contexts = await getContexts();
  const featured = getNextUpcomingElection(contexts) ?? contexts[0];

  return (
    <>
      <LandingHeader contextId={featured?.context_id} />
      <main className="flex w-full flex-col">{children}</main>
      <LandingFooter />
    </>
  );
}

export default LandingLayout;
