# botmux-fleet-ops

一组 macOS 机器上 botmux 机队的运维脚本。
这些脚本原先放在 botmux fork 的 `ops/local` 分支或各机 `~/.botmux/ops-scripts/` 里，跟 botmux 代码没有耦合。
现在单独管理，好让 botmux 能直接跑纯上游 master。

凭证刷新已经由 [cred-keeper](https://github.com/xu4wang/cred-keeper) 接管，旧的 `bot-cred-refresh*.sh`、`cred-contract-audit.sh` 等不再收录。

## 目录

| 路径 | 用途 |
|-|-|
| `scripts/add-bot-default.sh` | 按机队默认偏好新增一个 bot（读隔离、角色系统、per-bot lark-cli 身份等）。需要 `BOTMUX_OWNER=<管理员邮箱>` |
| `scripts/migrate-bots-default.sh` | 把存量 bot 批量迁移到默认偏好。先 `--dry-run`；管理 bot 必须 `--exclude` |
| `scripts/role-deploy.sh` | 部署角色库（协议模板、目录、bots.json 配置），也负责导入 `role-export.sh` 的包 |
| `scripts/role-export.sh` | 导出角色库和各角色的记忆桶，供另一台机器导入 |
| `scripts/self-upgrade.sh` | botmux 自升级：跟随部署分支，build 后重启，全程脱离进程树（bot 自己跑也安全） |
| `host/amber-writer-lock.sh` | `~/amber` 单写入者锁（同一时间只允许一个会话写） |
| `host/data-mcp-outbox-cleanup.sh` | 清理 Data MCP 过期导出文件（cron 调度）。需要 `DATA_MCP_OUTBOX=<outbox 目录>` |
| `host/card-secret-scan.py` | 扫描待分享文本里的密钥和敏感信息，输出 BLOCK / REVIEW / PASS |
| `host/redact-glpat.py` | 对日志、transcript 中泄露的 GitLab PAT 做脱敏（默认 dry-run） |
| `skills/render-html-image/` | 在沙盒里把 HTML 渲染成高清图片的 skill |

## 约定

- 依赖 botmux 源码的脚本，默认从 `~/.botmux/bin/botmux` 的 exec 行推出 checkout 位置，也可以用 `BOTMUX_REPO` 指定。
- 仓库里不放任何凭证、token、内部账号；需要的身份（管理员邮箱、App Secret 等）一律在运行时通过参数或环境变量传入。
- 各机实际调度的副本放在 `~/.botmux/ops-scripts/`。更新时从本仓库拷过去，**不要**再让 cron 指向任何 git checkout（2026-08-08 就出过一次事故：切分支把脚本切丢了）。
