/**
 * Tests for the plugin-level version-check staleness nudge.
 *
 * A 1:1 port of engines/_shared/tests/test_version_check.py — same cases, same
 * names — so the move from Python to Node loses no coverage. Runs on the built-in
 * `node:test` runner (Node >= 18, no dependencies), matching the script's own rule
 * that this path must work with nothing installed:
 *
 *     node --test plugins/neurawork-cc-harness/hooks/
 */

"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");

const vc = require("./version-check.js");

function settingsFor(dirname, marker) {
  return {
    hooks: {
      SessionStart: [
        {
          matcher: "",
          hooks: [
            {
              type: "command",
              command: `uv run --directory "$CLAUDE_PROJECT_DIR/${dirname}" python ${marker}`,
              timeout: 15,
            },
          ],
        },
      ],
    },
  };
}

/** Temp repo + plugin tree with a knowledge-compiler install. Returns a cleanup fn. */
function setupTree(installed, shipped) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "vc-test-"));
  const repo = path.join(root, "repo");
  const plugin = path.join(root, "plugin");
  fs.mkdirSync(path.join(repo, "knowledge-base"), { recursive: true });
  fs.writeFileSync(path.join(repo, "knowledge-base", "VERSION"), installed);
  fs.mkdirSync(path.join(plugin, "engines", "knowledge-compiler"), { recursive: true });
  fs.writeFileSync(path.join(plugin, "engines", "knowledge-compiler", "VERSION"), shipped);
  const settings = settingsFor("knowledge-base", "hooks/session-start.py");
  const cleanup = () => fs.rmSync(root, { recursive: true, force: true });
  return { repo, plugin, settings, cleanup };
}

/** Run `fn` with a captured stdout and the given env, then restore both. */
function captureStdout(env, fn) {
  const originalWrite = process.stdout.write;
  const originalEnv = process.env;
  let out = "";
  process.stdout.write = (chunk) => {
    out += chunk;
    return true;
  };
  process.env = env;
  try {
    fn();
  } finally {
    process.stdout.write = originalWrite;
    process.env = originalEnv;
  }
  return out;
}

// --- installedDirFor ---------------------------------------------------------

test("installedDirFor: default dir", () => {
  const s = settingsFor("knowledge-base", "hooks/session-start.py");
  assert.equal(vc.installedDirFor(s, "hooks/session-start.py"), "knowledge-base");
});

test("installedDirFor: renamed dir", () => {
  const s = settingsFor("my-kb", "hooks/session-start.py");
  assert.equal(vc.installedDirFor(s, "hooks/session-start.py"), "my-kb");
});

test("installedDirFor: missing marker", () => {
  const s = settingsFor("knowledge-base", "hooks/session-start.py");
  assert.equal(vc.installedDirFor(s, "hooks/co-post-tooluse.py"), null);
});

test("installedDirFor: no hooks", () => {
  assert.equal(vc.installedDirFor({}, "hooks/session-start.py"), null);
});

// --- isBehind ----------------------------------------------------------------

test("isBehind: int behind", () => assert.equal(vc.isBehind("1", "2"), true));
test("isBehind: int current", () => assert.equal(vc.isBehind("2", "2"), false));
test("isBehind: int ahead", () => assert.equal(vc.isBehind("2", "1"), false));
test("isBehind: non-int differs", () => assert.equal(vc.isBehind("a", "b"), true));
test("isBehind: non-int equal", () => assert.equal(vc.isBehind("a", "a"), false));

// Not in the Python suite, but the behaviour it relied on: a version that int()
// would have rejected must fall through to the string comparison, not to NaN.
test("isBehind: mixed int and non-int compares as strings", () => {
  assert.equal(vc.isBehind("2", "2.0"), true);
  assert.equal(vc.isBehind("10", "9"), false);
});

// --- findStale ---------------------------------------------------------------

test("findStale: stale detected", () => {
  const { repo, plugin, settings, cleanup } = setupTree("1", "2");
  try {
    const stale = vc.findStale(repo, plugin, settings);
    assert.equal(stale.length, 1);
    assert.equal(stale[0].engine, "knowledge-compiler");
    assert.equal(stale[0].dir, "knowledge-base");
    assert.deepEqual([stale[0].installed, stale[0].shipped], ["1", "2"]);
  } finally {
    cleanup();
  }
});

test("findStale: current, no stale", () => {
  const { repo, plugin, settings, cleanup } = setupTree("2", "2");
  try {
    assert.deepEqual(vc.findStale(repo, plugin, settings), []);
  } finally {
    cleanup();
  }
});

test("findStale: missing installed VERSION is skipped", () => {
  const { repo, plugin, settings, cleanup } = setupTree("1", "2");
  try {
    fs.rmSync(path.join(repo, "knowledge-base", "VERSION"));
    assert.deepEqual(vc.findStale(repo, plugin, settings), []);
  } finally {
    cleanup();
  }
});

test("findStale: no install is silent", () => {
  const { repo, plugin, cleanup } = setupTree("1", "2");
  try {
    assert.deepEqual(vc.findStale(repo, plugin, { hooks: {} }), []);
  } finally {
    cleanup();
  }
});

// Each engine carries several hook markers, and the first one is not guaranteed to
// be wired: the knowledge-compiler's SessionStart entry can be removed by hand while
// the install is still an install. Discovery has to fall through to a later marker.
test("findStale: found by a marker other than the first", () => {
  const { repo, plugin, cleanup } = setupTree("1", "2");
  try {
    const settings = settingsFor("knowledge-base", "hooks/session-end.py");
    const stale = vc.findStale(repo, plugin, settings);
    assert.equal(stale.length, 1);
    assert.equal(stale[0].dir, "knowledge-base");
  } finally {
    cleanup();
  }
});

// The fourth engine shipped after this map was first written, and its absence from
// the map is exactly how the Python original went stale — silently, because an
// unregistered engine is indistinguishable from an uninstalled one.
test("findStale: stack-compiler is registered", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "vc-test-"));
  const repo = path.join(root, "repo");
  const plugin = path.join(root, "plugin");
  try {
    fs.mkdirSync(path.join(repo, "stack-base"), { recursive: true });
    fs.writeFileSync(path.join(repo, "stack-base", "VERSION"), "1");
    fs.mkdirSync(path.join(plugin, "engines", "stack-compiler"), { recursive: true });
    fs.writeFileSync(path.join(plugin, "engines", "stack-compiler", "VERSION"), "2");
    const settings = settingsFor("stack-base", "hooks/st-post-tooluse.py");
    const stale = vc.findStale(repo, plugin, settings);
    assert.equal(stale.length, 1);
    assert.equal(stale[0].engine, "stack-compiler");
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
});

// --- main --------------------------------------------------------------------

test("main: no env, no output", () => {
  assert.equal(captureStdout({}, vc.main), "");
});

test("main: stale prints additionalContext", () => {
  const { repo, plugin, settings, cleanup } = setupTree("1", "2");
  try {
    fs.mkdirSync(path.join(repo, ".claude"));
    fs.writeFileSync(path.join(repo, ".claude", "settings.json"), JSON.stringify(settings));
    const env = { CLAUDE_PROJECT_DIR: repo, CLAUDE_PLUGIN_ROOT: plugin };
    const out = captureStdout(env, vc.main);
    const ctx = JSON.parse(out).hookSpecificOutput.additionalContext;
    assert.match(ctx, /knowledge-compiler/);
    assert.match(ctx, /\/neurawork-cc-harness:knowledge-compiler/);
  } finally {
    cleanup();
  }
});

// The contract the docstring promises and the hook depends on: an unreadable or
// absent settings.json must produce no stdout at all, because SessionStart stdout
// is injected into the session as context.
test("main: unreadable settings.json is a silent no-op", () => {
  const { repo, plugin, cleanup } = setupTree("1", "2");
  try {
    const env = { CLAUDE_PROJECT_DIR: repo, CLAUDE_PLUGIN_ROOT: plugin };
    assert.equal(captureStdout(env, vc.main), "");
    fs.mkdirSync(path.join(repo, ".claude"));
    fs.writeFileSync(path.join(repo, ".claude", "settings.json"), "{ not json");
    assert.equal(captureStdout(env, vc.main), "");
  } finally {
    cleanup();
  }
});
