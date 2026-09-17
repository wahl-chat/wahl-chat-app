import 'server-only';

import { credential } from 'firebase-admin';
import {
  type App as FirebaseApp,
  getApp,
  initializeApp,
} from 'firebase-admin/app';
import { type Firestore, getFirestore } from 'firebase-admin/firestore';

// Lazily initialize the Firebase Admin app + Firestore on first use rather than
// at module load. Importing this module must not require Firebase env vars at
// build time — the env check only runs when a server function actually touches
// Firestore at request time, where credentials are present.
let _db: Firestore | undefined;

export function getAdminApp(): FirebaseApp {
  getAdminDb();
  return getApp();
}

export function getAdminDb(): Firestore {
  if (_db) {
    return _db;
  }

  let app: FirebaseApp;

  try {
    app = getApp();
  } catch (error) {
    console.log('Initializing Firebase Admin App', error);

    const { NEXT_PUBLIC_FIREBASE_PROJECT_ID, FIRESTORE_EMULATOR_HOST } =
      process.env;

    // Against the local emulator (FIRESTORE_EMULATOR_HOST set) the Admin SDK
    // routes to the emulator and needs no service-account credentials — a
    // project id is enough. Only require real creds when talking to a real
    // project.
    if (FIRESTORE_EMULATOR_HOST) {
      if (!NEXT_PUBLIC_FIREBASE_PROJECT_ID) {
        throw new Error(
          'NEXT_PUBLIC_FIREBASE_PROJECT_ID is required to use the Firestore emulator.',
        );
      }
      app = initializeApp({ projectId: NEXT_PUBLIC_FIREBASE_PROJECT_ID });
    } else {
      const { FIREBASE_CLIENT_EMAIL, FIREBASE_PRIVATE_KEY } = process.env;

      if (
        !NEXT_PUBLIC_FIREBASE_PROJECT_ID ||
        !FIREBASE_CLIENT_EMAIL ||
        !FIREBASE_PRIVATE_KEY
      ) {
        throw new Error('Missing Firebase environment variables.');
      }

      app = initializeApp({
        credential: credential.cert({
          projectId: NEXT_PUBLIC_FIREBASE_PROJECT_ID,
          clientEmail: FIREBASE_CLIENT_EMAIL,
          privateKey: FIREBASE_PRIVATE_KEY.replace(/\\n/g, '\n'),
        }),
      });
    }
  }

  _db = getFirestore(app);
  return _db;
}
