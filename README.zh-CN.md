# Daily Tool Discovery

[English](README.md) | 中文

**信任优先的每日工具发现:筛出靠谱的 dev/CLI 工具,挡掉垃圾与恶意软件,并学习一份你完全掌控的口味画像。**

Daily Tool Discovery 是一个跑在服务器上的简报工作流,让你不用刷社交流也能发现好用的工具。
它按计划运行,采集候选项目,**先按社区与维护信任度、再按相关度**来判断,然后每天写出一份简短、
可检视的 Markdown 简报。

它的存在是因为这个想法的"幼稚版"会在两处翻车:一是会推荐塞满关键词的垃圾/恶意软件(一个只奖励
关键词匹配的评分器,最爱 LLM 生成的 README),二是每天给你看同一批热门仓库。这套管线就是为了
避免这两点而设计的。

## 它有何不同

- **信任先于相关。** 每个候选都会被打成一档 —— `trusted` / `review` / `reject` —— 依据是
  star、fork、issues/PR、维护近度、发布者可信度。低于你设的 star 门槛的仓库**永远进不了
  "Try Today"**,无论它关键词匹配得多完美。自动生成的用户名 + 0 star/fork + 空洞 README
  会被隔离。
- **口味可配置。** "什么算相关"写在 `profile.toml` 里,不在代码里。改类目、信号标签、
  权重和源,就能**把这个工具重定向到任意领域** —— 见 `daily-tool-discovery/templates/profiles/web-frontend.example.toml`。
- **它不会重复自己。** 已经推给你看过的项目会进入一个新鲜度冷却窗,所以每日简报是真的在轮换。
- **它会学,但很克制。** 收藏一个项目会让未来的推荐轻微偏向同类 —— 但这个学习回路被刻意做得
  弱、有上限、会衰减,而且每份简报都硬留一个 **🎲 Explore** 位给一个故意不合口味的项目,
  所以它不会塌缩成信息茧房。
- **确定性且可检视。** 排序是纯规则(不需要 LLM);每个决策都能追溯到一条你能读的 JSONL 记录。

## 工作原理

```
采集(curated awesome-list + GitHub 搜索)
  → 给每个候选打信任档(trusted / review / reject)
  → 打分(社区/维护主导;profile 相关度 + 学到的口味做微调)
  → 分桶选择,剔除已拉黑/已收藏/近期已推
  → 写出 Markdown 简报 + JSONL 收件箱
```

一份简报有五段:

- **Try Today** / **Save** —— 信任达标、且匹配你 profile 的项目。
- **Review yourself** —— 上题但社区信号弱;跑之前先自己审。
- **🎲 Explore** —— 一个故意不合 profile、但信任达标的项目,用来打破信息茧房。
- 页脚报告过滤掉了多少可疑候选。

## 当作 skill 用(整文件夹拖入,免安装)

`daily-tool-discovery/` 这个文件夹本身就是一个自包含、仅依赖标准库的 Hermes skill:
把这一个文件夹拷进 agent 的 skill 目录,跑它自带的入口即可——无需 venv/pip。
确保 `python3` 是 3.11+ 且已 export `GITHUB_TOKEN`:

```bash
cp -r daily-tool-discovery ~/.hermes/skills/software-development/daily-tool-discovery
export GITHUB_TOKEN=ghp_...
python3 ~/.hermes/skills/software-development/daily-tool-discovery/scripts/run.py discover
```

`scripts/run.py` 一切路径都从它自身位置解析,所以拷过去的文件夹能独立工作。
状态存在 `~/.daily-tool-discovery`(可用 `DAILY_TOOL_DISCOVERY_HOME` 覆盖);首次运行会
把示例 profile 和种子(来自 skill 的 `templates/`)拷到那里,简报写到
`~/.daily-tool-discovery/briefings/<今天>.md`。`dry-run`、`save`、`deny`、`feedback`
也以同样方式运行(`python3 .../scripts/run.py dry-run`)。

如果你更想要 `pip` 安装的命令行脚本,用下面的方式。

## 安装

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
```

## 发现 (Discover)

```bash
daily-tool-discovery discover --root . --date 2026-06-06 --limit 80
```

默认读取(`--root` 下的)`config/profile.toml`(若存在),否则读 skill 自带的
`templates/profile.example.toml`。发现过程综合三条输入:

- `seeds/manual.jsonl`:朋友推荐和你已知的好口味种子。服务器安装脚本首次安装时会把 skill 的
  `templates/manual.example.jsonl` 拷到这里。`discover` 把它们当作口味参考,并把种子 URL 从当日
  候选列表中过滤掉。
- `[[category.source]]`:curated 的 README 式源列表(awesome-list)。每个源有产出配额上限,
  一个大列表填不满整个候选池。
- `[[category.search]]`:直接的 GitHub 搜索查询(用 topic + 时间限定来挖新鲜项目)。`discover`
  会为搜索预留一部分池子。

产物:

- `candidates/YYYY-MM-DD.jsonl` —— 完整的发现收件箱,带信任档和风险标记(可追溯,绝不静默丢弃)。
- `briefings/YYYY-MM-DD.md` —— 渲染好的当日简报。

运行前请 export `GITHUB_TOKEN`。没有它,GitHub 只给很低的未认证配额,curated 元数据可能退化为
空摘要并带 `metadata_error_status: 403`。元数据请求默认有节流;需要时调
`DAILY_TOOL_DISCOVERY_GITHUB_DELAY_SECONDS`。

## 口味画像 (profile)

口味是数据,不是代码。活动的 `profile.toml`(回退到 skill 自带的 `templates/profile.example.toml`)定义了一切:

```toml
[[category]]
name = "agent-dev"
weight = 2                       # 主线权重
signal_tags = ["mcp", "agent", "claude-code", "skill"]
  [[category.source]]
  name = "awesome-mcp-servers"
  url = "https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md"
  [[category.search]]
  name = "fresh-agent-tools"
  query = "topic:mcp created:>2026-03-01"
  min_stars = 50

[trust]                          # star 门槛、新鲜度窗口、维护近度
min_stars = 20
novelty_days = 30

[recommend]                      # 学习回路的护栏
taste_max_points = 12            # 学到的口味只是有上限的微调
learn_last_n_saves = 20          # 衰减:只看最近的收藏
cold_start_min_saves = 5         # 收藏够多之前不学习
explore_slots = 1                # 强制的 off-profile 曝光

[lists]
deny = ["someowner/*"]           # 永不出现(也见 denylist.txt)
```

相关度是**纯标签**的:候选的 topics/名字/简介会与每个类目的 `signal_tags` 匹配、按 `weight`
加权、并封顶 —— 所以相关度能在可信项目内部排序,但永远盖不过信任门槛。要换一个领域去挖,
拷一份 profile 改类目即可。

## 命令 (Commands)

```bash
# 收藏一个项目:加书签、不再重复推荐、轻微偏向同类。
daily-tool-discovery save --root . --candidate-id github:owner/repo

# 拉黑一个项目或 owner(支持 glob):永不再出现。追加到 denylist.txt。
daily-tool-discovery deny --root . --pattern owner/repo

# 轻量反馈(tried / saved / ignored)。追加到 feedback.jsonl。
daily-tool-discovery feedback \
  --root . \
  --date 2026-06-06 \
  --candidate-id github:owner/repo \
  --verdict tried \
  --value useful \
  --note "Worth keeping"
```

信任与推荐参数也可经命令行(`--min-stars`/`DAILY_TOOL_DISCOVERY_MIN_STARS`,
`--novelty-days`/`DAILY_TOOL_DISCOVERY_NOVELTY_DAYS`)或 profile 的 `[trust]`/`[recommend]` 设置。

## 手动种子与 dry run

手动种子用于朋友推荐或你已知的项目。在 `discover` 里它们是口味参考,不是当日推荐。用 `dry-run`
来单独检视种子本身:

```bash
mkdir -p seeds
cp daily-tool-discovery/templates/manual.example.jsonl seeds/manual.jsonl
daily-tool-discovery dry-run --root . --date 2026-06-06
```

`dry-run` 仅基于手动种子写出同样的产物(`candidates/YYYY-MM-DD.jsonl`、`briefings/YYYY-MM-DD.md`)。

## Hermes 集成

Hermes 集成通过一个 cron 友好的脚本 + 自带的 `daily-tool-discovery` Hermes skill 提供。这个
skill 同时教 agent **什么叫好项目**(信任方法论)和**怎么操作管线**(改 profile、save、deny)。
默认的服务器安装可以直接投递生成的简报、不调用 LLM,也可以先让 Hermes 用 skill 复核一遍。

在一台已登录 Hermes 和 GitHub CLI 的服务器上:

```bash
mkdir -p ~/apps
gh repo clone mothieras/daily-tool-discovery ~/apps/daily-tool-discovery
cd ~/apps/daily-tool-discovery
bash scripts/install-hermes-server.sh
```

这会把自包含的 `daily-tool-discovery/` skill 文件夹(包代码 + `SKILL.md` + `templates/`)
拷进 `~/.hermes/skills/`、在 `~/.daily-tool-discovery` 建好数据根并放一份起始 `profile.toml`、
写入 `~/.hermes/scripts/daily-tool-discovery.sh`,并跑一次冒烟发现——无需 venv/pip(纯标准库)。
它不会创建 cron。常用检查:

```bash
~/.hermes/scripts/daily-tool-discovery.sh
hermes skills list | grep daily-tool-discovery
```

### 可选的 Hermes Cron

cron 应由用户显式创建。最省钱模式 —— 跑脚本、不调 LLM 直接投递简报:

```bash
hermes cron create "0 9 * * *" \
  --name daily-tool-discovery \
  --script daily-tool-discovery.sh \
  --no-agent \
  --deliver local
```

Skill 复核模式 —— 先让 Hermes 用安装好的 skill 复核简报:

```bash
hermes cron create "0 9 * * *" \
  "Review today's Daily Tool Discovery briefing. Pick at most one try item and up to two save items. Use the daily-tool-discovery skill and do not discover or install anything." \
  --name daily-tool-discovery-agent \
  --script daily-tool-discovery.sh \
  --skill daily-tool-discovery \
  --deliver local
```

用 `hermes cron list` 查看已配置的任务。

## 设计说明

最初的设计思路(历史存档;此后管线又加上了信任闸门、可配置 profile 和 Explore 位)见
[docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md](docs/specs/2026-06-05-daily-tool-discovery-briefing-design.md)。
