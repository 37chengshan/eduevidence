# EduEvidence 提交包布局（dist/eduevidence-submission/）

> 配套：`packaging/make_upload.sh`、`packaging/scp-manifest.json`、`packaging/UPLOAD-README.md`。

## 一、总体原则

1. `SKILL.md` 是根目录唯一 Skill 入口；平台若强制小写，提交时再复制，不在仓库内制造第二入口。
2. 实际比赛包由 allowlist staging 构建，每次清空 `dist/eduevidence-submission/`，不依赖旧目录残留。
3. 不生成压缩包；官方提交媒介、大小限制和联网策略以官方规则为准。
4. 排除 `.git/`、`.venv/`、缓存、内部 brief、旧 Web 归档、tests/、benchmarks/、`visualization/lieflat-charts/`。

## 二、真实布局

```text
dist/eduevidence-submission/
├── SKILL.md / README.md / README.zh-CN.md / LICENSE
├── CHANGELOG.md / pyproject.toml / install.sh / eduevidence_cli.py
├── engine/ domains/ scripts/ retrieval/ integrations/
├── schemas/ skill/ references/
├── visualization/eduevidence-report/   # 报告渲染器与三适配器运行时
├── web/                                # index.html + styles.css + 六个 live JS 模块
├── examples/                           # 主 Demo 与必要结果/报告工件
├── docs/                               # 必要架构、Demo、复现、release contract
├── UPLOAD-README.md / scp-manifest.json / upload-layout.md
└── submission-manifest.json            # 内容文件 hash/字节清单，不含自身
```

当前实测：301 个内容文件，24,693,641 bytes；manifest 使用 UTF-8 JSON、POSIX 相对路径和 SHA-256。

## 三、构建与核对

```bash
bash packaging/make_upload.sh
python3 -m json.tool dist/eduevidence-submission/submission-manifest.json >/dev/null
find dist/eduevidence-submission -name '__pycache__' -o -name '*.pyc'
```

最后一个命令必须无输出。核心 smoke 还应从临时目录、任意 cwd、无仓库环境变量启动报告适配器和 Web。

## 四、运行时依赖

- Python 核心和三适配器使用标准库。
- baked HTML/SVG 报告是离线真实能力。
- Web 交互图从 jsDelivr 加载 ECharts 5.4.3；提交包未内置该 runtime，断网时使用静态报告。
- 旧 Web archive、landing、wizard、DID sandbox 和 Lieflat gallery 不属于提交包。
