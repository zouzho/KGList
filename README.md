# chart-playlist-aggregator

全球音乐榜单聚合歌单生成器。每周一自动采集国内外各大音乐平台的**欧洲榜、热歌榜、新歌榜**三类榜单，
统一归一化后跨源合并去重，按统一综合分排序并各截取 **TOP100**，输出可直接导入**酷狗音乐**的歌单文件。

需求与验收依据见《全球音乐榜单聚合歌单项目说明书》。

## 功能概览

| 能力 | 说明 |
| --- | --- |
| 榜单采集 | 按配置采集各平台欧洲榜/热歌榜/新歌榜，保留原始快照，支持限流、指数退避重试与单源失败降级 |
| 归一化 | 统一全半角、大小写、标点与空白，剥离 `feat.`/`Remaster`/`Live`/`伴奏`等版本后缀，拆分多歌手并取主歌手作为去重键 |
| 合并去重 | 同一首歌跨平台、跨榜单出现只保留一条，同时保存全部来源、各榜名次与出现次数 |
| 加权排序 | 综合分 = 榜单类型权重 × 来源权重 × 名次折算得分；并列时按出现平台数、最好名次、首次出现顺序稳定排序 |
| 歌单生成 | 每类歌单最多 100 首，输出酷狗歌单文件（.kgl）+ 便于核对的纯文本 + 中间 JSON 数据（可还原来源与名次） |
| 自动校验 | 校验条数、去重、序号连续性、行格式与中间数据一致性，校验不通过则任务失败，不产出不完整歌单 |
| 定时调度 | GitHub Actions 每周一 01:00 UTC（北京时间 09:00）执行一次，支持手动触发与单源回补 |

## 目录结构

```text
chart-playlist-aggregator/
  config/
    settings.yaml            数据源开关、权重、条数上限、归一化与评分规则
    format.yaml              酷狗 .kgl 与纯文本歌单格式参数（全部可配置，格式调整不改数据处理逻辑）
  sources/                   采集层：各平台适配器，接口变更只改对应模块
    base.py                  HTTP 客户端（重试/礼貌间隔）、数据对象
    netease.py / qq.py / kugou.py / apple.py / billboard.py / deezer.py / kuwo.py
    registry.py              按配置生成榜单采集规格
  pipeline/                  处理层：归一化、去重键、加权打分、排序与截断
  formatters/                输出层：酷狗 .kgl 歌单、纯文本歌单与中间 JSON 生成
  validators/                校验层：条数、去重、格式与完整性校验
  output/<周次>/             运行产物（歌单文件、中间数据、raw/ 原始快照）
  logs/                      运行摘要与逐源采集明细
  main.py                    统一命令行入口
  runner.py                  编排：采集 -> 归一化 -> 聚合 -> 生成 -> 校验 -> 留存
  requirements.txt           依赖清单（仅 PyYAML）
  .github/workflows/weekly-playlist.yml   定时与手动触发工作流
```

## 本地运行

```bash
python -m pip install -r requirements.txt
python main.py run                    # 完整流程
python main.py run -v                 # 输出调试日志
python main.py run --chart hot        # 只生成热歌榜歌单
python main.py run --platform netease --platform qq   # 只回补指定平台
python main.py run --week 2026-11-02 --limit 50       # 指定周次目录与条数上限
```

运行结束后：

- `output/<周次>/` 下生成 `<slug>_top100.kgl`（酷狗歌单文件）、`<slug>_top100.txt`（便于核对）与 `<slug>.json`（中间数据）；
- `output/<周次>/raw/` 保存各榜单源原始快照；
- `logs/run-<周次>.md` 为运行摘要，`logs/collect-<周次>.jsonl` 为逐源采集明细。

退出码：`0` 成功，`1` 关键校验不通过或所需歌单未产出，`2` 配置错误。

## 数据源

| 平台 | 欧洲榜 | 热歌榜 | 新歌榜 | 接入入口 |
| --- | --- | --- | --- | --- |
| 网易云音乐 | 欧美热歌榜 | 热歌榜 | 新歌榜 | 公开接口 `/api/playlist/detail` |
| QQ 音乐 | — | 巅峰榜·热歌 | 巅峰榜·新歌 | 公开接口 `fcg_v8_toplist_cp` |
| 酷狗音乐 | 欧美榜 | TOP500 | 新歌榜 | 公开接口 `api/v3/rank/song` |
| Apple Music | 英国榜、德国榜 | 美国热歌榜 | — | Apple Marketing Tools RSS |
| Billboard | — | Hot 100 | — | 榜单页已前端渲染，适配器待接入浏览器方案，默认关闭 |
| Deezer | — | 全球热歌榜 | — | 公开接口 `/chart/{id}/tracks` |
| 酷我音乐 | 待接入 | 待接入 | 待接入 | 默认关闭，接口需 csrf 令牌校验 |

单源失败只记录异常并降级，不影响其他来源与整体产出，运行报告中会标注失败来源。

## 调度

`.github/workflows/weekly-playlist.yml`：

- `schedule`：`0 1 * * 1`（UTC），即每周一北京时间 09:00 自动执行；
- `workflow_dispatch`：可手动指定周次、榜单类型与平台；
- `push`：代码推送到默认分支时执行一次，用于验证流程；工作流自身的回写提交只涉及 `output/`、`logs/`，不会再次触发；
- 产物以 `actions/upload-artifact` 上传保留 30 天，同时提交回仓库 `output/`、`logs/` 形成可追溯历史；
- 提交步骤为 `continue-on-error`，推送权限受限时不影响本次产出与产物上传。

## 输出格式（酷狗歌单 .kgl）

酷狗音乐的歌单文件是 `.kgl`：XML 结构，客户端在列表空白处右键「导入列表」选择该文件即可导入。

```xml
<?xml version="1.0" encoding="windows-1252"?>
<List ListName="热歌榜 TOP100">
<File><FilePath>E:\</FilePath><FileSize>0</FileSize><Duration>0</Duration><Hash>0</Hash><Lyric>E:\</Lyric><BitRate>192</BitRate><MediaFileType>0</MediaFileType><FileName>歌手 - 歌名</FileName></File>
</List>
```

`config/format.yaml` 的 `kugou_kgl` 段集中定义：编码与编码回退、行尾、XML 声明、ListName 模板、
FileName 模板与多歌手连接符、是否输出完整 File 字段、扩展名与命名规范；`kugou_text` 段保留纯文本输出，
便于人工核对。该结构来自公开资料（KGL 词条与社区导入实践），酷狗未公开格式规范，因此：

- 默认沿用酷狗原生导出组合：内容按 GBK（本地 ANSI）写入、声明行写 `windows-1252`，`&` 等按 XML 规则转义；
- 目标编码无法表示的字符（如个别韩文、日文假名）按 `encoding_errors: xmlcharrefreplace` 写成 XML 字符引用；
- **首次使用请在酷狗音乐客户端实际导入验证**：重点确认 FileName 写法（`{artist} - {title}` 或 `{artist}-{title}`）、
  编码与完整字段是否被接受；如导入异常，只改 `format.yaml` 参数，不改动数据处理逻辑；
- 验证通过后把 `config/format.yaml` 中 `kugou_kgl.verified` 置为 `true`。

## 合规说明

- 只采集公开榜单页与公开接口的元数据，不下载、不存储、不分发任何音频文件；
- 限制请求频率并设置合理超时，遵守平台使用条款；
- 不绕过平台授权、不破解接口加密、不使用登录态批量抓取；
- 不涉及任何账号凭据，无需配置密钥。
