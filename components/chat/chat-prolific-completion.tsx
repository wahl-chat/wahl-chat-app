'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import { getProlificCompletionCode } from '@/lib/study/prolific-server';
import { Check, Copy, Gift } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { toast } from 'sonner';

type Props = {
  minInteractions: number;
};

function ChatProlificCompletion({ minInteractions }: Props) {
  const prolificMessageCount = useChatStore(
    (state) => state.prolificMessageCount,
  );
  const [modalOpen, setModalOpen] = useState(false);
  const [completionCode, setCompletionCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const isEligible = prolificMessageCount >= minInteractions;

  useEffect(() => {
    if (isEligible && !completionCode) {
      getProlificCompletionCode().then(setCompletionCode);
    }
  }, [isEligible, completionCode]);

  const handleCopy = useCallback(async () => {
    if (!completionCode) return;
    await navigator.clipboard.writeText(completionCode);
    setCopied(true);
    toast.success('Code in die Zwischenablage kopiert!');
    setTimeout(() => setCopied(false), 2000);
  }, [completionCode]);

  if (!isEligible) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setModalOpen(true)}
        className="mb-3 flex w-full cursor-pointer items-center gap-2 rounded-lg border-2 border-green-500 bg-green-50 p-3 text-left transition-colors hover:bg-green-100 dark:bg-green-950 dark:hover:bg-green-900"
      >
        <Gift className="size-5 shrink-0 text-green-600 dark:text-green-400" />
        <div className="flex-1">
          <p className="font-semibold text-green-800 dark:text-green-200">
            Studie abgeschlossen!
          </p>
          <p className="text-sm text-green-700 dark:text-green-300">
            Klicke hier, um deinen Abschlusscode zu erhalten.
          </p>
        </div>
      </button>

      <ResponsiveDialog open={modalOpen} onOpenChange={setModalOpen}>
        <ResponsiveDialogContent>
          <ResponsiveDialogHeader>
            <ResponsiveDialogTitle>
              Vielen Dank für deine Teilnahme!
            </ResponsiveDialogTitle>
            <ResponsiveDialogDescription>
              Kopiere den folgenden Code, um die Studie auf Prolific
              abzuschliessen.
            </ResponsiveDialogDescription>
          </ResponsiveDialogHeader>
          <div className="px-4 md:px-0">
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-md bg-muted px-4 py-3 font-mono text-lg font-bold">
                {completionCode ?? 'Laden...'}
              </code>
              <Button
                variant="outline"
                size="icon"
                onClick={handleCopy}
                disabled={!completionCode}
              >
                {copied ? (
                  <Check className="size-4 text-green-600" />
                ) : (
                  <Copy className="size-4" />
                )}
              </Button>
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              Du kannst diesen Tab jetzt schliessen und den Code auf Prolific
              eingeben.
            </p>
          </div>
        </ResponsiveDialogContent>
      </ResponsiveDialog>
    </>
  );
}

export default ChatProlificCompletion;
