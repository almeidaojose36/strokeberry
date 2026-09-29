import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
const page = path => fileURLToPath(new URL(`frontend/${path}`, import.meta.url));
export default defineConfig({root:'frontend',envDir:'..',build:{outDir:'../dist',emptyOutDir:true,rollupOptions:{input:{landing:page('index.html'),studio:page('studio/index.html'),terms:page('terms/index.html'),privacy:page('privacy/index.html'),refunds:page('refunds/index.html')}}},server:{port:5173,proxy:{'/api':'http://127.0.0.1:8001','/media':'http://127.0.0.1:8001'}}});
