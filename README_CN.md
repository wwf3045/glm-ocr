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

## 注意事项

- GLM-4v-flash 对手写内容识别较差，手写场景建议用 Claude 或 GPT
- PPT/PPTX 文件会先通过 LibreOffice 转为 PDF 再处理
- 处理成功后，源文件会自动从 `input/` 中删除

## 开源协议

MIT
