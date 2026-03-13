[English](OCR_AUDIT_POLICY.md) | 简体中文

# OCR 审计约定

本文档定义了当某些页面无法通过 GLM 主管线产出时，应该如何审计 GLM-OCR 结果。

## 适用范围

以下情况应使用本约定：

- `_failed_segments/*.failed.json` 标记的失败分段
- 通过非 GLM 路径补齐的页面
- 清理前必须人工核对的旧版残留输出

## 三类结果

1. **GLM 原生结果**
   - 由 `ocr.py` 标准管线产出
   - 可以包含整段 PDF、逐页图片回退、原生 PDF 文本兜底
   - 不需要额外标记
2. **已登记的非 GLM 补页**
   - 页面无法通过 GLM 主管线完成
   - 改走了备用路径，例如 Mathpix、其他视觉模型，或基于页图的 AI 视觉补录
   - 对应 `.md` 必须带有 `OCR_AUDIT` 标记
3. **未登记的替换页**
   - 页面被其他方式替换了，但来源没有记录
   - 这不符合长期可审计要求

## 必须使用的标记

每个非 GLM 补页都应在文件头附近加入一行注释：

```md
<!-- OCR_AUDIT: supplement=non_glm mode=ai_visual_supplement reason=provider_content_filter source=rendered_page_image operator=codex_session_vision -->
```

推荐字段：

- `supplement=non_glm`
- `mode=ai_visual_supplement` 或其他更准确模式
- `reason=provider_content_filter` 或其他具体原因
- `source=rendered_page_image` 或其他来源说明
- `operator=...` 记录由哪个工作流补齐

## 推荐处理顺序

1. 先拆分失败分段，保住未受影响的页面。
2. 再把被拦页按单页重跑。
3. 在离开 GLM 管线前，先走完内建兜底链。
4. 如果页面仍失败，再改走备用路径。
5. 用 `OCR_AUDIT` 标记登记这次补页。

## 审计解释

- 出现 `_failed_segments/*.failed.json`，说明这批结果还不能算完成。
- 带 `OCR_AUDIT` 标记的页面，不属于“静默残缺”。
- 已登记的非 GLM 补页应当继续在审计报告中可见。
- 旧 `segment_*.md` 在确认新版分页覆盖和正文连续性之前，不能直接删除。

## 当前脚本行为

- `verify_ocr.py` 仍然是完成验收闸门。
- `audit_ocr_integrity.py` 会把已登记的非 GLM 补页单独列出来，保证它们可见，但不与真正的高风险失败混在一起。
