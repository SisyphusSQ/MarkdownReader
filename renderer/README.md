# Renderer bundle

`server.js` is the committed runtime artifact used by Sublime Text. It bundles
the pinned Mermaid and `puppeteer-core` dependencies and does not require
`npm install` on an end-user machine.

To reproduce it with Node.js 22.12 or newer:

```bash
npm ci
npm run build
```

The renderer communicates only through newline-delimited JSON on stdin/stdout.
It launches the user's existing Chrome or Chromium with an isolated temporary
profile, pipe-based browser control, and page request interception.
