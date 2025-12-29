'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { PartyPopper, Heart, RefreshCw, CheckCircle2 } from 'lucide-react';
import { useEffect, useState } from 'react';

export default function CompletionScreen() {
    const reset = useAgentStore((state) => state.reset);
    const [showConfetti, setShowConfetti] = useState(false);

    useEffect(() => {
        // Trigger confetti animation after mount
        setShowConfetti(true);
        const timer = setTimeout(() => setShowConfetti(false), 3000);
        return () => clearTimeout(timer);
    }, []);

    return (
        <div className="flex flex-col items-center p-4 py-8">
            <div className="w-full max-w-lg space-y-6">
                {/* Celebration Animation */}
                <div className="relative flex justify-center">
                    <div
                        className={`transition-all duration-500 ${showConfetti ? 'scale-110' : 'scale-100'}`}
                    >
                        <div className="flex size-24 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                            <PartyPopper className="size-12 text-green-600 dark:text-green-400" />
                        </div>
                    </div>

                    {/* Floating particles (CSS animation) */}
                    {showConfetti && (
                        <>
                            <span className="absolute -top-2 left-1/4 animate-bounce text-2xl">
                                🎉
                            </span>
                            <span
                                className="absolute -top-4 right-1/4 animate-bounce text-2xl"
                                style={{ animationDelay: '0.1s' }}
                            >
                                🎊
                            </span>
                            <span
                                className="absolute left-1/3 top-0 animate-bounce text-xl"
                                style={{ animationDelay: '0.2s' }}
                            >
                                ✨
                            </span>
                        </>
                    )}
                </div>

                {/* Thank You Card */}
                <Card className="border-green-200 bg-green-50/50 dark:border-green-900 dark:bg-green-950/30">
                    <CardHeader className="text-center">
                        <CardTitle className="flex items-center justify-center gap-2 text-2xl text-green-700 dark:text-green-300">
                            <CheckCircle2 className="size-6" />
                            Vielen Dank für Ihre Teilnahme!
                        </CardTitle>
                        <CardDescription className="text-green-600 dark:text-green-400">
                            Die Unterhaltung ist beendet.
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4 text-center">
                        <p className="text-sm text-green-800 dark:text-green-200">
                            <strong>
                                Vielen Dank, dass Sie sich die Zeit genommen haben, an diesem
                                Dialog teilzunehmen!
                            </strong>
                        </p>
                        <p className="text-sm text-green-700/80 dark:text-green-300/80">
                            Ihre Beiträge sind wertvoll für unsere Forschung zum Verständnis
                            politischer Diskussionen und Meinungsbildung.
                        </p>
                        <p className="text-sm text-green-700/80 dark:text-green-300/80">
                            Alle Ihre Antworten werden vertraulich behandelt und nur für
                            wissenschaftliche Zwecke verwendet.
                        </p>
                    </CardContent>
                </Card>

                {/* Appreciation */}
                <div className="flex items-center justify-center gap-2 text-muted-foreground">
                    <Heart className="size-4 text-red-500" />
                    <span className="text-sm">
                        Ihr Beitrag macht einen Unterschied für die Demokratie
                    </span>
                    <Heart className="size-4 text-red-500" />
                </div>

                {/* Restart Button */}
                <div className="flex justify-center">
                    <Button
                        onClick={reset}
                        variant="outline"
                        size="lg"
                        className="gap-2"
                    >
                        <RefreshCw className="size-4" />
                        Neues Gespräch starten
                    </Button>
                </div>
            </div>
        </div>
    );
}


