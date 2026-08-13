import {build} from "esbuild";
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
  entryPoints: [path.join(rendererDirectory, "src", "server.js")],
  bundle: true,
  define: {
    __MERMAID_BROWSER_SOURCE__: JSON.stringify(browserBundle.outputFiles[0].text),
    __MERMAID_VERSION__: JSON.stringify("11.16.1"),
    __PUPPETEER_VERSION__: JSON.stringify("25.6.0"),
  },
  format: "cjs",
  legalComments: "eof",
  minify: true,
  outfile: path.join(rendererDirectory, "server.js"),
  platform: "node",
  target: ["node22"],
});
