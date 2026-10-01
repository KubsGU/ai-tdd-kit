// No shell parsing: paths with spaces remain one argument on every platform.
const { spawnSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const input = fs.readFileSync(0, 'utf8');
const candidates = process.env.AI_TDD_PYTHON
  ? [process.env.AI_TDD_PYTHON]
  : process.platform === 'win32' ? ['python', 'python3'] : ['python3', 'python'];
let executed = false;
for (const executable of candidates) {
  const result = spawnSync(executable, ['-B', path.join(__dirname, 'tdd.py'), 'hook'], {
    input, encoding: 'utf8', timeout: 12000, windowsHide: true, maxBuffer: 1024 * 1024
  });
  if (result.error && result.error.code === 'ENOENT') continue;
  executed = true;
  if (!result.error && result.status === 0) {
    process.stdout.write(result.stdout || '');
    process.exit(0);
  }
  break;
}
process.stdout.write(JSON.stringify({hookSpecificOutput: {
  hookEventName: 'PreToolUse', permissionDecision: 'deny',
  permissionDecisionReason: executed
    ? 'AI TDD hook failed. Check Python 3.10+ and the plugin installation.'
    : 'AI TDD needs Python 3.10+ on PATH; set AI_TDD_PYTHON to its executable if needed.'
}}));
