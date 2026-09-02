"""边缘节点代理：轮询平台拉取部署与推理请求，本地执行并回传结果。

用法：
  python scripts/node_agent.py --base http://localhost:8000/api/v1 --node-id <id> --token <token> --work-dir <dir>

仅使用标准库。工作流程：
  1. 心跳保持在线
  2. 拉取已部署算法包（下载 zip 到 work-dir，首次下载后缓存）
  3. 拉取待处理推理请求，加载包内 entrypoint 执行，回传结果
"""

import argparse
import importlib.util
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

POLL_INTERVAL_SECONDS = 5


def _request(base: str, path: str, token: str, method: str = "GET", body: dict | None = None):
    url = f"{base}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("X-Node-Token", token)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read()


def _load_entrypoint(module_path: Path):
    spec = importlib.util.spec_from_file_location("node_pkg_inference", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载入口模块: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_package(package_dir: Path, entrypoint: str, params: dict) -> dict:
    module_name, _, func_name = entrypoint.partition(":")
    module = _load_entrypoint(package_dir / module_name)
    func = getattr(module, func_name or "run")
    output = func({"params": params})
    return output or {}


def main() -> None:
    parser = argparse.ArgumentParser(description="边缘节点代理")
    parser.add_argument("--base", required=True, help="平台 API 基础地址，如 http://localhost:8000/api/v1")
    parser.add_argument("--node-id", required=True, help="节点 ID")
    parser.add_argument("--token", required=True, help="节点令牌")
    parser.add_argument("--work-dir", default=".node_agent_cache", help="算法包缓存目录")
    args = parser.parse_args()

    base = args.base.rstrip("/")
    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"[node-agent] 节点 {args.node_id} 连接 {base}")

    while True:
        try:
            _request(base, f"/nodes/{args.node_id}/heartbeat", args.token, method="POST")

            _, content = _request(base, "/nodes/me/deployments", args.token)
            deployments = json.loads(content.decode("utf-8"))
            for dep in deployments:
                deployment_id = dep["deployment_id"]
                package_dir = work_dir / deployment_id
                if not (package_dir / "manifest.json").exists():
                    status, package_bytes = _request(
                        base, f"/nodes/deployments/{deployment_id}/package", args.token
                    )
                    if status != 200:
                        continue
                    with zipfile.ZipFile(io.BytesIO(package_bytes)) as zf:
                        zf.extractall(package_dir)
                    print(f"[node-agent] 下载算法包 {deployment_id}")

                manifest = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
                _, pending_content = _request(
                    base, f"/nodes/deployments/{deployment_id}/pending", args.token
                )
                pending = json.loads(pending_content.decode("utf-8"))
                if not pending["pending"]:
                    continue

                params = pending.get("params") or {}
                output = _run_package(package_dir, manifest["entrypoint"], params)
                _request(
                    base,
                    f"/nodes/deployments/{deployment_id}/results",
                    args.token,
                    method="POST",
                    body=output,
                )
                print(f"[node-agent] 执行完成 {deployment_id}: {output}")
        except urllib.error.HTTPError as exc:
            print(f"[node-agent] 平台返回 {exc.code}", file=sys.stderr)
        except Exception as exc:
            print(f"[node-agent] 轮询异常: {exc}", file=sys.stderr)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
