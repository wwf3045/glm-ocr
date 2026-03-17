from __future__ import annotations

import argparse
import json
import mimetypes
import os
import urllib.parse
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>恢复候选图过审</title>
  <style>
    :root {
      --bg: #f6f0e6;
      --panel: rgba(255,255,255,0.82);
      --line: #dccfb8;
      --text: #2d2418;
      --muted: #7d6f5c;
      --accent: #9e4b24;
      --accent-2: #cb7c44;
      --good: #2a7b4d;
      --bad: #9b2b2b;
      --shadow: 0 16px 44px rgba(73, 45, 14, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--text);
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top right, rgba(203,124,68,0.14), transparent 28%),
        radial-gradient(circle at bottom left, rgba(158,75,36,0.12), transparent 32%),
        var(--bg);
    }
    .app {
      display: grid;
      grid-template-columns: 330px minmax(0,1fr);
      gap: 18px;
      min-height: 100vh;
      padding: 18px;
    }
    .sidebar, .main {
      border: 1px solid var(--line);
      background: var(--panel);
      backdrop-filter: blur(14px);
      border-radius: 24px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .sidebar { display: flex; flex-direction: column; }
    .header {
      padding: 18px 20px 14px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(255,255,255,0.5));
    }
    .title { margin: 0; font-size: 22px; font-weight: 700; }
    .subtitle { margin-top: 8px; color: var(--muted); font-size: 13px; line-height: 1.5; }
    .controls {
      display: grid;
      gap: 10px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: rgba(240,231,216,0.55);
    }
    input, button { font: inherit; }
    input {
      width: 100%;
      padding: 11px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.9);
    }
    button {
      border: 0;
      border-radius: 12px;
      padding: 11px 14px;
      cursor: pointer;
      background: var(--accent);
      color: #fff8f2;
    }
    button.secondary { background: #8c6d4c; }
    button.good { background: var(--good); }
    button.bad { background: var(--bad); }
    button:disabled { opacity: .45; cursor: not-allowed; }
    .group-list {
      overflow: auto;
      padding: 10px;
      display: grid;
      gap: 8px;
    }
    .group-item {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 10px;
      background: rgba(255,255,255,0.74);
      cursor: pointer;
      display: grid;
      gap: 8px;
    }
    .group-item.active {
      border-color: var(--accent);
      background: linear-gradient(180deg, rgba(203,124,68,0.18), rgba(255,255,255,0.86));
    }
    .group-title {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 14px;
      font-weight: 700;
    }
    .group-path {
      font-size: 12px;
      color: var(--muted);
      word-break: break-all;
      line-height: 1.45;
    }
    .main { display: flex; flex-direction: column; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }
    .content {
      min-height: 0;
      overflow: auto;
      padding: 18px 22px 26px;
      display: grid;
      gap: 18px;
    }
    .empty {
      min-height: 320px;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 20px;
      background: rgba(255,255,255,0.55);
      text-align: center;
      padding: 30px;
    }
    .preview {
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 12px;
      background: rgba(255,255,255,0.75);
      display: grid;
      gap: 10px;
    }
    .preview img {
      width: 100%;
      max-height: 520px;
      object-fit: contain;
      border-radius: 14px;
      background: #fff;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 18px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 12px;
      background: rgba(255,255,255,0.78);
      display: grid;
      gap: 10px;
    }
    .thumb-wrap {
      position: relative;
      aspect-ratio: 1 / 1;
      overflow: hidden;
      border-radius: 14px;
      background: linear-gradient(180deg, rgba(240,231,216,0.8), rgba(255,255,255,0.85));
      display: grid;
      place-items: center;
    }
    .thumb-wrap img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      background: #fff;
    }
    .pick-box {
      position: absolute;
      top: 10px;
      left: 10px;
      width: 22px;
      height: 22px;
      accent-color: var(--accent);
    }
    .card-info { font-size: 12px; color: var(--muted); display: grid; gap: 6px; }
    .path { word-break: break-all; line-height: 1.45; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .actions a { color: var(--accent); text-decoration: none; font-weight: 600; }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 700;
      background: rgba(158,75,36,0.12);
      color: var(--accent);
    }
    @media (max-width: 960px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { max-height: 40vh; }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="header">
        <h1 class="title">恢复候选图过审</h1>
        <div class="subtitle" id="summaryText">正在加载候选分组...</div>
      </div>
      <div class="controls">
        <input id="searchInput" type="text" placeholder="按书名/页码筛选">
        <div style="display:flex; gap:10px;">
          <button id="refreshButton" class="secondary">刷新</button>
          <button id="openRootButton">打开根目录</button>
        </div>
      </div>
      <div class="group-list" id="groupList"></div>
    </aside>
    <main class="main">
      <div class="header">
        <h2 class="title" id="groupTitle">请选择左侧页分组</h2>
        <div class="subtitle" id="groupStatus">这里会显示恢复来源、页码和候选数量。</div>
        <div class="toolbar">
          <button class="secondary" id="selectAllButton" disabled>全选本页</button>
          <button class="secondary" id="clearSelectionButton" disabled>清空选择</button>
          <button class="good" id="approveButton" disabled>移动到 approved</button>
          <button class="bad" id="rejectButton" disabled>移动到 rejected</button>
        </div>
      </div>
      <div class="content" id="content">
        <div class="empty">左边按“书/页”列出恢复候选。点开一页之后，可以先看整页预览，再逐张检查候选图。</div>
      </div>
    </main>
  </div>
  <script>
    const state = {
      groups: [],
      filteredGroups: [],
      selectedGroupId: null,
      selectedPaths: new Set(),
      search: '',
    };

    const summaryText = document.getElementById('summaryText');
    const groupList = document.getElementById('groupList');
    const groupTitle = document.getElementById('groupTitle');
    const groupStatus = document.getElementById('groupStatus');
    const content = document.getElementById('content');
    const searchInput = document.getElementById('searchInput');
    const refreshButton = document.getElementById('refreshButton');
    const openRootButton = document.getElementById('openRootButton');
    const selectAllButton = document.getElementById('selectAllButton');
    const clearSelectionButton = document.getElementById('clearSelectionButton');
    const approveButton = document.getElementById('approveButton');
    const rejectButton = document.getElementById('rejectButton');

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `请求失败：${response.status}`);
      }
      return response.json();
    }

    function applyFilters() {
      const keyword = state.search.trim().toLowerCase();
      state.filteredGroups = state.groups.filter(group => {
        if (!keyword) return true;
        return [group.book_name, group.page_label, group.relative_dir, group.note].join(' ').toLowerCase().includes(keyword);
      });
      if (!state.filteredGroups.some(group => group.id === state.selectedGroupId)) {
        state.selectedGroupId = state.filteredGroups.length ? state.filteredGroups[0].id : null;
        state.selectedPaths.clear();
      }
    }

    function currentGroup() {
      return state.filteredGroups.find(group => group.id === state.selectedGroupId) || null;
    }

    function updateButtons(group) {
      const enabled = !!group;
      const picked = state.selectedPaths.size > 0;
      selectAllButton.disabled = !enabled;
      clearSelectionButton.disabled = !enabled;
      approveButton.disabled = !enabled || !picked;
      rejectButton.disabled = !enabled || !picked;
    }

    function renderGroupList() {
      const total = state.filteredGroups.reduce((sum, group) => sum + group.candidate_count, 0);
      summaryText.textContent = `共有 ${state.filteredGroups.length} 个页分组，候选图 ${total} 张。`;
      groupList.innerHTML = '';
      if (!state.filteredGroups.length) {
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = '当前没有可展示的恢复候选。';
        groupList.appendChild(empty);
        renderCurrentGroup();
        return;
      }
      for (const group of state.filteredGroups) {
        const item = document.createElement('div');
        item.className = 'group-item' + (group.id === state.selectedGroupId ? ' active' : '');
        item.addEventListener('click', () => {
          state.selectedGroupId = group.id;
          state.selectedPaths.clear();
          renderGroupList();
          renderCurrentGroup();
        });
        item.innerHTML = `
          <div class="group-title">
            <span>${group.book_name}</span>
            <span>${group.page_label} · ${group.candidate_count} 张</span>
          </div>
          <div class="group-path">${group.relative_dir}</div>
        `;
        groupList.appendChild(item);
      }
    }

    function renderCurrentGroup() {
      const group = currentGroup();
      content.innerHTML = '';
      if (!group) {
        groupTitle.textContent = '请选择左侧页分组';
        groupStatus.textContent = '这里会显示恢复来源、页码和候选数量。';
        updateButtons(null);
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = '当前没有可展示的恢复候选。';
        content.appendChild(empty);
        return;
      }
      groupTitle.textContent = `${group.book_name} · ${group.page_label}`;
      groupStatus.innerHTML = `${group.relative_dir}<br>${group.note || ''}`;

      const preview = document.createElement('div');
      preview.className = 'preview';
      preview.innerHTML = `
        <div class="badge">整页预览</div>
        <img src="/image?path=${encodeURIComponent(group.preview_path)}" alt="page-preview">
        <div class="actions">
          <a href="/image?path=${encodeURIComponent(group.preview_path)}" target="_blank" rel="noopener">看整页原图</a>
          <a href="/open?path=${encodeURIComponent(group.preview_path)}" target="_blank" rel="noopener">打开所在位置</a>
        </div>
      `;
      content.appendChild(preview);

      const grid = document.createElement('div');
      grid.className = 'grid';
      for (const item of group.items) {
        const checked = state.selectedPaths.has(item.path) ? 'checked' : '';
        const encoded = encodeURIComponent(item.path);
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
          <div class="thumb-wrap">
            <input class="pick-box" type="checkbox" data-path="${item.path.replaceAll('"', '&quot;')}" ${checked}>
            <img src="/image?path=${encoded}" alt="${item.name}">
          </div>
          <div class="card-info">
            <div><strong>${item.name}</strong></div>
            <div class="badge">${item.width}×${item.height}</div>
            <div class="path">${item.path}</div>
            <div class="actions">
              <a href="/image?path=${encoded}" target="_blank" rel="noopener">看原图</a>
              <a href="/open?path=${encoded}" target="_blank" rel="noopener">打开所在位置</a>
            </div>
          </div>
        `;
        grid.appendChild(card);
      }
      content.appendChild(grid);

      content.querySelectorAll('.pick-box').forEach(box => {
        box.addEventListener('change', event => {
          const path = event.target.dataset.path;
          if (event.target.checked) state.selectedPaths.add(path);
          else state.selectedPaths.delete(path);
          updateButtons(group);
        });
      });

      updateButtons(group);
    }

    async function loadGroups({ preserveSelection = false } = {}) {
      const oldGroup = preserveSelection ? state.selectedGroupId : null;
      const oldSelected = preserveSelection ? new Set(state.selectedPaths) : new Set();
      const payload = await fetchJson('/api/groups');
      state.groups = payload.groups;
      applyFilters();
      if (oldGroup && state.filteredGroups.some(group => group.id === oldGroup)) {
        state.selectedGroupId = oldGroup;
      }
      state.selectedPaths = new Set();
      const group = currentGroup();
      if (group) {
        group.items.forEach(item => {
          if (oldSelected.has(item.path)) state.selectedPaths.add(item.path);
        });
      }
      renderGroupList();
      renderCurrentGroup();
    }

    async function moveSelected(action) {
      const group = currentGroup();
      if (!group || state.selectedPaths.size === 0) return;
      const payload = await fetchJson('/api/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, paths: Array.from(state.selectedPaths) }),
      });
      window.alert(`${action} ${payload.moved} 张，目标目录：${payload.dest_root}`);
      state.selectedPaths.clear();
      await loadGroups({ preserveSelection: false });
    }

    searchInput.addEventListener('input', () => {
      state.search = searchInput.value;
      applyFilters();
      renderGroupList();
      renderCurrentGroup();
    });

    refreshButton.addEventListener('click', async () => {
      refreshButton.disabled = true;
      try { await loadGroups({ preserveSelection: true }); }
      finally { refreshButton.disabled = false; }
    });

    openRootButton.addEventListener('click', () => window.open('/open-root', '_blank'));
    selectAllButton.addEventListener('click', () => {
      const group = currentGroup();
      if (!group) return;
      state.selectedPaths = new Set(group.items.map(item => item.path));
      renderCurrentGroup();
    });
    clearSelectionButton.addEventListener('click', () => {
      state.selectedPaths.clear();
      renderCurrentGroup();
    });
    approveButton.addEventListener('click', async () => { await moveSelected('approved'); });
    rejectButton.addEventListener('click', async () => { await moveSelected('rejected'); });

    loadGroups().catch(error => {
      summaryText.textContent = `加载失败：${error.message}`;
    });
  </script>
</body>
</html>
"""


@dataclass
class ReviewItem:
    name: str
    path: str
    width: int
    height: int


@dataclass
class ReviewGroup:
    id: str
    book_name: str
    page_label: str
    relative_dir: str
    note: str
    preview_path: str
    candidate_count: int
    items: list[dict]


class ReviewStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._groups: list[ReviewGroup] = []
        self.rebuild()

    def rebuild(self) -> None:
        groups: list[ReviewGroup] = []
        for manifest_path in sorted(self.root.rglob("manifest.json")):
            page_dir = manifest_path.parent
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            book_manifest_path = page_dir.parent / "book_manifest.json"
            book_manifest = {}
            if book_manifest_path.exists():
                book_manifest = json.loads(book_manifest_path.read_text(encoding="utf-8"))
            items = [
                {
                    "name": item["name"],
                    "path": item["path"],
                    "width": item["width"],
                    "height": item["height"],
                }
                for item in data.get("candidates", [])
                if Path(item["path"]).exists()
            ]
            if not items:
                continue
            groups.append(
                ReviewGroup(
                    id=f"{page_dir.parent.name}/{page_dir.name}",
                    book_name=book_manifest.get("display_name", page_dir.parent.name),
                    page_label=f"第 {data['page']} 页",
                    relative_dir=str(page_dir.relative_to(self.root)),
                    note=book_manifest.get("note", ""),
                    preview_path=data["preview"],
                    candidate_count=len(items),
                    items=items,
                )
            )
        self._groups = groups

    def groups(self) -> list[dict]:
        return [
            {
                "id": group.id,
                "book_name": group.book_name,
                "page_label": group.page_label,
                "relative_dir": group.relative_dir,
                "note": group.note,
                "preview_path": group.preview_path,
                "candidate_count": group.candidate_count,
                "items": group.items,
            }
            for group in self._groups
        ]

    def move_paths(self, paths: list[str], action: str) -> dict:
        if action not in {"approved", "rejected"}:
            raise ValueError(action)
        dest_root = self.root / "_review_result" / action
        moved = 0
        for raw_path in paths:
            path = Path(raw_path).resolve()
            if not path.exists():
                continue
            try:
                relative = path.relative_to(self.root)
            except ValueError:
                continue
            dest_path = dest_root / relative
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            path.replace(dest_path)
            moved += 1
        self.rebuild()
        return {"moved": moved, "dest_root": str(dest_root)}


class ReviewHandler(BaseHTTPRequestHandler):
    server_version = "RecoveredOrphanReview/1.0"

    @property
    def app(self) -> "ReviewApp":
        return self.server.app  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
            return
        if parsed.path == "/api/groups":
            payload = {"groups": self.app.store.groups()}
            self.send_json(payload)
            return
        if parsed.path == "/image":
            self.handle_image(parsed)
            return
        if parsed.path == "/open":
            self.handle_open(parsed)
            return
        if parsed.path == "/open-root":
            os.startfile(str(self.app.store.root))
            self.send_json({"ok": True})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/move":
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) if length else b"{}")
            result = self.app.store.move_paths(payload.get("paths", []), payload.get("action", "approved"))
            self.send_json(result)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def handle_image(self, parsed: urllib.parse.ParseResult) -> None:
        query = urllib.parse.parse_qs(parsed.query)
        raw = query.get("path", [""])[0]
        if not raw:
            self.send_error(HTTPStatus.BAD_REQUEST, "missing path")
            return
        path = Path(urllib.parse.unquote(raw))
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        mime, _ = mimetypes.guess_type(path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime or "application/octet-stream")
        self.end_headers()
        self.wfile.write(path.read_bytes())

    def handle_open(self, parsed: urllib.parse.ParseResult) -> None:
        query = urllib.parse.parse_qs(parsed.query)
        raw = query.get("path", [""])[0]
        if not raw:
            self.send_error(HTTPStatus.BAD_REQUEST, "missing path")
            return
        path = Path(urllib.parse.unquote(raw))
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        os.startfile(str(path.parent))
        self.send_json({"ok": True, "path": str(path.parent)})

    def send_json(self, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ReviewApp:
    def __init__(self, root: Path, host: str, port: int) -> None:
        self.store = ReviewStore(root)
        self.host = host
        self.port = port

    def run(self, open_browser: bool = True) -> None:
        server = ThreadingHTTPServer((self.host, self.port), ReviewHandler)
        server.app = self  # type: ignore[attr-defined]
        url = f"http://{self.host}:{self.port}/"
        print(f"[OK] 恢复候选图过审窗口已启动：{url}")
        print(f"[INFO] 根目录：{self.store.root}")
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[INFO] 已停止。")
        finally:
            server.server_close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review recovered orphan-image candidates by book/page.")
    parser.add_argument("--root", type=Path, default=Path(r"C:\Users\28033\Desktop\codex_short_sessions\recovered_orphan_review"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    app = ReviewApp(args.root.resolve(), args.host, args.port)
    app.run(open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
