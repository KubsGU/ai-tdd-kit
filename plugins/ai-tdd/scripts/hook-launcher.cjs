// A quiescent project needs no controller runtime. Active tasks fail closed.
'use strict';
const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');

function needsRuntime(payload) {
  if (payload.tool_name === 'AI_TDD_SELFTEST') return true;
  if (typeof payload.cwd !== 'string' || !payload.cwd.trim()) throw new Error('Missing hook cwd');
  let cursor = path.resolve(payload.cwd);
  const realpath = fs.realpathSync.native || fs.realpathSync;
  while (true) {
    const folder = path.join(cursor, '.ai-tdd');
    try {
      const stats = fs.lstatSync(folder);
      const canonical = realpath(folder);
      const same = process.platform === 'win32' ? canonical.toLowerCase() === folder.toLowerCase() : canonical === folder;
      if (!stats.isDirectory() || stats.isSymbolicLink() || !same) throw new Error('Linked or invalid task state directory');
      try { fs.lstatSync(path.join(folder, 'state.json')); return true; }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    const parent = path.dirname(cursor);
    if (parent === cursor) return false;
    cursor = parent;
  }
}

try {
  const input = fs.readFileSync(0, 'utf8');
  const payload = JSON.parse(input);
  if (needsRuntime(payload)) {
    const { resolveRuntime, runtimeInvocation } = require('./tdd-launcher.cjs');
    const invocation = runtimeInvocation(resolveRuntime(), path.join(__dirname, 'tdd.py'), ['hook']);
    const result = spawnSync(invocation.executable, invocation.args, {
      input, encoding: 'utf8', timeout: 12000, windowsHide: true, maxBuffer: 1024 * 1024, shell: false
    });
    if (result.error || result.status !== 0) throw new Error('Controller hook execution failed');
    process.stdout.write(result.stdout || '');
  }
} catch (error) {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: {
    hookEventName: 'PreToolUse', permissionDecision: 'deny',
    permissionDecisionReason: 'AI TDD hook failed: ' + error.message
  } }));
}
