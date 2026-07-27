// Local Firebase emulator wiring, shared by the browser and server client SDKs.
//
// Opt-in via NEXT_PUBLIC_USE_FIREBASE_EMULATORS=true (set in web/.env.local for
// local development). When off, the SDKs talk to the real project exactly as
// before — so production is unaffected and this is a no-op unless deliberately
// enabled. Ports mirror firebase/firebase.json's emulators block.

export const FIREBASE_EMULATOR_HOST = '127.0.0.1';
export const FIRESTORE_EMULATOR_PORT = 8081;
export const AUTH_EMULATOR_PORT = 9099;

export function firebaseEmulatorsEnabled(): boolean {
  return process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATORS === 'true';
}

export function authEmulatorUrl(): string {
  return `http://${FIREBASE_EMULATOR_HOST}:${AUTH_EMULATOR_PORT}`;
}
