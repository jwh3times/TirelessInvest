import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

import { checkRepository, dockerfilePython, main, pinnedPython } from "./check-python-version.mjs";

// A repository root holding `files` (relative path to content), passed to `run`.
function withRepository(files, run) {
  const root = mkdtempSync(path.join(tmpdir(), "check-python-version-"));
  try {
    for (const [rel, content] of Object.entries(files)) {
      mkdirSync(path.dirname(path.join(root, rel)), { recursive: true });
      writeFileSync(path.join(root, rel), content);
    }
    return run(root);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

const problemsIn = (files) => withRepository(files, (root) => checkRepository(root).problems);

test("reads major.minor from the Dockerfile's python base image", () => {
  assert.equal(dockerfilePython("# comment\nFROM python:3.15-slim\nRUN true\n"), "3.15");
});

test("tolerates a patch version, a digest, other suffixes, flags and a registry prefix", () => {
  for (const line of [
    "FROM python:3.16.2-slim",
    "FROM python:3.16-slim@sha256:0123abcd",
    "FROM python:3.16-bookworm AS build",
    "from python:3.16",
    "FROM --platform=linux/amd64 docker.io/library/python:3.16-alpine",
  ]) {
    assert.equal(dockerfilePython(`${line}\r\n`), "3.16", line);
  }
});

test("a multi-stage Dockerfile is read at its last python stage, the one that runs", () => {
  assert.equal(
    dockerfilePython("FROM python:3.14 AS build\nRUN make\nFROM python:3.15-slim\nCOPY --from=build /a /a\n"),
    "3.15",
  );
});

test("finds no version without a python base image", () => {
  assert.equal(dockerfilePython("FROM debian:12\n"), null);
  assert.equal(dockerfilePython("# FROM python:3.15-slim\n"), null);
  assert.equal(dockerfilePython(""), null);
});

test("reads major.minor from .python-version, with or without a patch version", () => {
  assert.equal(pinnedPython("3.15\n"), "3.15");
  assert.equal(pinnedPython("  3.16.1  \r\n"), "3.16");
  assert.equal(pinnedPython("# pinned for the API image\n3.15\n"), "3.15");
});

test("finds no version in an empty or unparseable .python-version", () => {
  assert.equal(pinnedPython(""), null);
  assert.equal(pinnedPython("\n\n"), null);
  assert.equal(pinnedPython("pypy3\n"), null);
});

test("a repository whose image and pin agree has no problems", () => {
  assert.deepEqual(
    problemsIn({ "api/Dockerfile": "FROM python:3.15-slim\n", "api/.python-version": "3.15.2\n" }),
    [],
  );
});

test("an image and a pin on different minors is one problem naming both versions and files", () => {
  assert.deepEqual(
    problemsIn({ "api/Dockerfile": "FROM python:3.16-slim\n", "api/.python-version": "3.15\n" }),
    ["API Python mismatch: api/Dockerfile runs 3.16, api/.python-version pins 3.15"],
  );
  assert.deepEqual(
    problemsIn({ "api/Dockerfile": "FROM python:3.15-slim\n", "api/.python-version": "3.16\n" }),
    ["API Python mismatch: api/Dockerfile runs 3.15, api/.python-version pins 3.16"],
  );
});

test("a missing file is a problem naming it, and no mismatch is reported", () => {
  assert.deepEqual(problemsIn({ "api/Dockerfile": "FROM python:3.15-slim\n" }), [
    "api/.python-version is missing",
  ]);
  assert.deepEqual(problemsIn({ "api/.python-version": "3.15\n" }), ["api/Dockerfile is missing"]);
});

test("a file with no version is a problem naming it, what was expected and what was found", () => {
  assert.deepEqual(
    problemsIn({ "api/Dockerfile": "FROM debian:12\n", "api/.python-version": "pypy3\n" }),
    [
      "api/Dockerfile has no `FROM python:<major>.<minor>…` line; its last FROM is `FROM debian:12`",
      "api/.python-version has no `<major>.<minor>` version; it requests `pypy3`",
    ],
  );
  assert.deepEqual(
    problemsIn({ "api/Dockerfile": "RUN true\n", "api/.python-version": "# no pin\n\n" }),
    [
      "api/Dockerfile has no `FROM python:<major>.<minor>…` line; it has no FROM line",
      "api/.python-version has no `<major>.<minor>` version; it is empty",
    ],
  );
});

// main() with its console output captured, so the test run stays quiet.
function quietMain(argv) {
  const { log, error } = console;
  const output = [];
  console.log = console.error = (line) => output.push(line);
  try {
    return { code: main(argv), output };
  } finally {
    Object.assign(console, { log, error });
  }
}

test("main exits 1 listing the problems for a checkout whose image and pin differ", () => {
  withRepository(
    { "api/Dockerfile": "FROM python:3.16-slim\n", "api/.python-version": "3.15\n" },
    (root) => {
      const { code, output } = quietMain([root]);
      assert.equal(code, 1);
      assert.equal(output[0], "API Python mismatch: api/Dockerfile runs 3.16, api/.python-version pins 3.15");
    },
  );
});

test("this repository's image and pin agree", () => {
  assert.equal(quietMain([]).code, 0);
});
