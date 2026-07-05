#!/usr/bin/env python3
"""Empaqueta agents/{common,orchestrator} en un tar.gz base64 para Agent Engine.

Uso: build_source.py <agents_dir> <out_dir>
Genera: <out_dir>/source.tar.gz.b64
"""
import base64
import io
import pathlib
import sys
import tarfile

agents_dir = pathlib.Path(sys.argv[1]).resolve()
out_dir = pathlib.Path(sys.argv[2]).resolve()
out_dir.mkdir(parents=True, exist_ok=True)

buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tar:
    for sub in ("common", "orchestrator"):
        for f in sorted((agents_dir / sub).rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                tar.add(f, arcname=str(f.relative_to(agents_dir)))
    # requirements en la raíz del paquete
    req = agents_dir / "orchestrator" / "requirements.txt"
    tar.add(req, arcname="requirements.txt")

(out_dir / "source.tar.gz").write_bytes(buf.getvalue())
(out_dir / "source.tar.gz.b64").write_text(base64.b64encode(buf.getvalue()).decode())
import shutil; shutil.copy(agents_dir / "orchestrator" / "requirements.txt", out_dir / "requirements.txt")
print(f"OK -> {out_dir} (source.tar.gz, source.tar.gz.b64, requirements.txt)")
