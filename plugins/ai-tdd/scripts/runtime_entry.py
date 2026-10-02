"""Restricted bundled interpreter entry; controller source remains external."""
from pathlib import Path
import runpy
import sys


ALLOWED = {"tdd.py", "dotnet_runner.py", "dotnet_setup.py", "unittest_runner.py"}


def scripts_folder():
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).absolute()
        if executable.is_symlink() or executable.resolve() != executable:
            raise ValueError("Bundled runtime executable cannot be linked")
        # Installer-owned layout: plugin/.runtime/version/platform/asset.
        if len(executable.parents) < 4 or executable.parents[2].name != ".runtime":
            raise ValueError("Bundled runtime must run from the plugin runtime cache")
        folder = executable.parents[3] / "scripts"
    else:
        folder = Path(__file__).absolute().parent
    if folder.is_symlink() or folder.resolve() != folder or not folder.is_dir():
        raise ValueError("External plugin scripts folder cannot be linked")
    return folder


def main():
    if len(sys.argv) < 2:
        raise ValueError("A permitted external controller script is required")
    supplied = Path(sys.argv[1])
    folder = scripts_folder()
    if not supplied.is_absolute() or supplied.name not in ALLOWED or supplied.parent != folder:
        raise ValueError("Runtime accepts only permitted scripts from its installed plugin")
    if supplied.is_symlink() or supplied.resolve() != supplied or not supplied.is_file():
        raise ValueError("External controller source must be a regular file without links")
    sys.argv = [str(supplied), *sys.argv[2:]]
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(folder))
    # No arbitrary -c/module/project execution and no copy of controller semantics.
    runpy.run_path(str(supplied), run_name="__main__")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print("AI TDD bundled runtime: " + str(error), file=sys.stderr)
        raise SystemExit(1) from error
