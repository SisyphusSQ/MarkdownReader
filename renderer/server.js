"use strict";

const readline = require("node:readline");

const MAX_MESSAGE_BYTES = 2 * 1024 * 1024;
const input = readline.createInterface({input: process.stdin, crlfDelay: Infinity});

function respond(message) {
  process.stdout.write(JSON.stringify(message) + "\n");
}

input.on("line", (line) => {
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

  if (request.method === "ping") {
    respond({
      id: request.id,
      ok: true,
      result: {
        pong: true,
        protocolVersion: 1,
        processId: process.pid,
        nodeVersion: process.version,
        chromePath: process.env.MARKDOWN_READER_CHROME_PATH || "",
      },
    });
    return;
  }

  respond({id: request.id, ok: false, error: "unsupported renderer request"});
});
