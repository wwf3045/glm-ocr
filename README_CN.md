[English](README.md) | 简体中文

# GLM-OCR — PDF/PPT/图片转Markdown OCR工具

使用[智谱 GLM-OCR](https://open.bigmodel.cn/) API 批量将文档转换为干净的 Markdown —— 2026 年初 [OmniDocBench v1.5 榜首模型](https://opendatalab.com/omnidocbench)。零 GPU 要求，支持 LaTeX 公式，并发处理，断点续传。

## 功能特点

- **PDF / PPT / PPTX -> Markdown**：分段 OCR，自动回退（文件上传 -> 逐页图片）
- **并发处理**：当文件有多个片段时，2 段并行 OCR（GLM-OCR API 最大并发数为 2）
- **长截图支持**：自动切分超长图片（如微信聊天记录截图），重叠分段避免截断（仅文字 OCR，不提取图片）
- **断点续传**：已完成的段落不会重复处理，中断后再次运行即可继续
- **图片提取**：内嵌图片自动保存到 `images/` 子目录
- **垃圾图片清理**：自动删除 OCR 产生的常见垃圾图（背景图、小图标）
- **数学公式支持**：LaTeX 输出（行内 `$...$`，独立公式 `$$...$$`）
- **AI 编程助手支持**：内置 `CLAUDE.md` 和 `AGENTS.md`，兼容 Claude Code、Codex、OpenCode、OpenClaw

## 使用场景

- 课件/教材转 Markdown，用于笔记整理和 RAG 知识库构建
- **微信聊天记录导出**：通过长截图导出聊天记录，比第三方导出工具风险更小（不调用私有 API，不易触发平台风控）。OCR 后的文本可用于训练 AI 个人助手
- 批量数字化扫描文档
- 网页截图文字提取

## 为什么选择 GLM？

[OmniDocBench v1.5](https://opendatalab.com/omnidocbench)（[GitHub](https://github.com/opendatalab/OmniDocBench)）是目前最全面的 OCR 评测基准。截至 2026 年 2 月初，GLM-OCR 在 5 模型对比测试中综合排名**第一**（vs DeepSeek OCR2、MinerU、PaddleOCR VL、PaddleOCR VL 1.5）。2026 年 2 月底，[云知声 U1](https://www.bilibili.com/video/BV1rqAUzAE4z/) 在榜单上超越了 GLM-OCR（95.1 vs 94.62），尤其在医疗/病历文档场景表现突出。

作为参考，通用大模型在 OmniDocBench 上的 OCR 分数远低于专用模型：**GPT-4o** 仅 75.02，**Gemini-2.5 Pro** 88.03，**Qwen3-VL-235B** 89.15 —— 专用 OCR 模型如 GLM-OCR（仅 0.9B 参数）以极小的体积和成本大幅超越它们。

### 价格

通过[智谱特惠专区](https://bigmodel.cn/special_area)，5000 万 tokens（足够 OCR **约 60 本教材**，每本 300 页）：

| 分档 | 价格 | ~ 美元 | ~ 欧元 |
|------|------|--------|--------|
| 秒杀（每账号限 1 次） | **¥2.9** | $0.40 | €0.37 |
| 开发者 / 教育（每账号限 3 次） | **¥8** | $1.10 | €1.02 |
| 标准（无资源包） | ¥10 | $1.38 | €1.28 |

标准单价：¥0.2/百万 tokens（~$0.03 / €0.03），仅为 GPT-4o Vision 的 1/100。

> 完整价格分档 → [附录：API 定价详情](#附录api-定价详情)

### 方案对比总结

| 方案 | OmniDocBench v1.5 | 最适合 | 劣势 | 部署方式 |
|------|--------------------|--------|------|----------|
| **云知声 U1**（Unisound） | **95.1** | 医疗/病历文档，字段级定位溯源，50+ 文档类型分类（99%+），极端场景（模糊、多语言） | 较新，社区实测较少，API 定价未公开 | 云端 API / 私有化部署 |
| **GLM-OCR**（智谱 ZhipuAI） | **94.62** | 结构化文档、公式、专业术语。0.9B 参数，~1.86页/秒，API 仅 0.2元/百万 token（传统 OCR 的 1/10） | 不能提取图片，无 bbox 输出，模糊文字有幻觉 | 云端 API / VLLM 本地 |
| **PaddleOCR VL 1.5**（百度 Baidu） | **94.5** | 手写体、表格、物理畸变图片 | CUDA 依赖地狱，逻辑重组能力弱 | 仅本地 GPU |
| **MinerU 2.5**（OpenDataLab） | 90.67 | 排版简单的干净 PDF | 复杂版面错字多 | 仅本地 GPU |
| **DeepSeek OCR**（深度求索 DeepSeek） | 87.01 | 表格（信息零丢失） | 公式错误，图片丢弃 | 云端 API |
| **Gemini-2.5 Pro**（Google） | 88.03 | 通用大模型，OCR 能力尚可 | 非 OCR 专用，$2.50/$15.00 每百万 tokens | 云端 API |
| **GPT-4o**（OpenAI） | 75.02 | 通用大模型 | OCR 精度低，$2.50/$10.00 每百万 tokens | 云端 API |

### 为什么用云端 API？

本项目面向**个人用户**（学生、研究者），不需要处理成千上万份文档。云端 API 意味着零 GPU 要求、不用配 CUDA、不用下载模型——`pip install` 即可使用。本地部署只适合有专用 GPU 服务器的企业场景。

脚本架构与模型解耦——切换到其他 API（DeepSeek、云知声 U1 等）只需修改 `ocr.py` 中的 API 客户端和模型名称。

> 参考：
> - [5 模型 OCR 实测对比（2026.02）](https://www.bilibili.com/video/BV1UjFjz1EdD/) by [@AI创客空间](https://space.bilibili.com/396997624)
> - [OCR 模型选型指南（2026.02）](https://www.bilibili.com/video/BV1GYF7z9E7n/) by [@从零开始学AI](https://space.bilibili.com/91394217)
> - [OmniDocBench v1.5 榜单](https://github.com/opendatalab/OmniDocBench)
> - [云知声 U1 OCR 发布](https://www.bilibili.com/video/BV1rqAUzAE4z/)

## 快速开始

### 1. 获取 API Key

在[智谱开放平台](https://open.bigmodel.cn/)注册并创建 API Key。

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

在项目根目录创建 `.env` 文件：

```
GLM_API_KEY=你的API密钥
```

### 4. 运行

```bash
# 将 PDF/PPT/图片放入 input/ 目录
python ocr.py
# Markdown 输出到 output/
```

## 输出结构

```
output/
└── 文件名/
    ├── 文件名_0001-0020.md    # 第 1-20 页
    ├── 文件名_0021-0040.md    # 第 21-40 页
    ├── ...
    └── images/                # 提取的 bbox 图片
        ├── p0003_fig0001.png
        └── ...
```

## 清理垃圾图片

```bash
python clean_junk_images.py
```

删除常见 OCR 垃圾图（~3.2MB 背景图、<3KB 小图标），并清理 Markdown 中的失效引用。

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `PAGES_PER_MD_PDF` | 20 | PDF 每段页数 |
| `PAGES_PER_MD_PPT` | 50 | PPT 每段页数 |
| `MAX_WORKERS` | 2 | API 最大并发数（GLM-OCR API 限制为 2） |
| `IMAGE_SEGMENT_HEIGHT` | 4000px | 长图每段最大高度 |
| `IMAGE_OVERLAP` | 200px | 相邻段重叠像素 |

## 环境要求

- Python 3.8+
- [智谱 API Key](https://open.bigmodel.cn/)
- PowerPoint 或 WPS Office（仅 PPT/PPTX 转换需要，通过 COM 自动化）

## 已知局限

- **幻觉问题**：GLM 对模糊文字会猜测合理值而非报错——财务/医疗等需要绝对精度的场景慎用
- **复读 bug**：处理极度密集的 Excel 截图时偶尔会循环输出同一行
- **手写识别差**：手写场景建议用 Claude 或 GPT
- PPT/PPTX 文件在后台线程转为 PDF（与 OCR 并行），复用单个 PowerPoint COM 实例，不阻塞 PDF/图片的 OCR
- 源文件在处理后保留在 `input/` 中，不会自动删除

## 开源协议

MIT

---

## 附录：评测实测详细结果

> 来源：[5 模型 OCR 实测对比（2026.02）](https://www.bilibili.com/video/BV1UjFjz1EdD/) by [@AI创客空间](https://space.bilibili.com/396997624)

<details>
<summary>点击展开</summary>

**测试 1 — 公式密集 PDF（大量数学公式）**：
| 模型 | 结果 |
|------|------|
| GLM-OCR | 公式层级完美还原，版面完整，章节标题全保留 |
| PaddleOCR VL 1.5 | 零错误，LaTeX 等效写法 |
| MinerU | 文字零错误，LaTeX 结构完整 |
| DeepSeek OCR2 | 公式符号丢失，内容缺失 |

**测试 2 — 复杂杂志排版（图片、模糊字体、混合版面）**：
| 模型 | 结果 |
|------|------|
| GLM-OCR | 唯一正确识别所有生物专业术语（血蓝蛋白、铜离子等） |
| PaddleOCR VL 1.5 | 接近正确，但专业术语有误 |
| MinerU | 大量错字（阳光→目光、植物激素→植被激素、铜离子→阴离子） |
| DeepSeek OCR2 | 文字基本正确，但图片丢弃、页码丢失 |

**测试 3 — 竖版手写中文书法（苏轼《江城子》）**：
| 模型 | 结果 |
|------|------|
| PaddleOCR VL | 零错误，全文十句完整无误 |
| GLM-OCR | 竖排顺序正确，整体稳健，但漏掉一个"话"字 |
| MinerU | 顺序正确但书法字形识别薄弱 |
| DeepSeek OCR2 | 阅读顺序完全颠倒 |

**测试 4 — 复杂手写表格（复选框、手写数字）**：
| 模型 | 结果 |
|------|------|
| PaddleOCR VL 1.5 | 最佳——手写数字全对、复选框精准识别、结构最清晰 |
| GLM-OCR | 手写数字全部正确，表格格式正确，但表头信息全丢、复选框遗漏 |
| MinerU | 表格识别完全错误 |
| DeepSeek OCR2 | 信息零丢失，但表头与数据分离 |

</details>

---

## 附录：API 定价详情

> 来源：[智谱特惠专区](https://bigmodel.cn/special_area) · [标准价格](https://bigmodel.cn/pricing)（截至 2026 年 3 月）

<details>
<summary>点击展开</summary>

| 分档 | 资源包规格 | 价格 | 每百万 tokens | 限购 |
|------|-----------|------|--------------|------|
| **秒杀** | 5000万 tokens / 3个月 | ¥2.9（$0.40 / €0.37） | ¥0.058 | 每账号 1 次 |
| **开发者** | 5000万 tokens / 3个月 | ¥8（$1.10 / €1.02） | ¥0.16 | 每账号 3 次 |
| **教育** | 5000万 tokens / 3个月 | ¥8（$1.10 / €1.02） | ¥0.16 | 每账号 3 次 |
| **企业** | 100亿 tokens / 4个月 | ¥1,600（$221 / €204） | ¥0.16 | 每账号 3 次 |
| 标准（无资源包） | 按量付费 | — | ¥0.2（$0.03 / €0.03） | 无限制 |

**成本估算**：平均每页约 2,500 tokens（图片输入 + Markdown 输出）。一本 300 页教材 ≈ 75 万 tokens ≈ 标准价 ¥0.15。

*汇率参考：1 USD ≈ 7.25 CNY，1 EUR ≈ 7.85 CNY（2026 年 3 月近似值）*

</details>
