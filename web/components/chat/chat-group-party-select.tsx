import ChatGroupPartySelectContent from './chat-group-party-select-content';
import {
  ResponsiveDialog,
  ResponsiveDialogContent,
  ResponsiveDialogDescription,
  ResponsiveDialogHeader,
  ResponsiveDialogTitle,
  ResponsiveDialogTrigger,
} from './responsive-drawer-dialog';

type Props = {
  children: React.ReactNode;
  onApplySelection?: (partyIds: string[]) => void;
  onNewChat?: (partyIds: string[]) => void;
  selectedPartyIdsInStore?: string[];
  addPartiesToChat?: boolean;
  contextId?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
};

function ChatGroupPartySelect({
  children,
  onNewChat,
  onApplySelection,
  selectedPartyIdsInStore,
  addPartiesToChat,
  contextId,
  open,
  onOpenChange,
}: Props) {
  return (
    <ResponsiveDialog open={open} onOpenChange={onOpenChange}>
      <ResponsiveDialogTrigger asChild>{children}</ResponsiveDialogTrigger>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader className="text-left">
          <ResponsiveDialogTitle>Parteiauswahl</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {onApplySelection
              ? 'Wähle bis zu sieben Parteien für deine Frage. Du kannst die Auswahl jederzeit ändern.'
              : addPartiesToChat
                ? 'Ändere die ausgewählten Parteien.'
                : 'Wähle bis zu sieben Parteien, mit denen du den Chat starten möchtest.'}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <ChatGroupPartySelectContent
          selectedPartyIdsInStore={selectedPartyIdsInStore}
          onNewChat={onNewChat}
          onApplySelection={onApplySelection}
          addPartiesToChat={addPartiesToChat}
          contextId={contextId}
        />
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default ChatGroupPartySelect;
