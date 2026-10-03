import { defineConfig } from 'vite';
import { readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const front = fileURLToPath(new URL('frontend/', import.meta.url));
// Every page is an index.html under frontend/ (the landing page, the studio, legal pages, gallery, blog, guides) plus the
// 404 page, so a page written by scripts/site/build_pages.py is built without listing it here.
const pages = readdirSync(front, {recursive: true})
  .filter(file => /(^|\/)index\.html$/.test(file) && !/^(public|src|node_modules)\//.test(file))
  .reduce((input, file) => ({...input, [file.replace(/\/?index\.html$/, '').replaceAll('/', '-') || 'landing']: front + file}),
          {notfound: front + '404.html'});
export default defineConfig({root:'frontend',envDir:'..',build:{outDir:'../dist',emptyOutDir:true,rollupOptions:{input:pages}},server:{port:5173,proxy:{'/api':'http://127.0.0.1:8001','/media':'http://127.0.0.1:8001'}}});
