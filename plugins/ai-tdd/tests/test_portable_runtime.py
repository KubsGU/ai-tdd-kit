"""Portable runtime contracts: trust, argv fidelity, and real external sources."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1]
LAUNCHER = PLUGIN / "scripts/tdd-launcher.cjs"
ENTRY = PLUGIN / "scripts/runtime_entry.py"
NODE = shutil.which("node")
NODE_FLAGS = ["--preserve-symlinks", "--preserve-symlinks-main"]
PLATFORM = {"win32": "win32-x64", "linux": "linux-x64", "darwin": "darwin-arm64"}[sys.platform]
PAYLOAD = b"pinned-runtime-fixture\n"


class RuntimeBuildTests(unittest.TestCase):
    def builder(self):
        source = PLUGIN.parents[1] / "scripts/build_runtime.py"
        self.assertTrue(source.is_file(), "Native runtime builder has not been implemented")
        loader = importlib.util.spec_from_file_location("portable_runtime_builder", source)
        module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(module)
        return module

    @unittest.skipUnless(sys.platform == "win32", "Windows architecture hints are environment variables")
    def test_windows_build_architecture_does_not_depend_on_process_environment(self):
        builder = self.builder()
        with mock.patch.object(builder.platform, "machine", return_value=""):
            try:
                actual = builder.platform_key()
            except ValueError as error:
                self.fail("Build must determine the interpreter architecture without environment hints: " + str(error))
            self.assertEqual(actual, PLATFORM)

    def test_build_import_inventory_accepts_only_stdlib(self):
        builder = self.builder()
        with tempfile.TemporaryDirectory(prefix="ai-tdd-build-imports-") as temporary:
            sources = Path(temporary)
            for name in builder.SOURCES:
                (sources / name).write_text("import argparse\n", encoding="utf-8")
            (sources / "quality.py").write_text("import xml.etree.ElementTree\n", encoding="utf-8")
            builder.SCRIPTS = sources
            self.assertEqual(builder.hidden_imports(), ["argparse", "xml.etree.ElementTree"])
            (sources / "quality.py").write_text("import requests\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "third-party dependency"):
                builder.hidden_imports()

    def test_installed_stdlib_license_is_preserved_when_prefix_has_no_root_license(self):
        builder = self.builder()
        with tempfile.TemporaryDirectory(prefix="ai-tdd-license-layout-") as temporary:
            prefix = Path(temporary)
            stdlib = prefix / "lib/python3.12"
            stdlib.mkdir(parents=True)
            (stdlib / "LICENSE.txt").write_text("Installed CPython notice\nBundled component notice\n", encoding="utf-8")
            copying = prefix / "COPYING.txt"
            copying.write_text("PyInstaller bootloader exception\n", encoding="utf-8")
            distribution = mock.Mock(files=["licenses/COPYING.txt"])
            distribution.locate_file.return_value = copying
            with mock.patch.object(builder.sys, "base_prefix", str(prefix)), \
                    mock.patch.object(builder.sysconfig, "get_path", return_value=str(stdlib)), \
                    mock.patch.object(builder.metadata, "distribution", return_value=distribution):
                try:
                    notices = builder.license_text()
                except ValueError as error:
                    self.fail("Installed stdlib license must be found for setup-python builds: " + str(error))
            self.assertIn("Installed CPython notice\nBundled component notice\n", notices)
            self.assertIn("PyInstaller bootloader exception", notices)

    def test_root_distribution_notices_are_preferred_to_plain_stdlib_license(self):
        builder = self.builder()
        with tempfile.TemporaryDirectory(prefix="ai-tdd-license-priority-") as temporary:
            prefix = Path(temporary)
            stdlib = prefix / "Lib"
            stdlib.mkdir()
            (prefix / "LICENSE.txt").write_text("Full distribution and bundled component notices\n", encoding="utf-8")
            (stdlib / "LICENSE.txt").write_text("Plain stdlib license only\n", encoding="utf-8")
            copying = prefix / "COPYING.txt"
            copying.write_text("PyInstaller bootloader exception\n", encoding="utf-8")
            distribution = mock.Mock(files=["licenses/COPYING.txt"])
            distribution.locate_file.return_value = copying
            with mock.patch.object(builder.sys, "base_prefix", str(prefix)), \
                    mock.patch.object(builder.sysconfig, "get_path", return_value=str(stdlib)), \
                    mock.patch.object(builder.metadata, "distribution", return_value=distribution):
                notices = builder.license_text()
            self.assertIn("Full distribution and bundled component notices", notices)
            self.assertNotIn("Plain stdlib license only", notices)


class RuntimeMeasurementTests(unittest.TestCase):
    def helper(self):
        source = PLUGIN.parents[1] / "scripts/measure_runtime.py"
        self.assertTrue(source.is_file(), "Native hook measurement helper has not been implemented")
        loader = importlib.util.spec_from_file_location("portable_runtime_measurement", source)
        module = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(module)
        return module

    def test_three_samples_require_three_successful_fresh_processes(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory(prefix="ai-tdd-runtime-timing-") as temporary:
            counter = Path(temporary) / "counter.txt"
            code = ("from pathlib import Path;import json; p=Path(" + repr(str(counter)) + ");"
                    "p.write_text(str(int(p.read_text())+1 if p.exists() else 1));"
                    "print(json.dumps({'hook_health':'pass'}))")
            samples = helper.doctor_samples([sys.executable, "-c", code], dict(os.environ))
            self.assertEqual(counter.read_text(), "3")
            self.assertEqual(len(samples), 3)
            self.assertTrue(all(value > 0 for value in samples))

    def test_failed_or_invalid_doctor_never_produces_timing_evidence(self):
        helper = self.helper()
        for code in ("print('{\"hook_health\":\"fail\"}')", "print('{}')", "print('not JSON')",
                     "print('{\"hook_health\":\"pass\"}');raise SystemExit(1)"):
            with self.subTest(code=code):
                with self.assertRaises(ValueError):
                    helper.doctor_samples([sys.executable, "-c", code], dict(os.environ))


@unittest.skipUnless(NODE, "Node.js is required for the launcher tests")
class PortableRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ai-tdd-portable-")
        self.addCleanup(self.temp.cleanup)
        self.sandbox = Path(self.temp.name).resolve()
        self.plugin = self.sandbox / "plugin with spaces"
        self.project = self.sandbox / "project with spaces"
        (self.plugin / "scripts").mkdir(parents=True)
        self.project.mkdir()
        suffix = ".exe" if PLATFORM.startswith("win32") else ""
        self.asset = "ai-tdd-controller-1.5.0-" + PLATFORM + suffix
        self.manifest = {"version": "1.5.0", "platforms": {PLATFORM: {
            "url": "https://github.com/KubsGU/ai-tdd-kit/releases/download/v1.5.0/" + self.asset,
            "sha256": hashlib.sha256(PAYLOAD).hexdigest(), "size": len(PAYLOAD),
        }}}
        self.write_manifest()

    def write_manifest(self):
        (self.plugin / "runtime-manifest.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def api(self, body, **values):
        self.assertTrue(LAUNCHER.is_file(), "Portable Node facade has not been implemented")
        script = ("const api=require(" + json.dumps(str(LAUNCHER)) + ");"
                  "const input=JSON.parse(process.argv[1]);"
                  "(async()=>{" + body + "})().catch(error=>{"
                  "process.stdout.write(JSON.stringify({error:error.message}));process.exitCode=1;});")
        data = {"pluginRoot": str(self.plugin), "root": str(self.project), "platform": PLATFORM.split("-")[0],
                "arch": PLATFORM.split("-")[1], **values}
        result = subprocess.run([NODE, *NODE_FLAGS, "-e", script, json.dumps(data)], capture_output=True, text=True, timeout=20)
        self.assertTrue(result.stdout, result.stderr)
        return result, json.loads(result.stdout)

    def cached_binary(self, data=PAYLOAD):
        binary = self.plugin / ".runtime/1.5.0" / PLATFORM / self.asset
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(data)
        return binary

    def test_missing_runtime_gives_offline_setup_instruction(self):
        result, value = self.api("const spawn=()=>({error:{code:'ENOENT'}});"
                                 "const value=api.resolveRuntime({...input,env:{PATH:''},spawn});"
                                 "process.stdout.write(JSON.stringify(value));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("setup-runtime", value["error"])
        self.assertFalse((self.plugin / ".runtime").exists())

    def test_verified_cache_is_preferred_over_explicit_python(self):
        binary = self.cached_binary()
        result, value = self.api("const spawn=()=>{throw Error('Python must not be probed')};"
                                 "process.stdout.write(JSON.stringify(api.resolveRuntime({...input,"
                                 "env:{AI_TDD_PYTHON:'unwanted-python'},spawn}))); ")
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(value["backend"], "bundled")
        self.assertEqual(Path(value["executable"]), binary)
        self.assertEqual(value["binary_sha256"], hashlib.sha256(PAYLOAD).hexdigest())

    def test_changed_cache_fails_closed_instead_of_falling_back(self):
        self.cached_binary(b"changed binary")
        result, value = self.api("process.stdout.write(JSON.stringify(api.resolveRuntime({...input,"
                                 "env:{AI_TDD_PYTHON:'python'}}))); ")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("integrity", value["error"].lower())

    def test_explicit_real_python_reports_actual_binary_identity(self):
        result, value = self.api("process.stdout.write(JSON.stringify(api.resolveRuntime({...input,"
                                 "env:{...process.env,AI_TDD_PYTHON:input.python}})));", python=sys.executable)
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(value["backend"], "python")
        self.assertEqual(Path(value["executable"]).resolve(), Path(sys.executable).resolve())
        self.assertEqual(value["binary_sha256"], hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest())

    def test_python_version_below_minimum_is_rejected(self):
        result, value = self.api("const spawn=()=>({status:0,stdout:JSON.stringify({"
                                 "executable:input.python,version:[3,9,0]})});"
                                 "process.stdout.write(JSON.stringify(api.resolveRuntime({...input,"
                                 "env:{AI_TDD_PYTHON:input.python},spawn})));", python=sys.executable)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("3.10", value["error"])

    def test_install_verifies_exact_bytes_before_resolving_runtime(self):
        result, value = self.api("const result=await api.setupRuntime({...input,"
                                 "fetchAsset:async()=>Buffer.from(input.bytes,'base64')});"
                                 "process.stdout.write(JSON.stringify(result));", bytes="cGlubmVkLXJ1bnRpbWUtZml4dHVyZQo=")
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(value["backend"], "bundled")
        self.assertEqual(Path(value["executable"]).read_bytes(), PAYLOAD)
        if os.name != "nt":
            self.assertTrue(os.access(value["executable"], os.X_OK))

    def test_wrong_download_hash_is_not_installed(self):
        result, value = self.api("await api.setupRuntime({...input,fetchAsset:async()=>Buffer.from('wrong')});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("integrity", value["error"].lower())
        self.assertFalse(any(path.is_file() for path in (self.plugin / ".runtime").rglob("*")))

    def test_wrong_download_size_is_not_installed(self):
        self.manifest["platforms"][PLATFORM]["size"] += 1
        self.write_manifest()
        result, value = self.api("await api.setupRuntime({...input,fetchAsset:async()=>Buffer.from(input.bytes,'base64')});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));", bytes="cGlubmVkLXJ1bnRpbWUtZml4dHVyZQo=")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("integrity", value["error"].lower())

    def test_active_task_blocks_provisioning_before_fetch(self):
        folder = self.project / ".ai-tdd"
        folder.mkdir()
        (folder / "state.json").write_text('{"phase":"RED"}', encoding="utf-8")
        result, value = self.api("await api.setupRuntime({...input,fetchAsset:async()=>{throw Error('fetch ran')}});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("task", value["error"].lower())
        self.assertNotIn("fetch ran", value["error"])
        self.assertFalse((self.plugin / ".runtime").exists())

    def test_nested_working_directory_cannot_hide_active_task(self):
        (self.project / ".ai-tdd").mkdir()
        (self.project / ".ai-tdd/state.json").write_text("{}", encoding="utf-8")
        nested = self.project / "src/nested"
        nested.mkdir(parents=True)
        result, value = self.api("await api.setupRuntime({...input,root:input.nested,"
                                 "fetchAsset:async()=>{throw Error('fetch ran')}});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));", nested=str(nested))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("task", value["error"].lower())

    def test_manifest_cannot_supply_an_unpinned_url(self):
        self.manifest["platforms"][PLATFORM]["url"] = "https://attacker.invalid/runtime"
        self.write_manifest()
        result, value = self.api("await api.setupRuntime({...input,fetchAsset:async()=>{throw Error('fetch ran')}});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release", value["error"].lower())
        self.assertNotIn("fetch ran", value["error"])

    def test_manifest_version_cannot_escape_cache_directory(self):
        self.manifest["version"] = "../../escape"
        self.write_manifest()
        result, value = self.api("process.stdout.write(JSON.stringify(api.safeCachePath(input.pluginRoot,"
                                 "api.loadManifest(input.pluginRoot),input.platform+'-'+input.arch)));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("version", value["error"].lower())
        self.assertFalse((self.sandbox / "escape").exists())

    def test_safe_path_helper_rejects_direct_traversal_manifest(self):
        result, value = self.api("const version='../../escape';const key=input.platform+'-'+input.arch;"
                                 "const manifest={version,platforms:{[key]:{"
                                 "url:'https://github.com/KubsGU/ai-tdd-kit/releases/download/v'+version+"
                                 "'/ai-tdd-controller-'+version+'-'+key+(key.startsWith('win32')?'.exe':''),"
                                 "sha256:'a'.repeat(64),size:1}}};"
                                 "process.stdout.write(JSON.stringify({path:api.safeCachePath(input.pluginRoot,manifest,key)}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("version", value["error"].lower())

    def test_network_timeout_is_bounded(self):
        result, value = self.api("const https=require('https');const EventEmitter=require('events');"
                                 "https.get=()=>{const request=new EventEmitter();request.destroy=()=>{};return request};"
                                 "await api.fetchAsset('https://github.com/pinned',{timeoutMs:20,maxBytes:10});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("timed out", value["error"])

    def test_network_stream_cannot_exceed_size_bound(self):
        result, value = self.api("const https=require('https');const EventEmitter=require('events');"
                                 "https.get=(url,options,callback)=>{const request=new EventEmitter();request.destroy=()=>{};"
                                 "process.nextTick(()=>{const response=new EventEmitter();response.statusCode=200;response.headers={};"
                                 "response.destroy=()=>{};callback(response);response.emit('data',Buffer.alloc(11));});return request};"
                                 "await api.fetchAsset('https://github.com/pinned',{timeoutMs:1000,maxBytes:10});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("size bound", value["error"])

    def test_download_redirect_cannot_send_request_to_foreign_host(self):
        result, value = self.api("const https=require('https');const EventEmitter=require('events');"
                                 "https.get=(url,options,callback)=>{const request=new EventEmitter();request.destroy=()=>{};"
                                 "process.nextTick(()=>{const response=new EventEmitter();response.statusCode=302;"
                                 "response.headers={location:'https://attacker.invalid/runtime'};response.resume=()=>{};"
                                 "response.destroy=()=>{};callback(response)});return request};"
                                 "await api.fetchAsset('https://github.com/pinned',{timeoutMs:1000,maxBytes:10});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("approved HTTPS GitHub", value["error"])

    def test_malformed_download_redirect_fails_without_process_crash(self):
        result, value = self.api("const https=require('https');const EventEmitter=require('events');"
                                 "https.get=(url,options,callback)=>{const request=new EventEmitter();request.destroy=()=>{};"
                                 "process.nextTick(()=>{const response=new EventEmitter();response.statusCode=302;"
                                 "response.headers={location:'https://[malformed'};response.resume=()=>{};"
                                 "response.destroy=()=>{};callback(response)});return request};"
                                 "await api.fetchAsset('https://github.com/pinned',{timeoutMs:1000,maxBytes:10});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("redirect", value["error"].lower())

    def test_unsupported_platform_does_not_download(self):
        result, value = self.api("await api.setupRuntime({...input,platform:'freebsd',"
                                 "fetchAsset:async()=>{throw Error('fetch ran')}});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported", value["error"].lower())

    def test_linked_cache_directory_is_rejected_without_external_writes(self):
        external = self.sandbox / "external"
        external.mkdir()
        link = self.plugin / ".runtime"
        try:
            if os.name == "nt":
                result = subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(link), str(external)],
                                        capture_output=True, text=True)
                if result.returncode:
                    self.skipTest("Native Windows junction creation unavailable")
            else:
                link.symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("Directory links unavailable")
        result, value = self.api("await api.setupRuntime({...input,"
                                 "fetchAsset:async()=>Buffer.from(input.bytes,'base64')});"
                                 "process.stdout.write(JSON.stringify({accepted:true}));", bytes="cGlubmVkLXJ1bnRpbWUtZml4dHVyZQo=")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("link", value["error"].lower())
        self.assertEqual(list(external.iterdir()), [])

    def test_library_import_does_not_consume_stdin_or_execute_commands(self):
        result, value = self.api("process.stdout.write(JSON.stringify({exports:typeof api.resolveRuntime}));")
        self.assertEqual(result.returncode, 0, value)
        self.assertEqual(value, {"exports": "function"})

    def test_cli_preserves_arguments_with_spaces_and_shell_metacharacters(self):
        self.assertTrue(LAUNCHER.is_file(), "Portable Node facade has not been implemented")
        shutil.copy2(LAUNCHER, self.plugin / "scripts/tdd-launcher.cjs")
        (self.plugin / "scripts/tdd.py").write_text("import json,sys; print(json.dumps(sys.argv[1:]))", encoding="utf-8")
        args = ["--root", str(self.project), "status", "a;b", "$(touch sneaky)", "quoted value"]
        environment = {**os.environ, "AI_TDD_PYTHON": sys.executable}
        result = subprocess.run([NODE, *NODE_FLAGS, str(self.plugin / "scripts/tdd-launcher.cjs"), *args],
                                cwd=self.project, env=environment, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), args)
        self.assertFalse((self.project / "sneaky").exists())

    def test_cli_runtime_info_is_json_without_controller_execution(self):
        self.assertTrue(LAUNCHER.is_file(), "Portable Node facade has not been implemented")
        shutil.copy2(LAUNCHER, self.plugin / "scripts/tdd-launcher.cjs")
        result = subprocess.run([NODE, *NODE_FLAGS, str(self.plugin / "scripts/tdd-launcher.cjs"), "--runtime-info"],
                                env={**os.environ, "AI_TDD_PYTHON": sys.executable}, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["backend"], "python")

    def test_runtime_entry_rejects_arbitrary_external_python(self):
        self.assertTrue(ENTRY.is_file(), "Restricted runtime entry has not been implemented")
        sentinel = self.sandbox / "executed"
        script = self.sandbox / "tdd.py"
        script.write_text("from pathlib import Path; Path(" + repr(str(sentinel)) + ").touch()", encoding="utf-8")
        result = subprocess.run([sys.executable, str(ENTRY), str(script)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(sentinel.exists())

    def test_runtime_entry_executes_real_controller_source(self):
        self.assertTrue(ENTRY.is_file(), "Restricted runtime entry has not been implemented")
        result = subprocess.run([sys.executable, str(ENTRY), str(PLUGIN / "scripts/tdd.py"), "--help"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("begin", result.stdout)
        self.assertIn("status", result.stdout)

    def test_runtime_entry_supports_external_sibling_imports(self):
        self.assertTrue(ENTRY.is_file(), "Restricted runtime entry has not been implemented")
        entry = self.plugin / "scripts/runtime_entry.py"
        source = self.plugin / "scripts/tdd.py"
        shutil.copy2(ENTRY, entry)
        (self.plugin / "scripts/_portable_sibling.py").write_text("MARKER='sibling source loaded'", encoding="utf-8")
        source.write_text("from _portable_sibling import MARKER; import sys; print(MARKER); print(sys.argv[1])", encoding="utf-8")
        # -c does not automatically add the entry's directory to sys.path; frozen
        # interpreters likewise begin with bundled library paths only.
        wrapper = "import runpy,sys;sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
        result = subprocess.run([sys.executable, "-I", "-c", wrapper, str(entry), str(source), "original argument"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["sibling source loaded", "original argument"])
        self.assertFalse((self.plugin / "scripts/__pycache__").exists(),
                         "Bundled entry must preserve the facade's -B no-bytecode behavior")

    def test_runtime_entry_rejects_source_symlink(self):
        self.assertTrue(ENTRY.is_file(), "Restricted runtime entry has not been implemented")
        shutil.copy2(ENTRY, self.plugin / "scripts/runtime_entry.py")
        external = self.sandbox / "outside.py"
        external.write_text("print('external source ran')", encoding="utf-8")
        try:
            (self.plugin / "scripts/tdd.py").symlink_to(external)
        except OSError:
            self.skipTest("File symlinks unavailable")
        result = subprocess.run([sys.executable, str(self.plugin / "scripts/runtime_entry.py"),
                                 str(self.plugin / "scripts/tdd.py")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("external source ran", result.stdout)


@unittest.skipUnless(NODE and os.environ.get("AI_TDD_PACKAGED_EXECUTABLE"), "Run after the native runtime build")
class PackagedRuntimeSmokeTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("PyInstaller"), "Archive inspection uses development-only PyInstaller")
    def test_notices_are_embedded_in_the_downloaded_single_executable(self):
        from PyInstaller.archive.readers import CArchiveReader

        binary = Path(os.environ["AI_TDD_PACKAGED_EXECUTABLE"]).resolve()
        self.assertTrue(binary.is_file(), "Native executable has not been built")
        archive = CArchiveReader(str(binary))
        self.assertIn("ai-tdd-runtime-LICENSES.txt", archive.toc,
                      "Downloadable executable must contain its runtime license notices")
        embedded = archive.extract("ai-tdd-runtime-LICENSES.txt")
        sidecar = binary.with_name(binary.stem + ".LICENSES.txt")
        self.assertEqual(embedded, sidecar.read_bytes())
        self.assertIn(b"CPython", embedded)
        self.assertIn(b"PyInstaller", embedded)
        modules = archive.open_embedded_archive("PYZ.pyz")
        self.assertEqual(set(modules.toc) & {"tdd", "quality", "dotnet_runner", "dotnet_setup"}, set(),
                         "Controller semantics must remain in the real external plugin source")

    def test_native_controller_and_hook_run_with_no_python_on_path(self):
        binary = Path(os.environ["AI_TDD_PACKAGED_EXECUTABLE"]).resolve()
        self.assertTrue(binary.is_file())
        with tempfile.TemporaryDirectory(prefix="ai-tdd-native-") as temporary:
            sandbox = Path(temporary).resolve()
            plugin, project, executables = sandbox / "plugin", sandbox / "project", sandbox / "bin"
            shutil.copytree(PLUGIN / "scripts", plugin / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            project.mkdir()
            executables.mkdir()
            node = executables / ("node.exe" if os.name == "nt" else "node")
            shutil.copy2(NODE, node)
            suffix = ".exe" if os.name == "nt" else ""
            asset = "ai-tdd-controller-1.5.0-" + PLATFORM + suffix
            cached = plugin / ".runtime/1.5.0" / PLATFORM / asset
            cached.parent.mkdir(parents=True)
            shutil.copy2(binary, cached)
            manifest = {"version": "1.5.0", "platforms": {PLATFORM: {
                "url": "https://github.com/KubsGU/ai-tdd-kit/releases/download/v1.5.0/" + asset,
                "sha256": hashlib.sha256(cached.read_bytes()).hexdigest(), "size": cached.stat().st_size,
            }}}
            (plugin / "runtime-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            environment = {**os.environ, "PATH": str(executables)}
            environment.pop("AI_TDD_PYTHON", None)
            launcher = plugin / "scripts/tdd-launcher.cjs"
            info = subprocess.run([str(node), *NODE_FLAGS, str(launcher), "--runtime-info"], env=environment,
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(info.returncode, 0, info.stderr)
            self.assertEqual(json.loads(info.stdout)["backend"], "bundled")
            for route in ("--dotnet-test", "--dotnet-setup"):
                help_result = subprocess.run([str(node), *NODE_FLAGS, str(launcher), route, "--help"],
                                             env=environment, capture_output=True, text=True, timeout=30)
                self.assertEqual(help_result.returncode, 0, help_result.stderr)
                self.assertIn("usage:", help_result.stdout)
            init = subprocess.run([str(node), *NODE_FLAGS, str(launcher), "--root", str(project), "init"], env=environment,
                                  capture_output=True, text=True, timeout=30)
            self.assertEqual(init.returncode, 0, init.stderr)
            self.assertTrue((project / ".ai-tdd/config.json").is_file())
            doctor = subprocess.run([str(node), *NODE_FLAGS, str(launcher), "doctor"], env=environment,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            self.assertEqual(json.loads(doctor.stdout)["hook_health"], "pass")
            rejected = subprocess.run([str(cached), "-c", "print('arbitrary')"], env=environment,
                                      capture_output=True, text=True, timeout=30)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertNotIn("arbitrary", rejected.stdout)


if __name__ == "__main__":
    unittest.main()
