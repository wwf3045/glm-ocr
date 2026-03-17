from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence


DEFAULT_PROJECT_DIR = Path(r"C:\Users\28033\Desktop\GLM-OCR")
PYTHONW_EXE = Path(r"D:\anaconda3\pythonw.exe")
APP_SCRIPT_NAME = "duplicate_image_reviewer_app.py"
DEFAULT_ROOT = Path(r"F:\中间文件库")


def message_box(title: str, text: str) -> None:
    if os.name != "nt":
        print(f"{title}: {text}")
        return
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    except Exception:
        print(f"{title}: {text}")


def resolve_project_dir() -> Path:
    exe_dir = Path(sys.executable).resolve().parent
    if (exe_dir / APP_SCRIPT_NAME).exists():
        return exe_dir
    return DEFAULT_PROJECT_DIR


def build_command(project_dir: Path, argv: Sequence[str]) -> list[str]:
    app_script = project_dir / APP_SCRIPT_NAME
    cmd = [str(PYTHONW_EXE), str(app_script)]
    if argv:
        cmd.extend(argv)
    else:
        cmd.extend(["--root", str(DEFAULT_ROOT)])
    return cmd


def main(argv: Sequence[str]) -> int:
    project_dir = resolve_project_dir()
    app_script = project_dir / APP_SCRIPT_NAME
    if not PYTHONW_EXE.exists():
        message_box("OCR Duplicate Reviewer", f"未找到 Python 运行时：\n{PYTHONW_EXE}")
        return 1
    if not app_script.exists():
        message_box("OCR Duplicate Reviewer", f"未找到桌面版脚本：\n{app_script}")
        return 1

    cmd = build_command(project_dir, argv)
    try:
        subprocess.Popen(cmd, cwd=str(project_dir))
    except Exception as exc:
        message_box("OCR Duplicate Reviewer", f"启动失败：\n{exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
