// Passes an image dropped on the website to the studio. It stays in this browser (IndexedDB): nothing is uploaded until
// the studio opens it as the visitor's own project.
const DB = 'strokeberry-handoff', STORE = 'files', KEY = 'pending';

function open() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function saveHandoff(file) {
  const db = await open();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put({file, saved: Date.now()}, KEY);
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
}

// The dropped image (and forget it), or null when there is none or it is more than ten minutes old.
export async function takeHandoff() {
  try {
    const db = await open();
    return await new Promise(resolve => {
      const tx = db.transaction(STORE, 'readwrite'), store = tx.objectStore(STORE), request = store.get(KEY);
      request.onsuccess = () => {
        store.delete(KEY);
        const item = request.result;
        resolve(item && Date.now() - item.saved < 10 * 60 * 1000 ? item.file : null);
      };
      request.onerror = () => resolve(null);
    });
  } catch {
    return null;
  }
}
