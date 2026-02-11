type SyncIdTokenMessage = {
  type: 'SYNC_ID_TOKEN';
};

type IdTokenMessage = {
  type: 'ID_TOKEN';
  idToken: string | null;
};

type SWClientMessage = SyncIdTokenMessage;
type SWServiceWorkerMessage = IdTokenMessage;

export async function waitForServiceWorkerIsAuthenticated(): Promise<boolean> {
  return new Promise<boolean>((resolve, reject) => {
    if (!('serviceWorker' in navigator)) {
      reject(new Error('Service workers are not supported in this browser.'));
      return;
    }

    if (!navigator.serviceWorker.controller) {
      reject(
        new Error(
          'No active service worker found. Please ensure the service worker is registered and active.',
        ),
      );
      return;
    }

    const messageHandler = (event: MessageEvent<SWServiceWorkerMessage>) => {
      const data = event.data;

      if (data && data.type === 'ID_TOKEN') {
        if (data.idToken) {
          cleanup();
          resolve(true);
        } else {
          console.warn('Received ID_TOKEN message with null idToken.');
        }
      }
    };

    // Function to clean up listeners and intervals
    const cleanup = () => {
      clearInterval(intervalId);
      navigator.serviceWorker.removeEventListener('message', messageHandler);
      clearTimeout(timeoutId);
    };

    navigator.serviceWorker.addEventListener('message', messageHandler);

    const syncMessage: SWClientMessage = { type: 'SYNC_ID_TOKEN' };
    const intervalId = setInterval(() => {
      navigator.serviceWorker.controller?.postMessage(syncMessage);
    }, 100);

    const timeoutDuration = 10000;
    const timeoutId = setTimeout(() => {
      cleanup();
      reject(
        new Error(
          'Timeout: Service worker did not confirm authentication within the expected time.',
        ),
      );
    }, timeoutDuration);
  });
}
