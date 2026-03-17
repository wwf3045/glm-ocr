from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Callable, Iterable

CRASH_LOG_PATH = Path(sys.executable).resolve().parent / "ocr_duplicate_reviewer_crash.log" if getattr(sys, "frozen", False) else Path(__file__).resolve().parent / "ocr_duplicate_reviewer_crash.log"


def write_crash_log(header: str, details: str) -> None:
    try:
        CRASH_LOG_PATH.write_text(f"{header}\n\n{details}", encoding="utf-8")
    except OSError:
        pass


def append_crash_log(header: str, details: str) -> None:
    try:
        with CRASH_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"\n\n{header}\n\n{details}")
    except OSError:
        pass


def install_crash_logging() -> None:
    def _sys_hook(exc_type, exc_value, exc_traceback):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        append_crash_log("sys.excepthook", text)
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def _thread_hook(args: threading.ExceptHookArgs):
        text = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        write_crash_log(f"threading.excepthook: {getattr(args.thread, 'name', 'unknown')}", text)
        threading.__excepthook__(args)

    sys.excepthook = _sys_hook
    threading.excepthook = _thread_hook


install_crash_logging()
write_crash_log("startup", "process started")

if sys.platform == "win32":
    def _prepend_env_path(name: str, path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if not resolved.exists():
            return
        current = os.environ.get(name, "")
        parts = [part for part in current.split(os.pathsep) if part]
        normalized = {part.lower() for part in parts}
        value = str(resolved)
        if value.lower() in normalized:
            return
        os.environ[name] = os.pathsep.join([value, *parts]) if parts else value

    def _set_env_path(name: str, path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if not resolved.exists():
            return
        os.environ[name] = str(resolved)

    def _candidate_python_roots() -> list[Path]:
        roots: list[Path] = []
        seen: set[str] = set()

        def _add(root: Path | None) -> None:
            if root is None:
                return
            try:
                resolved = root.resolve()
            except OSError:
                return
            key = str(resolved).lower()
            if key in seen or not resolved.exists():
                return
            seen.add(key)
            roots.append(resolved)

        env_candidates = [
            os.environ.get("CONDA_PREFIX"),
            os.environ.get("PYTHONHOME"),
        ]
        for item in env_candidates:
            if item:
                _add(Path(item))

        conda_python = os.environ.get("CONDA_PYTHON_EXE")
        if conda_python:
            _add(Path(conda_python).resolve().parent)

        try:
            _add(Path(sys.base_prefix))
        except Exception:
            pass

        for fallback in (
            Path(r"D:\anaconda3"),
            Path.home() / "anaconda3",
            Path.home() / "miniconda3",
            Path.home() / "miniforge3",
        ):
            _add(fallback)
        return roots

    candidate_dirs: list[Path] = []
    runtime_dirs: list[Path] = []
    windir = os.environ.get("WINDIR")
    system32 = Path(windir) / "System32" if windir else None

    def _push_runtime_dir(path: Path | None) -> None:
        if path is None:
            return
        runtime_dirs.append(path)

    python_roots = _candidate_python_roots()
    library_bins = [root / "Library" / "bin" for root in python_roots]
    python_dlls = [root / "DLLs" for root in python_roots]

    pyside_dir: Path | None = None
    plugin_root: Path | None = None
    platforms_root: Path | None = None
    pyside_spec = importlib.util.find_spec("PySide6")
    if pyside_spec and pyside_spec.submodule_search_locations:
        pyside_dir = Path(next(iter(pyside_spec.submodule_search_locations)))
        plugin_root = pyside_dir / "plugins"
        platforms_root = plugin_root / "platforms"

    shiboken_dir: Path | None = None
    shiboken_spec = importlib.util.find_spec("shiboken6")
    if shiboken_spec and shiboken_spec.submodule_search_locations:
        shiboken_dir = Path(next(iter(shiboken_spec.submodule_search_locations)))

    if getattr(sys, "frozen", False):
        frozen_roots: list[Path] = []
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            frozen_roots.append(Path(meipass))
        frozen_roots.append(Path(sys.executable).resolve().parent / "_internal")

        for frozen_root in frozen_roots:
            packaged_pyside = frozen_root / "PySide6"
            packaged_shiboken = frozen_root / "shiboken6"
            packaged_plugins = packaged_pyside / "plugins"
            packaged_platforms = packaged_plugins / "platforms"
            candidate_dirs.extend(
                [
                    *library_bins,
                    packaged_pyside,
                    packaged_shiboken,
                    *python_dlls,
                    system32,
                    packaged_plugins,
                    packaged_platforms,
                    frozen_root,
                ]
            )
            _set_env_path("QT_PLUGIN_PATH", packaged_plugins)
            _set_env_path("QT_QPA_PLATFORM_PLUGIN_PATH", packaged_platforms)
    else:
        candidate_dirs.extend(
            [
                *library_bins,
                pyside_dir,
                shiboken_dir,
                *python_dlls,
                system32,
                plugin_root,
                platforms_root,
            ]
        )
        if plugin_root is not None:
            _prepend_env_path("QT_PLUGIN_PATH", plugin_root)
        if platforms_root is not None:
            _prepend_env_path("QT_QPA_PLATFORM_PLUGIN_PATH", platforms_root)

    seen = set()
    for candidate in candidate_dirs:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not resolved.exists():
            continue
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        _push_runtime_dir(resolved)

    for resolved in runtime_dirs:
        _prepend_env_path("PATH", resolved)
        os.add_dll_directory(str(resolved))

    try:
        diagnostics = [
            f"frozen={getattr(sys, 'frozen', False)}",
            f"executable={Path(sys.executable).resolve()}",
            f"meipass={getattr(sys, '_MEIPASS', None)}",
            "candidate_dirs=",
            *[f"  {item}" for item in seen],
            f"QT_PLUGIN_PATH={os.environ.get('QT_PLUGIN_PATH', '')}",
            f"QT_QPA_PLATFORM_PLUGIN_PATH={os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH', '')}",
            "PATH_HEAD=",
            *[f"  {item}" for item in os.environ.get('PATH', '').split(os.pathsep)[:12]],
        ]
        write_crash_log("startup_diagnostics", "\n".join(diagnostics))
    except Exception:
        pass

from PySide6.QtCore import QSignalBlocker, QThread, Qt, Signal, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from duplicate_image_reviewer import DuplicateReviewStore, open_in_explorer
from junk_image_blacklist import DEFAULT_BLACKLIST_GALLERY, blacklist_summary


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_STATE_PATH = app_base_dir() / "duplicate_image_reviewer_app_state.json"
RECENT_ROOT_LIMIT = 12
_UNICODE_ESCAPE_RE = re.compile(r"(?:\\u[0-9a-fA-F]{4}|\\U[0-9a-fA-F]{8}|\\x[0-9a-fA-F]{2})")
_MOJIBAKE_HINT_CHARS = set("鍥鏂锟烫鐩褰曞彇娑堟爣璁剧疆璇锋牴鏍囩洰褰╂枃浠舵暟瀛﹁鍖栦腑闂")
_COMMON_PATH_HINTS = (
    "中间",
    "文件",
    "目录",
    "文件夹",
    "资料",
    "知识",
    "数学",
    "物理",
    "政治",
    "人工智能",
    "计算机",
    "通信",
    "讲义",
    "教材",
    "课件",
    "图论",
    "优化",
    "离散",
)


def default_root() -> Path:
    middle = Path(r"F:\中间文件库")
    if middle.exists():
        return middle
    return Path("output").resolve()


def exception_text(exc: BaseException) -> str:
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))


def _text_quality_score(text: str) -> int:
    cjk_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    ascii_path_count = sum(1 for ch in text if ch.isascii() and (ch.isalnum() or ch in r":\._-/ ()[]"))
    mojibake_penalty = sum(1 for ch in text if ch in _MOJIBAKE_HINT_CHARS)
    replacement_penalty = text.count("\ufffd") * 3 + text.count("?")
    hint_bonus = sum(4 for hint in _COMMON_PATH_HINTS if hint in text)
    return cjk_count + ascii_path_count + hint_bonus - mojibake_penalty * 2 - replacement_penalty


def normalize_ui_text(value: str | Path) -> str:
    text = str(value)
    original = text

    if _UNICODE_ESCAPE_RE.search(text):
        try:
            decoded = _UNICODE_ESCAPE_RE.sub(
                lambda match: bytes(match.group(0), "ascii").decode("unicode_escape"),
                text,
            )
            if decoded:
                text = decoded
        except Exception:
            pass

    for source_encoding in ("gbk", "cp936", "latin-1", "cp1252"):
        try:
            candidate = text.encode(source_encoding).decode("utf-8")
        except Exception:
            continue
        if candidate and _text_quality_score(candidate) > _text_quality_score(text) + 2:
            text = candidate

    if _text_quality_score(original) > _text_quality_score(text):
        return original
    return text


def is_blacklist_group(group) -> bool:
    return bool(getattr(group, "blacklist_families", []))


def load_app_state() -> dict:
    if APP_STATE_PATH.exists():
        try:
            payload = json.loads(APP_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except (OSError, json.JSONDecodeError):
            pass
    return {"recent_roots": []}


def save_app_state(payload: dict) -> None:
    APP_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_existing_roots(paths: Iterable[str | Path]) -> list[Path]:
    roots: list[Path] = []
    seen: set[str] = set()
    for item in paths:
        try:
            path = Path(item).resolve()
        except OSError:
            continue
        if not path.exists() or not path.is_dir():
            continue
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        roots.append(path)
    return roots


def default_quick_roots() -> list[Path]:
    roots = [default_root()]
    middle = default_root()
    if middle.exists():
        try:
            children = sorted([child for child in middle.iterdir() if child.is_dir()], key=lambda item: item.name)
        except OSError:
            children = []
        roots.extend(children[:16])
    return normalize_existing_roots(roots)


def load_delete_log_entries(root: Path, limit: int = 60) -> tuple[Path, list[dict]]:
    log_path = root / "_audit" / "reviewer_delete_log.jsonl"
    entries: list[dict] = []
    if not log_path.exists():
        return log_path, entries
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    entries.append(payload)
    except OSError:
        return log_path, []
    return log_path, list(reversed(entries[-limit:]))


class GroupsLoadThread(QThread):
    loaded = Signal(object, object)
    failed = Signal(str)

    def __init__(
        self,
        root: Path,
        store: DuplicateReviewStore | None,
        mode: str,
        threshold: int,
        min_count: int,
        reference_filter: str,
        rebuild: bool,
    ) -> None:
        super().__init__()
        self.root = root
        self.store = store
        self.mode = mode
        self.threshold = threshold
        self.min_count = min_count
        self.reference_filter = reference_filter
        self.rebuild = rebuild

    def run(self) -> None:
        try:
            store = self.store
            if store is None or store.root != self.root:
                store = DuplicateReviewStore(self.root)
            elif self.rebuild:
                store.rebuild()
            groups = store.groups(
                min_count=self.min_count,
                mode=self.mode,
                threshold=self.threshold,
                reference_filter=self.reference_filter,
            )
            self.loaded.emit(store, groups)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(exception_text(exc))


class StoreOperationThread(QThread):
    succeeded = Signal(str, object)
    failed = Signal(str, str)

    def __init__(
        self,
        operation_name: str,
        target: Callable[[], Any],
    ) -> None:
        super().__init__()
        self.operation_name = operation_name
        self.target = target
        self.success_handler: Callable[[Any], None] | None = None

    def run(self) -> None:
        try:
            payload = self.target()
            self.succeeded.emit(self.operation_name, payload)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(self.operation_name, exception_text(exc))


class ImageCard(QFrame):
    toggled = Signal(str, bool)
    blacklist_requested = Signal(str)

    def __init__(self, item: dict, checked: bool) -> None:
        super().__init__()
        self.item = item
        self.path = item["path"]
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { border: 1px solid #d8cbb7; border-radius: 14px; background: rgba(255,255,255,0.9); }"
        )
        self._build_ui(checked)

    def _build_ui(self, checked: bool) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top_row = QHBoxLayout()
        self.checkbox = QCheckBox("删除")
        self.checkbox.setChecked(checked)
        self.checkbox.toggled.connect(lambda state: self.toggled.emit(self.path, state))
        top_row.addWidget(self.checkbox)
        top_row.addStretch(1)
        if self.item.get("blacklist_families"):
            badge = QLabel("拉黑候选: " + " / ".join(self.item["blacklist_families"]))
            badge.setStyleSheet("QLabel { color: #9d221c; font-weight: 700; }")
            top_row.addWidget(badge)
        layout.addLayout(top_row)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setMinimumHeight(180)
        image_label.setStyleSheet("QLabel { background: #faf7f2; border-radius: 10px; }")
        pixmap = QPixmap(self.path)
        if not pixmap.isNull():
            image_label.setPixmap(
                pixmap.scaled(
                    260,
                    220,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            image_label.setText("无法加载缩略图")
        layout.addWidget(image_label)

        status_text = f"已引用 {self.item['reference_count']}" if self.item["referenced"] else "孤儿图"
        status = QLabel(status_text)
        status.setStyleSheet(
            "QLabel { color: %s; font-weight: 700; }"
            % ("#2d7a46" if self.item["referenced"] else "#a02828")
        )
        layout.addWidget(status)

        path_label = QLabel(normalize_ui_text(self.path))
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        path_label.setStyleSheet("QLabel { color: #6f624d; }")
        layout.addWidget(path_label)

        button_row = QHBoxLayout()
        open_image_button = QPushButton("看原图")
        open_image_button.clicked.connect(self._open_image)
        button_row.addWidget(open_image_button)

        open_folder_button = QPushButton("打开位置")
        open_folder_button.clicked.connect(self._open_folder)
        button_row.addWidget(open_folder_button)

        blacklist_button = QPushButton("拉黑此图")
        blacklist_button.clicked.connect(lambda: self.blacklist_requested.emit(self.path))
        button_row.addWidget(blacklist_button)
        layout.addLayout(button_row)

    def _open_image(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))

    def _open_folder(self) -> None:
        open_in_explorer(Path(self.path).parent)

    def set_checked(self, checked: bool) -> None:
        blocker = QSignalBlocker(self.checkbox)
        self.checkbox.setChecked(checked)
        del blocker


class BlacklistManagerDialog(QDialog):
    blacklist_changed = Signal()

    def __init__(self, store: DuplicateReviewStore | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.store = store
        self.setWindowTitle("拉黑图集管理")
        self.resize(980, 720)
        self.families: list[dict] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        summary_row = QHBoxLayout()
        self.summary_label = QLabel("正在加载拉黑图集...")
        self.summary_label.setWordWrap(True)
        summary_row.addWidget(self.summary_label, 1)
        open_folder_button = QPushButton("打开本地图集")
        open_folder_button.clicked.connect(lambda: open_in_explorer(DEFAULT_BLACKLIST_GALLERY))
        summary_row.addWidget(open_folder_button)
        root_layout.addLayout(summary_row)

        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.family_list = QListWidget()
        self.family_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.family_list.currentItemChanged.connect(self._update_preview)
        left_layout.addWidget(self.family_list, 1)

        button_row = QHBoxLayout()
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh)
        button_row.addWidget(refresh_button)

        rename_button = QPushButton("重命名")
        rename_button.clicked.connect(self.rename_selected)
        button_row.addWidget(rename_button)

        merge_button = QPushButton("合并")
        merge_button.clicked.connect(self.merge_selected)
        button_row.addWidget(merge_button)

        delete_button = QPushButton("删除")
        delete_button.clicked.connect(self.delete_selected)
        button_row.addWidget(delete_button)
        left_layout.addLayout(button_row)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        self.preview_image = QLabel("选择左侧废图族查看详情")
        self.preview_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_image.setMinimumHeight(280)
        self.preview_image.setStyleSheet(
            "QLabel { background: #faf7f2; border: 1px solid #e0d3bf; border-radius: 12px; }"
        )
        right_layout.addWidget(self.preview_image)

        self.preview_meta = QLabel("")
        self.preview_meta.setWordWrap(True)
        self.preview_meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right_layout.addWidget(self.preview_meta, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        root_layout.addWidget(splitter, 1)

    def refresh(self) -> None:
        summary = blacklist_summary()
        self.families = summary["families"]
        self.summary_label.setText(
            f"图集目录：{summary['gallery_path']}  |  废图族数量：{summary['family_count']}"
        )
        self.family_list.clear()
        for family in self.families:
            text = f"{family['name']}  |  {family['source']}  |  样本 {family['sample_count']}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, family)
            self.family_list.addItem(item)
        if self.family_list.count():
            self.family_list.setCurrentRow(0)
        else:
            self.preview_image.setText("当前没有废图族")
            self.preview_meta.clear()

    def selected_families(self) -> list[dict]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.family_list.selectedItems()]

    def current_family(self) -> dict | None:
        item = self.family_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _update_preview(self) -> None:
        family = self.current_family()
        if family is None:
            self.preview_image.setText("未选择废图族")
            self.preview_meta.clear()
            return
        image_path = family.get("representative_image")
        if image_path and Path(image_path).exists():
            pixmap = QPixmap(image_path)
            self.preview_image.setPixmap(
                pixmap.scaled(
                    420,
                    360,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self.preview_image.setPixmap(QPixmap())
            self.preview_image.setText("这类废图还没有代表图")
        self.preview_meta.setText(
            "\n".join(
                [
                    f"名称：{family['name']}",
                    f"来源：{family['source']}",
                    f"样本数：{family['sample_count']}",
                    f"备注：{family.get('notes') or '未填写'}",
                    f"代表图：{family.get('representative_image') or '暂无'}",
                ]
            )
        )

    def rename_selected(self) -> None:
        families = self.selected_families()
        if len(families) != 1:
            QMessageBox.information(self, "重命名", "请选择且仅选择一个废图族。")
            return
        family = families[0]
        new_name, ok = QInputDialog.getText(self, "重命名废图族", "新的废图族名称：", text=family["name"])
        if not ok or not new_name.strip():
            return
        try:
            if self.store is None:
                raise RuntimeError("当前还没有可用的 reviewer store。")
            self.store.rename_blacklist_family(family["name"], new_name.strip())
            self.refresh()
            self.blacklist_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "重命名失败", str(exc))

    def delete_selected(self) -> None:
        families = self.selected_families()
        if not families:
            QMessageBox.information(self, "删除废图族", "请先选择至少一个废图族。")
            return
        names = [family["name"] for family in families]
        confirmed = QMessageBox.question(
            self,
            "删除废图族",
            "确认删除以下废图族吗？\n\n" + "\n".join(names),
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        try:
            if self.store is None:
                raise RuntimeError("当前还没有可用的 reviewer store。")
            for name in names:
                self.store.delete_blacklist_family(name)
            self.refresh()
            self.blacklist_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "删除失败", str(exc))

    def merge_selected(self) -> None:
        families = self.selected_families()
        if len(families) < 2:
            QMessageBox.information(self, "合并废图族", "至少选择两个废图族。")
            return
        default_name = families[0]["name"]
        new_name, ok = QInputDialog.getText(self, "合并废图族", "合并后的名称：", text=default_name)
        if not ok or not new_name.strip():
            return
        try:
            if self.store is None:
                raise RuntimeError("当前还没有可用的 reviewer store。")
            self.store.merge_blacklist_families([family["name"] for family in families], new_name.strip())
            self.refresh()
            self.blacklist_changed.emit()
        except Exception as exc:
            QMessageBox.critical(self, "合并失败", str(exc))


class DeleteLogDialog(QDialog):
    def __init__(self, root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.root = root
        self.log_path: Path | None = None
        self.entries: list[dict] = []
        self.setWindowTitle("最近删除记录")
        self.resize(1080, 760)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        self.summary_label = QLabel("正在读取删除记录...")
        self.summary_label.setWordWrap(True)
        root_layout.addWidget(self.summary_label)

        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        self.entry_list = QListWidget()
        self.entry_list.currentItemChanged.connect(self._update_detail)
        left_layout.addWidget(self.entry_list, 1)

        left_buttons = QHBoxLayout()
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh)
        left_buttons.addWidget(refresh_button)
        open_audit_button = QPushButton("打开审计目录")
        open_audit_button.clicked.connect(self.open_audit_dir)
        left_buttons.addWidget(open_audit_button)
        left_layout.addLayout(left_buttons)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        self.detail_edit = QTextEdit()
        self.detail_edit.setReadOnly(True)
        right_layout.addWidget(self.detail_edit, 1)
        detail_buttons = QHBoxLayout()
        open_first_button = QPushButton("打开首张位置")
        open_first_button.clicked.connect(self.open_first_path)
        detail_buttons.addWidget(open_first_button)
        right_layout.addLayout(detail_buttons)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root_layout.addWidget(splitter, 1)

    def set_root(self, root: Path) -> None:
        self.root = root
        self.refresh()

    def refresh(self) -> None:
        self.log_path, self.entries = load_delete_log_entries(self.root)
        self.entry_list.clear()
        self.summary_label.setText(
            "根目录："
            f"{normalize_ui_text(self.root)}\n日志文件：{normalize_ui_text(self.log_path)}\n最近记录数：{len(self.entries)}"
        )
        for entry in self.entries:
            timestamp = entry.get("timestamp", "未知时间")
            deleted = entry.get("deleted", 0)
            cleaned_md = entry.get("cleaned_md", 0)
            text = f"{timestamp}  |  删除 {deleted} 张  |  清理 md {cleaned_md}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.entry_list.addItem(item)
        if self.entry_list.count():
            self.entry_list.setCurrentRow(0)
        else:
            self.detail_edit.setPlainText("当前根目录还没有删除记录。")

    def current_entry(self) -> dict | None:
        item = self.entry_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _update_detail(self) -> None:
        entry = self.current_entry()
        if entry is None:
            self.detail_edit.setPlainText("未选择任何记录。")
            return
        paths = entry.get("paths", [])
        preview = paths[:80]
        lines = [
            f"时间：{entry.get('timestamp', '未知')}",
            f"根目录：{normalize_ui_text(entry.get('root', self.root))}",
            f"删除数量：{entry.get('deleted', 0)}",
            f"释放空间：{entry.get('freed_bytes', 0)} bytes",
            f"清理 Markdown：{entry.get('cleaned_md', 0)}",
            "",
            "路径预览：",
            *[normalize_ui_text(path) for path in preview],
        ]
        if len(paths) > len(preview):
            lines.append("")
            lines.append(f"... 其余 {len(paths) - len(preview)} 条未展开")
        self.detail_edit.setPlainText("\n".join(lines))

    def open_audit_dir(self) -> None:
        open_in_explorer(self.root / "_audit")

    def open_first_path(self) -> None:
        entry = self.current_entry()
        if entry is None:
            return
        paths = entry.get("paths", [])
        if not paths:
            QMessageBox.information(self, "打开位置", "这条记录里没有图片路径。")
            return
        open_in_explorer(Path(paths[0]).parent)


class MainWindow(QMainWindow):
    def __init__(self, root: Path) -> None:
        super().__init__()
        self.setWindowTitle("OCR 重复图片桌面审核器")
        self.resize(1600, 980)
        self.root = root.resolve()
        self.state = load_app_state()
        self.store: DuplicateReviewStore | None = None
        self.all_groups = []
        self.filtered_groups = []
        self.selected_paths: set[str] = set()
        self.current_card_widgets: dict[str, ImageCard] = {}
        self.load_thread: GroupsLoadThread | None = None
        self.operation_thread: StoreOperationThread | None = None
        self.blacklist_dialog: BlacklistManagerDialog | None = None
        self.delete_log_dialog: DeleteLogDialog | None = None
        self.progress_dialog: QProgressDialog | None = None
        self._wait_cursor_active = False
        self._operation_busy_active = False
        self._load_busy_active = False
        self._operation_busy_message = ""
        self._load_busy_message = ""
        self._reload_after_operation = False
        self._reload_rebuild_after_operation = False
        self._build_ui()
        self.remember_root(self.root, save=False)
        self.start_load(rebuild=True)

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("根目录"))
        self.root_edit = QLineEdit(normalize_ui_text(self.root))
        self.root_edit.setReadOnly(True)
        path_row.addWidget(self.root_edit, 1)
        self.quick_root_combo = QComboBox()
        self.quick_root_combo.setMinimumWidth(320)
        path_row.addWidget(self.quick_root_combo)
        apply_quick_root_button = QPushButton("切换快捷项")
        apply_quick_root_button.clicked.connect(self.apply_quick_root)
        path_row.addWidget(apply_quick_root_button)
        browse_button = QPushButton("切换目录")
        browse_button.clicked.connect(self.choose_root)
        path_row.addWidget(browse_button)
        open_root_button = QPushButton("打开根目录")
        open_root_button.clicked.connect(lambda: open_in_explorer(self.root))
        path_row.addWidget(open_root_button)
        root_layout.addLayout(path_row)

        filter_row = QHBoxLayout()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["灰度近似聚类", "精确重复（MD5）"])
        self.mode_combo.currentIndexChanged.connect(lambda: self.start_load(rebuild=False))
        filter_row.addWidget(self.mode_combo)

        self.reference_combo = QComboBox()
        self.reference_combo.addItems(["全部图片", "只看正文已引用", "只看孤儿图片"])
        self.reference_combo.currentIndexChanged.connect(lambda: self.start_load(rebuild=False))
        filter_row.addWidget(self.reference_combo)

        self.blacklist_combo = QComboBox()
        self.blacklist_combo.addItems(["全部分组", "只看黑名单候选组", "排除黑名单候选组"])
        self.blacklist_combo.currentIndexChanged.connect(self.apply_group_filters)
        filter_row.addWidget(self.blacklist_combo)

        self.min_count_combo = QComboBox()
        self.min_count_combo.addItems(["至少 2 张", "至少 3 张", "至少 5 张", "至少 10 张"])
        self.min_count_combo.currentIndexChanged.connect(lambda: self.start_load(rebuild=False))
        filter_row.addWidget(self.min_count_combo)

        self.threshold_combo = QComboBox()
        self.threshold_combo.addItems(["阈值 6", "阈值 8", "阈值 10", "阈值 12", "阈值 14"])
        self.threshold_combo.setCurrentText("阈值 10")
        self.threshold_combo.currentIndexChanged.connect(lambda: self.start_load(rebuild=False))
        filter_row.addWidget(self.threshold_combo)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("按路径筛选分组")
        self.search_edit.textChanged.connect(self.apply_group_filters)
        filter_row.addWidget(self.search_edit, 1)

        self.refresh_button = QPushButton("刷新分组")
        self.refresh_button.clicked.connect(lambda: self.start_load(rebuild=True))
        filter_row.addWidget(self.refresh_button)

        self.clear_cache_button = QPushButton("清空缓存")
        self.clear_cache_button.clicked.connect(self.clear_index_cache)
        filter_row.addWidget(self.clear_cache_button)
        root_layout.addLayout(filter_row)

        self.status_label = QLabel("准备加载分组...")
        self.status_label.setWordWrap(True)
        root_layout.addWidget(self.status_label)

        splitter = QSplitter()

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(QLabel("重复分组"))
        self.group_list = QListWidget()
        self.group_list.currentRowChanged.connect(self.render_current_group)
        left_layout.addWidget(self.group_list, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        self.group_title = QLabel("请选择左侧分组")
        self.group_title.setStyleSheet("QLabel { font-size: 18px; font-weight: 700; }")
        right_layout.addWidget(self.group_title)

        self.group_meta = QLabel("这里会显示当前分组的路径、数量和审核状态。")
        self.group_meta.setWordWrap(True)
        right_layout.addWidget(self.group_meta)

        toolbar = QHBoxLayout()
        self.select_all_button = QPushButton("全选本组")
        self.select_all_button.clicked.connect(self.select_all_in_group)
        toolbar.addWidget(self.select_all_button)

        self.clear_selection_button = QPushButton("取消本组勾选")
        self.clear_selection_button.clicked.connect(self.clear_group_selection)
        toolbar.addWidget(self.clear_selection_button)

        self.clear_all_selection_button = QPushButton("取消全部勾选")
        self.clear_all_selection_button.clicked.connect(self.clear_all_selection)
        toolbar.addWidget(self.clear_all_selection_button)

        self.keep_first_button = QPushButton("保留第一张，勾选其余")
        self.keep_first_button.clicked.connect(self.keep_first_select_rest)
        toolbar.addWidget(self.keep_first_button)

        self.learn_blacklist_button = QPushButton("加入废图样本库")
        self.learn_blacklist_button.clicked.connect(self.learn_current_selection)
        toolbar.addWidget(self.learn_blacklist_button)

        self.manage_blacklist_button = QPushButton("管理拉黑图集")
        self.manage_blacklist_button.clicked.connect(self.open_blacklist_manager)
        toolbar.addWidget(self.manage_blacklist_button)

        self.blacklist_only_button = QPushButton("只看黑名单候选")
        self.blacklist_only_button.clicked.connect(lambda: self.set_blacklist_filter(1))
        toolbar.addWidget(self.blacklist_only_button)

        self.show_all_groups_button = QPushButton("显示全部分组")
        self.show_all_groups_button.clicked.connect(lambda: self.set_blacklist_filter(0))
        toolbar.addWidget(self.show_all_groups_button)

        self.purge_blacklist_button = QPushButton("按样本库清本目录")
        self.purge_blacklist_button.clicked.connect(self.purge_blacklist)
        toolbar.addWidget(self.purge_blacklist_button)

        self.delete_selected_button = QPushButton("删除已勾选")
        self.delete_selected_button.clicked.connect(self.delete_selected_paths)
        toolbar.addWidget(self.delete_selected_button)

        self.delete_log_button = QPushButton("最近删除记录")
        self.delete_log_button.clicked.connect(self.open_delete_log)
        toolbar.addWidget(self.delete_log_button)
        right_layout.addLayout(toolbar)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        self.cards_layout.setColumnStretch(3, 1)
        self.scroll_area.setWidget(self.cards_container)
        right_layout.addWidget(self.scroll_area, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        menu = self.menuBar().addMenu("文件")
        refresh_action = QAction("重建索引", self)
        refresh_action.triggered.connect(lambda: self.start_load(rebuild=True))
        menu.addAction(refresh_action)
        clear_cache_action = QAction("清空索引缓存", self)
        clear_cache_action.triggered.connect(self.clear_index_cache)
        menu.addAction(clear_cache_action)
        delete_log_action = QAction("最近删除记录", self)
        delete_log_action.triggered.connect(self.open_delete_log)
        menu.addAction(delete_log_action)
        blacklist_action = QAction("管理拉黑图集", self)
        blacklist_action.triggered.connect(self.open_blacklist_manager)
        menu.addAction(blacklist_action)

        selection_menu = self.menuBar().addMenu("选择")
        select_all_action = QAction("全选本组", self)
        select_all_action.triggered.connect(self.select_all_in_group)
        selection_menu.addAction(select_all_action)
        clear_group_action = QAction("取消本组勾选", self)
        clear_group_action.triggered.connect(self.clear_group_selection)
        selection_menu.addAction(clear_group_action)
        clear_all_action = QAction("取消全部勾选", self)
        clear_all_action.triggered.connect(self.clear_all_selection)
        selection_menu.addAction(clear_all_action)
        self.refresh_quick_roots()

    def current_mode(self) -> str:
        return "perceptual" if self.mode_combo.currentIndex() == 0 else "exact"

    def current_reference_filter(self) -> str:
        return ["all", "referenced", "orphan"][self.reference_combo.currentIndex()]

    def current_blacklist_filter(self) -> str:
        return ["all", "blacklistOnly", "nonBlacklist"][self.blacklist_combo.currentIndex()]

    def current_min_count(self) -> int:
        return [2, 3, 5, 10][self.min_count_combo.currentIndex()]

    def current_threshold(self) -> int:
        return [6, 8, 10, 12, 14][self.threshold_combo.currentIndex()]

    def _busy_widgets(self) -> list[QWidget]:
        return [
            self.quick_root_combo,
            self.mode_combo,
            self.reference_combo,
            self.blacklist_combo,
            self.min_count_combo,
            self.threshold_combo,
            self.search_edit,
            self.refresh_button,
            self.clear_cache_button,
            self.group_list,
            self.cards_container,
            self.select_all_button,
            self.clear_selection_button,
            self.clear_all_selection_button,
            self.keep_first_button,
            self.learn_blacklist_button,
            self.manage_blacklist_button,
            self.blacklist_only_button,
            self.show_all_groups_button,
            self.purge_blacklist_button,
            self.delete_selected_button,
            self.delete_log_button,
        ]

    def _ensure_progress_dialog(self) -> QProgressDialog:
        if self.progress_dialog is None:
            dialog = QProgressDialog(self)
            dialog.setCancelButton(None)
            dialog.setMinimumDuration(0)
            dialog.setRange(0, 0)
            dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
            dialog.setAutoClose(False)
            dialog.setAutoReset(False)
            self.progress_dialog = dialog
        return self.progress_dialog

    def _apply_busy_state(self) -> None:
        busy = self._operation_busy_active or self._load_busy_active
        for widget in self._busy_widgets():
            widget.setEnabled(not busy)
        if busy and not self._wait_cursor_active:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self._wait_cursor_active = True
        elif not busy and self._wait_cursor_active:
            QApplication.restoreOverrideCursor()
            self._wait_cursor_active = False

        if self._operation_busy_active:
            message = self._operation_busy_message or "正在处理图片操作..."
            title = "正在处理"
        elif self._load_busy_active:
            message = self._load_busy_message or "正在刷新分组..."
            title = "正在刷新"
        else:
            message = ""
            title = ""

        if busy:
            dialog = self._ensure_progress_dialog()
            dialog.setWindowTitle(title)
            dialog.setLabelText(message)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            QApplication.processEvents()
            self.status_label.setText(message)
        elif self.progress_dialog is not None:
            self.progress_dialog.hide()
            QApplication.processEvents()

    def set_operation_busy(self, busy: bool, message: str | None = None) -> None:
        self._operation_busy_active = busy
        self._operation_busy_message = message or ""
        self._apply_busy_state()

    def set_load_busy(self, busy: bool, message: str | None = None) -> None:
        self._load_busy_active = busy
        self._load_busy_message = message or ""
        self._apply_busy_state()

    def start_store_operation(
        self,
        operation_name: str,
        started_message: str,
        target: Callable[[], Any],
        success_handler: Callable[[Any], None],
        reload_after: bool = False,
        reload_rebuild: bool = False,
    ) -> None:
        if self.operation_thread is not None and self.operation_thread.isRunning():
            QMessageBox.information(self, "请稍等", "已有一个图片操作正在后台执行。")
            return
        self.set_operation_busy(True, started_message)
        thread = StoreOperationThread(operation_name, target)
        thread.success_handler = success_handler
        thread.reload_after = reload_after
        thread.reload_rebuild = reload_rebuild
        thread.succeeded.connect(self._on_store_operation_succeeded)
        thread.failed.connect(self._on_store_operation_failed)
        thread.finished.connect(self._on_store_operation_finished)
        self.operation_thread = thread
        thread.start()

    def _on_store_operation_succeeded(self, operation_name: str, payload: Any) -> None:
        self.set_operation_busy(False)
        thread = self.sender()
        handler = getattr(thread, "success_handler", None)
        if callable(handler):
            handler(payload)
        self._reload_after_operation = bool(getattr(thread, "reload_after", False))
        self._reload_rebuild_after_operation = bool(getattr(thread, "reload_rebuild", False))

    def _on_store_operation_failed(self, operation_name: str, text: str) -> None:
        self.set_operation_busy(False, "后台操作失败，请查看错误信息。")
        title_map = {
            "learn_blacklist": "加入失败",
            "delete_paths": "删除失败",
            "purge_blacklist": "清理失败",
            "clear_index_cache": "清空缓存失败",
        }
        QMessageBox.critical(self, title_map.get(operation_name, "操作失败"), text)

    def _on_store_operation_finished(self) -> None:
        thread = self.sender()
        if thread is self.operation_thread:
            self.operation_thread = None
        if thread is not None:
            thread.deleteLater()
        if self._reload_after_operation:
            self._reload_after_operation = False
            rebuild = self._reload_rebuild_after_operation
            self._reload_rebuild_after_operation = False
            self.start_load(rebuild=rebuild)

    def remember_root(self, root: Path, save: bool = True) -> None:
        recent = [str(root), *self.state.get("recent_roots", [])]
        normalized = [str(path) for path in normalize_existing_roots(recent)]
        self.state["recent_roots"] = normalized[:RECENT_ROOT_LIMIT]
        if save:
            save_app_state(self.state)
        self.refresh_quick_roots()

    def refresh_quick_roots(self) -> None:
        roots = normalize_existing_roots(
            [self.root, *self.state.get("recent_roots", []), *default_quick_roots()]
        )
        current_text = str(self.root)
        self.quick_root_combo.blockSignals(True)
        self.quick_root_combo.clear()
        for root in roots:
            self.quick_root_combo.addItem(normalize_ui_text(root))
        index = self.quick_root_combo.findText(current_text)
        if index >= 0:
            self.quick_root_combo.setCurrentIndex(index)
        self.quick_root_combo.blockSignals(False)

    def set_root(self, root: Path) -> None:
        self.root = root.resolve()
        self.root_edit.setText(normalize_ui_text(self.root))
        self.store = None
        self.selected_paths.clear()
        self.remember_root(self.root)
        if self.delete_log_dialog is not None:
            self.delete_log_dialog.set_root(self.root)
        self.start_load(rebuild=True)

    def apply_quick_root(self) -> None:
        selected = self.quick_root_combo.currentText().strip()
        if not selected:
            return
        path = Path(selected)
        if not path.exists() or not path.is_dir():
            QMessageBox.information(self, "切换根目录", "这个快捷目录当前不存在。")
            self.refresh_quick_roots()
            return
        self.set_root(path)

    def set_blacklist_filter(self, index: int) -> None:
        self.blacklist_combo.setCurrentIndex(index)

    def choose_root(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择审核根目录", str(self.root))
        if not selected:
            return
        self.set_root(Path(selected))

    def start_load(self, rebuild: bool) -> None:
        if self.operation_thread is not None and self.operation_thread.isRunning():
            return
        if self.load_thread is not None and self.load_thread.isRunning():
            return
        self.set_load_busy(True, "正在后台扫描并建立分组索引，这一步在整库模式下会比较慢，请稍等。")
        self.load_thread = GroupsLoadThread(
            root=self.root,
            store=self.store,
            mode=self.current_mode(),
            threshold=self.current_threshold(),
            min_count=self.current_min_count(),
            reference_filter=self.current_reference_filter(),
            rebuild=rebuild,
        )
        self.load_thread.loaded.connect(self._on_groups_loaded)
        self.load_thread.failed.connect(self._on_groups_failed)
        self.load_thread.finished.connect(self._on_load_finished)
        self.load_thread.start()

    def _on_groups_loaded(self, store: DuplicateReviewStore, groups: list) -> None:
        self.store = store
        self.all_groups = groups
        self.apply_group_filters()

    def _on_groups_failed(self, text: str) -> None:
        QMessageBox.critical(self, "加载失败", text)
        self.status_label.setText("加载失败，请查看错误信息。")

    def _on_load_finished(self) -> None:
        self.set_load_busy(False)
        self.load_thread = None

    def apply_group_filters(self) -> None:
        keyword = self.search_edit.text().strip().lower()
        blacklist_mode = self.current_blacklist_filter()
        groups = []
        for group in self.all_groups:
            is_blacklisted = is_blacklist_group(group)
            if blacklist_mode == "blacklistOnly" and not is_blacklisted:
                continue
            if blacklist_mode == "nonBlacklist" and is_blacklisted:
                continue
            if keyword and not any(keyword in path.lower() for path in group.paths):
                continue
            groups.append(group)
        self.filtered_groups = groups
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for group in self.filtered_groups:
            title = f"{group.id} | {group.count}"
            if group.total_count != group.count:
                title += f" / {group.total_count}"
            title += " 张"
            if group.blacklist_families:
                title += " | 拉黑候选 " + " / ".join(group.blacklist_families)
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, group)
            if group.blacklist_families:
                item.setForeground(Qt.GlobalColor.darkRed)
            self.group_list.addItem(item)
        self.group_list.blockSignals(False)
        total_images = sum(group.count for group in self.filtered_groups)
        blacklist_hits = sum(1 for group in self.filtered_groups if is_blacklist_group(group))
        self.status_label.setText(
            f"当前共有 {len(self.filtered_groups)} 个分组，合计 {total_images} 张候选图片；其中 {blacklist_hits} 组命中拉黑图集。"
        )
        if self.group_list.count():
            self.group_list.setCurrentRow(0)
        else:
            self.render_current_group()

    def current_group(self):
        item = self.group_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def clear_cards(self) -> None:
        self.current_card_widgets = {}
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            widget = child.widget()
            if widget is not None:
                widget.deleteLater()

    def render_current_group(self) -> None:
        self.clear_cards()
        group = self.current_group()
        if group is None:
            self.group_title.setText("请选择左侧分组")
            self.group_meta.setText("这里会显示当前分组的路径、数量和审核状态。")
            return

        self.group_title.setText(f"{group.id} · {group.count} 张")
        lines = [
            f"代表图尺寸：{group.width} × {group.height}",
            f"模式：{'灰度近似聚类' if group.grouping == 'perceptual' else '精确重复'}",
            f"已引用：{group.referenced_count} | 孤儿：{group.orphan_count}",
            f"拉黑候选：{' / '.join(group.blacklist_families) if group.blacklist_families else '否'}",
            normalize_ui_text(group.paths[0]),
        ]
        self.group_meta.setText("\n".join(lines))

        for index, item in enumerate(group.items):
            card = ImageCard(item, checked=item["path"] in self.selected_paths)
            card.toggled.connect(self._on_card_toggled)
            card.blacklist_requested.connect(self.blacklist_single_image)
            self.current_card_widgets[item["path"]] = card
            self.cards_layout.addWidget(card, index // 3, index % 3)

    def _on_card_toggled(self, path: str, checked: bool) -> None:
        if checked:
            self.selected_paths.add(path)
        else:
            self.selected_paths.discard(path)

    def group_paths(self) -> list[str]:
        group = self.current_group()
        if group is None:
            return []
        return list(group.paths)

    def update_visible_card_checks(self, paths: Iterable[str] | None = None) -> None:
        if not self.current_card_widgets:
            return
        target_paths = set(paths) if paths is not None else set(self.current_card_widgets.keys())
        for path, card in self.current_card_widgets.items():
            if path in target_paths:
                card.set_checked(path in self.selected_paths)

    def select_all_in_group(self) -> None:
        paths = self.group_paths()
        for path in paths:
            self.selected_paths.add(path)
        self.update_visible_card_checks(paths)
        self.status_label.setText(f"已勾选当前分组全部 {len(paths)} 张图片。")

    def clear_group_selection(self) -> None:
        paths = self.group_paths()
        cleared = 0
        for path in paths:
            if path in self.selected_paths:
                cleared += 1
            self.selected_paths.discard(path)
        self.update_visible_card_checks(paths)
        self.status_label.setText(f"已取消当前分组 {cleared} 项勾选。")

    def clear_all_selection(self) -> None:
        cleared = len(self.selected_paths)
        self.selected_paths.clear()
        self.update_visible_card_checks()
        self.status_label.setText(f"已取消全部 {cleared} 项勾选。")

    def keep_first_select_rest(self) -> None:
        paths = self.group_paths()
        if not paths:
            return
        self.selected_paths.discard(paths[0])
        for path in paths[1:]:
            self.selected_paths.add(path)
        self.update_visible_card_checks(paths)
        self.status_label.setText(f"已保留当前分组第 1 张，并勾选其余 {max(len(paths) - 1, 0)} 张。")

    def prompt_blacklist_name(self, title: str, default: str = "") -> str | None:
        text, ok = QInputDialog.getText(self, title, "废图族名称（可留空自动生成）：", text=default)
        if not ok:
            return None
        return text.strip()

    def learn_current_selection(self) -> None:
        group = self.current_group()
        if group is None:
            return
        paths = [path for path in group.paths if path in self.selected_paths] or list(group.paths)
        suggested_name = self.prompt_blacklist_name("加入废图样本库")
        self.learn_blacklist(paths, suggested_name)

    def blacklist_single_image(self, path: str) -> None:
        suggested_name = self.prompt_blacklist_name("拉黑此图")
        self.learn_blacklist([path], suggested_name)

    def learn_blacklist(self, paths: Iterable[str], family_name: str | None) -> None:
        if self.store is None:
            QMessageBox.information(self, "请稍等", "索引尚未准备好。")
            return
        selected_paths = list(paths)

        def _success(payload: Any) -> None:
            if payload.get("already_exists"):
                QMessageBox.information(
                    self,
                    "已存在相似废图族",
                    "这类图片已经在拉黑图集中：\n"
                    + " / ".join(payload["matched_families"])
                    + f"\n\n代表图：{payload.get('representative_image') or '未记录'}",
                )
            else:
                QMessageBox.information(
                    self,
                    "已加入废图样本库",
                    f"废图族：{payload['family_name']}\n"
                    f"样本数：{payload['sample_count']}\n"
                    f"代表图：{payload.get('representative_image') or '未记录'}",
                )
            if self.blacklist_dialog is not None:
                self.blacklist_dialog.refresh()
            self.status_label.setText("废图样本库已更新，正在后台刷新当前分组。")

        self.start_store_operation(
            operation_name="learn_blacklist",
            started_message="正在把样本加入废图图集，并更新当前索引...",
            target=lambda: self.store.learn_blacklist(selected_paths, family_name=family_name or None),
            success_handler=_success,
            reload_after=True,
        )

    def reload_from_store(self) -> None:
        if self.store is None:
            return
        self.start_load(rebuild=False)

    def purge_blacklist(self) -> None:
        if self.store is None:
            QMessageBox.information(self, "请稍等", "索引尚未准备好。")
            return
        confirmed = QMessageBox.question(
            self,
            "按样本库清理",
            "确认按当前废图样本库扫描并清理这个根目录吗？这会删除所有命中的废图并同步清理 Markdown 引用。",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        def _success(payload: Any) -> None:
            QMessageBox.information(
                self,
                "清理完成",
                f"命中 {payload['matched']} 张，删除 {payload['deleted']} 张，清理 {payload['cleaned_md']} 个 Markdown 文件。",
            )
            self.selected_paths.clear()
            if self.delete_log_dialog is not None:
                self.delete_log_dialog.refresh()
            self.status_label.setText("按样本库清理完成，正在后台刷新当前分组。")

        self.start_store_operation(
            operation_name="purge_blacklist",
            started_message="正在按样本库扫描并清理当前根目录，这一步可能需要一些时间...",
            target=self.store.purge_blacklist,
            success_handler=_success,
            reload_after=True,
        )

    def delete_selected_paths(self) -> None:
        if self.store is None:
            QMessageBox.information(self, "请稍等", "索引尚未准备好。")
            return
        group_paths = [path for path in self.group_paths() if path in self.selected_paths]
        if not group_paths:
            QMessageBox.information(self, "删除图片", "当前组还没有勾选任何图片。")
            return
        confirmed = QMessageBox.question(
            self,
            "删除已勾选图片",
            f"确认删除当前勾选的 {len(group_paths)} 张图片吗？对应 Markdown 引用也会同步清理。",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        def _success(payload: Any) -> None:
            for path in group_paths:
                self.selected_paths.discard(path)
            QMessageBox.information(
                self,
                "删除完成",
                f"已删除 {payload['deleted']} 张，清理 {payload['cleaned_md']} 个 Markdown 文件。",
            )
            if self.delete_log_dialog is not None:
                self.delete_log_dialog.refresh()
            self.status_label.setText("删除完成，正在后台刷新当前分组。")

        self.start_store_operation(
            operation_name="delete_paths",
            started_message=f"正在删除 {len(group_paths)} 张图片并清理 Markdown 引用...",
            target=lambda: self.store.delete_paths(group_paths),
            success_handler=_success,
            reload_after=True,
        )

    def clear_index_cache(self) -> None:
        if self.store is None:
            QMessageBox.information(self, "请稍等", "索引尚未准备好。")
            return
        confirmed = QMessageBox.question(
            self,
            "清空索引缓存",
            "确认清空当前根目录的索引缓存吗？\n\n这不会删除任何图片或 Markdown，只会删除签名和引用缓存，然后自动重新建立索引。",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return

        def _success(payload: Any) -> None:
            cache_path = normalize_ui_text(payload.get("cache_path", ""))
            QMessageBox.information(
                self,
                "缓存已清空",
                f"缓存文件：{cache_path}\n"
                f"图片缓存条目：{payload.get('image_entries', 0)}\n"
                f"Markdown 引用缓存：{payload.get('md_entries', 0)}\n\n"
                "接下来会自动重新建立当前根目录的索引。",
            )
            self.status_label.setText("索引缓存已清空，正在后台重新建立索引。")

        self.start_store_operation(
            operation_name="clear_index_cache",
            started_message="正在清空索引缓存，并准备重新建立索引...",
            target=self.store.clear_index_cache,
            success_handler=_success,
            reload_after=True,
            reload_rebuild=True,
        )

    def open_blacklist_manager(self) -> None:
        if self.blacklist_dialog is None:
            self.blacklist_dialog = BlacklistManagerDialog(self.store, self)
            self.blacklist_dialog.blacklist_changed.connect(self._on_blacklist_changed)
        else:
            self.blacklist_dialog.store = self.store
            self.blacklist_dialog.refresh()
        self.blacklist_dialog.show()
        self.blacklist_dialog.raise_()
        self.blacklist_dialog.activateWindow()

    def open_delete_log(self) -> None:
        if self.delete_log_dialog is None:
            self.delete_log_dialog = DeleteLogDialog(self.root, self)
        else:
            self.delete_log_dialog.set_root(self.root)
        self.delete_log_dialog.show()
        self.delete_log_dialog.raise_()
        self.delete_log_dialog.activateWindow()

    def _on_blacklist_changed(self) -> None:
        self.reload_from_store()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PySide6 desktop app for OCR duplicate image review.")
    parser.add_argument(
        "--root",
        type=Path,
        default=default_root(),
        help="Root directory containing OCR image trees. Default: F:\\中间文件库 if it exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    window = MainWindow(args.root)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
