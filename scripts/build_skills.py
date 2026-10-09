"""Build standalone Agent Skills from explicit public source mappings."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

KIT = Path(__file__).resolve().parents[1]


def safe_relative(value):
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or PurePosixPath(value).is_absolute() or any(part in ("", ".", "..") for part in value.split("/"))):
        raise ValueError("Unsafe distribution path")
    return value


def build_all(kit, output_dir):
    kit, output_dir = Path(kit).resolve(), Path(output_dir).resolve()
    manifest = json.loads((kit / "SKILLS_MANIFEST.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Invalid release version")
    results = []
    for name, mapping in sorted(manifest["skills"].items()):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
            raise ValueError("Invalid skill name")
        if not {"SKILL.md", "README.md", "LICENSE"}.issubset(mapping):
            raise ValueError("Incomplete skill")
        files, seen = {}, set()
        for destination, source in mapping.items():
            safe_relative(destination)
            safe_relative(source)
            if destination.casefold() in seen or destination == "CHECKSUMS.json":
                raise ValueError("Duplicate or reserved distribution path")
            seen.add(destination.casefold())
            path = kit / source
            if (not path.is_file() or path.is_symlink() or kit not in path.resolve().parents
                    or any(parent.is_symlink() for parent in path.parents if parent != kit and kit in parent.parents)):
                raise ValueError("Missing or unsafe public source: " + source)
            files[destination] = path.read_bytes()
        files["CHECKSUMS.json"] = (json.dumps({name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
                                             sort_keys=True, indent=2) + "\n").encode()
        output_dir.mkdir(parents=True, exist_ok=True)
        output = output_dir / (name + "-" + version + ".zip")
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for relative, data in sorted(files.items()):
                item = zipfile.ZipInfo(name + "/" + relative, date_time=(2026, 10, 9, 0, 0, 0))
                item.compress_type = zipfile.ZIP_DEFLATED
                item.external_attr = 0o100644 << 16
                archive.writestr(item, data, compresslevel=9)
        sha = hashlib.sha256(output.read_bytes()).hexdigest()
        output.with_suffix(".zip.sha256").write_text(sha + "  " + output.name + "\n", encoding="ascii")
        results.append({"name": name, "version": version, "output": str(output), "sha256": sha,
                        "files": len(files), "bytes": output.stat().st_size})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=KIT / "dist/skills")
    args = parser.parse_args()
    print(json.dumps(build_all(KIT, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
