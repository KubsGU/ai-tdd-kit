// Node.js companion to launch_claude.py; changes only the child environment.
'use strict';
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');
const realpath = fs.realpathSync.native || fs.realpathSync;
const CACHE_FLAGS = ['DISABLE_PROMPT_CACHING', 'DISABLE_PROMPT_CACHING_OPUS', 'DISABLE_PROMPT_CACHING_SONNET',
  'DISABLE_PROMPT_CACHING_HAIKU', 'DISABLE_PROMPT_CACHING_FABLE'];
const EFFORTS = new Set(['low', 'medium', 'high', 'xhigh', 'max']);

function launchEnvironment(parent) {
  const child = { ...parent };
  for (const name of [...CACHE_FLAGS, 'CLAUDE_CODE_SUBAGENT_MODEL', 'CLAUDE_CODE_SUBAGENT_MODEL_FORCE']) delete child[name];
  child.CLAUDE_CODE_DISABLE_BACKGROUND_TASKS = '1';
  return child;
}

function launchArgv(executable, model, effort, extra) {
  const argv = [executable, '--model', model];
  if (effort) argv.push('--effort', effort);
  return argv.concat(extra);
}

function parse(argv, options = {}) {
  const cwd = options.cwd || process.cwd();
  let project = cwd;
  let model = 'sonnet';
  let effort = null;
  let dryRun = false;
  let extra = [];
  for (let index = 0; index < argv.length; index++) {
    const token = argv[index];
    if (token === '--') { extra = argv.slice(index + 1); break; }
    if (!token.startsWith('-')) { extra = argv.slice(index); break; }
    if (token === '--help' || token === '-h') return { help: true };
    if (token === '--dry-run') { dryRun = true; continue; }
    const equals = token.indexOf('=');
    const name = equals === -1 ? token : token.slice(0, equals);
    if (!['--project', '--model', '--effort'].includes(name)) throw new Error('Unknown launcher option: ' + name);
    const value = equals === -1 ? argv[++index] : token.slice(equals + 1);
    if (value === undefined || (equals === -1 && value.startsWith('--'))) throw new Error(name + ' requires a value');
    if (name === '--project') project = path.resolve(cwd, value);
    else if (name === '--model') model = value;
    else {
      if (!EFFORTS.has(value)) throw new Error('Effort must be low, medium, high, xhigh, or max');
      effort = value;
    }
  }
  if (extra.some(value => ['--model', '--effort', '--fallback-model'].includes(value.split('=')[0]))) {
    throw new Error('Set model/effort through launcher options; an automatic fallback profile is not supplied');
  }
  try {
    if (!fs.statSync(project).isDirectory()) throw new Error('not a directory');
    project = realpath(project);
  } catch (error) {
    throw new Error('The feature project must be an existing directory');
  }
  return { project, model, effort, dryRun, extra, help: false };
}

function findClaude(options = {}) {
  const env = options.env || process.env;
  const platform = options.platform || process.platform;
  const filename = platform === 'win32' ? 'claude.exe' : 'claude';
  const directories = (env.PATH || env.Path || '').split(path.delimiter).filter(Boolean);
  for (const directory of directories) {
    const folder = directory.startsWith('"') && directory.endsWith('"') ? directory.slice(1, -1) : directory;
    const candidate = path.resolve(folder, filename);
    try {
      if (!fs.statSync(candidate).isFile()) continue;
      if (platform !== 'win32') fs.accessSync(candidate, fs.constants.X_OK);
      return realpath(candidate);
    } catch (error) {
      // Continue only to other PATH entries; never execute a shell wrapper.
    }
  }
  if (platform === 'win32') {
    throw new Error('Native Claude Code (claude.exe) is required on PATH; install the native CLI. Legacy .cmd wrappers are unsupported');
  }
  throw new Error('Claude Code is not on PATH');
}

function main(argv = process.argv.slice(2), options = {}) {
  const args = parse(argv, options);
  if (args.help) {
    process.stdout.write('Usage: node launch_claude.cjs [--project DIRECTORY] [--model MODEL] [--effort LEVEL] [--dry-run] [-- CLAUDE_OPTIONS]\n');
    return 0;
  }
  if (args.dryRun) {
    process.stdout.write(JSON.stringify({ project: args.project, requested_model: args.model, worker_model: 'inherit',
      effort: args.effort || 'Claude configuration', foreground_workers: true,
      native_prompt_caching: 'not disabled by launch environment', parent_settings_changed: false }) + '\n');
    return 0;
  }
  const env = options.env || process.env;
  const executable = findClaude({ ...options, env });
  const command = launchArgv(executable, args.model, args.effort, args.extra);
  const result = (options.spawn || spawnSync)(command[0], command.slice(1), {
    cwd: args.project, env: launchEnvironment(env), stdio: 'inherit', shell: false, windowsHide: false
  });
  if (result.error) throw new Error('Claude Code execution failed: ' + result.error.message);
  if (result.signal === 'SIGINT') return 130;
  return typeof result.status === 'number' ? result.status : 1;
}

module.exports = { launchEnvironment, launchArgv, parse, findClaude, main };

if (require.main === module) {
  try { process.exitCode = main(); }
  catch (error) { process.stderr.write('AI TDD Claude launcher: ' + error.message + '\n'); process.exitCode = 2; }
}
