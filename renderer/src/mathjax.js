"use strict";

const {mathjax} = require("@mathjax/src/js/mathjax.js");
const {liteAdaptor} = require("@mathjax/src/js/adaptors/liteAdaptor.js");
const {RegisterHTMLHandler} = require("@mathjax/src/js/handlers/html.js");
const {TeX} = require("@mathjax/src/js/input/tex.js");
const {SVG} = require("@mathjax/src/js/output/svg.js");

require("@mathjax/src/js/input/tex/ams/AmsConfiguration.js");
require("@mathjax/src/js/input/tex/newcommand/NewcommandConfiguration.js");
require("@mathjax/src/js/input/tex/textmacros/TextMacrosConfiguration.js");

function createMathJaxConverter() {
  const adaptor = liteAdaptor({fontSize: 16});
  RegisterHTMLHandler(adaptor);
  const input = new TeX({
    packages: ["base", "ams", "newcommand", "textmacros"],
    maxBuffer: 32 * 1024,
    formatError: (_jax, error) => {
      throw error;
    },
  });
  const output = new SVG({fontCache: "local", useXlink: false});
  const document = mathjax.document("", {
    InputJax: input,
    OutputJax: output,
    compileError: (_document, _math, error) => {
      throw error;
    },
    typesetError: (_document, _math, error) => {
      throw error;
    },
  });

  return {
    async convert(source, options) {
      const node = await document.convertPromise(source, {
        display: options.display,
        em: options.fontSize,
        ex: options.fontSize / 2,
        containerWidth: options.width,
      });
      return adaptor.outerHTML(node);
    },
  };
}

module.exports = {createMathJaxConverter};
