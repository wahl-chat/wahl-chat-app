'use client';

import { useState } from 'react';
import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { AgentTopic } from '@/lib/stores/agent-store';
import {
    Info,
    Users,
    TrendingUp,
    Leaf,
    CheckCircle2,
    AlertCircle,
} from 'lucide-react';

interface TopicOption {
    id: AgentTopic;
    label: string;
    description: string;
    icon: React.ReactNode;
    color: string;
    activeColor: string;
}

const TOPICS: TopicOption[] = [
    {
        id: 'Migration',
        label: 'Migration',
        description:
            'Asylpolitik, Integration, Einwanderung und gesellschaftlicher Zusammenhalt',
        icon: <Users className="size-6" />,
        color:
            'border-orange-200 hover:border-orange-400 dark:border-orange-900 dark:hover:border-orange-700',
        activeColor:
            'border-orange-500 bg-orange-50 dark:border-orange-500 dark:bg-orange-950/50',
    },
    {
        id: 'Wirtschaft',
        label: 'Wirtschaft',
        description:
            'Steuern, Arbeitsmarkt, Unternehmensförderung und wirtschaftliche Stabilität',
        icon: <TrendingUp className="size-6" />,
        color:
            'border-blue-200 hover:border-blue-400 dark:border-blue-900 dark:hover:border-blue-700',
        activeColor:
            'border-blue-500 bg-blue-50 dark:border-blue-500 dark:bg-blue-950/50',
    },
    {
        id: 'Umwelt und Klima',
        label: 'Umwelt und Klima',
        description:
            'Klimaschutz, erneuerbare Energien, Nachhaltigkeit und Umweltpolitik',
        icon: <Leaf className="size-6" />,
        color:
            'border-green-200 hover:border-green-400 dark:border-green-900 dark:hover:border-green-700',
        activeColor:
            'border-green-500 bg-green-50 dark:border-green-500 dark:bg-green-950/50',
    },
];

export default function TopicSelection() {
    const setTopic = useAgentStore((state) => state.setTopic);
    const [selectedTopic, setSelectedTopic] = useState<AgentTopic | null>(null);

    const handleContinue = () => {
        if (selectedTopic) {
            setTopic(selectedTopic);
        }
    };

    return (
        <div className="flex min-h-full flex-col items-center justify-center p-4">
            <div className="w-full max-w-2xl space-y-6">
                {/* Header */}
                <div className="text-center">
                    <h1 className="text-3xl font-bold tracking-tight">Themenauswahl</h1>
                    <p className="mt-2 text-muted-foreground">
                        Wählen Sie ein Thema für Ihr Gespräch mit dem Wahl Agent
                    </p>
                </div>

                {/* Info Card */}
                <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/30">
                    <CardContent className="flex items-start gap-3 pt-4">
                        <Info className="mt-0.5 size-5 shrink-0 text-blue-600 dark:text-blue-400" />
                        <div className="space-y-1 text-sm text-blue-900/80 dark:text-blue-100/80">
                            <p className="font-medium">
                                Bitte wählen Sie EIN Thema aus, über das Sie mit dem Wahl Agent
                                diskutieren möchten.
                            </p>
                            <p>
                                Für diese Studie haben wir einige Themen vorbereitet, die im
                                politischen Diskurs besonders häufig vorkommen.
                            </p>
                        </div>
                    </CardContent>
                </Card>

                {/* Topic Cards */}
                <div className="space-y-3">
                    <h2 className="text-sm font-medium text-muted-foreground">
                        Wählen Sie Ihr Thema:
                    </h2>

                    <div className="grid gap-3">
                        {TOPICS.map((topic) => {
                            const isSelected = selectedTopic === topic.id;

                            return (
                                <button
                                    key={topic.id}
                                    onClick={() => setSelectedTopic(topic.id)}
                                    className={cn(
                                        'relative flex items-start gap-4 rounded-lg border-2 p-4 text-left transition-all',
                                        isSelected ? topic.activeColor : topic.color,
                                        'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2'
                                    )}
                                >
                                    {/* Icon */}
                                    <div
                                        className={cn(
                                            'flex size-12 shrink-0 items-center justify-center rounded-full',
                                            isSelected
                                                ? 'bg-primary text-primary-foreground'
                                                : 'bg-muted text-muted-foreground'
                                        )}
                                    >
                                        {topic.icon}
                                    </div>

                                    {/* Content */}
                                    <div className="flex-1">
                                        <h3 className="font-semibold">{topic.label}</h3>
                                        <p className="mt-1 text-sm text-muted-foreground">
                                            {topic.description}
                                        </p>
                                    </div>

                                    {/* Selection Indicator */}
                                    {isSelected && (
                                        <CheckCircle2 className="absolute right-4 top-4 size-5 text-green-600" />
                                    )}
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Selection Status */}
                {selectedTopic ? (
                    <div className="flex items-center justify-center gap-2 text-sm text-green-600 dark:text-green-400">
                        <CheckCircle2 className="size-4" />
                        <span>
                            Ausgewähltes Thema: <strong>{selectedTopic}</strong>
                        </span>
                    </div>
                ) : (
                    <div className="flex items-center justify-center gap-2 text-sm text-amber-600 dark:text-amber-400">
                        <AlertCircle className="size-4" />
                        <span>Bitte wählen Sie ein Thema aus, um fortzufahren.</span>
                    </div>
                )}

                {/* Continue Button */}
                <div className="flex justify-center">
                    <Button
                        onClick={handleContinue}
                        disabled={!selectedTopic}
                        size="lg"
                        className="min-w-[200px]"
                    >
                        Weiter zur Diskussion
                    </Button>
                </div>
            </div>
        </div>
    );
}

