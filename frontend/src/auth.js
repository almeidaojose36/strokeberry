// Sign-in with Firebase (Google or a one-time email link). When the VITE_FIREBASE_* settings are absent the
// studio runs as the single local user, exactly as before, and the Firebase SDK is never downloaded.
const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};
export const authEnabled = Boolean(config.apiKey && config.projectId);
const EMAIL_KEY = 'strokeberry-sign-in-email';
let loaded = null;

function firebase() {
  loaded ??= Promise.all([import('firebase/app'), import('firebase/auth')]).then(([app, auth]) => {
    const instance = auth.getAuth(app.initializeApp(config));
    auth.setPersistence(instance, auth.browserLocalPersistence).catch(() => {});
    return {auth, instance};
  });
  return loaded;
}

export async function authHeaders() {
  if (!authEnabled) return {};
  const {instance} = await firebase();
  const token = await instance.currentUser?.getIdToken();
  return token ? {Authorization: `Bearer ${token}`} : {};
}

// Calls back with the signed-in user (or null) now and on every change. Returns an unsubscribe function.
export function watchUser(callback) {
  if (!authEnabled) { callback({local: true}); return () => {}; }
  let stop = () => {}, alive = true;
  firebase().then(({auth, instance}) => { if (alive) stop = auth.onAuthStateChanged(instance, callback); })
    .catch(() => callback(null));
  return () => { alive = false; stop(); };
}

export async function signInWithGoogle() {
  const {auth, instance} = await firebase();
  const provider = new auth.GoogleAuthProvider();
  provider.setCustomParameters({prompt: 'select_account'});
  try { await auth.signInWithPopup(instance, provider); }
  catch (error) {
    // Popups are blocked in some in-app browsers (Instagram, TikTok); fall back to a full-page redirect.
    if (['auth/popup-blocked', 'auth/operation-not-supported-in-this-environment'].includes(error.code))
      return auth.signInWithRedirect(instance, provider);
    if (error.code !== 'auth/popup-closed-by-user' && error.code !== 'auth/cancelled-popup-request') throw friendly(error);
  }
}

export async function sendEmailLink(email) {
  const {auth, instance} = await firebase();
  try {
    await auth.sendSignInLinkToEmail(instance, email, {url: `${location.origin}/studio/`, handleCodeInApp: true});
    try { localStorage.setItem(EMAIL_KEY, email); } catch {}
  } catch (error) { throw friendly(error); }
}

// If this page was opened from a sign-in email, finish signing in. `askEmail` is used when the link is opened
// on a different device than the one that requested it.
export async function completeEmailLink(askEmail) {
  if (!authEnabled) return false;
  const {auth, instance} = await firebase();
  if (!auth.isSignInWithEmailLink(instance, location.href)) return false;
  let email = null;
  try { email = localStorage.getItem(EMAIL_KEY); } catch {}
  email ||= await askEmail();
  if (!email) return false;
  try { await auth.signInWithEmailLink(instance, email, location.href); }
  catch (error) { throw friendly(error); }
  finally { history.replaceState(null, '', location.pathname); }
  try { localStorage.removeItem(EMAIL_KEY); } catch {}
  return true;
}

export async function signOut() {
  if (!authEnabled) return;
  const {auth, instance} = await firebase();
  await auth.signOut(instance);
}

function friendly(error) {
  const messages = {
    'auth/invalid-email': 'That email address doesn’t look right.',
    'auth/invalid-action-code': 'This sign-in link has expired or was already used. Request a new one.',
    'auth/expired-action-code': 'This sign-in link has expired. Request a new one.',
    'auth/network-request-failed': 'We couldn’t reach the sign-in service. Check your connection and try again.',
    'auth/too-many-requests': 'Too many attempts. Please wait a minute and try again.',
    'auth/quota-exceeded': 'We can’t send more sign-in emails right now. Please use Google or try again later.',
  };
  return new Error(messages[error.code] || 'Sign-in didn’t work. Please try again.');
}
