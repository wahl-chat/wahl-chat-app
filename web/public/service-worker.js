importScripts(
  'https://www.gstatic.com/firebasejs/11.0.2/firebase-app-compat.js',
  'https://www.gstatic.com/firebasejs/11.0.2/firebase-auth-compat.js'
);

const urlParams = new URLSearchParams(location.search);
const config = Object.fromEntries(urlParams);

// Initialize the Firebase app in the service worker script.
firebase.initializeApp(config);

/**
 * Returns a promise that resolves with an ID token if available.
 * @return {!Promise<?string>} The promise that resolves with an ID token if
 *     available. Otherwise, the promise resolves with null.
 */
const getIdToken = () => {
  return new Promise((resolve, reject) => {
    const unsubscribe = firebase.auth().onAuthStateChanged((user) => {
      unsubscribe();

      if (user) {
        user.getIdToken().then(
          (idToken) => {
            resolve(idToken);
          },
          (error) => {
            resolve(null);
          }
        );
      } else {
        firebase
          .auth()
          .signInAnonymously()
          .then((res) => {
            resolve(res.user.getIdToken());
          })
          .catch((error) => {
            resolve(null);
          });
      }
    });
  });
};

const getOriginFromUrl = (url) => {
  // https://stackoverflow.com/questions/1420881/how-to-extract-base-url-from-a-string-in-javascript
  const pathArray = url.split('/');
  const protocol = pathArray[0];
  const host = pathArray[2];
  return protocol + '//' + host;
};

// Get underlying body if available. Works for text and json bodies.
const getBodyContent = (req) => {
  return Promise.resolve()
    .then(() => {
      if (req.method !== 'GET') {
        if (req.headers.get('Content-Type').indexOf('json') !== -1) {
          return req.json().then((json) => {
            return JSON.stringify(json);
          });
        } else {
          return req.text();
        }
      }
    })
    .catch((error) => {
      // Ignore error.
    });
};

self.addEventListener('fetch', (event) => {
  /** @type {FetchEvent} */
  const evt = event;

  const requestProcessor = (idToken) => {
    let req = evt.request;
    let processRequestPromise = Promise.resolve();

    // For same origin https requests, append idToken to header.
    if (
      self.location.origin == getOriginFromUrl(evt.request.url) &&
      (self.location.protocol == 'https:' ||
        self.location.hostname == 'localhost') &&
      idToken
    ) {
      // Clone headers as request headers are immutable.
      const headers = new Headers();
      req.headers.forEach((val, key) => {
        headers.append(key, val);
      });
      // Add ID token to header.
      headers.append('Authorization', 'Bearer ' + idToken);
      processRequestPromise = getBodyContent(req).then((body) => {
        try {
          req = new Request(req.url, {
            method: req.method,
            headers: headers,
            mode: 'same-origin',
            credentials: req.credentials,
            cache: req.cache,
            redirect: req.redirect,
            referrer: req.referrer,
            body,
            // bodyUsed: req.bodyUsed,
            // context: req.context
          });
        } catch (e) {
          // This will fail for CORS requests. We just continue with the
          // fetch caching logic below and do not pass the ID token.
        }
      });
    }
    return processRequestPromise.then(() => {
      return fetch(req);
    });
  };
  // Fetch the resource after checking for the ID token.
  // This can also be integrated with existing logic to serve cached files
  // in offline mode.
  evt.respondWith(getIdToken().then(requestProcessor, requestProcessor));
});

self.addEventListener('message', (event) => {
  const data = event.data;

  switch (data.type) {
    case 'SYNC_ID_TOKEN':
      getIdToken().then((idToken) => {
        event.source.postMessage({ type: 'ID_TOKEN', idToken });
      });
      break;

    // Handle other message types as needed
    default:
      console.warn('Unknown message type:', data.type);
  }
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});
