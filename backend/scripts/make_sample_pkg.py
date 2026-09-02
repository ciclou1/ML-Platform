"""构造一个最小算法包 zip，用于本地验证算法上架链路。"""

import io
import zipfile

INFERENCE_CODE = '''
def run(payload):
    params = payload.get("params") or {}
    values = params.get("values") or []
    return {"sum": sum(values), "count": len(values)}
'''


def main() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("inference.py", INFERENCE_CODE)
        zf.writestr("README.md", "sample algorithm package")
    with open("sample_pkg.zip", "wb") as fp:
        fp.write(buf.getvalue())
    print("sample_pkg.zip created")


if __name__ == "__main__":
    main()
