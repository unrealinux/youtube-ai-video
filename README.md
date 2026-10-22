# youtube-ai-video

个人 AI 视频实验仓库。两条独立的生产线，各自产出成片。

**只入库文本源。所有图片、音频、视频都在本地，不在 git 里。** clone 之后能看到脚本和分镜，
但看不到也重建不了成片——需要重新跑生成（花 Agnes 调用和渲染时间）。

## 成片在哪

| 片子 | 文件 | 规格 |
|---|---|---|
| AI 改变普通人的日常生活（长版，最终） | `longvideo/output/AI改变普通人的日常生活-长版-final.mp4` | 1080×1920 · 30fps · 71.8s |
| AI Bathroom, Made Real（英文竖版） | `productions/ai-bathroom-real/output/ai-bathroom-real.mp4` | 1080×1920 · 30fps · 95.8s |
| 旧版本（4 个长版变体 + 2 个 track） | `archive/` | 仅留档，不再维护 |

`longvideo/output/...-final.mp4` 来自 v2 流水线（img2video + 锚定首帧 + 30 steps）。
`archive/` 里的 `-长版.mp4`（纯 Ken Burns）、`-动态镜头.mp4`（text2video）、`-动态转场.mp4`
都是被 v2 取代的中间版本。

## 两条生产线

### 1. `longvideo/` — 中文长版

12 句旁白，从字幕边界反推每句在时间轴上的精确帧数，逐句生成画面。

```bash
python3 longvideo/build.py        # 图片 + Ken Burns 片段（v0）
python3 longvideo/gen_videos.py   # text2video 片段（v1，免费额度下 1 RPM）
python3 longvideo/rebuild_v2.py   # img2video + 锚定首帧（v2，最终版）
python3 longvideo/make_track.py   # 拼接成一条 track
```

- 输入：`script.txt`、`timeline.json`
- 外部依赖：`~/MoneyPrinterTurbo`（第一遍的 TTS 和 SRT 由它产生）
- 第一遍的任务 id 记在 `longvideo/pass1_taskid.txt`，对应的 `audio.mp3` / `subtitle.srt`
  在 `~/MoneyPrinterTurbo/storage/tasks/23186812-.../`，**不在本仓库**
- 运行状态（`*.log`、`*_state.json`、`video_tasks.json`、`v2_done.txt`）不入库

### 2. `productions/ai-bathroom-real/` — 英文竖版

复刻一条印尼参考短片的爆点结构；Hypit 声明式编排，图片 + 推拉运镜 + macOS `say` 配音。

```bash
python3 productions/ai-bathroom-real/tools/build_svml.py   # 由 shots.json + 语音时长生成 SVML
hypit build productions/ai-bathroom-real/runs/build.svrun
hypit get <build-id> --output final.video --to productions/ai-bathroom-real/output/ai-bathroom-real.mp4
```

- 详情见 `productions/ai-bathroom-real/PROGRESS.md`（含已知限制和重跑方式）
- 参考片拆解在 `references/bikin-kamar-mandi-ai/`

## 本地资产（不在 git）

| 位置 | 内容 | 体积 |
|---|---|---|
| `longvideo/frames_v2/` `videos_raw_v2/` `clips_ext_v2/` | v2 图片与片段 | 61 MB |
| `productions/ai-bathroom-real/assets/` | 32 张分镜 + 31 段配音 + 人像锚点 | 60 MB |
| `references/bikin-kamar-mandi-ai/source.mp4` | 参考视频 | 12 MB |
| `.hypit/results/` | Hypit 最后一次 Build 的输出（复用依据） | 28 MB |
| `archive/` | 旧版成片 | 160 MB |

## 凭据

没有密钥入库。实际位置：

- Agnes：`~/.config/agnes/key`（`chmod 600`）
- Google（Gemini TTS / 图片）：环境变量 `GOOGLE_GENERATIVE_AI_API_KEY`
- Hypit：`hypit.runtime.json` 只存 credential 引用，值在本地 credential store
- MoneyPrinterTurbo：`~/MoneyPrinterTurbo/config.toml`

## 已知限制

- `.gitignore` 全局忽略 `*.png *.jpg *.wav *.mp4`。往仓库里加新素材前先确认这是想要的。
- `longvideo/` 依赖 `~/MoneyPrinterTurbo` 的存在和张量环境，不能只靠本仓库重建第一遍语音。
- `productions/ai-bathroom-real/authors/main.svml` 是生成文件，别手改；改 `shots.json` 或
  `tools/build_svml.py` 后重跑生成器。
