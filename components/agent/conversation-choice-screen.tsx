'use client';

import { useState } from 'react';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
    MessageSquarePlus,
    History,
    Loader2,
    AlertCircle,
} from 'lucide-react';
import {
    getConversationMessages,
    getConversationTopic,
    getConversationStage,
} from '@/lib/agent/agent-api';
import { ConversationChoiceCard } from './conversation-choice-card';

export default function ConversationChoiceScreen() {
    const startNewConversation = useAgentStore(
        (state) => state.startNewConversation
    );
    const restoreConversation = useAgentStore(
        (state) => state.restoreConversation
    );

    const [showResumeInput, setShowResumeInput] = useState(false);
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
                role: (msg.role === 'human' ? 'user' : 'assistant') as 'user' | 'assistant',
                content: msg.content,
            }));

            // Restore the conversation
            restoreConversation(
                conversationId.trim(),
                messages,
                topicRes.topic,
                stageRes.stage
            );
        } catch (err) {
            console.error('Error restoring conversation:', err);
            setError(
                'Konversation konnte nicht gefunden werden. Bitte überprüfen Sie die ID.'
            );
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex min-h-full flex-col items-center justify-center p-4 py-8">
            <div className="w-full max-w-lg space-y-6">
                {/* Header */}
                <div className="text-center">
                    <h1 className="text-3xl font-bold tracking-tight">
                        Wie möchten Sie fortfahren?
                    </h1>
                    <p className="mt-2 text-muted-foreground">
                        Starten Sie eine neue Konversation oder setzen Sie eine
                        bestehende fort.
                    </p>
                </div>

                {/* New Conversation Button */}
                <ConversationChoiceCard
                    icon={MessageSquarePlus}
                    title="Neue Konversation starten"
                    description="Beginnen Sie ein neues Gespräch mit dem Wahl Agent"
                    onClick={startNewConversation}
                    variant="primary"
                />

                {/* Resume Conversation */}
                {!showResumeInput ? (
                    <ConversationChoiceCard
                        icon={History}
                        title="Konversation fortsetzen"
                        description="Setzen Sie ein bestehendes Gespräch fort"
                        onClick={() => setShowResumeInput(true)}
                        variant="secondary"
                    />
                ) : (
                    <Card className="border-2 border-muted-foreground/30 transition-all">
                        <ConversationChoiceCard
                            icon={History}
                            title="Konversation fortsetzen"
                            description="Setzen Sie ein bestehendes Gespräch fort"
                            variant="secondary"
                            className="border-0 shadow-none"
                        />
                        <CardContent className="space-y-4 pt-0">
                            <div className="space-y-2">
                                <Label htmlFor="conversation-id">
                                    Conversation ID
                                </Label>
                                <Input
                                    id="conversation-id"
                                    placeholder="Geben Sie Ihre Conversation ID ein..."
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
                                />
                            </div>

                            {error && (
                                <div className="flex items-center gap-2 text-sm text-destructive">
                                    <AlertCircle className="size-4" />
                                    <span>{error}</span>
                                </div>
                            )}

                            <div className="flex gap-2">
                                <Button
                                    variant="outline"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        setShowResumeInput(false);
                                        setConversationId('');
                                        setError(null);
                                    }}
                                    disabled={isLoading}
                                >
                                    Abbrechen
                                </Button>
                                <Button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleResume();
                                    }}
                                    disabled={!conversationId.trim() || isLoading}
                                    className="flex-1"
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
                            </div>
                        </CardContent>
                    </Card>
                )}
            </div>
        </div>
    );
}

