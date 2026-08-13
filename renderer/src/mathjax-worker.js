"use strict";

const {parentPort, workerData} = require("node:worker_threads");
const {createMathJaxConverter} = require("./mathjax.js");

async function main() {
  try {
    const converter = createMathJaxConverter();
    const markup = await converter.convert(workerData.source, workerData);
    parentPort.postMessage({ok: true, markup});
  } catch (error) {
    parentPort.postMessage({
      ok: false,
      error: error && error.message ? error.message : String(error || "rendering failed"),
    });
  } finally {
    parentPort.close();
  }
}

main();
