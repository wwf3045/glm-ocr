[English](README.md) | 简体中文

# GLM-OCR

使用[智谱 GLM-4v-flash](https://open.bigmodel.cn/) API 批量将 PDF / PPT / 图片转换为 Markdown。输出干净的 Markdown 格式，支持 LaTeX 数学公式。

## 功能特点

- **PDF / PPT / PPTX -> Markdown**：分段 OCR，自动回退（文件上传 -> 逐页图片）
- **长截图支持**：自动切分超长图片（如微信聊天记录截图），重叠分段避免截断
- **断点续传**：已完成的段落不会重复处理，中断后再次运行即可继续
- **图片提取**：内嵌图片自动保存到 `images/` 子目录
- **垃圾图片清理**：自动删除 OCR 产生的常见垃圾图（背景图、小图标）
- **数学公式支持**：LaTeX 输出（行内 `$...$`，独立公式 `$$...$$`）

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
    ├── segment_1.md      # 第 1-20 页
    ├── segment_2.md      # 第 21-40 页
    ├── ...
    └── images/           # 提取的图片
        ├── page_3_img_1.png
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
| `PDF_SEGMENT_SIZE` | 20 | PDF 每段页数 |
| `PPT_SEGMENT_SIZE` | 50 | PPT 每段页数 |
| `IMAGE_SEGMENT_HEIGHT` | 4000px | 长图每段最大高度 |
| `IMAGE_OVERLAP` | 200px | 相邻段重叠像素 |

## 环境要求

- Python 3.8+
- [智谱 API Key](https://open.bigmodel.cn/)（GLM-4v-flash 为免费模型）
- LibreOffice（仅 PPT/PPTX 转换需要）

## 为什么选择 GLM？

截至 2026 年初，智谱 GLM-OCR 是**结构化文档 OCR 的综合最优解**（[OmniDocBench v1.5](https://github.com/opendatalab/OmniDocBench) 榜单），尤其擅长 PDF 转 Markdown。与同类方案对比：

| 方案 | 优势 | 劣势 |
|------|------|------|
| **GLM-OCR** | Markdown 结构输出最佳，语义理解跨页表格和复杂排版，~2页/秒，显存仅需 2-3GB，支持 VLLM 加速 | 模糊文字会脑补（幻觉），不适合扭曲/褶皱纸张 |
| **PaddleOCR v1.5** | 物理畸变场景最强（小票、褶皱、侧拍），像素级精度 | 部署地狱（CUDA 冲突、依赖报错），逻辑重组能力弱 |
| **MinerU** | 不错的开源文档解析器 | 需要本地 GPU 部署，依赖重 |

**结论**：如果输入是干净的数字文档（PDF、PPT、截图），GLM-OCR 输出的 Markdown 结构最干净，几乎不需要二次清洗——非常适合 RAG 知识库构建和学习笔记整理。如果是物理损坏或手写文档，建议用 PaddleOCR 或 Claude/GPT。

> 参考：[OCR 模型横评（2026.02）](https://www.bilibili.com/video/BV1GYF7z9E7n/) by [@从零开始学AI](https://space.bilibili.com/91394217)

## 已知局限

- **幻觉问题**：GLM 对模糊文字会猜测合理值而非报错——财务/医疗等需要绝对精度的场景慎用
- **复读 bug**：处理极度密集的 Excel 截图时偶尔会循环输出同一行
- **手写识别差**：手写场景建议用 Claude 或 GPT
- PPT/PPTX 文件会先通过 LibreOffice 转为 PDF 再处理
- 处理成功后，源文件会自动从 `input/` 中删除

## 开源协议

MIT
