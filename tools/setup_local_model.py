"""Download pinned official GGUF weights and a portable Windows CUDA runtime."""

import hashlib
import json
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / ".cache" / "local-models" / "qwen3-vl-8b"
RUNTIME_DIR = ROOT / ".cache" / "llama-cpp" / "b12613"
REVISION = "f982a07559d4a2f6c8744d840bf6fccab30eea96"
HF = f"https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF/resolve/{REVISION}"
GH = "https://github.com/ggml-org/llama.cpp/releases/download/b12613"
FILES = [
    (MODEL_DIR, "Qwen3VL-8B-Instruct-Q4_K_M.gguf", HF, 5027784800,
     "67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2"),
    (MODEL_DIR, "mmproj-Qwen3VL-8B-Instruct-F16.gguf", HF, 1159029824,
     "ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38"),
    (RUNTIME_DIR, "llama-b12613-bin-win-cuda-13.5-x64.zip", GH, 225600888,
     "87fbf5aab2747a0d18699d8f2894203b904b503926a1656c830ad68bcb5d3cee"),
    (RUNTIME_DIR, "cudart-llama-bin-win-cuda-13.5-x64.zip", GH, 426314199,
     "c2bf4cc202bfbaaa7a0b75f5082457c3811326947bb216059b72839d844e9cba"),
]


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def download_ranges(partial, url, size):
    """Use bounded HTTP ranges so a multi-GB file is not limited to one connection."""
    offset = partial.stat().st_size if partial.exists() else 0
    chunks = partial.with_suffix(".parts")
    chunks.mkdir(exist_ok=True)
    ranges = [(start, min(start + 128 * 1024 * 1024, size) - 1)
              for start in range(offset, size, 128 * 1024 * 1024)]

    def fetch(bounds):
        start, end = bounds
        target = chunks / f"{start}-{end}"
        if target.exists() and target.stat().st_size == end - start + 1:
            return target
        for attempt in range(4):
            try:
                request = urllib.request.Request(
                    f"{url}?download=true&range_start={start}", headers={"Range": f"bytes={start}-{end}"},
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}":
                        raise ValueError("Server did not honor the requested byte range.")
                    with target.open("wb") as output:
                        while chunk := response.read(4 * 1024 * 1024):
                            output.write(chunk)
                if target.stat().st_size != end - start + 1:
                    raise OSError("Incomplete download range.")
                print(f"Downloaded model range {start / 2**30:.2f}-{(end+1) / 2**30:.2f} GiB", flush=True)
                return target
            except (OSError, TimeoutError):
                if attempt == 3:
                    raise
                time.sleep(2)

    with ThreadPoolExecutor(max_workers=8) as executor:
        paths = list(executor.map(fetch, ranges))
    with partial.open("ab") as output:
        for target in paths:
            with target.open("rb") as source:
                while chunk := source.read(4 * 1024 * 1024):
                    output.write(chunk)
            target.unlink()
    chunks.rmdir()


def download(spec):
    directory, name, base, size, sha = spec
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / name
    if target.exists():
        if target.stat().st_size == size and digest(target) == sha:
            print(f"Verified existing {name}", flush=True)
            return target
        raise ValueError(f"Existing file failed verification: {target}")
    partial = target.with_suffix(target.suffix + ".partial")
    if size > 2 * 1024**3:
        download_ranges(partial, f"{base}/{name}", size)
    for attempt in range(4):
        try:
            offset = partial.stat().st_size if partial.exists() else 0
            if offset > size:
                raise ValueError(f"Partial file exceeds expected size: {partial}")
            if offset < size:
                request = urllib.request.Request(
                    f"{base}/{name}?download=true", headers={"Range": f"bytes={offset}-"} if offset else {},
                )
                with urllib.request.urlopen(request, timeout=60) as response:
                    if offset and response.status != 206:
                        offset = 0
                    elif offset and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
                        raise ValueError("Unexpected download range.")
                    with partial.open("ab" if offset else "wb") as output:
                        checkpoint = offset
                        while chunk := response.read(4 * 1024 * 1024):
                            output.write(chunk)
                            offset += len(chunk)
                            if offset - checkpoint >= 128 * 1024 * 1024:
                                print(f"{name}: {offset / size:.0%} ({offset / 2**30:.2f} GiB)", flush=True)
                                checkpoint = offset
            if partial.stat().st_size != size or digest(partial) != sha:
                raise ValueError(f"Size or SHA-256 verification failed: {name}")
            partial.replace(target)
            print(f"Downloaded and SHA-256 verified {name}", flush=True)
            return target
        except (OSError, TimeoutError) as error:
            if attempt == 3:
                raise
            print(f"Retrying {name}: {type(error).__name__}", flush=True)
            time.sleep(2)


def main():
    with ThreadPoolExecutor(max_workers=4) as executor:
        paths = list(executor.map(download, FILES))
    for archive in paths:
        if archive.suffix != ".zip":
            continue
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                if Path(member.filename).suffix.lower() not in {".exe", ".dll"}:
                    continue
                destination = RUNTIME_DIR / Path(member.filename).name
                if not destination.resolve().is_relative_to(RUNTIME_DIR.resolve()):
                    raise ValueError("Archive member is outside the runtime directory.")
                with bundle.open(member) as source, destination.open("wb") as target:
                    while chunk := source.read(4 * 1024 * 1024):
                        target.write(chunk)
    manifest = {"model": "Qwen/Qwen3-VL-8B-Instruct-GGUF", "revision": REVISION,
                "runtime": "llama.cpp b12613, Windows CUDA 13.5 x64",
                "files": [{"path": str(directory / name), "url": f"{base}/{name}", "bytes": size,
                           "sha256": sha} for directory, name, base, size, sha in FILES]}
    (MODEL_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"model_dir": str(MODEL_DIR), "runtime_dir": str(RUNTIME_DIR)}), flush=True)


if __name__ == "__main__":
    main()
