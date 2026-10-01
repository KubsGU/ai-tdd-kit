# Publishing and maintaining this marketplace

This public repository is already a Claude Code marketplace because its root
contains `.claude-plugin/marketplace.json`. Users add `KubsGU/ai-tdd-kit` and
install `ai-tdd@ai-tdd-kit`. A directory listing is a separate distribution route.

## Release an update

From the standalone plugin repository:

1. Update the version in `.claude-plugin/marketplace.json`,
   `plugins/ai-tdd/.claude-plugin/plugin.json` and `BUILD_MANIFEST.json`, plus
   README/plugin README and CHANGELOG.md. Keep plugin and marketplace names stable.
2. Run the controller tests and `scripts/smoke_demo.py`. For runtime/prompt changes,
   also run the opt-in real-Claude evaluation and record its exact scope.
3. Run `claude plugin validate --strict .` and
   `claude plugin validate --strict ./plugins/ai-tdd`.
4. Build with `python -B scripts/build_zip.py`, then check the resulting ZIP with
   `python -B scripts/check_install.py dist/ai-tdd-kit-<version>.zip`.
   The install check uses a temporary `CLAUDE_CONFIG_DIR`.
5. Commit explicit public paths, push normally, and check all GitHub CI jobs.
   Attach the ZIP and its `.sha256` file to the GitHub release for that commit.

The ZIP contains only the files in BUILD_MANIFEST.json and a generated checksum
manifest. The git repository should likewise contain public source only. Never
use a private project's git history as this repository's initial history.

Users can run `claude plugin update ai-tdd@ai-tdd-kit`; the plugin version must
change for the new copy to be installed. Automatic update is a user-side
marketplace setting.
Finish and archive active tasks before updating because their receipts bind
protected plugin files. Launch Claude with `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1`
and an explicit selected model, or use `scripts/launch_claude.py --project <path>`.
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
homepage/repository fields and plugin README. Choose marketplace/plugin names
before your first release. Keep names stable after people install your fork.
