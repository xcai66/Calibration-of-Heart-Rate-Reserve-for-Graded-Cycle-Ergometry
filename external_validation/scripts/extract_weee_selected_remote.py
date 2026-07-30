from __future__ import annotations

import binascii
import hashlib
import json
import re
import struct
import time
import urllib.error
import urllib.request
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "weee"
OUT = RAW / "selected"
MANIFESTS = ROOT / "manifests"
URL = "https://zenodo.org/records/6420886/files/dataset.zip?download=1"
ARCHIVE_BYTES = 651_557_047
TAIL_START = 650_500_000


def parse_entries() -> list[dict]:
    data = (RAW / "dataset.tail").read_bytes() + (RAW / "dataset.tail.part2").read_bytes()
    position = 0
    entries = []
    while True:
        position = data.find(b"PK\x01\x02", position)
        if position < 0 or position + 46 > len(data):
            break
        fields = struct.unpack_from("<4s6H3I5H2I", data, position)
        compressed, uncompressed = fields[8], fields[9]
        name_length, extra_length, comment_length = fields[10], fields[11], fields[12]
        crc32, method, local_offset = fields[7], fields[4], fields[16]
        name = data[position + 46 : position + 46 + name_length].decode("utf-8", "replace")
        entries.append({
            "name": name,
            "compression_method": method,
            "crc32": crc32,
            "compressed_bytes": compressed,
            "uncompressed_bytes": uncompressed,
            "local_header_offset": local_offset,
        })
        position += 46 + name_length + extra_length + comment_length
    if len(entries) < 4000:
        raise RuntimeError(f"Central-directory parse incomplete: {len(entries)} entries")
    return entries


def wanted(name: str) -> bool:
    if name.startswith("__MACOSX/") or name.endswith("/"):
        return False
    if name in {
        "dataset/Study_Information.csv",
        "dataset/Demographics.csv",
        "dataset/Apple watch/HealthAutoExport.csv",
    }:
        return True
    patterns = [
        r"dataset/P\d{2}/E4/HR\.csv$",
        r"dataset/P\d{2}/VO2/(?:Part\d/)?DataAverage\.csv$",
        r"dataset/P\d{2}/VO2/(?:Part\d/)?HeartRateMonitor-Data\.csv$",
        r"dataset/P\d{2}/ZEPHYR/.+_Summary\.csv$",
    ]
    return any(re.fullmatch(pattern, name) for pattern in patterns)


def range_get(start: int, end: int) -> bytes:
    for attempt in range(1, 6):
        try:
            request = urllib.request.Request(URL, headers={"Range": f"bytes={start}-{end}", "User-Agent": "tHRR-I external validation/1.0"})
            with urllib.request.urlopen(request, timeout=180) as response:
                payload = response.read()
                status = getattr(response, "status", None)
            if status != 206:
                raise RuntimeError(f"Server did not honor Range request {start}-{end}; HTTP {status}")
            return payload
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt == 5:
                raise
            print(f"  retry {attempt}/5 after {type(error).__name__}", flush=True)
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def extract_entry(entry: dict) -> dict:
    relative = Path(entry["name"]).relative_to("dataset")
    destination = OUT / relative
    if destination.exists() and destination.stat().st_size == int(entry["uncompressed_bytes"]):
        return {
            **entry,
            "relative_path": str(relative),
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        }
    offset = int(entry["local_header_offset"])
    requested_end = min(ARCHIVE_BYTES - 1, offset + int(entry["compressed_bytes"]) + 8192)
    block = range_get(offset, requested_end)
    if block[:4] != b"PK\x03\x04":
        raise RuntimeError(f"Local header signature missing for {entry['name']}")
    local = struct.unpack_from("<4s5H3I2H", block, 0)
    method, name_length, extra_length = local[3], local[9], local[10]
    data_start = 30 + name_length + extra_length
    data_end = data_start + int(entry["compressed_bytes"])
    compressed = block[data_start:data_end]
    if len(compressed) != int(entry["compressed_bytes"]):
        raise RuntimeError(f"Short range for {entry['name']}")
    if method == 0:
        content = compressed
    elif method == 8:
        content = zlib.decompress(compressed, -15)
    else:
        raise RuntimeError(f"Unsupported ZIP method {method} for {entry['name']}")
    if len(content) != int(entry["uncompressed_bytes"]):
        raise RuntimeError(f"Size mismatch for {entry['name']}")
    crc = binascii.crc32(content) & 0xFFFFFFFF
    if crc != int(entry["crc32"]):
        raise RuntimeError(f"CRC mismatch for {entry['name']}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return {
        **entry,
        "relative_path": str(relative),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    entries = parse_entries()
    selected_by_name = {entry["name"]: entry for entry in entries if wanted(entry["name"])}
    selected = list(selected_by_name.values())
    extracted = []
    for index, entry in enumerate(selected, start=1):
        print(f"[{index}/{len(selected)}] {entry['name']}", flush=True)
        extracted.append(extract_entry(entry))
        time.sleep(0.25)
    manifest = {
        "dataset": "WEEE, A Multi-Device and Multi-Modal Dataset for Wearable Human Energy Expenditure Estimation",
        "doi": "10.5281/zenodo.6420886",
        "version": "v1",
        "license": "CC BY 4.0",
        "source_url": URL,
        "archive_bytes": ARCHIVE_BYTES,
        "access_date": "2026-07-30",
        "selection_rule": "study metadata, demographics, Apple Watch export, participant E4 HR, VO2 DataAverage and chest-HR files, and Zephyr Summary files",
        "selected_files": extracted,
    }
    (MANIFESTS / "weee_selected_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"selected_files": len(extracted), "uncompressed_bytes": sum(item["uncompressed_bytes"] for item in extracted)}, indent=2))


if __name__ == "__main__":
    main()
