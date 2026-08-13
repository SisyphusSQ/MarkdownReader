import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {fileURLToPath, pathToFileURL} from "node:url";

import puppeteer from "puppeteer-core";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const rendererDirectory = path.resolve(scriptDirectory, "..");
const runtimePath = path.join(rendererDirectory, "browser-preview.js");

const chromeCandidates = [
  process.env.MARKDOWN_READER_CHROME_PATH,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
].filter(Boolean);

async function firstExecutable(paths) {
  for (const candidate of paths) {
    try {
      await fs.access(candidate);
      return candidate;
    } catch (_error) {
      // Continue to the next supported Chrome location.
    }
  }
  throw new Error("Chrome or Chromium is required for browser-preview verification");
}

const temporaryDirectory = await fs.mkdtemp(
  path.join(os.tmpdir(), "markdown-reader-browser-verify-"),
);
const profileDirectory = path.join(temporaryDirectory, "profile");
const suppliedHtmlPath = process.env.MARKDOWN_READER_PREVIEW_HTML;
const htmlPath = suppliedHtmlPath
  ? path.resolve(suppliedHtmlPath)
  : path.join(temporaryDirectory, "preview.html");
const pdfPath = path.join(temporaryDirectory, "preview.pdf");
if (!suppliedHtmlPath) {
  const runtime = await fs.readFile(runtimePath, "utf8");
  assert.equal(/[\t ]+$/m.test(runtime), false, "browser bundle has trailing whitespace");
  const runtimeData = Buffer.from(runtime, "utf8").toString("base64");
  const html = `<!doctype html>
<html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy"
  content="default-src 'none'; connect-src 'none'; img-src data:; script-src data:; style-src 'unsafe-inline'">
</head><body>
<button type="button" data-action="print">Print / Save as PDF</button>
<section class="interactive-mermaid">
  <button type="button" data-action="zoom-out">Zoom out</button>
  <button type="button" data-action="reset">Reset</button>
  <button type="button" data-action="zoom-in">Zoom in</button>
  <div class="mermaid-viewport"><div class="mermaid-target"></div></div>
  <pre class="mermaid-definition" hidden>flowchart LR
  A --> B
  click A href "https://example.com"</pre>
</section>
<section class="interactive-mermaid">
  <button type="button" data-action="zoom-out">Zoom out</button>
  <button type="button" data-action="reset">Reset</button>
  <button type="button" data-action="zoom-in">Zoom in</button>
  <div class="mermaid-viewport"><div class="mermaid-target"></div></div>
  <pre class="mermaid-definition" hidden>flowchart LR
  this is not valid</pre>
</section>
<span class="math-expression inline-math">
  <span class="math-target"></span><code class="math-definition" hidden>x^2+1</code>
</span>
<span class="math-expression inline-math">
  <span class="math-target"></span><code class="math-definition" hidden>\\badcontrolsequence</code>
</span>
<script src="data:text/javascript;base64,${runtimeData}"></script>
</body></html>`;
  await fs.writeFile(htmlPath, html, "utf8");
}
const chromePath = await firstExecutable(chromeCandidates);
const browser = await puppeteer.launch({
  browser: "chrome",
  executablePath: chromePath,
  headless: true,
  pipe: true,
  userDataDir: profileDirectory,
  args: [
    "--disable-background-networking",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-sync",
    "--no-default-browser-check",
    "--no-first-run",
  ],
});

try {
  const page = await browser.newPage();
  let externalRequests = 0;
  page.on("request", (request) => {
    if (/^https?:/i.test(request.url())) {
      externalRequests += 1;
    }
  });
  await page.evaluateOnNewDocument(() => {
    globalThis.__markdownReaderPrintCalled = false;
    globalThis.print = () => {
      globalThis.__markdownReaderPrintCalled = true;
    };
  });
  await page.goto(pathToFileURL(htmlPath).href, {waitUntil: "load"});
  await page.waitForFunction(
    () => document.documentElement.dataset.markdownReaderReady === "true",
    {timeout: 15_000},
  );

  assert.equal(await page.$$eval(".mermaid-target svg", (nodes) => nodes.length), 1);
  assert.equal(
    await page.$$eval(".math-target mjx-container", (nodes) => nodes.length),
    1,
  );
  assert.equal(
    await page.$eval(".math-target mjx-container", (node) => Boolean(node.querySelector("svg"))),
    true,
  );
  assert.equal(
    await page.$$eval(
      ".mermaid-target a, .mermaid-target [onclick], .mermaid-target [onload]",
      (nodes) => nodes.length,
    ),
    0,
  );
  if (!suppliedHtmlPath) {
    assert.equal(
      await page.$$eval(".interactive-mermaid .render-error", (nodes) => nodes.length),
      1,
    );
    assert.equal(
      await page.$$eval(".math-expression .render-error", (nodes) => nodes.length),
      1,
    );
  }
  assert.equal(externalRequests, 0);

  await page.click('[data-action="zoom-in"]');
  assert.equal(
    await page.$eval(".interactive-mermaid", (node) => node.dataset.scale),
    "1.25",
  );

  await page.click('[data-action="print"]');
  assert.equal(
    await page.evaluate(() => globalThis.__markdownReaderPrintCalled),
    true,
  );

  await page.pdf({path: pdfPath, printBackground: true});
  const pdf = await fs.readFile(pdfPath);
  assert.equal(pdf.subarray(0, 5).toString("ascii"), "%PDF-");
} finally {
  await browser.close().catch(() => {});
  await fs.rm(temporaryDirectory, {force: true, recursive: true});
}
