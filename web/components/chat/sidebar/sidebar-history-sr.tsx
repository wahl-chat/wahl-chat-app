import {
  getCurrentUser,
  getUsersChatSessions,
} from '@/lib/firebase/firebase-server';
import SidebarHistory from './sidebar-history';

async function getChatHistory() {
  const user = await getCurrentUser();
  if (!user) return;

  return getUsersChatSessions(user.uid);
}

async function SidebarHistorySr() {
  const history = await getChatHistory();

  return <SidebarHistory history={history} />;
}

export default SidebarHistorySr;
