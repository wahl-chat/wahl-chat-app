'use client';

import { useRouter } from 'next/navigation';
import {
    Card,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { MessageSquarePlus, History } from 'lucide-react';
import { clearStoredConversation } from '@/lib/agent/conversation-storage';

interface ResumeConversationPromptProps {
    conversationId: string;
    onStartNew: () => void;
}

export default function ResumeConversationPrompt({
    conversationId,
    onStartNew,
}: ResumeConversationPromptProps) {
    const router = useRouter();

    const handleResume = () => {
        router.push(`/agent/${conversationId}`);
    };

    const handleStartNew = () => {
        clearStoredConversation();
        onStartNew();
    };

    return (
        <div className="flex min-h-full flex-col items-center justify-center p-4 py-8">
            <div className="w-full max-w-lg space-y-6">
                <div className="text-center">
                    <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-muted">
                        <History className="size-8 text-muted-foreground" />
                    </div>
                    <h1 className="text-3xl font-bold tracking-tight">
                        Du hast eine laufende Unterhaltung
                    </h1>
                    <p className="mt-2 text-muted-foreground">
                        Möchtest du diese fortsetzen oder eine neue starten?
                    </p>
                </div>

                <Card
                    className="cursor-pointer border-2 transition-all hover:border-primary hover:shadow-md"
                    onClick={handleResume}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handleResume();
                        }
                    }}
                    role="button"
                    tabIndex={0}
                >
                    <CardHeader>
                        <div className="flex items-center gap-4">
                            <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                                <History className="size-6" />
                            </div>
                            <div>
                                <CardTitle className="text-lg">Fortfahren</CardTitle>
                                <CardDescription>
                                    Setze deine bestehende Unterhaltung fort
                                </CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                </Card>

                <Card
                    className="cursor-pointer border-2 transition-all hover:border-muted-foreground/50 hover:shadow-md"
                    onClick={handleStartNew}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            handleStartNew();
                        }
                    }}
                    role="button"
                    tabIndex={0}
                >
                    <CardHeader>
                        <div className="flex items-center gap-4">
                            <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                                <MessageSquarePlus className="size-6" />
                            </div>
                            <div>
                                <CardTitle className="text-lg">
                                    Neue Unterhaltung starten
                                </CardTitle>
                                <CardDescription>
                                    Beginne ein neues Gespräch mit dem Wahl Agent
                                </CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                </Card>
            </div>
        </div>
    );
}
