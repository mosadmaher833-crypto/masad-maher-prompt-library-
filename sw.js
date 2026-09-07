const CACHE = 'masad-maher-prompts-v2';
const CORE = [
  './', './index.html', './library-final.html', './library-pro.html',
  './prompt-generator.html', './prompt-editor.html', './prompt-details.html',
  './add-prompt.html', './sources.html', './source-manager.html',
  './manifest.webmanifest', './offline.html'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

async function arabicPromptResponse(request, response) {
  if (!response.ok) return response;
  try {
    const data = await response.clone().json();
    if (!Array.isArray(data.prompts)) return response;
    for (const p of data.prompts) {
      if (p.prompt_ar && p.prompt && p.prompt_ar !== p.prompt) {
        p.prompt_en = p.prompt;
        p.prompt = p.prompt_ar;
      }
    }
    return new Response(JSON.stringify(data), {
      status: response.status,
      statusText: response.statusText,
      headers: {'Content-Type':'application/json; charset=utf-8', 'Cache-Control':'no-cache'}
    });
  } catch (_) {
    return response;
  }
}

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET' || url.origin !== location.origin) return;

  if (url.pathname.endsWith('/data/prompts.json')) {
    event.respondWith(fetch(event.request).then(async response => {
      const transformed = await arabicPromptResponse(event.request, response);
      const copy = transformed.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy));
      return transformed;
    }).catch(() => caches.match(event.request)));
    return;
  }

  if (url.pathname.includes('/data/')) {
    event.respondWith(fetch(event.request).then(response => {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy));
      return response;
    }).catch(() => caches.match(event.request)));
    return;
  }

  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    const copy = response.clone();
    caches.open(CACHE).then(cache => cache.put(event.request, copy));
    return response;
  }).catch(() => caches.match('./offline.html'))));
});
