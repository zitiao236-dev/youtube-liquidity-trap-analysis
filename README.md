# YouTube 流动性陷阱策略分析

本项目研究 Chart Fanatics 视频 [STEAL This EASY Liquidity TRAP Trading Strategy - $500K+ (PERFECT Sniper Entries)](https://www.youtube.com/watch?v=DAnXM7C16h0)，整理其中的流动性、扫损、假突破、多周期结构、入场与风险管理逻辑，并给出可供后续回测的规则草案。

## 分析入口

- [完整中文分析](reports/analysis_zh.md)
- [视频原始规则与量化假设](reports/strategy_rules.md)
- [关键时间戳](reports/key_timestamps.md)
- [数据来源与研究方法](docs/methodology.md)

## 目录结构

```text
.
├── README.md
├── requirements.txt
├── scripts/
│   ├── download_video_data.py
│   ├── analyze_transcript.py
│   └── validate_transcripts.py
├── data/
│   ├── metadata.json
│   └── transcripts/          # 仅本地；被 .gitignore 排除
├── reports/
│   ├── analysis_zh.md
│   ├── strategy_rules.md
│   └── key_timestamps.md
└── docs/
    └── methodology.md
```

## 安装

需要 Python 3.10 或更高版本。建议使用虚拟环境：

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 自行获取字幕

在您对该公开视频具备正常访问权限时运行：

```bash
python scripts/download_video_data.py "https://www.youtube.com/watch?v=DAnXM7C16h0" --output-dir data
```

默认优先 YouTube/`yt-dlp` 标为人工的英文轨，再尝试自动英文轨；另按 `zh-CN,zh-Hans,zh,zh-TW` 获取中文轨。可调整语言或优先自动字幕：

```bash
python scripts/download_video_data.py VIDEO_URL --output-dir data --languages en,en-US --zh-languages zh-CN,zh-TW
python scripts/download_video_data.py VIDEO_URL --output-dir data --prefer-auto
```

验证 SRT 时间轴：

```bash
python scripts/validate_transcripts.py data/transcripts/original.srt data/transcripts/zh.srt
```

生成仅供本地研究的关键词证据索引：

```bash
python scripts/analyze_transcript.py data/transcripts/original.srt --output data/transcripts/evidence_index.json
```

脚本不会下载音视频，也不需要 API 密钥。YouTube 的公开接口和页面行为可能变化；如遇到访问限制，请遵守平台条款，不要绕过 DRM、付费墙或访问控制，也不要把 Cookie 或登录凭据提交到仓库。

## 字幕来源与版权

本次本地研究取得 `en` 与 `zh-CN` 两条字幕，`yt-dlp` 均将其列在视频的 `subtitles` 集合中。该分类不等同于对人工制作或校对质量的独立认证。元数据记录在 `data/metadata.json`。

完整英文字幕、中文字幕及其纯文本版本属于第三方内容，仅用于个人学习与研究。`data/transcripts/` 已被 `.gitignore` 整体排除，**不会推送到公开 GitHub 仓库**。公开报告只保留原创分析、时间戳和必要的短引用。请使用脚本从视频来源自行获取有权访问的字幕。

## 风险免责声明

本项目不构成投资建议、交易信号或收益承诺。期货、外汇和差价合约可能造成重大损失。视频标题、口述提款、胜率、盈利金额和赞助商宣传均未经本项目独立验证；展示案例不能证明未来表现。任何回测还必须考虑手续费、买卖价差、滑点、流动性、合约换月、新闻冲击、过度拟合与样本选择偏差。

