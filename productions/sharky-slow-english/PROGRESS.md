# Progress — Sharky's Slow English

## State: v3 动态版已交付

`output/sharky-sample-v3.mp4` — 1920×1080 / 30fps / **5:03** / 137 拍 / 87 MB
`output/sharky-sample.mp4` — v2（静态版，35 镜 5:02），留作对比

| 运动指标 | 参考片 | v2 | v3 |
| --- | --- | --- | --- |
| 帧间差均值 | 4.54 | 0.53 | **3.34** |
| 画面变化间隔 | 2.0s | 8.9s | **2.2s** |

v3 的做法：每镜拆成约 2.2 秒一拍，每拍换取景中心 + 推拉方向，加手持微旋转（±0.6°/s），
湿镜头叠程序化气泡粒子层（60 帧循环）。构建脚本 `tools/build3.py`。

## 资产

| 路径 | 内容 |
| --- | --- |
| `BRIEF.md` | 定位（B 儿童向）、5 章扩展方案、成本 |
| `SCRIPT.md` | 26 镜头逐条词表 + 时长 |
| `shots.json` | 26 个图像提示词（全部带角色锚点） |
| `voice.json` | 旁白行（macOS `say`，Samantha，rate 145） |
| `assets/persona/anchor.png` | 角色锚点：Sharky + 两颗牙齿 |
| `assets/shots/S01-S26.png` | 26 张静帧（agnes-image-2.5-flash，免费档） |
| `assets/work/*.wav` | 26 段旁白 |
| `tools/agnes.py` | 生图驱动（已加 `AGNES_SIZE` / `AGNES_ANCHOR` 环境变量） |
| `tools/build.py` | 静帧 → Ken Burns + 字幕 + 旁白 → 拼接 |

## 已知问题

1. **静帧是 1312×736**，被放大到 1920×1080（1.46x）。agnes 接口不吃 1920×1080 请求。
2. **微距镜头角色漂移**：S14（黏糖）第一版生成了"巨型牙齿 + 苍蝇 + 粉胶"，已重生成一次，仍不如其他镜头干净。挂角色锚点会让模型强行塞角色进微距画面。
3. **旁白是 macOS `say`**，机械感明显。换真人/更好 TTS 只需替换 `assets/work/*.wav` 重跑 `build.py`，构图不动。
4. **无 BGM**（参考片也没有明显音床）。

## 下一步（按优先级）

| 动作 | 时长 | 成本 |
| --- | --- | --- |
| 换 TTS（真人或 Voicebox）→ 只换 `assets/work/*.wav` 重跑 build | 15 分钟 | $0-低 |
| 真·主体运动：agnes-video-v2.0 恢复后，给 16 个湿镜头出 img2video | 1-2 小时 | $0-低 |
| 修 3 个漂移镜头（S14 黏糖、C6 吐绿泡沫、C7 水花） | 10 分钟 | $0 |
| 扩到 35-49 分钟（+60 静帧，按 5 章换病人） | 半天 | $0-低 |
