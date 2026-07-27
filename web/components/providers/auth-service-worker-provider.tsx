'use client';

import { firebaseConfigAsUrlParams } from '@/lib/firebase/firebase-config';
import {
  authEmulatorUrl,
  firebaseEmulatorsEnabled,
} from '@/lib/firebase/firebase-emulators';
import { useEffect } from 'react';

function AuthServiceWorkerProvider() {
  useEffect(() => {
    registerServiceWorker();
  }, []);

  const registerServiceWorker = async () => {
    if ('serviceWorker' in navigator) {
      // In emulator mode the worker must sign into the SAME Auth emulator as
      // the page SDK — otherwise it silently authenticates against the real
      // project while local development runs against the emulator.
      const params = new URLSearchParams(firebaseConfigAsUrlParams);
      if (firebaseEmulatorsEnabled()) {
        params.set('authEmulatorUrl', authEmulatorUrl());
      }
      await navigator.serviceWorker.register(`/service-worker.js?${params}`, {
        scope: '/',
      });
    }
  };

  return null;
}

export default AuthServiceWorkerProvider;
