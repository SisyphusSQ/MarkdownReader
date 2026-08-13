"use strict";

const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const readline = require("node:readline");
const puppeteer = require("puppeteer-core");

const MERMAID_BROWSER_SOURCE = __MERMAID_BROWSER_SOURCE__;
const MERMAID_VERSION = __MERMAID_VERSION__;
const PUPPETEER_VERSION = __PUPPETEER_VERSION__;
const MAX_MESSAGE_BYTES = 2 * 1024 * 1024;
const MAX_MERMAID_SOURCE_BYTES = 128 * 1024;
const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
const MAX_PIXEL_DIMENSION = 4096;
const RENDER_TIMEOUT_MS = 10_000;
const ALLOWED_THEMES = new Set(["default", "dark"]);

class MermaidRenderer {
  constructor(chromePath) {
    this.chromePath = chromePath;
    this.browser = null;
    this.profileDirectory = null;
  }

  async render(params) {
    const options = validateRenderParams(params);
    const browser = await this.ensureBrowser();
    const page = await browser.newPage();
    try {
      page.setDefaultTimeout(RENDER_TIMEOUT_MS);
      await page.setViewport({
        width: options.width,
        height: 800,
        deviceScaleFactor: options.scale,
      });
      await page.setRequestInterception(true);
      await page.setOfflineMode(true);
      let blockedNetworkRequests = 0;
      page.on("request", (request) => {
        if (request.isInterceptResolutionHandled()) {
          return;
        }
        const requestUrl = request.url();
        if (requestUrl === "about:blank" || requestUrl.startsWith("data:")) {
          request.continue();
        } else {
          blockedNetworkRequests += 1;
          request.abort("blockedbyclient");
        }
      });
      await page.setContent(
        "<!doctype html><html><head><meta charset=\"utf-8\">" +
          "<meta http-equiv=\"Content-Security-Policy\" " +
          "content=\"default-src 'none'; img-src data:; " +
          "script-src 'unsafe-inline'; style-src 'unsafe-inline'\"><style>" +
          "html,body{margin:0;padding:0;background:transparent;overflow:visible}" +
          "#diagram{display:inline-block;background:transparent}" +
          "</style></head><body><div id=\"diagram\"></div></body></html>",
        {waitUntil: "domcontentloaded"},
      );
      await page.addScriptTag({content: MERMAID_BROWSER_SOURCE});

      const bounds = await withTimeout(
        page.evaluate(
          async ({source, theme, width}) => {
            const mermaid = globalThis.__MARKDOWN_READER_MERMAID__;
            mermaid.initialize({
              startOnLoad: false,
              securityLevel: "strict",
              suppressErrorRendering: true,
              theme,
              htmlLabels: false,
              maxEdges: 500,
              maxTextSize: 100_000,
              secure: [
                "secure",
                "securityLevel",
                "startOnLoad",
                "suppressErrorRendering",
                "theme",
                "themeCSS",
                "themeVariables",
                "htmlLabels",
                "maxEdges",
                "maxTextSize",
              ],
              flowchart: {htmlLabels: false, useMaxWidth: false},
            });
            let svg;
            try {
              ({svg} = await mermaid.render("markdown-reader-diagram", source));
            } catch (error) {
              const attemptedExternalResource = /\b(?:https?|file|ftp):\/\//i.test(source);
              if (error && error.name === "EncodingError" && attemptedExternalResource) {
                throw new Error("Mermaid diagram requested blocked network content");
              }
              throw error;
            }
            const container = document.getElementById("diagram");
            container.innerHTML = svg;
            const diagram = container.querySelector("svg");
            if (!diagram) {
              throw new Error("Mermaid did not produce an SVG element");
            }
            diagram.querySelectorAll("a").forEach((anchor) => {
              anchor.replaceWith(...anchor.childNodes);
            });
            for (const element of diagram.querySelectorAll("[href], [src]")) {
              const resource = element.getAttribute("href") || element.getAttribute("src");
              if (resource && !resource.startsWith("#") && !resource.startsWith("data:")) {
                throw new Error("Mermaid diagram requested blocked network content");
              }
            }

            const viewBox = diagram.viewBox && diagram.viewBox.baseVal;
            let naturalWidth = viewBox && viewBox.width ? viewBox.width : diagram.clientWidth;
            let naturalHeight = viewBox && viewBox.height ? viewBox.height : diagram.clientHeight;
            if (!(naturalWidth > 0 && naturalHeight > 0)) {
              throw new Error("Mermaid produced an empty diagram");
            }
            const displayWidth = Math.min(naturalWidth, width);
            const displayHeight = naturalHeight * (displayWidth / naturalWidth);
            diagram.removeAttribute("height");
            diagram.removeAttribute("width");
            diagram.style.display = "block";
            diagram.style.maxWidth = "none";
            diagram.style.width = `${displayWidth}px`;
            diagram.style.height = `${displayHeight}px`;
            const rectangle = diagram.getBoundingClientRect();
            return {width: rectangle.width, height: rectangle.height};
          },
          options,
        ),
        RENDER_TIMEOUT_MS,
        "Mermaid rendering timed out",
      );
      if (blockedNetworkRequests > 0) {
        throw new Error("Mermaid diagram requested blocked network content");
      }

      const pixelWidth = Math.ceil(bounds.width * options.scale);
      const pixelHeight = Math.ceil(bounds.height * options.scale);
      if (
        pixelWidth <= 0 ||
        pixelHeight <= 0 ||
        pixelWidth > MAX_PIXEL_DIMENSION ||
        pixelHeight > MAX_PIXEL_DIMENSION
      ) {
        throw new Error("rendered diagram exceeds the 4096-pixel dimension limit");
      }

      const diagram = await page.$("#diagram svg");
      if (!diagram) {
        throw new Error("Mermaid diagram disappeared before capture");
      }
      let data;
      try {
        data = await withTimeout(
          diagram.screenshot({encoding: "base64", omitBackground: true, type: "png"}),
          RENDER_TIMEOUT_MS,
          "Mermaid capture timed out",
        );
      } catch (error) {
        if (blockedNetworkRequests > 0) {
          throw new Error("Mermaid diagram requested blocked network content");
        }
        throw error;
      }
      if (blockedNetworkRequests > 0) {
        throw new Error("Mermaid diagram requested blocked network content");
      }
      const image = Buffer.from(data, "base64");
      if (image.length > MAX_IMAGE_BYTES) {
        throw new Error("rendered diagram exceeds the 5 MiB image limit");
      }
      if (
        image.length < 24 ||
        image.subarray(0, 8).compare(Buffer.from("89504e470d0a1a0a", "hex")) !== 0
      ) {
        throw new Error("browser capture did not return a PNG image");
      }
      return {
        mimeType: "image/png",
        data,
        width: image.readUInt32BE(16),
        height: image.readUInt32BE(20),
        blockedNetworkRequests,
      };
    } finally {
      await page.close().catch(() => {});
    }
  }

  async ensureBrowser() {
    if (this.browser && this.browser.connected) {
      return this.browser;
    }
    await this.close();
    if (!this.chromePath) {
      throw new Error("Chrome or Chromium executable was not configured");
    }

    this.profileDirectory = await fs.mkdtemp(
      path.join(os.tmpdir(), "markdown-reader-chrome-"),
    );
    try {
      this.browser = await puppeteer.launch({
        browser: "chrome",
        executablePath: this.chromePath,
        headless: true,
        pipe: true,
        userDataDir: this.profileDirectory,
        timeout: 15_000,
        args: [
          "--disable-background-networking",
          "--disable-component-update",
          "--disable-default-apps",
          "--disable-extensions",
          "--disable-features=MediaRouter,OptimizationHints,Translate",
          "--disable-sync",
          "--metrics-recording-only",
          "--no-default-browser-check",
          "--no-first-run",
          "--password-store=basic",
          "--use-mock-keychain",
        ],
      });
      return this.browser;
    } catch (error) {
      await this.close();
      throw error;
    }
  }

  async close() {
    const browser = this.browser;
    const profileDirectory = this.profileDirectory;
    this.browser = null;
    this.profileDirectory = null;
    if (browser) {
      await browser.close().catch(() => {});
    }
    if (profileDirectory) {
      await fs.rm(profileDirectory, {force: true, recursive: true}).catch(() => {});
    }
  }
}

function validateRenderParams(params) {
  if (!params || typeof params.source !== "string") {
    throw new Error("Mermaid source must be a string");
  }
  if (Buffer.byteLength(params.source, "utf8") > MAX_MERMAID_SOURCE_BYTES) {
    throw new Error("Mermaid source exceeds the 128 KiB rendering limit");
  }
  if (!ALLOWED_THEMES.has(params.theme)) {
    throw new Error("Mermaid theme must be default or dark");
  }
  if (!Number.isInteger(params.width) || params.width < 320 || params.width > 1600) {
    throw new Error("Mermaid width must be an integer from 320 to 1600");
  }
  if (!Number.isInteger(params.scale) || params.scale < 1 || params.scale > 3) {
    throw new Error("Mermaid scale must be an integer from 1 to 3");
  }
  return params;
}

function withTimeout(promise, timeoutMs, message) {
  let timeout;
  const rejection = new Promise((_, reject) => {
    timeout = setTimeout(() => reject(new Error(message)), timeoutMs);
  });
  return Promise.race([promise, rejection]).finally(() => clearTimeout(timeout));
}

function conciseError(error) {
  const message = error && error.message ? error.message : String(error || "rendering failed");
  return message
    .trim()
    .split(/\r?\n/, 1)[0]
    .replace(/ for text:.*/, "")
    .slice(0, 500);
}

function respond(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

const renderer = new MermaidRenderer(process.env.MARKDOWN_READER_CHROME_PATH || "");
const input = readline.createInterface({input: process.stdin, crlfDelay: Infinity});

async function handleLine(line) {
  if (Buffer.byteLength(line, "utf8") > MAX_MESSAGE_BYTES) {
    respond({id: null, ok: false, error: "renderer request exceeds the message-size limit"});
    return;
  }

  let request;
  try {
    request = JSON.parse(line);
  } catch (_error) {
    respond({id: null, ok: false, error: "invalid JSON request"});
    return;
  }

  try {
    if (request.method === "ping") {
      respond({
        id: request.id,
        ok: true,
        result: {
          pong: true,
          protocolVersion: 2,
          processId: process.pid,
          nodeVersion: process.version,
          chromePath: process.env.MARKDOWN_READER_CHROME_PATH || "",
          mermaidVersion: MERMAID_VERSION,
          puppeteerVersion: PUPPETEER_VERSION,
        },
      });
      return;
    }
    if (request.method === "renderMermaid") {
      respond({id: request.id, ok: true, result: await renderer.render(request.params)});
      return;
    }
    respond({id: request.id, ok: false, error: "unsupported renderer request"});
  } catch (error) {
    respond({id: request.id, ok: false, error: conciseError(error)});
  }
}

async function main() {
  for await (const line of input) {
    await handleLine(line);
  }
  await renderer.close();
}

let shuttingDown = false;
function shutdown() {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  renderer.close().finally(() => process.exit(0));
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
main().catch((error) => {
  process.stderr.write(`${conciseError(error)}\n`);
  renderer.close().finally(() => process.exit(1));
});
