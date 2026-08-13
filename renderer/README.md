# Renderer bundle

`server.js` is the committed headless-renderer artifact used by Sublime Text.
`browser-preview.js` is the committed in-page runtime used by the offline full
browser preview. Together they bundle the pinned Mermaid, MathJax, and
`puppeteer-core` dependencies and do not require `npm install` on an end-user
machine.

To reproduce it with Node.js 22.12 or newer:

```bash
npm ci
npm run build
npm run verify:browser-preview
```

The renderer communicates only through newline-delimited JSON on stdin/stdout.
It launches the user's existing Chrome or Chromium with an isolated temporary
profile, pipe-based browser control, and page request interception.
MathJax uses direct, statically bundled v4 modules to produce self-contained
SVG before the same offline browser captures transparent PNG output.
The full-page verifier launches Chrome with a temporary isolated profile,
checks Mermaid and MathJax SVG output, exercises zoom and print, exports a PDF,
asserts error isolation and zero HTTP(S) requests, and deletes every temporary
artifact when it exits.
