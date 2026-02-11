'use client';

import { firebaseConfigAsUrlParams } from '@/lib/firebase/firebase-config';
import { useEffect } from 'react';

function AuthServiceWorkerProvider() {
  useEffect(() => {
    registerServiceWorker();
  }, []);

  const registerServiceWorker = async () => {
    if ('serviceWorker' in navigator) {
      await navigator.serviceWorker.register(
        `/service-worker.js?${firebaseConfigAsUrlParams}`,
        {
          scope: '/',
        },
      );
    }
  };

  return null;
}

export default AuthServiceWorkerProvider;
