import { createContext, useContext } from 'react';

type ChatVotingDetailsContextType = {
  selectedPartyId: string;
  setSelectedPartyId: (partyId: string) => void;
};

const ChatVotingDetailsContext = createContext<ChatVotingDetailsContextType>({
  selectedPartyId: '',
  setSelectedPartyId: () => {},
});

export function ChatVotingDetailsProvider({
  children,
  selectedPartyId,
  setSelectedPartyId,
}: {
  children: React.ReactNode;
  selectedPartyId: string;
  setSelectedPartyId: (partyId: string) => void;
}) {
  return (
    <ChatVotingDetailsContext.Provider
      value={{ selectedPartyId, setSelectedPartyId }}
    >
      {children}
    </ChatVotingDetailsContext.Provider>
  );
}

export function useChatVotingDetails() {
  return useContext(ChatVotingDetailsContext);
}
