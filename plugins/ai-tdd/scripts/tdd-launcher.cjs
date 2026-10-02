// Stable Node.js 14+ facade. Downloads occur only in explicit setup-runtime.
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const https = require('https');
const { spawnSync } = require('child_process');
const realpath = fs.realpathSync.native || fs.realpathSync;

const PLUGIN_ROOT = path.resolve(__dirname, '..');
const MAX_ASSET_BYTES = 128 * 1024 * 1024;
const DOWNLOAD_TIMEOUT_MS = 120000;
const SUPPORTED = new Set(['win32-x64', 'linux-x64', 'darwin-arm64']);
const ENTRIES = new Set(['tdd.py', 'dotnet_runner.py', 'dotnet_setup.py', 'unittest_runner.py']);

function samePath(left, right) {
  return process.platform === 'win32' ? left.toLowerCase() === right.toLowerCase() : left === right;
}

function regularFile(file, label) {
  const stats = fs.lstatSync(file);
  if (!stats.isFile() || stats.isSymbolicLink() || !samePath(realpath(file), path.resolve(file))) {
    throw new Error(label + ' must be a regular file without links');
  }
  return stats;
}

function loadManifest(pluginRoot = PLUGIN_ROOT) {
  const file = path.join(pluginRoot, 'runtime-manifest.json');
  if (regularFile(file, 'Runtime manifest').size > 65536) throw new Error('Oversized runtime manifest');
  const manifest = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!manifest || typeof manifest.version !== 'string' ||
      !/^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$/.test(manifest.version)) {
    throw new Error('Invalid pinned runtime version');
  }
  if (!manifest.platforms || typeof manifest.platforms !== 'object' || Array.isArray(manifest.platforms)) {
    throw new Error('Invalid runtime platform manifest');
  }
  return manifest;
}

function assetFor(manifest, platformKey) {
  if (!SUPPORTED.has(platformKey) || !Object.prototype.hasOwnProperty.call(manifest.platforms, platformKey)) {
    throw new Error('Unsupported bundled runtime platform: ' + platformKey + '; install Python 3.10+ instead');
  }
  const asset = manifest.platforms[platformKey];
  const name = 'ai-tdd-controller-' + manifest.version + '-' + platformKey + (platformKey.startsWith('win32-') ? '.exe' : '');
  const expected = 'https://github.com/KubsGU/ai-tdd-kit/releases/download/v' + manifest.version + '/' + name;
  if (!asset || asset.url !== expected) throw new Error('Runtime URL must name the exact pinned GitHub release asset');
  if (typeof asset.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(asset.sha256) ||
      !Number.isSafeInteger(asset.size) || asset.size <= 0 || asset.size > MAX_ASSET_BYTES) {
    throw new Error('Invalid runtime integrity metadata');
  }
  return { ...asset, name };
}

function safeCachePath(pluginRoot, manifest, platformKey) {
  if (!manifest || typeof manifest.version !== 'string' ||
      !/^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$/.test(manifest.version)) {
    throw new Error('Invalid pinned runtime version');
  }
  const root = path.resolve(pluginRoot);
  if (!samePath(realpath(root), root) || !fs.lstatSync(root).isDirectory()) {
    throw new Error('Plugin cache root cannot contain linked directories');
  }
  const asset = assetFor(manifest, platformKey);
  const parts = ['.runtime', manifest.version, platformKey];
  let cursor = root;
  for (const part of parts) {
    cursor = path.join(cursor, part);
    if (!fs.existsSync(cursor)) {
      // lstat also detects dangling links which existsSync would hide.
      try {
        fs.lstatSync(cursor);
        throw new Error('Runtime cache cannot contain linked directories');
      } catch (error) {
        if (error.code !== 'ENOENT') throw error;
      }
      continue;
    }
    const stats = fs.lstatSync(cursor);
    if (!stats.isDirectory() || stats.isSymbolicLink() || !samePath(realpath(cursor), cursor)) {
      throw new Error('Runtime cache cannot contain linked directories');
    }
  }
  return path.join(cursor, asset.name);
}

function verifyIntegrity(file, asset) {
  const stats = regularFile(file, 'Runtime binary');
  if (stats.size !== asset.size || stats.size > MAX_ASSET_BYTES) throw new Error('Runtime integrity check failed: size');
  const actual = crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
  if (actual !== asset.sha256) throw new Error('Runtime integrity check failed: SHA256');
  return actual;
}

function runtimeInfo(runtime) {
  return { executable: runtime.executable, backend: runtime.backend, binary_sha256: runtime.binary_sha256 };
}

function resolveRuntime(options = {}) {
  const pluginRoot = options.pluginRoot || PLUGIN_ROOT;
  const platform = options.platform || process.platform;
  const arch = options.arch || process.arch;
  const platformKey = platform + '-' + arch;
  const env = options.env || process.env;
  const spawn = options.spawn || spawnSync;
  const manifest = loadManifest(pluginRoot);
  if (SUPPORTED.has(platformKey) && Object.prototype.hasOwnProperty.call(manifest.platforms, platformKey)) {
    const file = safeCachePath(pluginRoot, manifest, platformKey);
    try {
      fs.lstatSync(file);
      return { executable: file, backend: 'bundled', binary_sha256: verifyIntegrity(file, assetFor(manifest, platformKey)) };
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  const candidates = env.AI_TDD_PYTHON ? [env.AI_TDD_PYTHON] : platform === 'win32' ? ['python', 'python3'] : ['python3', 'python'];
  const probe = 'import json,sys;print(json.dumps({"executable":sys.executable,"version":list(sys.version_info[:3])}))';
  for (const candidate of candidates) {
    const result = spawn(candidate, ['-I', '-c', probe], {
      env, encoding: 'utf8', timeout: 10000, maxBuffer: 65536, windowsHide: true, shell: false
    });
    if (result.error && result.error.code === 'ENOENT') continue;
    try {
      if (result.error || result.status !== 0) continue;
      const found = JSON.parse(result.stdout);
      if (!Array.isArray(found.version) || found.version[0] !== 3 || found.version[1] < 10 ||
          typeof found.executable !== 'string' || !path.isAbsolute(found.executable)) continue;
      const executable = realpath(found.executable);
      regularFile(executable, 'Python executable');
      return { executable, backend: 'python', binary_sha256: crypto.createHash('sha256').update(fs.readFileSync(executable)).digest('hex') };
    } catch (error) {
      // A broken or incompatible candidate is never invoked as the controller.
    }
  }
  throw new Error('AI TDD needs Python 3.10+ or the pinned controller runtime. Before starting a task, run: node "' +
    path.join(pluginRoot, 'scripts/tdd-launcher.cjs') + '" setup-runtime');
}

function runtimeInvocation(runtime, script, args) {
  const absolute = path.resolve(script);
  if (!ENTRIES.has(path.basename(absolute)) || path.basename(path.dirname(absolute)) !== 'scripts') {
    throw new Error('Unsupported controller runtime entry');
  }
  regularFile(absolute, 'Controller source');
  if (!samePath(realpath(path.dirname(absolute)), path.dirname(absolute))) {
    throw new Error('Controller scripts cannot contain linked directories');
  }
  return { executable: runtime.executable, args: runtime.backend === 'bundled' ? [absolute, ...args] : ['-B', absolute, ...args] };
}

function assertBeforeTask(root) {
  let cursor = path.resolve(root);
  while (true) {
    const folder = path.join(cursor, '.ai-tdd');
    try {
      const stats = fs.lstatSync(folder);
      if (!stats.isDirectory() || stats.isSymbolicLink() || !samePath(realpath(folder), folder)) {
        throw new Error('Runtime setup cannot inspect linked task state directories');
      }
      for (const name of ['state.json', 'controller.lock']) {
        try {
          fs.lstatSync(path.join(folder, name));
          throw new Error('Provision the runtime before starting a task; archive the existing task first');
        } catch (error) {
          if (error.code !== 'ENOENT') throw error;
        }
      }
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    const parent = path.dirname(cursor);
    if (parent === cursor) return;
    cursor = parent;
  }
}

function fetchAsset(url, options = {}) {
  const maximum = options.maxBytes || MAX_ASSET_BYTES;
  const timeout = options.timeoutMs || DOWNLOAD_TIMEOUT_MS;
  return new Promise((resolve, reject) => {
    let request;
    let finished = false;
    const timer = setTimeout(() => finish(new Error('Runtime download timed out')), timeout);
    function finish(error, data) {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      if (error) {
        if (request) request.destroy();
        reject(error);
      } else resolve(data);
    }
    function requestUrl(address, redirects) {
      let target;
      try { target = new URL(address); } catch (error) { finish(new Error('Invalid runtime download URL')); return; }
      if (target.protocol !== 'https:' || target.username || target.password || (target.port && target.port !== '443') ||
          !['github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'].includes(target.hostname)) {
        finish(new Error('Runtime download redirect is not an approved HTTPS GitHub asset host')); return;
      }
      request = https.get(target, { headers: { 'User-Agent': 'ai-tdd-runtime-installer', 'Accept': 'application/octet-stream' } }, response => {
        if (finished) { response.destroy(); return; }
        if ([301, 302, 303, 307, 308].includes(response.statusCode)) {
          response.resume();
          if (redirects >= 4 || !response.headers.location) { finish(new Error('Too many runtime download redirects')); return; }
          try {
            requestUrl(new URL(response.headers.location, target).href, redirects + 1);
          } catch (error) {
            finish(new Error('Invalid runtime download redirect URL'));
          }
          return;
        }
        if (response.statusCode !== 200) { response.resume(); finish(new Error('Runtime download returned HTTP ' + response.statusCode)); return; }
        const length = response.headers['content-length'];
        if (length && (!/^\d+$/.test(length) || Number(length) > maximum)) {
          response.destroy(); finish(new Error('Runtime download exceeds the size bound')); return;
        }
        const chunks = [];
        let bytes = 0;
        response.on('data', chunk => {
          bytes += chunk.length;
          if (bytes > maximum) { response.destroy(); finish(new Error('Runtime download exceeds the size bound')); }
          else chunks.push(chunk);
        });
        response.on('end', () => finish(null, Buffer.concat(chunks)));
        response.on('error', error => finish(error));
        response.on('aborted', () => finish(new Error('Runtime download interrupted')));
      });
      request.on('error', error => finish(error));
    }
    requestUrl(url, 0);
  });
}

async function setupRuntime(options = {}) {
  const pluginRoot = options.pluginRoot || PLUGIN_ROOT;
  assertBeforeTask(options.root || process.cwd());
  assertBeforeTask(process.cwd());
  const manifest = loadManifest(pluginRoot);
  const platformKey = (options.platform || process.platform) + '-' + (options.arch || process.arch);
  const asset = assetFor(manifest, platformKey);
  const file = safeCachePath(pluginRoot, manifest, platformKey);
  try {
    fs.lstatSync(file);
    return { executable: file, backend: 'bundled', binary_sha256: verifyIntegrity(file, asset) };
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  const fetch = options.fetchAsset || fetchAsset;
  const bytes = await fetch(asset.url, { maxBytes: asset.size, timeoutMs: DOWNLOAD_TIMEOUT_MS });
  if (!Buffer.isBuffer(bytes) || bytes.length !== asset.size ||
      crypto.createHash('sha256').update(bytes).digest('hex') !== asset.sha256) {
    throw new Error('Downloaded runtime integrity check failed');
  }
  // Recheck paths and task state after network I/O, before any installation.
  assertBeforeTask(options.root || process.cwd());
  assertBeforeTask(process.cwd());
  safeCachePath(pluginRoot, manifest, platformKey);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  safeCachePath(pluginRoot, manifest, platformKey);
  const temporary = file + '.' + crypto.randomBytes(16).toString('hex') + '.tmp';
  try {
    fs.writeFileSync(temporary, bytes, { flag: 'wx', mode: 0o700 });
    verifyIntegrity(temporary, asset);
    safeCachePath(pluginRoot, manifest, platformKey);
    try {
      fs.lstatSync(file);
      throw new Error('Runtime destination appeared during setup; retry after inspecting the cache');
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    fs.renameSync(temporary, file);
    return { executable: file, backend: 'bundled', binary_sha256: verifyIntegrity(file, asset) };
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
}

async function runMain(argv = process.argv.slice(2), options = {}) {
  const pluginRoot = options.pluginRoot || PLUGIN_ROOT;
  if (argv[0] === 'setup-runtime') {
    let root = process.cwd();
    if (argv.length !== 1) {
      if (argv.length !== 3 || argv[1] !== '--root') throw new Error('Usage: setup-runtime [--root PROJECT]');
      root = path.resolve(argv[2]);
    }
    process.stdout.write(JSON.stringify(runtimeInfo(await setupRuntime({ ...options, pluginRoot, root }))) + '\n');
    return 0;
  }
  const runtime = resolveRuntime({ ...options, pluginRoot });
  if (argv[0] === '--runtime-info') {
    if (argv.length !== 1) throw new Error('--runtime-info takes no additional arguments');
    process.stdout.write(JSON.stringify(runtimeInfo(runtime)) + '\n');
    return 0;
  }
  let script = 'tdd.py';
  if (argv[0] === '--dotnet-test' || argv[0] === '--dotnet-setup') {
    script = argv[0] === '--dotnet-test' ? 'dotnet_runner.py' : 'dotnet_setup.py';
    argv = argv.slice(1);
  }
  const invocation = runtimeInvocation(runtime, path.join(pluginRoot, 'scripts', script), argv);
  const result = (options.spawn || spawnSync)(invocation.executable, invocation.args, {
    env: options.env || process.env, stdio: 'inherit', windowsHide: true, shell: false
  });
  if (result.error) throw new Error('Controller execution failed: ' + result.error.message);
  return typeof result.status === 'number' ? result.status : 1;
}

module.exports = { resolveRuntime, runtimeInvocation, runtimeInfo, loadManifest, safeCachePath, verifyIntegrity,
  setupRuntime, fetchAsset, assertBeforeTask, runMain };

if (require.main === module) {
  runMain().then(status => { process.exitCode = status; }).catch(error => {
    process.stderr.write(JSON.stringify({ ok: false, error: error.message }) + '\n');
    process.exitCode = 1;
  });
}
