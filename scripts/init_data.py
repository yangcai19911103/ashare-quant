"""通过 HTTP 触发 /api/data/init 并轮询直到完成。

用法：
    python scripts/init_data.py
"""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.request

# 强制 stdout 用 UTF-8，避免 Windows cp936 控制台无法打印中文/emoji
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"


def _post(path: str, payload: dict) -> dict:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def _get(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read().decode())


def main() -> int:
    payload = {
        "sources": ["akshare", "efinance"],
        "start_date": "2018-01-01",
        "end_date": "2026-05-13",
        "workers": 4,
        "include_minute": False,
        "include_north_flow": True,
        "include_lhb": True,
    }

    print(">> POST /api/data/init", json.dumps(payload, ensure_ascii=False))
    try:
        resp = _post("/api/data/init", payload)
    except urllib.error.HTTPError as e:
        print(f"[ERR] HTTP {e.code}: {e.read().decode(errors='ignore')}")
        return 1
    print(">> 响应:", resp)
    job_id = resp.get("job_id")
    if not job_id:
        print("[ERR] 未返回 job_id")
        return 1

    print(f">> 开始轮询 job {job_id} ...")
    last_progress = -1
    for _ in range(120):
        time.sleep(1.0)
        info = _get(f"/api/data/jobs/{job_id}")
        pg = info.get("progress", 0)
        status = info.get("status")
        if pg != last_progress:
            print(f"   [{status}] {pg}%  {(info.get('log') or '').splitlines()[-1] if info.get('log') else ''}")
            last_progress = pg
        if status in ("success", "failed"):
            print(">> 最终状态:", status)
            print(">> 完整日志:")
            print(info.get("log") or "")
            print(">> 仓库统计：")
            print(json.dumps(_get("/api/data/warehouse"), ensure_ascii=False, indent=2))
            return 0 if status == "success" else 2
    print("[WARN] 超过 120s 仍未完成")
    return 3


if __name__ == "__main__":
    sys.exit(main())
