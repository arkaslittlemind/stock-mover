// Uploads an engine run JSON to Vercel Blob as runs/latest.json (used by the daily workflow).
// Usage: node scripts/upload-run.mjs <path-to-run.json>
import { readFileSync } from "node:fs";
import { put } from "@vercel/blob";

const RUN_PATHNAME = "runs/latest.json";

function fail(message) {
  console.error(`upload-run: ${message}`);
  process.exit(1);
}

const file = process.argv[2];
if (!file) fail("give the run JSON path, e.g. node scripts/upload-run.mjs ../../out/latest.json");
if (!process.env.BLOB_READ_WRITE_TOKEN) fail("BLOB_READ_WRITE_TOKEN is not set, nothing uploaded.");

let body;
let run;
try {
  body = readFileSync(file, "utf8");
  run = JSON.parse(body);
} catch (error) {
  fail(`cannot read a valid JSON run from ${file} (${error.message}), nothing uploaded.`);
}

const blob = await put(RUN_PATHNAME, body, {
  access: "public",
  addRandomSuffix: false,
  allowOverwrite: true,
  contentType: "application/json",
  cacheControlMaxAge: 60,
});

console.log(`Uploaded ${blob.pathname}: run ${run?.run?.id ?? "?"}, generated_at ${run?.run?.generated_at ?? "?"}`);
