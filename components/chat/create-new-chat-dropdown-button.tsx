'use client';

import PartyCards from '@/components/party-cards';
import {
  DropdownMenu,
  DropdownMenuContent,
} from '@/components/ui/dropdown-menu';
import { useState } from 'react';
import CreateNewChatDropdownButtonTrigger from './create-new-chat-dropdown-button-trigger';

function CreateNewChatDropdownButton() {
  const [open, setOpen] = useState(false);

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <CreateNewChatDropdownButtonTrigger
        onTriggerClick={() => setOpen(true)}
      />
      <DropdownMenuContent align="end" className="w-[80vw] max-w-[300px] p-3">
        <div className="mb-2 flex flex-col">
          <h2 className="text-lg font-bold">Neuer Chat</h2>
          <p className="text-sm text-muted-foreground">
            Erstelle einen neuen Chat.
          </p>
        </div>
        <PartyCards
          gridColumns={3}
          selectable={false}
          onPartyClicked={() => setOpen(false)}
          showWahlChatButton
        />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export default CreateNewChatDropdownButton;
