import AgentHeader from '@/components/agent/agent-header';
import AgentSidebar from '@/components/agent/agent-sidebar';
import { AgentStoreProvider } from '@/components/providers/agent-store-provider';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import type { Locale } from '@/i18n/locales';
import type { Metadata } from 'next';
import { getTranslations } from 'next-intl/server';

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>;
}): Promise<Metadata> {
  const { locale } = await params;
  // The root layout has already rejected unknown locales with a 404.
  const t = await getTranslations({
    locale: locale as Locale,
    namespace: 'agent.meta',
  });

  return {
    title: t('title'),
    description: t('description'),
    robots: 'noindex, nofollow',
  };
}

interface Props {
  children: React.ReactNode;
}

export default function AgentLayout({ children }: Props) {
  return (
    <AgentStoreProvider>
      <SidebarProvider defaultOpen={true}>
        <AgentSidebar />
        <SidebarInset className="flex h-dvh flex-col overflow-hidden">
          <AgentHeader />
          <div className="flex-1 overflow-y-auto">{children}</div>
        </SidebarInset>
      </SidebarProvider>
    </AgentStoreProvider>
  );
}
