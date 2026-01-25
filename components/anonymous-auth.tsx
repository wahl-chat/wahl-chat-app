'use client';

import {
  auth,
  getUser,
  updateUser as updateUserFirebase,
} from '@/lib/firebase/firebase';
import {
  type UserInfo,
  type UserMetadata,
  signInAnonymously,
} from 'firebase/auth';
import type { Timestamp } from 'firebase/firestore';
import { createContext, useContext, useEffect, useState } from 'react';
import { toast } from 'sonner';

export type WahlChatUser = {
  survey_status?: {
    // where closed just means that the user clicked on the close button on the top right corner of the banner
    state: 'opened' | 'closed';
    timestamp: Date | Timestamp;
  } | null;
  newsletter_allowed?: boolean;
  clicked_away_login_reminder?: Date | Timestamp;
  keep_up_to_date_email?: string;
};

export type SerializableFirebaseUser = UserInfo & {
  uid: string;
  emailVerified: boolean;
  isAnonymous: boolean;
  providerData: UserInfo[];
  metadata: UserMetadata;
};

export type FullUser = SerializableFirebaseUser & WahlChatUser;

type AnonymousAuthContextType = {
  user: FullUser | null;
  loading: boolean;
  updateUser: (data: Partial<WahlChatUser>) => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AnonymousAuthContext = createContext<AnonymousAuthContextType>({
  user: null,
  loading: true,
  updateUser: async () => {},
  refreshUser: async () => {},
});

export const useAnonymousAuth = () => {
  return useContext(AnonymousAuthContext);
};

export function AnonymousAuthProvider({
  children,
  user: initialUser,
}: {
  children: React.ReactNode;
  user: FullUser | null;
}) {
  const [user, setUser] = useState<FullUser | null>(initialUser);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    auth.onAuthStateChanged(async (user) => {
      if (user) {
        setUser(user);

        fetchUser(user.uid);
      } else {
        createSession();
      }
    });
  }, []);

  async function fetchUser(uid: string) {
    const user = await getUser(uid);
    setUser((currUser) => {
      if (!currUser) {
        return null;
      }

      return {
        ...currUser,
        ...user,
      };
    });
    setLoading(false);
  }

  async function updateUser(data: Partial<WahlChatUser>) {
    if (!user?.uid) return;

    await updateUserFirebase(user?.uid, data);
    await fetchUser(user?.uid);
  }

  async function refreshUser() {
    setLoading(true);

    const user = auth.currentUser;

    setUser((currUser) =>
      currUser
        ? {
            ...currUser,
            ...user,
          }
        : null,
    );

    if (user) await fetchUser(user.uid);
  }

  async function createSession() {
    try {
      await signInAnonymously(auth);
    } catch (error) {
      console.error(error);

      toast.error(
        'Es ist ein Fehler aufgetreten. Bitte lade die Seite erneut.',
      );
    }
  }

  return (
    <AnonymousAuthContext.Provider
      value={{ user, updateUser, loading, refreshUser }}
    >
      {children}
    </AnonymousAuthContext.Provider>
  );
}
