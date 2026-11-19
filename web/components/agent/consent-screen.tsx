'use client';

import { useAgentStore } from '@/components/providers/agent-store-provider';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Info, Lock, Shield } from 'lucide-react';
import { useTranslations } from 'next-intl';

export default function ConsentScreen() {
  const t = useTranslations('agent.consent');
  const giveConsent = useAgentStore((state) => state.giveConsent);

  return (
    <div className="flex flex-col items-center p-4 py-8">
      <div className="w-full max-w-2xl space-y-6">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight">{t('title')}</h1>
          <p className="mt-2 text-muted-foreground">{t('subtitle')}</p>
        </div>

        {/* Info Card */}
        <Card className="border-blue-200 bg-blue-50/50 dark:border-blue-900 dark:bg-blue-950/30">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Info className="size-5 text-blue-600 dark:text-blue-400" />
              <CardTitle className="text-lg text-blue-900 dark:text-blue-100">
                {t('infoTitle')}
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-blue-900/80 dark:text-blue-100/80">
            <p>
              {t.rich('contribution', {
                strong: (chunks) => <strong>{chunks}</strong>,
              })}
            </p>
            <p>{t('purpose')}</p>
          </CardContent>
        </Card>

        {/* Privacy Info */}
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <Shield className="size-5 text-muted-foreground" />
              <CardTitle className="text-lg">{t('privacyTitle')}</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li className="flex items-start gap-2">
                <Lock className="mt-0.5 size-4 shrink-0 text-green-600" />
                <span>{t('privacyAnonymised')}</span>
              </li>
              <li className="flex items-start gap-2">
                <Lock className="mt-0.5 size-4 shrink-0 text-green-600" />
                <span>{t('privacyResearchOnly')}</span>
              </li>
              <li className="flex items-start gap-2">
                <Lock className="mt-0.5 size-4 shrink-0 text-green-600" />
                <span>{t('privacyConfidential')}</span>
              </li>
            </ul>
          </CardContent>
        </Card>

        {/* Consent Notice */}
        <p className="text-center text-sm text-muted-foreground">
          {t('notice')}
        </p>

        {/* Action Button */}
        <div className="flex justify-center">
          <Button
            onClick={giveConsent}
            size="lg"
            className="min-w-[200px] bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {t('agree')}
          </Button>
        </div>
      </div>
    </div>
  );
}
