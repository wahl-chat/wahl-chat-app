import { AgentStoreProvider } from '@/components/providers/agent-store-provider';
import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Wahl Agent',
    description:
        'Ihr persönlicher Begleiter zur politischen Meinungsbildung. Diskutieren Sie politische Themen mit dem Wahl Agent.',
};

interface Props {
    children: React.ReactNode;
}

export default function AgentLayout({ children }: Props) {
    return (
        <AgentStoreProvider>
            <main className="flex min-h-dvh flex-col bg-background">{children}</main>
        </AgentStoreProvider>
    );
}

