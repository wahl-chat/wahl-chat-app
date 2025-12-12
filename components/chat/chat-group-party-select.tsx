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
  onNewChat?: (partyIds: string[]) => void;
  selectedPartyIdsInStore?: string[];
  addPartiesToChat?: boolean;
};

function ChatGroupPartySelect({
  children,
  onNewChat,
  selectedPartyIdsInStore,
  addPartiesToChat,
}: Props) {
  return (
    <ResponsiveDialog>
      <ResponsiveDialogTrigger asChild>{children}</ResponsiveDialogTrigger>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader className="text-left">
          <ResponsiveDialogTitle>Parteiauswahl</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {addPartiesToChat
              ? 'Ändere die ausgewählten Parteien.'
              : 'Wähle bis zu sieben Parteien, mit denen du den Chat starten möchtest.'}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <ChatGroupPartySelectContent
          selectedPartyIdsInStore={selectedPartyIdsInStore}
          onNewChat={onNewChat}
          addPartiesToChat={addPartiesToChat}
        />
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default ChatGroupPartySelect;
