<div align="center">
  <img src="icon.png" width="120"/>
  <h1>Mahiro Search</h1>
  <p>基于向量模型的语义化搜索文件项目</p>
</div>



# 特点

- 全盘文件名索引 (os.walk + watchdog)
- 对PDF, DOCX, TXT, MD和代码类文件进行内容索引
- 通过 LanceDB + OpenAI 兼容的嵌入 API 进行向量语义搜索
- 结果融合：文件名向量搜索 + FTS 关键词搜索 + 内容向量搜索 (RRF)
- 使用QFluentWidgets，界面简洁
- 跨平台，Windows/Linux/MacOS均可运行~

## 依赖

- Python 3.11+
- requirements.txt

## 安装

1. 通过源代码运行

```bash
# 1. Clone and enter repo
git clone https://github.com/LeonspaceX/MahiroSearch && cd MahiroSearch

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. RUN IT!!!
python main.py
```

2. ⭐ 前往[Releases页面](https://github.com/LeonspaceX/MahiroSearch/releases/)下载构建产物

```bash
# Just run that executable!
```

## 🛠️ TODO

- [x] Github Workflow

## 项目架构

```
indexing/         File discovery and content extraction
embedding/        Embedding client + rate limiter
db/               LanceDB repositories
search/           Search engine + result fusion
ui/               PySide6 + QFluentWidgets desktop UI
utils/            Platform utilities
data/lancedb/     Local vector database (gitignored)
config.yaml       User configuration
main.py           Application entry point
```

# 许可证

GNU General Public License v3.0 (GPLv3)

Copyright (C) 2026 Leonxie



*项目由GPT-5.4 & Claude Opus 4.6辅助完成，难免有许多不足，作者技术有限，还望各位多多指教喵！
