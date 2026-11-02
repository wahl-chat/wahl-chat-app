import { useTranslations } from 'next-intl';
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
  contextId?: string;
};

function ChatGroupPartySelect({
  children,
  onNewChat,
  selectedPartyIdsInStore,
  addPartiesToChat,
  contextId,
}: Props) {
  const t = useTranslations('chat.partySelect');
  return (
    <ResponsiveDialog>
      <ResponsiveDialogTrigger asChild>{children}</ResponsiveDialogTrigger>
      <ResponsiveDialogContent>
        <ResponsiveDialogHeader className="text-left">
          <ResponsiveDialogTitle>{t('title')}</ResponsiveDialogTitle>
          <ResponsiveDialogDescription>
            {addPartiesToChat ? t('descriptionChange') : t('descriptionStart')}
          </ResponsiveDialogDescription>
        </ResponsiveDialogHeader>
        <ChatGroupPartySelectContent
          selectedPartyIdsInStore={selectedPartyIdsInStore}
          onNewChat={onNewChat}
          addPartiesToChat={addPartiesToChat}
          contextId={contextId}
        />
      </ResponsiveDialogContent>
    </ResponsiveDialog>
  );
}

export default ChatGroupPartySelect;
