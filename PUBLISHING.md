# Publishing and maintaining this marketplace

This public repository is already a Claude Code marketplace because its root
contains `.claude-plugin/marketplace.json`. Users add `KubsGU/ai-tdd-kit` and
install `ai-tdd@ai-tdd-kit`. A directory listing is a separate distribution route.

## Release an update

From the standalone plugin repository:

1. Update the version in `.claude-plugin/marketplace.json`,
   `plugins/ai-tdd/.claude-plugin/plugin.json` and `BUILD_MANIFEST.json`, plus
   README/plugin README, `runtime-manifest.json` and CHANGELOG.md. Keep plugin
   and marketplace names stable.
2. Run repository Ruff checks, controller tests, `scripts/smoke_demo.py` and
   `scripts/test_strength_demo.py`. For runtime/prompt changes,
   also run the opt-in real-Claude evaluation and record its exact scope.
3. Freeze controller/runtime/runner sources before native builds. Build each
   supported platform on its own host with `scripts/build_runtime.py`, using
   development-only PyInstaller 6.22.3. It is not a cross-compiler. Retain each
   executable, `.json` build metadata/source hashes and `.LICENSES.txt` notices.
   Test the actual bundle through the facade/hook with Python unavailable;
   measure startup against the hook timeout and exercise native .NET evidence.
   Do not describe a mocked platform or a Python-path run as bundled validation.
4. Populate the runtime manifest from those actual binaries' sizes/SHA256 and
   exact version-tagged GitHub asset URLs. Confirm build source hashes match
   the final packaged controller files. Rerun affected checks after changes;
   never edit protected files while a managed integration task is active.
5. Run `claude plugin validate --strict .` and
   `claude plugin validate --strict ./plugins/ai-tdd`.
6. Build with `python -B scripts/build_zip.py`, then check the resulting ZIP with
   `python -B scripts/check_install.py dist/ai-tdd-kit-<version>.zip`.
   The install check uses a temporary `CLAUDE_CONFIG_DIR`.
7. Commit explicit public paths, push normally, and check all GitHub CI jobs.
   Attach the ZIP, its `.sha256` file, all pinned native binaries and their
   metadata/license sidecars to the GitHub release for that commit. Verify
   anonymous ZIP download and a fresh runtime setup from the public asset URLs
   before declaring the release usable. Failed/unavailable hosts stay explicit.
   The post-publication bootstrap check runs on all three runtime hosts with
   `gh workflow run runtime.yml -f release_download=true`; it uses the real
   anonymous downloader and checks the downloaded bundle's doctor/nested hook
   with Python absent from its child PATH. Retain its run URL in release notes.

The ZIP contains only the files in BUILD_MANIFEST.json and a generated checksum
manifest. The git repository should likewise contain public source only. Never
use a private project's git history as this repository's initial history.
Platform binaries are separate release assets downloaded only through explicit
setup; the source ZIP contains their pinned manifest. A cache/download hash check
is integrity relative to that manifest, not an independent publisher signature.

Users can run `claude plugin update ai-tdd@ai-tdd-kit`; the plugin version must
change for the new copy to be installed. Automatic update is a user-side
marketplace setting.
Finish and archive active tasks before updating because their receipts bind
protected plugin files. Launch Claude with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`
and an explicit selected model, or use
`node scripts/launch_claude.cjs --project <path>`.
Include launch instructions in release notes. Version 1.2.0 defaults to compact
controller CLI output; document `--full` for scripts consuming the previous JSON.
Ordinary standalone install checks do not run a Claude task.

## Anthropic directory

The documented directory submission route is the
[developer portal](https://claude.ai/directory/manage), with a paid Claude plan
and the applicable account/organization permission. Review and publication are
managed by Anthropic. Local CLI validation does not guarantee portal acceptance.
Some components are Claude Code-only; this workflow needs local hooks, agents
and test execution, so its complete behavior targets Claude Code.

See [Publish and distribute a plugin](https://code.claude.com/docs/en/plugins/publish)
for the current requirements. The official `claude-plugins-official` marketplace
has a separate partner-contact route; directory submission does not itself add
the plugin to that marketplace.

## Forking

For your own marketplace, replace the repository owner/name in install commands,
homepage/repository fields and plugin README. The runtime manifest and launcher's
allowed release URL owner/name must also match your own published assets; changing
documentation alone is insufficient. Keep integrity and host checks intact.
Choose marketplace/plugin names
before your first release. Keep names stable after people install your fork.
