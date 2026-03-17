from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import threading
import time
import urllib.parse
import webbrowser
from collections import Counter
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, UnidentifiedImageError

from clean_junk_images import IMAGE_EXTS, clean_md_references
from junk_image_blacklist import (
    DEFAULT_BLACKLIST_GALLERY,
    DEFAULT_BLACKLIST_PATH,
    ImageSignature,
    add_or_update_family,
    blacklist_summary,
    delete_family,
    list_families,
    matches_family,
    merge_families,
    rename_family,
    scan_blacklist_matches,
)
from ocr_image_index import collect_markdown_image_name_counts


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>重复图片人工过审</title>
  <style>
    :root {
      --bg: #f4efe7;
      --panel: #fbf8f3;
      --panel-2: #f0e7d8;
      --line: #d9cbb2;
      --text: #2d2418;
      --muted: #7b6a52;
      --accent: #a7441f;
      --accent-2: #cf6f32;
      --danger: #a02828;
      --shadow: 0 18px 50px rgba(62, 37, 9, 0.12);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top right, rgba(207, 111, 50, 0.15), transparent 28%),
        radial-gradient(circle at bottom left, rgba(167, 68, 31, 0.12), transparent 30%),
        var(--bg);
    }

    .app {
      display: grid;
      grid-template-columns: 340px minmax(0, 1fr);
      height: 100vh;
      gap: 20px;
      padding: 20px;
    }

    .sidebar, .main {
      background: rgba(251, 248, 243, 0.88);
      border: 1px solid rgba(217, 203, 178, 0.85);
      backdrop-filter: blur(16px);
      box-shadow: var(--shadow);
      border-radius: 24px;
      overflow: hidden;
    }

    .sidebar {
      display: flex;
      flex-direction: column;
    }

    .sidebar-header, .main-header {
      padding: 20px 22px 16px;
      border-bottom: 1px solid rgba(217, 203, 178, 0.8);
      background: linear-gradient(180deg, rgba(255,255,255,0.6), rgba(251,248,243,0.85));
    }

    .title {
      margin: 0;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 0.02em;
    }

    .subtitle, .status {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
    }

    .controls {
      display: grid;
      gap: 10px;
      padding: 16px 18px;
      border-bottom: 1px solid rgba(217, 203, 178, 0.7);
      background: rgba(240, 231, 216, 0.55);
    }

    .control-row {
      display: grid;
      grid-template-columns: 1fr 100px;
      gap: 10px;
    }

    input, select, button {
      font: inherit;
    }

    input, select {
      width: 100%;
      padding: 11px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.86);
      color: var(--text);
    }

    button {
      border: 0;
      border-radius: 12px;
      padding: 11px 14px;
      cursor: pointer;
      background: var(--accent);
      color: #fff9f2;
      transition: transform 0.12s ease, opacity 0.12s ease, background 0.2s ease;
    }

    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.45; cursor: not-allowed; transform: none; }
    button.secondary { background: #886847; }
    button.warn { background: var(--danger); }

    .group-list {
      overflow: auto;
      padding: 10px 10px 18px;
      display: grid;
      gap: 8px;
    }

    .group-item {
      border: 1px solid rgba(217, 203, 178, 0.75);
      border-radius: 16px;
      background: rgba(255,255,255,0.72);
      padding: 10px;
      cursor: pointer;
      display: grid;
      gap: 8px;
      transition: transform 0.12s ease, border-color 0.2s ease, background 0.2s ease;
    }

    .group-item:hover { transform: translateY(-1px); border-color: var(--accent-2); }
    .group-item.active {
      border-color: var(--accent);
      background: linear-gradient(180deg, rgba(207,111,50,0.18), rgba(255,255,255,0.82));
    }

    .group-item.priority {
      border-color: #9d221c;
      background: linear-gradient(180deg, rgba(157,34,28,0.14), rgba(255,255,255,0.82));
    }

    .group-meta {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: baseline;
    }

    .group-name {
      font-weight: 700;
      font-size: 14px;
    }

    .group-count {
      color: var(--accent);
      font-weight: 700;
      font-size: 13px;
      white-space: nowrap;
    }

    .group-path {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
      word-break: break-all;
    }

    .main {
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .main-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }

    .content {
      min-height: 0;
      overflow: auto;
      padding: 18px 22px 26px;
      display: grid;
      gap: 18px;
    }

    .empty {
      min-height: 300px;
      display: grid;
      place-items: center;
      color: var(--muted);
      border: 1px dashed var(--line);
      border-radius: 22px;
      background: rgba(255,255,255,0.5);
      padding: 30px;
      text-align: center;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
      gap: 18px;
    }

    .card {
      border: 1px solid rgba(217, 203, 178, 0.85);
      border-radius: 18px;
      overflow: hidden;
      background: rgba(255,255,255,0.75);
      display: grid;
      gap: 10px;
      padding: 12px;
      position: relative;
    }

    .thumb-wrap {
      position: relative;
      background: linear-gradient(180deg, rgba(240,231,216,0.8), rgba(255,255,255,0.8));
      border-radius: 14px;
      overflow: hidden;
      aspect-ratio: 1 / 1;
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

    .card-info {
      display: grid;
      gap: 6px;
      font-size: 12px;
      color: var(--muted);
    }

    .path {
      line-height: 1.45;
      word-break: break-all;
    }

    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .actions a {
      text-decoration: none;
      color: var(--accent);
      font-weight: 600;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      background: rgba(167, 68, 31, 0.12);
      color: var(--accent);
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 700;
    }

    .badge.referenced {
      background: rgba(40, 120, 72, 0.12);
      color: #2d7a46;
    }

    .badge.orphan {
      background: rgba(160, 40, 40, 0.12);
      color: var(--danger);
    }

    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .danger-note {
      color: var(--danger);
      font-size: 12px;
    }

    @media (max-width: 960px) {
      .app {
        grid-template-columns: 1fr;
        height: auto;
        min-height: 100vh;
      }
      .sidebar {
        max-height: 40vh;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1 class="title">重复图片人工过审</h1>
        <div class="subtitle" id="summaryText">正在加载分组...</div>
      </div>
      <div class="controls">
        <div class="control-row">
          <input id="searchInput" type="text" placeholder="按路径筛选分组">
          <select id="minCountSelect">
            <option value="2">至少 2 张</option>
            <option value="3">至少 3 张</option>
            <option value="5">至少 5 张</option>
            <option value="10">至少 10 张</option>
          </select>
        </div>
        <div class="control-row">
          <select id="modeSelect">
            <option value="perceptual">灰度近似聚类</option>
            <option value="exact">精确重复（MD5）</option>
          </select>
          <select id="referenceFilterSelect">
            <option value="all">全部图片</option>
            <option value="referenced">只看正文已引用</option>
            <option value="orphan">只看孤儿图片</option>
          </select>
        </div>
        <div class="control-row">
          <select id="thresholdSelect">
            <option value="6">阈值 6</option>
            <option value="8">阈值 8</option>
            <option value="10" selected>阈值 10</option>
            <option value="12">阈值 12</option>
            <option value="14">阈值 14</option>
          </select>
          <select id="blacklistFilterSelect">
            <option value="all">全部分组</option>
            <option value="blacklistOnly">只看黑名单候选组</option>
            <option value="nonBlacklist">排除黑名单候选组</option>
          </select>
        </div>
        <div class="control-row">
          <button class="secondary" id="refreshButton">刷新分组</button>
          <div></div>
        </div>
        <div class="control-row">
          <button id="openRootButton">打开根目录</button>
          <button class="secondary" id="openBlacklistGalleryButton">打开拉黑图集</button>
        </div>
      </div>
      <div class="group-list" id="groupList"></div>
    </aside>
    <main class="main">
      <div class="main-header">
        <h2 class="title" id="groupTitle">请选择左侧分组</h2>
        <div class="status" id="groupStatus">这里会显示当前分组的路径、数量和删除状态。</div>
        <div class="main-toolbar">
          <button class="secondary" id="selectAllButton" disabled>全选本组</button>
          <button class="secondary" id="clearSelectionButton" disabled>清空选择</button>
          <button class="secondary" id="keepFirstButton" disabled>保留第一张，勾选其余</button>
          <button class="secondary" id="learnJunkButton" disabled>加入废图样本库</button>
          <button class="secondary" id="purgeBlacklistButton">按样本库清本目录</button>
          <button class="warn" id="deleteSelectedButton" disabled>删除已勾选</button>
        </div>
      </div>
      <div class="content" id="content">
        <div class="empty">左边会按“重复组”列出来。点开任意一组后，你可以像清理手机相册那样勾选想删的图片。</div>
      </div>
    </main>
  </div>

  <script>
    const state = {
      groups: [],
      filteredGroups: [],
      selectedGroupId: null,
      selectedPaths: new Set(),
      minCount: 2,
      mode: 'perceptual',
      referenceFilter: 'all',
      blacklistFilter: 'all',
      threshold: 10,
      search: '',
    };

    const summaryText = document.getElementById('summaryText');
    const groupList = document.getElementById('groupList');
    const groupTitle = document.getElementById('groupTitle');
    const groupStatus = document.getElementById('groupStatus');
    const content = document.getElementById('content');
    const searchInput = document.getElementById('searchInput');
    const minCountSelect = document.getElementById('minCountSelect');
    const modeSelect = document.getElementById('modeSelect');
    const referenceFilterSelect = document.getElementById('referenceFilterSelect');
    const thresholdSelect = document.getElementById('thresholdSelect');
    const blacklistFilterSelect = document.getElementById('blacklistFilterSelect');
    const refreshButton = document.getElementById('refreshButton');
    const openRootButton = document.getElementById('openRootButton');
    const openBlacklistGalleryButton = document.getElementById('openBlacklistGalleryButton');
    const selectAllButton = document.getElementById('selectAllButton');
    const clearSelectionButton = document.getElementById('clearSelectionButton');
    const keepFirstButton = document.getElementById('keepFirstButton');
    const learnJunkButton = document.getElementById('learnJunkButton');
    const purgeBlacklistButton = document.getElementById('purgeBlacklistButton');
    const deleteSelectedButton = document.getElementById('deleteSelectedButton');

    function modeLabel() {
      return state.mode === 'perceptual' ? '灰度近似聚类' : '精确重复';
    }

    function referenceFilterLabel() {
      if (state.referenceFilter === 'referenced') return '只看正文已引用';
      if (state.referenceFilter === 'orphan') return '只看孤儿图片';
      return '全部图片';
    }

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `请求失败：${response.status}`);
      }
      return response.json();
    }

    async function learnBlacklistForPaths(samplePaths, suggestedName) {
      const payload = await fetchJson('/api/blacklist-learn', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths: samplePaths, family_name: suggestedName || '' }),
      });
      if (payload.already_exists) {
        window.alert(`这类图片已经在拉黑图集中：${payload.matched_families.join(' / ')}\\n不需要重复拉黑。\\n代表图：${payload.representative_image || '未记录'}`);
      } else {
        window.alert(`已写入废图样本库：${payload.family_name}\\n新增/累计样本：${payload.sample_count}\\n代表图：${payload.representative_image}`);
      }
      await loadGroups({ preserveSelection: true });
    }

    function applyFilters() {
      const keyword = state.search.trim().toLowerCase();
      state.filteredGroups = state.groups.filter(group => {
        if (group.count < state.minCount) return false;
        const isBlacklistGroup = group.blacklist_families && group.blacklist_families.length > 0;
        if (state.blacklistFilter === 'blacklistOnly' && !isBlacklistGroup) return false;
        if (state.blacklistFilter === 'nonBlacklist' && isBlacklistGroup) return false;
        if (!keyword) return true;
        return group.paths.some(path => path.toLowerCase().includes(keyword));
      });

      if (!state.filteredGroups.some(group => group.id === state.selectedGroupId)) {
        state.selectedGroupId = state.filteredGroups.length ? state.filteredGroups[0].id : null;
        state.selectedPaths.clear();
      }
    }

    function renderGroupList() {
      const totalImages = state.filteredGroups.reduce((sum, group) => sum + group.count, 0);
      const blacklistHits = state.filteredGroups.filter(group => group.blacklist_families && group.blacklist_families.length > 0).length;
      summaryText.textContent = `当前模式：${modeLabel()} · ${referenceFilterLabel()}，共有 ${state.filteredGroups.length} 个重复组，合计 ${totalImages} 张候选图片，其中 ${blacklistHits} 组已命中拉黑图集并自动置顶。`;
      groupList.innerHTML = '';

      if (!state.filteredGroups.length) {
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = '当前筛选条件下没有重复组。';
        groupList.appendChild(empty);
        renderCurrentGroup();
        return;
      }

      for (const group of state.filteredGroups) {
        const item = document.createElement('div');
        const priorityClass = group.blacklist_families && group.blacklist_families.length > 0 ? ' priority' : '';
        item.className = 'group-item' + priorityClass + (group.id === state.selectedGroupId ? ' active' : '');
        item.addEventListener('click', () => {
          state.selectedGroupId = group.id;
          state.selectedPaths.clear();
          renderGroupList();
          renderCurrentGroup();
        });

        const thumb = encodeURIComponent(group.representative);
        item.innerHTML = `
          <div class="group-meta">
            <div class="group-name">${group.id}</div>
            <div class="group-count">${group.count}${group.total_count !== group.count ? ` / ${group.total_count}` : ''} 张</div>
          </div>
          <img src="/image?path=${thumb}&thumb=1" alt="${group.id}" style="width:100%;border-radius:12px;background:#fff;border:1px solid rgba(217,203,178,0.6);aspect-ratio:1/1;object-fit:contain;">
          <div class="badge-row">
            ${group.blacklist_families && group.blacklist_families.length ? `<span class="badge">拉黑候选 ${group.blacklist_families.join(' / ')}</span>` : ''}
            <span class="badge referenced">已引用 ${group.referenced_count}</span>
            <span class="badge orphan">孤儿 ${group.orphan_count}</span>
          </div>
          <div class="group-path">${group.representative}</div>
        `;
        groupList.appendChild(item);
      }
    }

    function currentGroup() {
      return state.filteredGroups.find(group => group.id === state.selectedGroupId) || null;
    }

    function updateActionButtons(group) {
      const enabled = !!group;
      selectAllButton.disabled = !enabled;
      clearSelectionButton.disabled = !enabled;
      keepFirstButton.disabled = !enabled;
      learnJunkButton.disabled = !enabled;
      deleteSelectedButton.disabled = !enabled || state.selectedPaths.size === 0;
    }

    function renderCurrentGroup() {
      const group = currentGroup();
      content.innerHTML = '';

      if (!group) {
        groupTitle.textContent = '请选择左侧分组';
        groupStatus.textContent = '这里会显示当前分组的路径、数量和删除状态。';
        updateActionButtons(null);
        const empty = document.createElement('div');
        empty.className = 'empty';
        empty.textContent = '当前没有可展示的分组。';
        content.appendChild(empty);
        return;
      }

      groupTitle.textContent = `${group.id} · ${group.count}${group.total_count !== group.count ? ` / ${group.total_count}` : ''} 张`;
      groupStatus.innerHTML = `
        <span class="badge">代表图尺寸 ${group.width}×${group.height}</span>
        <span class="badge">${modeLabel()}${state.mode === 'perceptual' ? ` · 阈值 ${state.threshold}` : ''}</span>
        <span class="badge">${referenceFilterLabel()}</span>
        ${group.blacklist_families && group.blacklist_families.length ? `<span class="badge">拉黑候选 ${group.blacklist_families.join(' / ')}</span>` : ''}
        <span class="badge referenced">已引用 ${group.referenced_count}</span>
        <span class="badge orphan">孤儿 ${group.orphan_count}</span>
        <div style="margin-top:10px">${group.paths[0]}</div>
        <div class="danger-note" style="margin-top:8px">删除时会同步清理本 OCR 目录下 Markdown 对这些图片的引用。</div>
      `;

      const grid = document.createElement('div');
      grid.className = 'grid';

      group.items.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = 'card';
        const path = item.path;
        const encoded = encodeURIComponent(path);
        const checked = state.selectedPaths.has(path) ? 'checked' : '';
        const statusClass = item.referenced ? 'referenced' : 'orphan';
        const statusText = item.referenced ? `已引用 ${item.reference_count}` : '孤儿图';
        card.innerHTML = `
          <div class="thumb-wrap">
            <input class="pick-box" type="checkbox" data-path="${path.replaceAll('"', '&quot;')}" ${checked}>
            <img src="/image?path=${encoded}&thumb=1" alt="thumb-${index}">
          </div>
          <div class="card-info">
            <div><strong>第 ${index + 1} 张</strong></div>
            <div class="badge-row">
              <span class="badge ${statusClass}">${statusText}</span>
              ${item.blacklist_families && item.blacklist_families.length ? `<span class="badge">拉黑候选 ${item.blacklist_families.join(' / ')}</span>` : ''}
            </div>
            <div class="path">${path}</div>
            <div class="actions">
              <a href="/image?path=${encoded}" target="_blank" rel="noopener">看原图</a>
              <a href="/open?path=${encoded}" target="_blank" rel="noopener">打开所在位置</a>
              <button type="button" class="secondary single-blacklist-button" data-path="${path.replaceAll('"', '&quot;')}">拉黑此图</button>
            </div>
          </div>
        `;
        grid.appendChild(card);
      });

      content.appendChild(grid);

      content.querySelectorAll('.pick-box').forEach(box => {
        box.addEventListener('change', event => {
          const path = event.target.dataset.path;
          if (event.target.checked) {
            state.selectedPaths.add(path);
          } else {
            state.selectedPaths.delete(path);
          }
          updateActionButtons(group);
        });
      });

      content.querySelectorAll('.single-blacklist-button').forEach(button => {
        button.addEventListener('click', async event => {
          const path = event.target.dataset.path;
          const suggestedName = window.prompt('给这张图所在的废图族起个名字（可留空自动生成）', '');
          button.disabled = true;
          try {
            await learnBlacklistForPaths([path], suggestedName || '');
          } catch (error) {
            window.alert(error.message);
          } finally {
            button.disabled = false;
          }
        });
      });

      updateActionButtons(group);
    }

    async function loadGroups({ preserveSelection = false } = {}) {
      const previousGroupId = preserveSelection ? state.selectedGroupId : null;
      const previousSelections = preserveSelection ? new Set(state.selectedPaths) : new Set();
      thresholdSelect.disabled = state.mode !== 'perceptual';
      const payload = await fetchJson(`/api/groups?min_count=${state.minCount}&mode=${encodeURIComponent(state.mode)}&reference_filter=${encodeURIComponent(state.referenceFilter)}&threshold=${state.threshold}`);
      state.groups = payload.groups;
      applyFilters();
      if (previousGroupId && state.filteredGroups.some(group => group.id === previousGroupId)) {
        state.selectedGroupId = previousGroupId;
      }
      const group = currentGroup();
      state.selectedPaths = new Set();
      if (group) {
        group.paths.forEach(path => {
          if (previousSelections.has(path)) {
            state.selectedPaths.add(path);
          }
        });
      }
      renderGroupList();
      renderCurrentGroup();
    }

    searchInput.addEventListener('input', () => {
      state.search = searchInput.value;
      applyFilters();
      renderGroupList();
      renderCurrentGroup();
    });

    minCountSelect.addEventListener('change', async () => {
      state.minCount = Number(minCountSelect.value);
      await loadGroups();
    });

    modeSelect.addEventListener('change', async () => {
      state.mode = modeSelect.value;
      await loadGroups();
    });

    referenceFilterSelect.addEventListener('change', async () => {
      state.referenceFilter = referenceFilterSelect.value;
      await loadGroups();
    });

    thresholdSelect.addEventListener('change', async () => {
      state.threshold = Number(thresholdSelect.value);
      await loadGroups();
    });

    blacklistFilterSelect.addEventListener('change', () => {
      state.blacklistFilter = blacklistFilterSelect.value;
      applyFilters();
      renderGroupList();
      renderCurrentGroup();
    });

    refreshButton.addEventListener('click', async () => {
      refreshButton.disabled = true;
      try {
        await loadGroups({ preserveSelection: true });
      } finally {
        refreshButton.disabled = false;
      }
    });

    openRootButton.addEventListener('click', () => {
      window.open('/open-root', '_blank', 'noopener');
    });

    openBlacklistGalleryButton.addEventListener('click', () => {
      window.open('/blacklist-gallery', '_blank', 'noopener');
    });

    selectAllButton.addEventListener('click', () => {
      const group = currentGroup();
      if (!group) return;
      state.selectedPaths = new Set(group.paths);
      renderCurrentGroup();
    });

    clearSelectionButton.addEventListener('click', () => {
      state.selectedPaths.clear();
      renderCurrentGroup();
    });

    keepFirstButton.addEventListener('click', () => {
      const group = currentGroup();
      if (!group) return;
      state.selectedPaths = new Set(group.paths.slice(1));
      renderCurrentGroup();
    });

    learnJunkButton.addEventListener('click', async () => {
      const group = currentGroup();
      if (!group) return;
      const samplePaths = state.selectedPaths.size > 0 ? Array.from(state.selectedPaths) : group.paths;
      const suggestedName = window.prompt('给这类废图起个样本族名字（可留空自动生成）', '');
      learnJunkButton.disabled = true;
      try {
        await learnBlacklistForPaths(samplePaths, suggestedName || '');
      } catch (error) {
        window.alert(error.message);
      } finally {
        learnJunkButton.disabled = false;
      }
    });

    purgeBlacklistButton.addEventListener('click', async () => {
      if (!window.confirm('确认按当前废图样本库扫描并清理这个根目录吗？这会删除所有命中的废图并同步清理 Markdown 引用。')) {
        return;
      }
      purgeBlacklistButton.disabled = true;
      try {
        const payload = await fetchJson('/api/blacklist-purge', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });
        await loadGroups();
        window.alert(`样本库命中 ${payload.matched} 张，实际删除 ${payload.deleted} 张，清理 ${payload.cleaned_md} 个 Markdown 文件。`);
      } catch (error) {
        window.alert(error.message);
      } finally {
        purgeBlacklistButton.disabled = false;
      }
    });

    deleteSelectedButton.addEventListener('click', async () => {
      const group = currentGroup();
      if (!group || state.selectedPaths.size === 0) return;
      const count = state.selectedPaths.size;
      if (!window.confirm(`确认删除当前勾选的 ${count} 张图片吗？对应 Markdown 引用也会同步清理。`)) {
        return;
      }
      deleteSelectedButton.disabled = true;
      try {
        await fetchJson('/api/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paths: Array.from(state.selectedPaths) }),
        });
        state.selectedPaths.clear();
        await loadGroups();
      } catch (error) {
        window.alert(error.message);
      } finally {
        deleteSelectedButton.disabled = false;
      }
    });

    modeSelect.value = state.mode;
    referenceFilterSelect.value = state.referenceFilter;
    thresholdSelect.value = String(state.threshold);
    blacklistFilterSelect.value = state.blacklistFilter;
    thresholdSelect.disabled = false;

    loadGroups().catch(error => {
      summaryText.textContent = `加载失败：${error.message}`;
    });
  </script>
</body>
</html>
"""


HTML_BLACKLIST_GALLERY_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>拉黑图集</title>
  <style>
    body {
      margin: 0;
      padding: 24px;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: #f6f1e7;
      color: #2d2418;
    }
    .header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }
    .title { font-size: 28px; font-weight: 700; }
    .muted { color: #7b6a52; font-size: 14px; }
    .actions { display: flex; gap: 10px; flex-wrap: wrap; }
    button, a.button {
      border: 0;
      border-radius: 12px;
      padding: 10px 14px;
      background: #a7441f;
      color: white;
      text-decoration: none;
      cursor: pointer;
      font: inherit;
    }
    a.button.secondary, button.secondary { background: #886847; }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 18px;
    }
    .toolbar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 18px;
    }
    .card {
      background: rgba(255,255,255,0.85);
      border: 1px solid #dbcdb6;
      border-radius: 18px;
      padding: 14px;
      display: grid;
      gap: 10px;
    }
    .card.selected {
      border-color: #a7441f;
      box-shadow: 0 8px 24px rgba(167,68,31,0.14);
    }
    .thumb {
      width: 100%;
      aspect-ratio: 1 / 1;
      border-radius: 12px;
      background: #fff;
      object-fit: contain;
      border: 1px solid #e6dccd;
    }
    .placeholder {
      width: 100%;
      aspect-ratio: 1 / 1;
      border-radius: 12px;
      background: #efe7d9;
      color: #7b6a52;
      display: grid;
      place-items: center;
      border: 1px dashed #cdbda0;
      text-align: center;
      padding: 20px;
    }
    .name { font-size: 18px; font-weight: 700; }
    .badge {
      display: inline-block;
      border-radius: 999px;
      padding: 4px 10px;
      background: rgba(167,68,31,0.12);
      color: #a7441f;
      font-size: 12px;
      font-weight: 700;
      margin-right: 8px;
    }
    .path {
      color: #7b6a52;
      font-size: 12px;
      word-break: break-all;
    }
    .row {
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    .family-select {
      width: 18px;
      height: 18px;
      accent-color: #a7441f;
    }
    .card-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    input.rename-input {
      width: 100%;
      border-radius: 10px;
      border: 1px solid #dbcdb6;
      padding: 8px 10px;
      font: inherit;
      background: #fffdf9;
      color: #2d2418;
    }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <div class="title">拉黑图集</div>
      <div class="muted" id="summary">正在加载拉黑图集...</div>
    </div>
    <div class="actions">
      <a class="button secondary" href="/">返回 reviewer</a>
      <a class="button" href="/open-blacklist-gallery" target="_blank" rel="noopener">打开本地文件夹</a>
    </div>
  </div>
  <div class="toolbar">
    <button id="mergeButton">合并已勾选废图族</button>
    <button class="secondary" id="refreshButton">刷新图集</button>
  </div>
  <div class="grid" id="grid"></div>
  <script>
    const state = {
      families: [],
      selected: new Set(),
    };

    function escapeHtml(text) {
      return String(text ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;');
    }

    async function fetchJson(url, options = {}) {
      const response = await fetch(url, options);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `请求失败：${response.status}`);
      }
      return response.json();
    }

    async function postJson(url, payload) {
      return fetchJson(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }

    function toggleSelection(name, checked) {
      if (checked) state.selected.add(name);
      else state.selected.delete(name);
      render();
    }

    function render() {
      document.getElementById('summary').textContent = `图集目录：${state.galleryPath} · 共 ${state.families.length} 个废图族，当前已勾选 ${state.selected.size} 个`;
      const grid = document.getElementById('grid');
      grid.innerHTML = '';
      for (const family of state.families) {
        const selected = state.selected.has(family.name);
        const card = document.createElement('div');
        card.className = 'card' + (selected ? ' selected' : '');
        const imagePart = family.representative_image
          ? `<img class="thumb" src="/image?path=${encodeURIComponent(family.representative_image)}&thumb=1" alt="${escapeHtml(family.name)}">`
          : `<div class="placeholder">暂时还没有代表图<br>通常是内置规则或还没人工学习过</div>`;
        card.innerHTML = `
          <div class="row">
            <input class="family-select" type="checkbox" data-family="${escapeHtml(family.name)}" ${selected ? 'checked' : ''}>
            <div class="name">${escapeHtml(family.name)}</div>
          </div>
          ${imagePart}
          <div>
            <span class="badge">${escapeHtml(family.source)}</span>
            <span class="badge">样本 ${family.sample_count}</span>
          </div>
          <div>${escapeHtml(family.notes || '未填写备注')}</div>
          <input class="rename-input" type="text" value="${escapeHtml(family.name)}" data-family="${escapeHtml(family.name)}">
          <div class="card-actions">
            <button class="secondary rename-button" data-family="${escapeHtml(family.name)}">重命名</button>
            <button class="secondary open-button" data-path="${escapeHtml(family.representative_image || '')}">看代表图</button>
            <button class="secondary delete-button" data-family="${escapeHtml(family.name)}">删除废图族</button>
          </div>
          <div class="path">${escapeHtml(family.representative_image || '暂无代表图文件')}</div>
        `;
        grid.appendChild(card);
      }

      grid.querySelectorAll('.family-select').forEach(box => {
        box.addEventListener('change', event => {
          toggleSelection(event.target.dataset.family, event.target.checked);
        });
      });

      grid.querySelectorAll('.rename-button').forEach(button => {
        button.addEventListener('click', async event => {
          const familyName = event.target.dataset.family;
          const input = event.target.closest('.card').querySelector('.rename-input');
          const newName = input.value.trim();
          if (!newName) {
            window.alert('新名字不能为空。');
            return;
          }
          try {
            await postJson('/api/blacklist-rename', { family_name: familyName, new_family_name: newName });
            if (state.selected.delete(familyName)) {
              state.selected.add(newName);
            }
            await loadFamilies();
          } catch (error) {
            window.alert(error.message);
          }
        });
      });

      grid.querySelectorAll('.delete-button').forEach(button => {
        button.addEventListener('click', async event => {
          const familyName = event.target.dataset.family;
          if (!window.confirm(`确认删除废图族 ${familyName} 吗？这会把规则和代表图一起删除。`)) {
            return;
          }
          try {
            await postJson('/api/blacklist-delete', { family_name: familyName });
            state.selected.delete(familyName);
            await loadFamilies();
          } catch (error) {
            window.alert(error.message);
          }
        });
      });

      grid.querySelectorAll('.open-button').forEach(button => {
        button.addEventListener('click', event => {
          const path = event.target.dataset.path;
          if (!path) {
            window.alert('这类废图暂时没有代表图文件。');
            return;
          }
          window.open(`/image?path=${encodeURIComponent(path)}`, '_blank', 'noopener');
        });
      });
    }

    async function loadFamilies() {
      const payload = await fetchJson('/api/blacklist-gallery');
      state.families = payload.families;
      state.galleryPath = payload.gallery_path;
      state.selected = new Set([...state.selected].filter(name => payload.families.some(family => family.name === name)));
      render();
    }

    document.getElementById('refreshButton').addEventListener('click', async () => {
      await loadFamilies();
    });

    document.getElementById('mergeButton').addEventListener('click', async () => {
      if (state.selected.size < 2) {
        window.alert('至少勾选两个废图族才能合并。');
        return;
      }
      const selected = [...state.selected];
      const suggested = selected[0];
      const targetName = window.prompt('合并后的废图族名称', suggested);
      if (!targetName || !targetName.trim()) {
        return;
      }
      try {
        await postJson('/api/blacklist-merge', {
          source_family_names: selected,
          target_family_name: targetName.trim(),
        });
        state.selected = new Set([targetName.trim()]);
        await loadFamilies();
      } catch (error) {
        window.alert(error.message);
      }
    });

    async function main() {
      await loadFamilies();
    }
    main().catch(error => {
      document.getElementById('summary').textContent = `加载失败：${error.message}`;
    });
  </script>
</body>
</html>
"""


@dataclass
class DuplicateGroup:
    id: str
    md5: str
    representative: str
    count: int
    total_count: int
    width: int
    height: int
    paths: list[str]
    grouping: str
    referenced_count: int
    orphan_count: int
    blacklist_families: list[str]
    items: list[dict[str, Any]]


@dataclass
class GroupItem:
    path: str
    width: int
    height: int
    reference_count: int
    referenced: bool
    blacklist_families: list[str]


@dataclass
class ImageEntry:
    path: str
    md5: str
    width: int
    height: int
    ahash: int
    dhash: int
    reference_count: int
    blacklist_families: list[str]

    @property
    def referenced(self) -> bool:
        return self.reference_count > 0


class DisjointSet:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))

    def find(self, index: int) -> int:
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]
            index = self.parent[index]
        return index

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


class ReviewerIndexCache:
    CACHE_VERSION = 1

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.audit_dir = self.root / "_audit"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.audit_dir / "duplicate_reviewer_index_cache.json"
        self.payload = self._load()
        self._dirty = False

    @staticmethod
    def _resolved_str(path: Path) -> str:
        return str(path.resolve())

    @classmethod
    def _cache_key(cls, path: Path) -> str:
        return cls._resolved_str(path).lower().replace("/", "\\")

    def _empty_payload(self) -> dict[str, Any]:
        return {
            "version": self.CACHE_VERSION,
            "root": self._resolved_str(self.root),
            "updated_at": None,
            "images": {},
            "md_refs": {},
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_payload()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self._empty_payload()
        if not isinstance(payload, dict):
            return self._empty_payload()
        if payload.get("version") != self.CACHE_VERSION:
            return self._empty_payload()
        if payload.get("root") != self._resolved_str(self.root):
            return self._empty_payload()
        payload.setdefault("images", {})
        payload.setdefault("md_refs", {})
        return payload

    def save(self) -> None:
        if not self._dirty:
            return
        self.payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.path.write_text(
            json.dumps(self.payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._dirty = False

    def _load_md_counts(self, md_path: Path) -> Counter[str]:
        md_path = md_path.resolve()
        key = self._cache_key(md_path)
        try:
            stat = md_path.stat()
        except OSError:
            self.payload["md_refs"].pop(key, None)
            self._dirty = True
            return Counter()

        cached = self.payload["md_refs"].get(key)
        if (
            isinstance(cached, dict)
            and cached.get("size") == stat.st_size
            and cached.get("mtime_ns") == stat.st_mtime_ns
            and isinstance(cached.get("image_counts"), dict)
        ):
            return Counter(cached["image_counts"])

        counts = collect_markdown_image_name_counts(md_path)
        self.payload["md_refs"][key] = {
            "path": self._resolved_str(md_path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "image_counts": dict(counts),
        }
        self._dirty = True
        return counts

    def build_book_reference_counts(self) -> dict[str, Counter[str]]:
        counts_by_book: dict[str, Counter[str]] = {}
        seen_md_keys: set[str] = set()

        for images_dir in self.root.rglob("images"):
            if not images_dir.is_dir():
                continue
            book_dir = images_dir.parent.resolve()
            book_key = self._resolved_str(book_dir)
            book_counts = Counter()
            for md_path in book_dir.glob("*.md"):
                md_key = self._cache_key(md_path)
                seen_md_keys.add(md_key)
                book_counts.update(self._load_md_counts(md_path))
            counts_by_book[book_key] = book_counts

        md_refs = self.payload["md_refs"]
        stale_md_keys = [
            key for key, item in md_refs.items()
            if key not in seen_md_keys and not Path(str(item.get("path", ""))).exists()
        ]
        for key in stale_md_keys:
            md_refs.pop(key, None)
            self._dirty = True

        return counts_by_book

    def get_image_entry(self, path: Path, reference_count: int = 0) -> ImageEntry:
        path = path.resolve()
        key = self._cache_key(path)
        resolved_str = self._resolved_str(path)
        try:
            stat = path.stat()
        except OSError:
            self.payload["images"].pop(key, None)
            self._dirty = True
            raise

        cached = self.payload["images"].get(key)
        if (
            isinstance(cached, dict)
            and cached.get("size") == stat.st_size
            and cached.get("mtime_ns") == stat.st_mtime_ns
        ):
            required = ("md5", "width", "height", "ahash", "dhash")
            if all(name in cached for name in required):
                return ImageEntry(
                    path=resolved_str,
                    md5=str(cached["md5"]),
                    width=int(cached["width"]),
                    height=int(cached["height"]),
                    ahash=int(cached["ahash"]),
                    dhash=int(cached["dhash"]),
                    reference_count=reference_count,
                    blacklist_families=[],
                )

        entry = build_image_entry(path, reference_count=reference_count)
        self.payload["images"][key] = {
            "path": resolved_str,
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "md5": entry.md5,
            "width": entry.width,
            "height": entry.height,
            "ahash": entry.ahash,
            "dhash": entry.dhash,
        }
        self._dirty = True
        return entry

    def prune_images(self, seen_paths: list[Path]) -> None:
        seen_keys = {self._cache_key(path) for path in seen_paths}
        images = self.payload["images"]
        stale_keys = [
            key for key, item in images.items()
            if key not in seen_keys and not Path(str(item.get("path", ""))).exists()
        ]
        for key in stale_keys:
            images.pop(key, None)
            self._dirty = True

    def remove_images(self, deleted_paths: list[Path]) -> None:
        images = self.payload["images"]
        for path in deleted_paths:
            key = self._cache_key(path)
            if key in images:
                images.pop(key, None)
                self._dirty = True

    def invalidate_markdown_files(self, md_paths: list[Path]) -> None:
        refs = self.payload["md_refs"]
        for md_path in md_paths:
            key = self._cache_key(md_path)
            if key in refs:
                refs.pop(key, None)
                self._dirty = True

    def clear(self) -> dict[str, Any]:
        image_entries = len(self.payload.get("images", {}))
        md_entries = len(self.payload.get("md_refs", {}))
        cache_path = self.path
        deleted = False
        if cache_path.exists():
            try:
                cache_path.unlink()
                deleted = True
            except OSError:
                deleted = False
        self.payload = self._empty_payload()
        self._dirty = False
        if cache_path.exists():
            self._dirty = True
            self.save()
        return {
            "cache_path": str(cache_path),
            "cache_deleted": deleted or not cache_path.exists(),
            "image_entries": image_entries,
            "md_entries": md_entries,
        }


class DuplicateReviewStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._lock = threading.RLock()
        self._entries: list[ImageEntry] = []
        self._group_cache: dict[tuple[str, int], list[DuplicateGroup]] = {}
        self._cache = ReviewerIndexCache(self.root)
        self.rebuild()

    def iter_images(self) -> list[Path]:
        return [
            path
            for path in self.root.rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS
        ]

    def rebuild(self) -> list[DuplicateGroup]:
        with self._lock:
            entries: list[ImageEntry] = []
            reference_counts_by_book = self._cache.build_book_reference_counts()
            blacklist_families = list_families(DEFAULT_BLACKLIST_PATH)
            image_paths = self.iter_images()
            for path in image_paths:
                try:
                    book_dir = path.parent.parent if path.parent.name.lower() == "images" else path.parent
                    book_key = ReviewerIndexCache._resolved_str(book_dir)
                    reference_count = reference_counts_by_book.get(book_key, Counter()).get(path.name, 0)
                    entry = self._cache.get_image_entry(path, reference_count=reference_count)
                    entry.blacklist_families = match_blacklist_families_for_entry(entry, blacklist_families)
                    entries.append(entry)
                except (OSError, UnidentifiedImageError):
                    continue

            self._entries = entries
            self._group_cache.clear()
            self._cache.prune_images(image_paths)
            self._cache.save()
            return self._build_groups(mode="perceptual", threshold=10)

    def _clear_group_cache(self) -> None:
        self._group_cache.clear()

    def clear_index_cache(self) -> dict[str, Any]:
        with self._lock:
            result = self._cache.clear()
            self._clear_group_cache()
            return result

    @staticmethod
    def _normalized_path_key(path: str | Path) -> str:
        return str(Path(path).resolve()).lower().replace("/", "\\")

    def _refresh_blacklist_matches(self) -> None:
        families = list_families(DEFAULT_BLACKLIST_PATH)
        for entry in self._entries:
            entry.blacklist_families = match_blacklist_families_for_entry(entry, families)
        self._clear_group_cache()

    def _remove_entries_by_paths(self, deleted_paths: list[Path]) -> None:
        if not deleted_paths:
            return
        deleted_keys = {self._normalized_path_key(path) for path in deleted_paths}
        self._entries = [
            entry for entry in self._entries
            if self._normalized_path_key(entry.path) not in deleted_keys
        ]
        self._clear_group_cache()

    def groups(
        self,
        min_count: int = 2,
        mode: str = "perceptual",
        threshold: int = 10,
        reference_filter: str = "all",
    ) -> list[DuplicateGroup]:
        with self._lock:
            groups = self._build_groups(mode=mode, threshold=threshold)
            filtered_groups = [
                filter_group_by_reference(group, reference_filter)
                for group in groups
            ]
            return [
                group for group in filtered_groups
                if group is not None and group.count >= min_count
            ]

    def _build_groups(self, mode: str, threshold: int) -> list[DuplicateGroup]:
        normalized_mode = mode if mode in {"exact", "perceptual"} else "perceptual"
        if normalized_mode == "exact":
            cache_key = ("exact", 0)
        else:
            cache_key = ("perceptual", threshold)

        cached = self._group_cache.get(cache_key)
        if cached is not None:
            return cached

        if normalized_mode == "exact":
            groups = self._build_exact_groups()
        else:
            groups = self._build_perceptual_groups(threshold=threshold)

        self._group_cache[cache_key] = groups
        return groups

    def _build_exact_groups(self) -> list[DuplicateGroup]:
        buckets: dict[str, list[ImageEntry]] = {}
        for entry in self._entries:
            buckets.setdefault(entry.md5, []).append(entry)

        candidates = [group for group in buckets.values() if len(group) > 1]
        return build_duplicate_groups(candidates, grouping="exact")

    def _build_perceptual_groups(self, threshold: int) -> list[DuplicateGroup]:
        buckets: dict[tuple[str, str], list[ImageEntry]] = {}
        for entry in self._entries:
            buckets.setdefault(perceptual_bucket(entry), []).append(entry)

        candidates: list[list[ImageEntry]] = []
        for entries in buckets.values():
            if len(entries) < 2:
                continue

            disjoint = DisjointSet(len(entries))
            for left in range(len(entries)):
                left_entry = entries[left]
                for right in range(left + 1, len(entries)):
                    right_entry = entries[right]
                    if is_perceptually_similar(left_entry, right_entry, threshold):
                        disjoint.union(left, right)

            components: dict[int, list[ImageEntry]] = {}
            for index, entry in enumerate(entries):
                root = disjoint.find(index)
                components.setdefault(root, []).append(entry)

            for component in components.values():
                if len(component) > 1:
                    candidates.append(component)

        return build_duplicate_groups(candidates, grouping="perceptual")

    def delete_paths(self, paths: list[str]) -> dict[str, Any]:
        resolved = []
        for item in paths:
            path = Path(item)
            if not path.is_absolute():
                path = (self.root / path).resolve()
            resolved.append(path)

        with self._lock:
            by_folder: dict[Path, list[str]] = {}
            deleted = 0
            freed_bytes = 0
            deleted_paths: list[str] = []
            deleted_file_paths: list[Path] = []
            touched_md_paths: list[Path] = []

            for image_path in resolved:
                if not image_path.exists() or not image_path.is_file():
                    continue
                freed_bytes += image_path.stat().st_size
                by_folder.setdefault(image_path.parent.parent, []).append(image_path.name)
                deleted_paths.append(str(image_path))
                deleted_file_paths.append(image_path)
                image_path.unlink()
                deleted += 1

            cleaned_md = 0
            for ocr_folder, image_names in by_folder.items():
                if not ocr_folder.exists():
                    continue
                for md_path in ocr_folder.glob("*.md"):
                    before = md_path.read_text(encoding="utf-8")
                    clean_md_references(md_path, image_names)
                    after = md_path.read_text(encoding="utf-8")
                    if before != after:
                        cleaned_md += 1
                        touched_md_paths.append(md_path)

            self._remove_entries_by_paths(deleted_file_paths)
            self._cache.remove_images(deleted_file_paths)
            self._cache.invalidate_markdown_files(touched_md_paths)
            self._cache.save()
            self._append_delete_audit(
                deleted_paths=deleted_paths,
                freed_bytes=freed_bytes,
                cleaned_md=cleaned_md,
            )
            return {
                "deleted": deleted,
                "freed_bytes": freed_bytes,
                "cleaned_md": cleaned_md,
            }

    def learn_blacklist(self, paths: list[str], family_name: str | None = None) -> dict[str, Any]:
        resolved: list[Path] = []
        for item in paths:
            path = Path(item)
            if not path.is_absolute():
                path = (self.root / path).resolve()
            if path.exists() and path.is_file():
                resolved.append(path)

        existing_families = list_families(DEFAULT_BLACKLIST_PATH)
        sample_matches: list[list[str]] = []
        for path in resolved:
            entry = build_image_entry(path)
            matched = match_blacklist_families_for_entry(entry, existing_families)
            if matched:
                sample_matches.append(matched)

        if sample_matches and len(sample_matches) == len(resolved):
            shared = set(sample_matches[0])
            for matched in sample_matches[1:]:
                shared &= set(matched)
            if shared:
                summary = blacklist_summary(DEFAULT_BLACKLIST_PATH)
                family_name_hit = sorted(shared)[0]
                family = next(
                    (item for item in existing_families if item["name"] == family_name_hit),
                    None,
                )
                return {
                    "already_exists": True,
                    "family_name": family_name_hit,
                    "matched_families": sorted(shared),
                    "sample_count": len((family or {}).get("samples", [])),
                    "blacklist_path": str(DEFAULT_BLACKLIST_PATH),
                    "representative_image": (family or {}).get("representative_image"),
                    "blacklist_gallery": summary.get("gallery_path"),
                }

        family = add_or_update_family(
            sample_paths=resolved,
            family_name=family_name,
            path=DEFAULT_BLACKLIST_PATH,
            gallery_dir=DEFAULT_BLACKLIST_GALLERY,
            source="reviewer",
            notes=f"learned from reviewer root {self.root}",
        )
        self._refresh_blacklist_matches()
        summary = blacklist_summary(DEFAULT_BLACKLIST_PATH)
        self._append_blacklist_audit(
            action="learn",
            family_name=family["name"],
            sample_paths=[str(path) for path in resolved],
        )
        return {
            "already_exists": False,
            "family_name": family["name"],
            "sample_count": len(family.get("samples", [])),
            "family_count": summary["family_count"],
            "blacklist_path": str(DEFAULT_BLACKLIST_PATH),
            "representative_image": family.get("representative_image"),
            "blacklist_gallery": summary.get("gallery_path"),
        }

    def purge_blacklist(self) -> dict[str, Any]:
        matched = scan_blacklist_matches(self.root, DEFAULT_BLACKLIST_PATH)
        unique_paths = sorted({path for paths in matched.values() for path in paths})
        result = self.delete_paths(unique_paths)
        self._append_blacklist_audit(
            action="purge",
            family_name="*",
            sample_paths=[],
            matched=matched,
        )
        return {
            **result,
            "matched": len(unique_paths),
            "families": {name: len(paths) for name, paths in matched.items()},
            "blacklist_path": str(DEFAULT_BLACKLIST_PATH),
        }

    def rename_blacklist_family(self, family_name: str, new_family_name: str) -> dict[str, Any]:
        result = rename_family(
            family_name=family_name,
            new_family_name=new_family_name,
            path=DEFAULT_BLACKLIST_PATH,
            gallery_dir=DEFAULT_BLACKLIST_GALLERY,
        )
        self._refresh_blacklist_matches()
        self._append_blacklist_audit(
            action="rename",
            family_name=family_name,
            sample_paths=[new_family_name],
        )
        return result

    def delete_blacklist_family(self, family_name: str) -> dict[str, Any]:
        result = delete_family(
            family_name=family_name,
            path=DEFAULT_BLACKLIST_PATH,
            gallery_dir=DEFAULT_BLACKLIST_GALLERY,
        )
        self._refresh_blacklist_matches()
        self._append_blacklist_audit(
            action="delete_family",
            family_name=family_name,
            sample_paths=[],
        )
        return result

    def merge_blacklist_families(self, source_family_names: list[str], target_family_name: str) -> dict[str, Any]:
        result = merge_families(
            source_family_names=source_family_names,
            target_family_name=target_family_name,
            path=DEFAULT_BLACKLIST_PATH,
            gallery_dir=DEFAULT_BLACKLIST_GALLERY,
        )
        self._refresh_blacklist_matches()
        self._append_blacklist_audit(
            action="merge",
            family_name=target_family_name,
            sample_paths=source_family_names,
        )
        return result

    def _append_delete_audit(
        self,
        deleted_paths: list[str],
        freed_bytes: int,
        cleaned_md: int,
    ) -> None:
        if not deleted_paths:
            return

        audit_dir = self.root / "_audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        log_path = audit_dir / "reviewer_delete_log.jsonl"
        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "root": str(self.root),
            "deleted": len(deleted_paths),
            "freed_bytes": freed_bytes,
            "cleaned_md": cleaned_md,
            "paths": deleted_paths,
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _append_blacklist_audit(
        self,
        action: str,
        family_name: str,
        sample_paths: list[str],
        matched: dict[str, list[str]] | None = None,
    ) -> None:
        audit_dir = self.root / "_audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        log_path = audit_dir / "blacklist_learning_log.jsonl"
        payload = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "action": action,
            "root": str(self.root),
            "family_name": family_name,
            "sample_paths": sample_paths,
            "matched_summary": {name: len(paths) for name, paths in (matched or {}).items()},
            "blacklist_path": str(DEFAULT_BLACKLIST_PATH),
        }
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def compute_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def average_hash_int(image: Image.Image, size: int = 8) -> int:
    sample = image.resize((size, size))
    pixels = list(sample.getdata())
    avg = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= avg)
    return value


def difference_hash_int(image: Image.Image, size: int = 8) -> int:
    sample = image.resize((size + 1, size))
    pixels = list(sample.getdata())
    value = 0
    width = size + 1
    for row in range(size):
        offset = row * width
        for col in range(size):
            value = (value << 1) | int(pixels[offset + col] >= pixels[offset + col + 1])
    return value


def build_image_entry(path: Path, reference_count: int = 0) -> ImageEntry:
    with Image.open(path) as image:
        width, height = image.size
        gray = image.convert("L")
        ahash = average_hash_int(gray)
        dhash = difference_hash_int(gray)
    return ImageEntry(
        path=str(path),
        md5=compute_md5(path),
        width=width,
        height=height,
        ahash=ahash,
        dhash=dhash,
        reference_count=reference_count,
        blacklist_families=[],
    )


def image_entry_signature(entry: ImageEntry) -> ImageSignature:
    return ImageSignature(
        width=entry.width,
        height=entry.height,
        ahash=entry.ahash,
        dhash=entry.dhash,
    )


def match_blacklist_families_for_entry(
    entry: ImageEntry,
    families: list[dict[str, Any]],
) -> list[str]:
    signature = image_entry_signature(entry)
    matched = [
        family["name"]
        for family in families
        if matches_family(signature, family)
    ]
    return sorted(set(matched))


def perceptual_bucket(entry: ImageEntry) -> tuple[str, str]:
    aspect = entry.width / max(entry.height, 1)
    longest = max(entry.width, entry.height)

    if aspect >= 2.2:
        shape = "wide"
    elif aspect >= 1.15:
        shape = "landscape"
    elif aspect <= 0.45:
        shape = "ultra_tall"
    elif aspect <= 0.87:
        shape = "portrait"
    else:
        shape = "square"

    if longest < 96:
        scale = "xs"
    elif longest < 280:
        scale = "s"
    elif longest < 700:
        scale = "m"
    else:
        scale = "l"

    return shape, scale


def is_perceptually_similar(left: ImageEntry, right: ImageEntry, threshold: int) -> bool:
    left_aspect = left.width / max(left.height, 1)
    right_aspect = right.width / max(right.height, 1)
    if abs(left_aspect - right_aspect) > 0.22:
        return False

    width_ratio = max(left.width, right.width) / max(1, min(left.width, right.width))
    height_ratio = max(left.height, right.height) / max(1, min(left.height, right.height))
    if width_ratio > 2.6 or height_ratio > 2.6:
        return False

    distance = (left.ahash ^ right.ahash).bit_count() + (left.dhash ^ right.dhash).bit_count()
    return distance <= threshold


def build_duplicate_groups(
    groups: list[list[ImageEntry]],
    grouping: str,
) -> list[DuplicateGroup]:
    normalized_groups: list[list[ImageEntry]] = []
    for group in groups:
        entries = sorted(group, key=lambda item: item.path.lower())
        normalized_groups.append(entries)

    normalized_groups.sort(
        key=lambda items: (
            -int(any(entry.blacklist_families for entry in items)),
            -len(items),
            items[0].path.lower(),
        )
    )

    result: list[DuplicateGroup] = []
    for index, entries in enumerate(normalized_groups, start=1):
        representative = entries[0]
        items = [
            GroupItem(
                path=entry.path,
                width=entry.width,
                height=entry.height,
                reference_count=entry.reference_count,
                referenced=entry.referenced,
                blacklist_families=entry.blacklist_families,
            )
            for entry in entries
        ]
        referenced_count = sum(1 for item in items if item.referenced)
        blacklist_families = sorted(
            {
                family
                for item in items
                for family in item.blacklist_families
            }
        )
        result.append(
            DuplicateGroup(
                id=f"G{index:04d}",
                md5=representative.md5,
                representative=representative.path,
                count=len(entries),
                total_count=len(entries),
                width=representative.width,
                height=representative.height,
                paths=[entry.path for entry in entries],
                grouping=grouping,
                referenced_count=referenced_count,
                orphan_count=len(entries) - referenced_count,
                blacklist_families=blacklist_families,
                items=[asdict(item) for item in items],
            )
        )
    return result


def filter_group_by_reference(group: DuplicateGroup, reference_filter: str) -> DuplicateGroup | None:
    normalized = reference_filter if reference_filter in {"all", "referenced", "orphan"} else "all"
    if normalized == "all":
        return group

    if normalized == "referenced":
        items = [item for item in group.items if item["referenced"]]
    else:
        items = [item for item in group.items if not item["referenced"]]

    if not items:
        return None

    representative = items[0]
    referenced_count = sum(1 for item in items if item["referenced"])
    blacklist_families = sorted(
        {
            family
            for item in items
            for family in item.get("blacklist_families", [])
        }
    )
    return DuplicateGroup(
        id=group.id,
        md5=group.md5,
        representative=representative["path"],
        count=len(items),
        total_count=group.total_count,
        width=representative["width"],
        height=representative["height"],
        paths=[item["path"] for item in items],
        grouping=group.grouping,
        referenced_count=referenced_count,
        orphan_count=len(items) - referenced_count,
        blacklist_families=blacklist_families,
        items=items,
    )


def render_thumbnail(path: Path, size: int = 512) -> tuple[bytes, str]:
    with Image.open(path) as image:
        image = image.copy()
        image.thumbnail((size, size))
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        fmt = "PNG" if image.mode == "RGBA" else "JPEG"
        if fmt == "JPEG" and image.mode != "RGB":
            image = image.convert("RGB")

        buffer = BytesIO()
        save_kwargs: dict[str, Any] = {"format": fmt}
        if fmt == "JPEG":
            save_kwargs["quality"] = 88
        image.save(buffer, **save_kwargs)
        mime = "image/png" if fmt == "PNG" else "image/jpeg"
        return buffer.getvalue(), mime


class DuplicateReviewHandler(BaseHTTPRequestHandler):
    server_version = "DuplicateImageReview/1.0"

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self.respond_html(HTML_PAGE)
            return
        if parsed.path == "/blacklist-gallery":
            self.respond_html(HTML_BLACKLIST_GALLERY_PAGE)
            return
        if parsed.path == "/api/groups":
            self.handle_groups(parsed)
            return
        if parsed.path == "/api/blacklist-gallery":
            self.handle_blacklist_gallery()
            return
        if parsed.path == "/image":
            self.handle_image(parsed)
            return
        if parsed.path == "/open":
            self.handle_open(parsed)
            return
        if parsed.path == "/open-root":
            self.handle_open_root()
            return
        if parsed.path == "/open-blacklist-gallery":
            self.handle_open_blacklist_gallery()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/delete":
            self.handle_delete()
            return
        if parsed.path == "/api/blacklist-learn":
            self.handle_blacklist_learn()
            return
        if parsed.path == "/api/blacklist-rename":
            self.handle_blacklist_rename()
            return
        if parsed.path == "/api/blacklist-delete":
            self.handle_blacklist_delete()
            return
        if parsed.path == "/api/blacklist-merge":
            self.handle_blacklist_merge()
            return
        if parsed.path == "/api/blacklist-purge":
            self.handle_blacklist_purge()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    @property
    def app(self) -> "DuplicateReviewApp":
        return self.server.app  # type: ignore[attr-defined]

    def handle_groups(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        min_count = int(params.get("min_count", ["2"])[0] or "2")
        mode = params.get("mode", ["perceptual"])[0] or "perceptual"
        threshold = int(params.get("threshold", ["10"])[0] or "10")
        reference_filter = params.get("reference_filter", ["all"])[0] or "all"
        groups = [
            {
                "id": group.id,
                "md5": group.md5,
                "representative": group.representative,
                "count": group.count,
                "total_count": group.total_count,
                "width": group.width,
                "height": group.height,
                "paths": group.paths,
                "grouping": group.grouping,
                "referenced_count": group.referenced_count,
                "orphan_count": group.orphan_count,
                "blacklist_families": group.blacklist_families,
                "items": group.items,
            }
            for group in self.app.store.groups(
                min_count=min_count,
                mode=mode,
                threshold=threshold,
                reference_filter=reference_filter,
            )
        ]
        self.respond_json(
            {
                "root": str(self.app.store.root),
                "groups": groups,
                "mode": mode,
                "threshold": threshold,
                "reference_filter": reference_filter,
                "blacklist_gallery": str(DEFAULT_BLACKLIST_GALLERY),
            }
        )

    def handle_blacklist_gallery(self) -> None:
        self.respond_json(blacklist_summary(DEFAULT_BLACKLIST_PATH))

    def handle_image(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        raw = params.get("path", [None])[0]
        if not raw:
            self.send_error(HTTPStatus.BAD_REQUEST, "missing path")
            return
        path = Path(raw)
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "image not found")
            return

        thumb = params.get("thumb", ["0"])[0] == "1"
        if thumb:
            payload, mime = render_thumbnail(path)
            self.respond_bytes(payload, mime)
            return

        mime, _ = mimetypes.guess_type(path.name)
        self.respond_bytes(path.read_bytes(), mime or "application/octet-stream")

    def handle_open(self, parsed: urllib.parse.ParseResult) -> None:
        params = urllib.parse.parse_qs(parsed.query)
        raw = params.get("path", [None])[0]
        if not raw:
            self.send_error(HTTPStatus.BAD_REQUEST, "missing path")
            return
        path = Path(raw)
        target = path.parent if path.exists() else self.app.store.root
        open_in_explorer(target)
        self.respond_html("<script>window.close()</script>")

    def handle_open_root(self) -> None:
        open_in_explorer(self.app.store.root)
        self.respond_html("<script>window.close()</script>")

    def handle_open_blacklist_gallery(self) -> None:
        open_in_explorer(DEFAULT_BLACKLIST_GALLERY)
        self.respond_html("<script>window.close()</script>")

    def handle_delete(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        paths = payload.get("paths", [])
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            self.send_error(HTTPStatus.BAD_REQUEST, "paths must be a string list")
            return
        result = self.app.store.delete_paths(paths)
        self.respond_json(result)

    def handle_blacklist_learn(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        paths = payload.get("paths", [])
        family_name = payload.get("family_name")
        if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
            self.send_error(HTTPStatus.BAD_REQUEST, "paths must be a string list")
            return
        if family_name is not None and not isinstance(family_name, str):
            self.send_error(HTTPStatus.BAD_REQUEST, "family_name must be a string")
            return
        result = self.app.store.learn_blacklist(paths, family_name=family_name or None)
        self.respond_json(result)

    def handle_blacklist_purge(self) -> None:
        result = self.app.store.purge_blacklist()
        self.respond_json(result)

    def handle_blacklist_rename(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        family_name = payload.get("family_name")
        new_family_name = payload.get("new_family_name")
        if not isinstance(family_name, str) or not family_name.strip():
            self.send_error(HTTPStatus.BAD_REQUEST, "family_name must be a non-empty string")
            return
        if not isinstance(new_family_name, str) or not new_family_name.strip():
            self.send_error(HTTPStatus.BAD_REQUEST, "new_family_name must be a non-empty string")
            return
        result = self.app.store.rename_blacklist_family(family_name, new_family_name)
        self.respond_json(result)

    def handle_blacklist_delete(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        family_name = payload.get("family_name")
        if not isinstance(family_name, str) or not family_name.strip():
            self.send_error(HTTPStatus.BAD_REQUEST, "family_name must be a non-empty string")
            return
        result = self.app.store.delete_blacklist_family(family_name)
        self.respond_json(result)

    def handle_blacklist_merge(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        source_family_names = payload.get("source_family_names", [])
        target_family_name = payload.get("target_family_name")
        if not isinstance(source_family_names, list) or not all(isinstance(item, str) for item in source_family_names):
            self.send_error(HTTPStatus.BAD_REQUEST, "source_family_names must be a string list")
            return
        if not isinstance(target_family_name, str) or not target_family_name.strip():
            self.send_error(HTTPStatus.BAD_REQUEST, "target_family_name must be a non-empty string")
            return
        result = self.app.store.merge_blacklist_families(source_family_names, target_family_name)
        self.respond_json(result)

    def respond_html(self, html: str) -> None:
        payload = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def respond_json(self, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def respond_bytes(self, payload: bytes, mime: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


class DuplicateReviewApp:
    def __init__(self, root: Path, host: str, port: int) -> None:
        self.store = DuplicateReviewStore(root)
        self.host = host
        self.port = port

    def run(self, open_browser: bool) -> None:
        server = ThreadingHTTPServer((self.host, self.port), DuplicateReviewHandler)
        server.app = self  # type: ignore[attr-defined]
        url = f"http://{self.host}:{self.port}/"
        print(f"[OK] 重复图片人工过审窗口已启动：{url}")
        print(f"[INFO] 根目录：{self.store.root}")
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n[INFO] 已停止。")
        finally:
            server.server_close()


def open_in_explorer(path: Path) -> None:
    import os

    os.startfile(str(path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch a local UI to review duplicate OCR images group by group."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("output"),
        help="Root directory containing OCR images.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port to bind. Default: 8765",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the browser automatically.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"找不到目录：{root}")
    app = DuplicateReviewApp(root=root, host=args.host, port=args.port)
    app.run(open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
