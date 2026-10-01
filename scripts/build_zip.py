"""Build a reproducible portable ZIP from an explicit public file allowlist."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

KIT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output")
    args = parser.parse_args()
    manifest = json.loads((KIT / "BUILD_MANIFEST.json").read_text(encoding="utf-8"))
    output = Path(args.output).resolve() if args.output else KIT / "dist" / f'ai-tdd-kit-{manifest["version"]}.zip'
    files = {}
    for relative in manifest["files"]:
        if relative in files or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise SystemExit("Invalid package path")
        path = KIT / relative
        if path.is_symlink() or not path.is_file() or KIT not in path.resolve().parents:
            raise SystemExit("Missing or unsafe package file: " + relative)
        files[relative] = path.read_bytes()
    checksums = {name: hashlib.sha256(value).hexdigest() for name, value in files.items()}
    files["CHECKSUMS.json"] = (json.dumps(checksums, sort_keys=True, indent=2) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, value in sorted(files.items()):
            item = zipfile.ZipInfo("ai-tdd-kit/" + name, date_time=(2026, 9, 30, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, value, compresslevel=9)
    sha = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(sha + "  " + output.name + "\n", encoding="ascii")
    print(json.dumps({"output": str(output), "files": len(files), "bytes": output.stat().st_size, "sha256": sha}))


if __name__ == "__main__":
    main()
