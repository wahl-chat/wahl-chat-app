'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    MessageSquarePlus,
    History,
    Loader2,
    AlertCircle,
    ArrowLeft,
} from 'lucide-react';
import {
    getConversationMessages,
    getConversationTopic,
    getConversationStage,
} from '@/lib/agent/agent-api';

type Screen = 'choice' | 'resume';

export default function ConversationChoiceScreen() {
    const router = useRouter();
    const startNewConversation = useAgentStore(
        (state) => state.startNewConversation
    );
    const restoreConversation = useAgentStore(
        (state) => state.restoreConversation
    );

    const [screen, setScreen] = useState<Screen>('choice');
    const [conversationId, setConversationId] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleResume = async () => {
        if (!conversationId.trim()) return;

        setIsLoading(true);
        setError(null);

        try {
            // Fetch all conversation data in parallel
            const [messagesRes, topicRes, stageRes] = await Promise.all([
                getConversationMessages(conversationId.trim()),
                getConversationTopic(conversationId.trim()),
                getConversationStage(conversationId.trim()),
            ]);

            // Map the messages to the correct format
            const messages = messagesRes.messages.map((msg) => ({
                role: (msg.role === 'human' ? 'user' : 'assistant') as
                    | 'user'
                    | 'assistant',
                content: msg.content,
            }));

            // Restore the conversation
            restoreConversation(
                conversationId.trim(),
                messages,
                topicRes.topic,
                stageRes.stage
            );

            // Update the URL to include the conversation ID
            router.replace(`/agent/${conversationId.trim()}`);
        } catch (err) {
            console.error('Error restoring conversation:', err);
            setError(
                'Konversation konnte nicht gefunden werden. Bitte überprüfe die ID.'
            );
        } finally {
            setIsLoading(false);
        }
    };

    const handleBack = () => {
        setScreen('choice');
        setConversationId('');
        setError(null);
    };

    // Resume screen
    if (screen === 'resume') {
        return (
            <div className="flex min-h-full flex-col items-center justify-center p-4 py-8">
                <div className="w-full max-w-lg space-y-6">
                    {/* Back button */}
                    <Button
                        variant="ghost"
                        onClick={handleBack}
                        className="gap-2"
                        disabled={isLoading}
                    >
                        <ArrowLeft className="size-4" />
                        Zurück
                    </Button>

                    {/* Header */}
                    <div className="text-center">
                        <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-muted">
                            <History className="size-8 text-muted-foreground" />
                        </div>
                        <h1 className="text-3xl font-bold tracking-tight">
                            Konversation fortsetzen
                        </h1>
                        <p className="mt-2 text-muted-foreground">
                            Gib deine Conversation ID ein, um fortzufahren.
                        </p>
                    </div>

                    {/* Input Card */}
                    <Card>
                        <CardContent className="space-y-4 pt-6">
                            <div className="space-y-2">
                                <Label htmlFor="conversation-id">
                                    Conversation ID
                                </Label>
                                <Input
                                    id="conversation-id"
                                    placeholder="z.B. abc123-def456-..."
                                    value={conversationId}
                                    onChange={(e) => {
                                        setConversationId(e.target.value);
                                        setError(null);
                                    }}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                            handleResume();
                                        }
                                    }}
                                    disabled={isLoading}
                                    className="font-mono"
                                    autoFocus
                                />
                            </div>

                            {error && (
                                <div className="flex items-center gap-2 rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                                    <AlertCircle className="size-4 shrink-0" />
                                    <span>{error}</span>
                                </div>
                            )}

                            <Button
                                onClick={handleResume}
                                disabled={!conversationId.trim() || isLoading}
                                className="w-full"
                                size="lg"
                            >
                                {isLoading ? (
                                    <>
                                        <Loader2 className="mr-2 size-4 animate-spin" />
                                        Laden...
                                    </>
                                ) : (
                                    'Fortsetzen'
                                )}
                            </Button>
                        </CardContent>
                    </Card>

                    <p className="text-center text-sm text-muted-foreground">
                        Du findest deine Conversation ID in der Seitenleiste während
                        eines aktiven Gesprächs.
                    </p>
                </div>
            </div>
        );
    }

    // Choice screen (default)
    return (
        <div className="flex min-h-full flex-col items-center justify-center p-4 py-8">
            <div className="w-full max-w-lg space-y-6">
                {/* Header */}
                <h1 className="text-3xl text-center font-bold tracking-tight">
                    Wie möchten Sie fortfahren?
                </h1>

                {/* New Conversation Card */}
                <Card
                    className="cursor-pointer border-2 transition-all hover:border-primary hover:shadow-md"
                    onClick={startNewConversation}
                >
                    <CardHeader>
                        <div className="flex items-center gap-4">
                            <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                                <MessageSquarePlus className="size-6" />
                            </div>
                            <div>
                                <CardTitle className="text-lg">
                                    Neue Konversation starten
                                </CardTitle>
                                <CardDescription>
                                    Lerne den Wahl Agent kennen
                                </CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                </Card>

                {/* Resume Conversation Card */}
                <Card
                    className="cursor-pointer border-2 transition-all hover:border-muted-foreground/50 hover:shadow-md"
                    onClick={() => setScreen('resume')}
                >
                    <CardHeader>
                        <div className="flex items-center gap-4">
                            <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                                <History className="size-6" />
                            </div>
                            <div>
                                <CardTitle className="text-lg">
                                    Konversation fortsetzen
                                </CardTitle>
                                <CardDescription>
                                    Bestehendes Gespräch mit Conversation ID fortsetzen
                                </CardDescription>
                            </div>
                        </div>
                    </CardHeader>
                </Card>
            </div>
        </div>
    );
}
