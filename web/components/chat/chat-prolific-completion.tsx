'use client';

import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from '@/components/chat/responsive-drawer-dialog';
import CompletionCode from '@/components/prolific-study/completion-code';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Gift } from 'lucide-react';
import { useState } from 'react';

type Props = {
  minInteractions: number;
};

function ChatProlificCompletion({ minInteractions }: Props) {
  const prolificMessageCount = useChatStore(
    (state) => state.prolificMessageCount,
  );
  const [modalOpen, setModalOpen] = useState(false);

  const isEligible = prolificMessageCount >= minInteractions;

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
            <ResponsiveDialogTitle>Studie abgeschlossen!</ResponsiveDialogTitle>
          </ResponsiveDialogHeader>
          <CompletionCode />
        </ResponsiveDialogContent>
      </ResponsiveDialog>
    </>
  );
}

export default ChatProlificCompletion;
