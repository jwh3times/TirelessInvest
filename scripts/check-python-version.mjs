#!/usr/bin/env node
// Fails when the API's Python version differs between the image production runs and the pin CI
// and local development use, so a base-image bump cannot leave CI testing an older Python.

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const DOCKERFILE = "api/Dockerfile";
const PIN = "api/.python-version";

// The major.minor of the first `FROM` line whose image is `python`, flags and a registry prefix
// allowed (`FROM --platform=… docker.io/library/python:3.15.2-slim@sha256:…`), or null.
export function dockerfilePython(text) {
  const match = /^\s*FROM\s+(?:--\S+\s+)*(?:\S+\/)?python:(\d+\.\d+)(?![\d])/im.exec(text);
  return match ? match[1] : null;
}

// The major.minor of a `.python-version` file's request: its first line that is neither blank nor
// a `#` comment, as uv reads it. Null when that line is not a CPython version number.
export function pinnedPython(text) {
  const request = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line && !line.startsWith("#"));
  const match = request && /^(\d+\.\d+)(?:\.\d+)?$/.exec(request);
  return match ? match[1] : null;
}

// Compares the image's Python with the pin under `root`, returning `{ problems }`: one for each
// file that is missing or names no version, else one when the two minors differ.
export function checkRepository(root) {
  const problems = [];
  const versionIn = (rel, parse, expected) => {
    let text;
    try {
      text = readFileSync(path.join(root, rel), "utf8");
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
      problems.push(`${rel} is missing`);
      return null;
    }
    const version = parse(text);
    if (!version) problems.push(`${rel} has no ${expected}`);
    return version;
  };
  const image = versionIn(DOCKERFILE, dockerfilePython, "`FROM python:<major>.<minor>…` line");
  const pin = versionIn(PIN, pinnedPython, "`<major>.<minor>` version");
  if (image && pin && image !== pin) {
    problems.push(`API Python mismatch: ${DOCKERFILE} runs ${image}, ${PIN} pins ${pin}`);
  }
  return { problems };
}

// Checks this repository, printing each problem; returns the exit code.
export function main() {
  const { problems } = checkRepository(repositoryRoot);
  for (const problem of problems) console.error(problem);
  if (problems.length) {
    console.error(`Make ${PIN} name the Python the ${DOCKERFILE} image runs.`);
    return 1;
  }
  console.log(`API Python agrees: ${DOCKERFILE} and ${PIN}.`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  process.exitCode = main();
}
