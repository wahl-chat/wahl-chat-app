import { AgentStoreProvider } from '@/components/providers/agent-store-provider';
import type { Metadata } from 'next';
import AgentHeader from '@/components/agent/agent-header';
import AgentSidebar from '@/components/agent/agent-sidebar';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';

export const metadata: Metadata = {
    title: 'Wahl Agent | wahl.chat',
    description:
        'Dein persönlicher Begleiter zur politischen Meinungsbildung. Diskutiere politische Themen mit dem Wahl Agent.',
};

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
