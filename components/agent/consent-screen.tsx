'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import { Info, Shield, Lock, FileText } from 'lucide-react';

export default function ConsentScreen() {
    const giveConsent = useAgentStore((state) => state.giveConsent);

    return (
        <div className="flex flex-col items-center p-4 py-8">
            <div className="w-full max-w-2xl space-y-6">
                {/* Header */}
                <div className="text-center">
                    <h1 className="text-3xl font-bold tracking-tight">
                        Willkommen zum Wahl Agent
                    </h1>
                    <p className="mt-2 text-muted-foreground">
                        Dein persönlicher Begleiter zur politischen Meinungsbildung
                    </p>
                </div>

                {/* Info Card */}
                <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/30">
                    <CardHeader className="pb-3">
                        <div className="flex items-center gap-2">
                            <Info className="size-5 text-blue-600 dark:text-blue-400" />
                            <CardTitle className="text-lg text-blue-900 dark:text-blue-100">
                                Wichtige Informationen vor Beginn
                            </CardTitle>
                        </div>
                    </CardHeader>
                    <CardContent className="space-y-4 text-sm text-blue-900/80 dark:text-blue-100/80">
                        <p>
                            Mit der Teilnahme an dieser Forschungsstudie trägst du deinen Teil
                            zu einer gesunden Demokratie in Deutschland bei.{' '}
                            <strong>Vielen Dank dafür!</strong>
                        </p>
                        <p>
                            Politik ist ein komplexes und häufig emotionales Thema. Gerade
                            deshalb ist es wichtig, sich eine fundierte Meinung zu bilden. Der
                            Wahl Agent wird dich in dem folgenden Gespräch dabei unterstützen,
                            deine Sorgen zu schildern und deine persönliche Ideallösung zu
                            formulieren, um die Partei zu finden, die am besten zu dir
                            passt.
                        </p>
                    </CardContent>
                </Card>

                {/* Data Collection Info */}
                <Card>
                    <CardHeader className="pb-3">
                        <div className="flex items-center gap-2">
                            <FileText className="size-5 text-muted-foreground" />
                            <CardTitle className="text-lg">Datenerhebung</CardTitle>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <ul className="space-y-2 text-sm text-muted-foreground">
                            <li className="flex items-start gap-2">
                                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-muted-foreground" />
                                <span>
                                    Wir werden während dieser Konversation anonymisierte
                                    Informationen sammeln
                                </span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-muted-foreground" />
                                <span>
                                    Diese umfassen das Alter, die Region, den Familienstand und
                                    den Beruf
                                </span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-muted-foreground" />
                                <span>
                                    Deine Antworten und Perspektiven zu politischen Themen werden
                                    aufgezeichnet
                                </span>
                            </li>
                        </ul>
                    </CardContent>
                </Card>

                {/* Privacy Info */}
                <Card>
                    <CardHeader className="pb-3">
                        <div className="flex items-center gap-2">
                            <Shield className="size-5 text-muted-foreground" />
                            <CardTitle className="text-lg">
                                Datenschutz & Anonymisierung
                            </CardTitle>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <ul className="space-y-2 text-sm text-muted-foreground">
                            <li className="flex items-start gap-2">
                                <Lock className="mt-0.5 size-4 shrink-0 text-green-600" />
                                <span>Alle Antworten werden anonymisiert</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <Lock className="mt-0.5 size-4 shrink-0 text-green-600" />
                                <span>
                                    Deine Informationen werden ausschließlich für wissenschaftliche
                                    Forschungszwecke verwendet
                                </span>
                            </li>
                            <li className="flex items-start gap-2">
                                <Lock className="mt-0.5 size-4 shrink-0 text-green-600" />
                                <span>
                                    Die Konversation ist vertraulich und wird nicht an Dritte
                                    weitergegeben
                                </span>
                            </li>
                        </ul>
                    </CardContent>
                </Card>

                {/* Consent Notice */}
                <p className="text-center text-sm text-muted-foreground">
                    Durch Klicken auf &quot;Ich stimme zu&quot; bestätigst du, dass du
                    damit einverstanden bist, an dieser Forschungsstudie teilzunehmen.
                </p>

                {/* Action Button */}
                <div className="flex justify-center">
                    <Button
                        onClick={giveConsent}
                        size="lg"
                        className="min-w-[200px] bg-primary text-primary-foreground hover:bg-primary/90"
                    >
                        Ich stimme zu
                    </Button>
                </div>
            </div>
        </div>
    );
}
