import { Button } from '@/components/ui/button';
import { clearProlificMetadata } from '@/lib/prolific-study/prolific-metadata';
import { getProlificCompletionCode } from '@/lib/prolific-study/prolific-server';
import { Check, Copy } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

function CompletionCode() {
  const t = useTranslations('common.prolific');
  const [completionCode, setCompletionCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    getProlificCompletionCode().then(setCompletionCode);
  }, []);

  useEffect(() => {
    clearProlificMetadata();
  }, []);

  const handleCopy = useCallback(async () => {
    if (!completionCode) return;
    await navigator.clipboard.writeText(completionCode);
    setCopied(true);
    toast.success(t('copied'));
    setTimeout(() => setCopied(false), 2000);
  }, [completionCode, t]);

  return (
    <>
      <div className="rounded-lg border-2 border-green-500 bg-green-50 p-4 dark:bg-green-950">
        <h2 className="text-lg font-bold text-green-800 dark:text-green-200">
          {t('thanks')}
        </h2>
        <p className="mt-1 text-sm text-green-700 dark:text-green-300">
          {t('instructions')}
        </p>
        <div className="mt-3 flex items-center gap-2">
          <code className="flex-1 rounded-md bg-white px-4 py-2 font-mono text-lg font-bold text-green-900 dark:bg-green-900 dark:text-green-100">
            {completionCode ?? t('codeUnavailable')}
          </code>
          <Button
            variant="outline"
            size="icon"
            onClick={handleCopy}
            disabled={!completionCode}
            aria-label={t('copyCode')}
          >
            {copied ? (
              <Check className="size-4 text-green-600" />
            ) : (
              <Copy className="size-4" />
            )}
          </Button>
        </div>
      </div>
    </>
  );
}
export default CompletionCode;
