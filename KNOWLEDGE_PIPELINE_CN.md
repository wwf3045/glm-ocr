[English](KNOWLEDGE_PIPELINE.md) | 简体中文

# 知识笔记生成流程

这份文档记录从原始课程文件到 Obsidian 成品笔记的完整链路。

## 1. 三层资料系统

1. 原件库：保存原始 `pdf / ppt / pptx / 扫描件 / 课程附件`
2. OCR 中间文件库：保存 `分页 md + images + 教材元数据页`
3. 知识库：保存清理后的课程 `大纲.md`、章节讲义、最终附件

不要跳过中间层。OCR 结果是语料，不是最终笔记本身。

## 2. 先做 OCR

1. 把文件放进 `input/`
2. 运行 `python ocr.py`
3. 手写材料运行 `python ocr.py --handwrite`
4. PPT 转出来的 PDF 只留在 `_cache/ppt_pdf/`，不要混进 `output/`

### PDF 后端约定

- `GLM-OCR` 的活跃 PDF 后端已经从 `PyMuPDF(fitz)` 迁到 `pypdf + pypdfium2`
- 分工如下：
  - `pypdf`：页数统计、分页切段、原生 PDF 文本兜底
  - `pypdfium2`：页面渲染、bbox 裁图、二维码页采样
- 这意味着：
  - 后续不要再默认给 `ocr.py`、`verify_ocr.py`、`reference_book_metadata.py` 一类脚本加回 `fitz`
  - 如果只是处理 PDF 结构、页码、文本，不要引入渲染型依赖
  - 如果需要像素级页面图，再走 `pdf_backend.py`

## 3. 验收 OCR，再进入下游流程

必须同时运行：

```bash
python verify_ocr.py
python audit_ocr_integrity.py
```

只有满足下面条件，才算 OCR 真正完成：

- 页码覆盖连续
- 没有空 Markdown 被误当成完成
- 对应目录下没有 `_failed_segments/*.failed.json`

如果只是某几个页段失败，优先用 `rerun_pdf_segments.py` 局部重跑，不要整本重扫。

## 4. 先清理公式和 OCR 排版问题

在进入知识笔记前，要先把 OCR 输出里的公式分隔符修正好：

- `$ 2x+1 $` -> `$2x+1$`
- 块公式保持为 `$$...$$`

相关脚本：

- `markdown_cleanup.py`
- `repair_math_delimiters.py`

## 5. 先治理图片，再让它们进入讲义

OCR 侧要优先抑制或审计：

- 页眉 / 页脚 / 页码角标
- 学校 logo、水印、横幅
- 单个括号、积分号、字母等公式碎片图
- 未被正文引用的整页截图

相关脚本：

- `clean_junk_images.py`
- `duplicate_image_reviewer.py`
- `middle_library_image_maintenance.py`
- `purge_sjtu_watermarks.py`

有争议的图尽量走 reviewer 前端人工过审。进入正式讲义的图，必须服务具体知识点、定理、例题或算法步骤。

## 6. 给教材生成元数据页

教材 / 参考书除了 OCR 正文外，还要补：

- `目录页.md`
- 正文页码偏移
- 二维码资源聚合

规则：

- 每本教材 OCR 目录都应该有 `目录页.md`
- 页码偏移要能把“原书页码”映射回 PDF 页码
- 二维码少时，直接收进 `目录页.md`
- 二维码多时，聚合到 `周边资源-全部.md`

相关脚本：

- `reference_book_metadata.py`
- `backfill_reference_book_directory_pages.py`

## 7. 先在知识库里做课程 `大纲.md`

正式讲义前，先做资源型 `大纲.md`，至少列清：

- 原件库入口
- 讲义 / PPT
- 教材及参考书
- 作业 / 复习资料
- 网课资源

如果课程结构还没稳定，不要假装这页已经是完整讲义。

## 8. 建立章节-来源映射

对每门课：

1. 以老师讲义顺序作为主骨架
2. 把教材章节对到这个骨架上
3. 明确区分：
   - 课内必修 / 考试优先
   - 书本补充（`*`）

如果存在多位老师，先确定主线老师，再让另一位老师的材料补细节和空缺。

## 9. 生成正式讲义

正式讲义必须是“重写整合稿”，不能直接把 OCR 原文堆进去。

每章通常至少包含：

- 本章要回答什么问题
- 从上一章怎么引到这一章
- 直观理解 / 几何图景
- 形式化定义
- 定理与结论
- 推导或证明思路
- 例题
- 易错点
- 对应作业
- 书本补充（`*`）

## 10. 接作业与详解

作业型课程推荐结构：

- 中文题意
- 考点
- 中文解题脉络
- `English Problem`
- `English Solution`

这样复习时脉络清楚，考试前又能保持对英文题面的熟悉度。

## 11. 最终放入 Obsidian

进入知识库时：

- 附件按镜像结构放到附件目录
- 图片要插在对应知识点附近
- 不允许把图堆在讲义末尾
- 不要把 OCR 中间文件夹直接当成正式课程笔记

## 12. 推荐脚本总表

- OCR 主流程：`ocr.py`
- PDF 后端桥接：`pdf_backend.py`
- 验收：`verify_ocr.py`、`audit_ocr_integrity.py`
- 局部重跑：`rerun_pdf_segments.py`
- 公式清洗：`markdown_cleanup.py`、`repair_math_delimiters.py`
- 图片审计/清理：`clean_junk_images.py`、`duplicate_image_reviewer.py`、`middle_library_image_maintenance.py`
- 教材元数据：`reference_book_metadata.py`、`backfill_reference_book_directory_pages.py`
