import {mathjax} from "@mathjax/src/js/mathjax.js";
import {liteAdaptor} from "@mathjax/src/js/adaptors/liteAdaptor.js";
import {RegisterHTMLHandler} from "@mathjax/src/js/handlers/html.js";
import {TeX} from "@mathjax/src/js/input/tex.js";
import "@mathjax/src/js/input/tex/ams/AmsConfiguration.js";
import "@mathjax/src/js/input/tex/newcommand/NewcommandConfiguration.js";
import "@mathjax/src/js/input/tex/textmacros/TextMacrosConfiguration.js";
import {SVG} from "@mathjax/src/js/output/svg.js";
import mermaid from "mermaid";

const MAX_MERMAID_SOURCE_BYTES = 128 * 1024;
const MAX_MATH_SOURCE_BYTES = 32 * 1024;
const textEncoder = new TextEncoder();

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  suppressErrorRendering: true,
  theme: document.documentElement.dataset.theme === "dark" ? "dark" : "default",
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
  flowchart: {htmlLabels: false, useMaxWidth: true},
});

const adaptor = liteAdaptor({fontSize: 16});
RegisterHTMLHandler(adaptor);
const mathInput = new TeX({
  packages: ["base", "ams", "newcommand", "textmacros"],
  maxBuffer: MAX_MATH_SOURCE_BYTES,
  formatError: (_jax, error) => {
    throw error;
  },
});
const mathOutput = new SVG({fontCache: "local", useXlink: false});
const mathDocument = mathjax.document("", {
  InputJax: mathInput,
  OutputJax: mathOutput,
  compileError: (_document, _math, error) => {
    throw error;
  },
  typesetError: (_document, _math, error) => {
    throw error;
  },
});

function conciseError(error) {
  return String((error && error.message) || error || "rendering failed")
    .trim()
    .split(/\r?\n/, 1)[0]
    .slice(0, 500);
}

function sanitizeGeneratedSvg(container) {
  container.querySelectorAll("a").forEach((anchor) => {
    anchor.replaceWith(...anchor.childNodes);
  });
  container
    .querySelectorAll("script,foreignObject,iframe,object,image")
    .forEach((element) => element.remove());
  container.querySelectorAll("*").forEach((element) => {
    for (const attribute of [...element.attributes]) {
      const name = attribute.name.toLowerCase();
      const value = attribute.value.trim();
      if (name.startsWith("on")) {
        element.removeAttribute(attribute.name);
      } else if (
        ["href", "src", "xlink:href"].includes(name) &&
        value &&
        !value.startsWith("#") &&
        !value.startsWith("data:")
      ) {
        element.removeAttribute(attribute.name);
      }
    }
  });
}

function installDiagramControls(section, target) {
  let scale = 1;
  const applyScale = () => {
    section.dataset.scale = String(scale);
    target.style.transform = `scale(${scale})`;
    target.style.transformOrigin = "top left";
  };
  section.querySelectorAll("[data-action]").forEach((button) => {
    button.addEventListener("click", () => {
      const action = button.dataset.action;
      if (action === "zoom-in") {
        scale = Math.min(3, scale + 0.25);
      } else if (action === "zoom-out") {
        scale = Math.max(0.5, scale - 0.25);
      } else if (action === "reset") {
        scale = 1;
      }
      applyScale();
    });
  });
  applyScale();
}

async function renderMermaid(section, index) {
  const definition = section.querySelector(".mermaid-definition");
  const target = section.querySelector(".mermaid-target");
  if (!definition || !target) {
    return;
  }
  installDiagramControls(section, target);
  const source = definition.textContent || "";
  if (textEncoder.encode(source).byteLength > MAX_MERMAID_SOURCE_BYTES) {
    target.textContent = "Mermaid: source exceeds the 128 KiB rendering limit";
    target.classList.add("render-error");
    return;
  }
  try {
    const {svg} = await mermaid.render(`markdown-reader-browser-${index}`, source);
    target.innerHTML = svg;
    sanitizeGeneratedSvg(target);
    const diagram = target.querySelector("svg");
    if (!diagram) {
      throw new Error("Mermaid did not produce an SVG element");
    }
    diagram.removeAttribute("width");
    diagram.removeAttribute("height");
    diagram.style.maxWidth = "100%";
    diagram.style.height = "auto";
  } catch (error) {
    target.textContent = `Mermaid: ${conciseError(error)}`;
    target.classList.add("render-error");
  }
}

async function renderMath(expression) {
  const definition = expression.querySelector(".math-definition");
  const target = expression.querySelector(".math-target");
  if (!definition || !target) {
    return;
  }
  const source = definition.textContent || "";
  if (textEncoder.encode(source).byteLength > MAX_MATH_SOURCE_BYTES) {
    target.textContent = "MathJax: source exceeds the 32 KiB rendering limit";
    target.classList.add("render-error");
    return;
  }
  try {
    const node = await mathDocument.convertPromise(source, {
      display: expression.classList.contains("display-math"),
      em: 16,
      ex: 8,
      containerWidth: Math.max(320, document.documentElement.clientWidth - 64),
    });
    target.innerHTML = adaptor.outerHTML(node);
    sanitizeGeneratedSvg(target);
    if (!target.querySelector("svg")) {
      throw new Error("MathJax did not produce an SVG formula");
    }
  } catch (error) {
    target.textContent = `MathJax: ${conciseError(error)}`;
    target.classList.add("render-error");
  }
}

async function main() {
  document.querySelectorAll('[data-action="print"]').forEach((button) => {
    button.addEventListener("click", () => globalThis.print());
  });
  const diagrams = [...document.querySelectorAll(".interactive-mermaid")];
  const formulas = [...document.querySelectorAll(".math-expression")];
  await Promise.all([
    ...diagrams.map((section, index) => renderMermaid(section, index)),
    ...formulas.map((expression) => renderMath(expression)),
  ]);
}

main()
  .catch((error) => {
    document.documentElement.dataset.markdownReaderError = conciseError(error);
  })
  .finally(() => {
    document.documentElement.dataset.markdownReaderReady = "true";
  });
