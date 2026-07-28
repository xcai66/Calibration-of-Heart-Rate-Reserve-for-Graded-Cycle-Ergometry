from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
BASE = Path(os.environ.get("PMDATA_ROOT", PROJECT_ROOT / "source" / "pmdata")).expanduser().resolve()
API_ROOT = "https://api.osf.io/v2/nodes/vx4bk/files/osfstorage/"
PMDATA_FOLDER = "5e99d05ef135350590d5316d"
INCLUDED = {f"p{index:02d}" for index in range(1, 16)}
USER_AGENT = "Codex-PMData-secondary-analysis/1.0"


def request_bytes(url: str, attempts: int = 4) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed after {attempts} attempts: {url}") from last_error


def request_json(url: str) -> dict:
    return json.loads(request_bytes(url).decode("utf-8"))


def list_folder(folder_id: str) -> list[dict]:
    url = f"{API_ROOT}{folder_id}/"
    rows: list[dict] = []
    while url:
        payload = request_json(url)
        rows.extend(payload.get("data", []))
        url = payload.get("links", {}).get("next")
    return rows


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_stream(url: str, destination: Path, expected_sha256: str | None) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and expected_sha256 and sha256_file(destination) == expected_sha256:
        return {"status": "already_present", "size": destination.stat().st_size, "sha256": expected_sha256}
    partial = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(4):
        digest = hashlib.sha256()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=300) as response, partial.open("wb") as handle:
                while True:
                    chunk = response.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    digest.update(chunk)
            actual = digest.hexdigest()
            if expected_sha256 and actual != expected_sha256:
                raise ValueError(f"SHA256 mismatch: {destination}")
            os.replace(partial, destination)
            return {"status": "downloaded", "size": destination.stat().st_size, "sha256": actual}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt + 1 < 4:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Unable to download {url}") from last_error


def locate_participants() -> dict[str, dict]:
    return {
        row["attributes"]["name"]: row
        for row in list_folder(PMDATA_FOLDER)
        if row["attributes"]["kind"] == "folder"
        and row["attributes"]["name"] in INCLUDED
    }


def process_participant(participant: str, participant_row: dict) -> dict:
    folders = {
        row["attributes"]["name"]: row
        for row in list_folder(participant_row["id"])
        if row["attributes"]["kind"] == "folder"
    }
    fitbit = folders["fitbit"]
    files = {
        row["attributes"]["name"]: row
        for row in list_folder(fitbit["id"])
        if row["attributes"]["kind"] == "file"
    }
    source = files["heart_rate.json"]
    expected = source["attributes"].get("extra", {}).get("hashes", {}).get("sha256")
    destination = BASE / participant / "fitbit" / "heart_rate.json"
    result = download_stream(source["links"]["download"], destination, expected)
    result.update(
        {
            "participant": participant,
            "path": str(destination.relative_to(BASE)),
            "source": source["links"]["download"],
            "source_file_id": source["id"],
            "expected_size": source["attributes"].get("size"),
        }
    )
    print(json.dumps({"participant": participant, "status": result["status"], "size": result["size"]}), flush=True)
    return result


def main() -> None:
    participants = locate_participants()
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(process_participant, participant, participants[participant]): participant
            for participant in sorted(participants)
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda row: row["participant"])
    manifest = {
        "dataset": "PMData",
        "osf_node": "vx4bk",
        "participants": results,
        "total_bytes": sum(int(row["size"]) for row in results),
    }
    (BASE / "hr_download_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps({"participants": len(results), "total_bytes": manifest["total_bytes"]}), flush=True)


if __name__ == "__main__":
    main()
