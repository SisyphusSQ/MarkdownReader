import {build} from "esbuild";
import fs from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const rendererDirectory = path.resolve(scriptDirectory, "..");

const browserBundle = await build({
  entryPoints: [path.join(rendererDirectory, "src", "mermaid-browser.js")],
  bundle: true,
  format: "iife",
  legalComments: "eof",
  minify: true,
  platform: "browser",
  target: ["chrome120"],
  write: false,
});

await build({
  entryPoints: [path.join(rendererDirectory, "src", "browser-preview.js")],
  bundle: true,
  format: "iife",
  legalComments: "eof",
  minify: true,
  outfile: path.join(rendererDirectory, "browser-preview.js"),
  platform: "browser",
  target: ["chrome110", "firefox115", "safari16"],
});

const browserPreviewPath = path.join(rendererDirectory, "browser-preview.js");
const browserPreviewSource = await fs.readFile(browserPreviewPath, "utf8");
await fs.writeFile(
  browserPreviewPath,
  browserPreviewSource.replace(/[\t ]+$/gm, ""),
  "utf8",
);

const mathJaxWorkerBundle = await build({
  entryPoints: [path.join(rendererDirectory, "src", "mathjax-worker.js")],
  bundle: true,
  format: "iife",
  legalComments: "eof",
  minify: true,
  platform: "node",
  target: ["node22"],
  write: false,
});

await build({
  entryPoints: [path.join(rendererDirectory, "src", "server.js")],
  bundle: true,
  define: {
    __MERMAID_BROWSER_SOURCE__: JSON.stringify(browserBundle.outputFiles[0].text),
    __MATHJAX_WORKER_SOURCE__: JSON.stringify(mathJaxWorkerBundle.outputFiles[0].text),
    __MERMAID_VERSION__: JSON.stringify("11.16.1"),
    __MATHJAX_VERSION__: JSON.stringify("4.1.3"),
    __PUPPETEER_VERSION__: JSON.stringify("25.6.0"),
  },
  format: "cjs",
  legalComments: "eof",
  minify: true,
  outfile: path.join(rendererDirectory, "server.js"),
  platform: "node",
  target: ["node22"],
});
