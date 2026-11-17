#!/usr/bin/env node
// Fails when the API's Python differs between the image production runs (`api/Dockerfile`) and the
// pin CI and local uv use (`api/.python-version`). Dependabot bumps only the base image, so this is
// what keeps CI from passing on a Python production no longer runs.
//
//   node scripts/check-python-version.mjs          # exit 1 and list every problem found
//   node scripts/check-python-version.mjs <root>   # check another checkout instead

import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const DOCKERFILE = "api/Dockerfile";
const PIN = "api/.python-version";

// A `FROM` line whose image is `python`, flags and a registry prefix allowed
// (`FROM --platform=… docker.io/library/python:3.15.2-slim@sha256:…`), capturing major.minor.
const PYTHON_FROM = /^FROM\s+(?:--\S+\s+)*(?:\S+\/)?python:(\d+\.\d+)/i;

const fromLines = (text) =>
  text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => /^FROM\s/i.test(line));

// The major.minor of the last `FROM python:…` line, the stage a multi-stage build runs, or null.
export function dockerfilePython(text) {
  const versions = fromLines(text).flatMap((line) => PYTHON_FROM.exec(line)?.[1] ?? []);
  return versions.at(-1) ?? null;
}

// A `.python-version` file's request: its first line that is neither blank nor a `#` comment, as
// uv reads it, or undefined.
const pinRequest = (text) =>
  text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line && !line.startsWith("#"));

// The major.minor the request names, or null when it is not a CPython version number.
export function pinnedPython(text) {
  const match = /^(\d+\.\d+)(?:\.\d+)?$/.exec(pinRequest(text) ?? "");
  return match ? match[1] : null;
}

// What each file must hold, and how to say what it held instead.
const SOURCES = [
  {
    rel: DOCKERFILE,
    parse: dockerfilePython,
    wanted: "`FROM python:<major>.<minor>…` line",
    found(text) {
      const last = fromLines(text).at(-1);
      return last ? `its last FROM is \`${last}\`` : "it has no FROM line";
    },
  },
  {
    rel: PIN,
    parse: pinnedPython,
    wanted: "`<major>.<minor>` version",
    found(text) {
      const request = pinRequest(text);
      return request ? `it requests \`${request}\`` : "it is empty";
    },
  },
];

// Compares the image's Python with the pin under `root`, returning `{ problems }`: one for each
// file that is missing or names no version, else one when the two minors differ.
export function checkRepository(root) {
  const problems = [];
  const [image, pin] = SOURCES.map(({ rel, parse, wanted, found }) => {
    let text;
    try {
      text = readFileSync(path.join(root, rel), "utf8");
    } catch (error) {
      if (error.code !== "ENOENT") throw error;
      problems.push(`${rel} is missing`);
      return null;
    }
    const version = parse(text);
    if (!version) problems.push(`${rel} has no ${wanted}; ${found(text)}`);
    return version;
  });
  if (image && pin && image !== pin) {
    problems.push(`API Python mismatch: ${DOCKERFILE} runs ${image}, ${PIN} pins ${pin}`);
  }
  return { problems };
}

export function main(argv) {
  const root = argv[0] ? path.resolve(argv[0]) : repositoryRoot;
  const { problems } = checkRepository(root);
  for (const problem of problems) console.error(problem);
  if (problems.length > 0) {
    console.error(`Make ${PIN} name the Python the ${DOCKERFILE} image runs, in ${root}.`);
    return 1;
  }
  console.log(`API Python agrees: ${DOCKERFILE} and ${PIN} in ${root}.`);
  return 0;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  process.exitCode = main(process.argv.slice(2));
}
