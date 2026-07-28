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
TARGETS = {
    "pmsys": {"srpe.csv", "wellness.csv"},
    "fitbit": {"exercise.json", "resting_heart_rate.json", "sleep_score.csv"},
}


def request_bytes(url: str, attempts: int = 4) -> bytes:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Codex-PMData-secondary-analysis/1.0"})
            with urllib.request.urlopen(req, timeout=180) as response:
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


def download_file(file_row: dict, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = request_bytes(file_row["links"]["download"])
    destination.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    expected = file_row["attributes"].get("extra", {}).get("hashes", {}).get("sha256")
    if expected and digest != expected:
        raise ValueError(f"SHA256 mismatch for {destination}")
    return {
        "path": str(destination.relative_to(BASE)),
        "size": len(data),
        "sha256": digest,
        "source": file_row["links"]["download"],
        "source_file_id": file_row["id"],
    }


def process_participant(row: dict) -> dict:
    participant = row["attributes"]["name"]
    participant_dir = BASE / participant
    result = {"participant": participant, "files": [], "missing": []}
    subfolders = {
        child["attributes"]["name"]: child["id"]
        for child in list_folder(row["id"])
        if child["attributes"]["kind"] == "folder"
    }
    for subfolder, target_names in TARGETS.items():
        folder_id = subfolders.get(subfolder)
        if not folder_id:
            result["missing"].extend(f"{subfolder}/{name}" for name in sorted(target_names))
            continue
        files = {
            child["attributes"]["name"]: child
            for child in list_folder(folder_id)
            if child["attributes"]["kind"] == "file"
        }
        for name in sorted(target_names):
            file_row = files.get(name)
            if file_row is None:
                result["missing"].append(f"{subfolder}/{name}")
                continue
            result["files"].append(
                download_file(file_row, participant_dir / subfolder / name)
            )
    return result


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    participants = [
        row
        for row in list_folder(PMDATA_FOLDER)
        if row["attributes"]["kind"] == "folder"
        and row["attributes"]["name"].startswith("p")
    ]
    participants.sort(key=lambda row: row["attributes"]["name"])
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_participant, row) for row in participants]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda row: row["participant"])
    manifest = {
        "dataset": "PMData",
        "osf_node": "vx4bk",
        "downloaded_file_types": {key: sorted(value) for key, value in TARGETS.items()},
        "participants": results,
    }
    (BASE / "metadata_download_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "participants": len(results),
        "files": sum(len(row["files"]) for row in results),
        "missing": sum(len(row["missing"]) for row in results),
    }))


if __name__ == "__main__":
    main()
