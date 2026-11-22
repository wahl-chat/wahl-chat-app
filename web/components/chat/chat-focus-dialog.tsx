'use client';

import PartyCards from '@/components/party-cards';
import { useChatStore } from '@/components/providers/chat-store-provider';
import { Button } from '@/components/ui/button';
import { toggleFocus } from '@/lib/chat-focus';
import { GENERAL_CONTEXT_ID } from '@/lib/constants';
import { useState } from 'react';
import {
  ResponsiveDialog,
  ResponsiveDialogClose,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogFooter,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
} from './responsive-drawer-dialog';

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

/** Picks the parties the general chat focuses on for every next turn. */
function ChatFocusDialog({ open, onOpenChange }: Props) {
  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader className="text-left">
          <ResponsiveDialogTitle>Parteien im Fokus</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            Die Antworten gehen auf die gewählten Parteien ein, bis du sie
            wieder entfernst.
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        {open && <FocusSelection />}
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

function FocusSelection() {
  const partyIds = useChatStore((state) => state.partyIds);
  const setPartyIds = useChatStore((state) => state.setPartyIds);
  const [selected, setSelected] = useState<string[]>(() => [...partyIds]);

  return (
    <>
      <PartyCards
        className="px-4 pb-2 md:px-0 md:pb-0"
        onPartyClicked={(id) => setSelected((prev) => toggleFocus(prev, id))}
        selectedPartyIds={selected}
        contextId={GENERAL_CONTEXT_ID}
      />
      <ResponsiveDialogFooter className="pt-2">
        <ResponsiveDialogClose asChild>
          <Button className="w-full" onClick={() => setPartyIds(selected)}>
            {selected.length > 0 ? 'Fokus übernehmen' : 'Ohne Fokus fortfahren'}
          </Button>
        </ResponsiveDialogClose>
      </ResponsiveDialogFooter>
    </>
  );
}

export default ChatFocusDialog;
