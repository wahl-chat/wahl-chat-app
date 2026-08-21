// Local Firebase emulator wiring, shared by the browser and server client SDKs.
//
// Opt-in via NEXT_PUBLIC_USE_FIREBASE_EMULATORS=true (set in web/.env.local for
// local development). When off, the SDKs talk to the real project exactly as
// before — so production is unaffected and this is a no-op unless deliberately
// enabled. Ports mirror firebase/firebase.json's emulators block.

// In the browser, follow the hostname the page was loaded from so a phone on
// the same LAN (http://<mac-ip>:3000) reaches the emulators on the Mac instead
// of itself; on the server 127.0.0.1 stays correct.
export const FIREBASE_EMULATOR_HOST =
  typeof window === 'undefined' ? '127.0.0.1' : window.location.hostname;
export const FIRESTORE_EMULATOR_PORT = 8081;
export const AUTH_EMULATOR_PORT = 9099;

export function firebaseEmulatorsEnabled(): boolean {
  return process.env.NEXT_PUBLIC_USE_FIREBASE_EMULATORS === 'true';
}

export function authEmulatorUrl(): string {
  return `http://${FIREBASE_EMULATOR_HOST}:${AUTH_EMULATOR_PORT}`;
}
