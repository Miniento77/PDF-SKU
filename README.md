# label-pdf-sku

`label-pdf-sku` 是一个本地网页工具，一次处理一张快递面单 PDF。它会尽量保留原始 PDF 的矢量内容，在页面下方扩展出新的底部区域，并把手动输入的 SKU 与数量排版进去，适配 4x6 面单打印。

## 工作方式

- 使用 `pypdf` 读取单页输入 PDF。
- 通过把原始页面合并到更高的新页面上，尽量保持原面单内容清晰且不栅格化。
- 使用 `reportlab` 测量底部文字宽度，让字号和行数自动适配实际排版空间。
- 只在 SKU 条目边界换行，保持原输入顺序。
- 通过一个简单的本地 WSGI 网页提供上传、生成和下载流程。

## 本地运行

优先使用项目自带的虚拟环境：

```bash
cd /Users/jrclawbot/.openclaw/workspace/projects/label-pdf-sku
.venv/bin/python app.py
```

然后在浏览器打开 `http://127.0.0.1:8000`。

可选启动参数：

```bash
.venv/bin/python app.py --host 127.0.0.1 --port 8000
```

## 网页使用方法

1. 上传一张 PDF 面单文件。
2. 输入使用中文或英文逗号分隔的 SKU 文本，例如 `SF601x1，BJ601DRY x1，任意字符都可以`。
3. 系统会自动按列对齐布局，每行最多放 4 个完整 SKU；如果你想手动控制布局，也可以展开“高级设置”填写 `min_font_size`、`max_font_size`、`max_lines`、`horizontal_padding`、`vertical_padding` 和 `footer_min_height`。
4. 提交表单。
5. 下载生成后的 PDF。

高级设置都是可选项，留空时会使用与 CLI 相同的默认排版参数。

## CLI

命令行版本依然可用：

```bash
.venv/bin/python -m label_pdf_sku.cli input.pdf output.pdf "SF601 x2, BJ601DRY x1"
```

## 测试

使用项目虚拟环境运行完整测试：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

当 `pypdf` 和 `reportlab` 都已安装时，PDF 集成测试会自动运行。
