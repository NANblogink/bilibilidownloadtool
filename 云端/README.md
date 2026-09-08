# bilidown 云端后端

桌面端 `BilibiliDownloader` 配套的 PHP 后端服务，为客户端提供**版本检查、热更新分发、公告推送、灰度/AB 测试、设备与统计、反馈收集**等能力。

> 桌面端仓库：`../BilibiliDownloader`

---

## 目录结构

```
bilidown-server/
|
|-- src/                        业务层
|   |-- ConfigLoader.php        配置加载
|   |-- TaskManager.php         任务管理
|   |-- DownloadManager.php     下载调度
|   |-- DownloadWorker.php      下载执行
|   |-- NetworkUtils.php        网络工具
|   |-- BilibiliParser.php      B站解析
|
|-- web/                        Web 根目录（站点部署指向这里）
|   |-- index.php               首页
|   |-- header.php / footer.php 公共布局
|   |-- api.php                 API 入口
|   |-- article.php / articles.php   文章
|   |-- disclaimer.php / privacy.php / terms.php   法律页
|   |-- feedback.php            用户反馈
|   |-- wasm_proxy.php          WASM 代理
|   |-- migrate_db.php          数据库迁移
|   |-- test_compat_check.php   兼容性自检
|   |
|   |-- api/
|   |   |-- check/index.php                    客户端版本检查
|   |   |-- v1/announcement/index.php          公告
|   |   |-- v1/version/index.php               版本信息
|   |   |-- v1/config/index.php                配置下发
|   |   |-- v1/patch/index.php                 补丁/热更新
|   |   |-- v1/hotfix/index.php                热修复
|   |   |-- v1/emergency/index.php             紧急开关
|   |   |-- v1/blacklist/index.php             黑名单
|   |   |-- v1/gray/index.php                  灰度发布
|   |   |-- v1/abtest/index.php                AB 测试
|   |   |-- v1/beta/index.php                  内测授权
|   |   |-- v1/device/index.php                设备登记
|   |   |-- v1/sync/index.php                  数据同步
|   |   |-- v1/pull/index.php                  拉取
|   |   |-- v1/stats/index.php                 统计
|   |   |-- v1/crash/index.php                 崩溃上报
|   |   |-- v1/feedback/index.php              反馈提交
|   |
|   |-- admin/                  管理后台
|   |   |-- index.php  auth.php  login.php  logout.php
|   |   |-- stats.php  stats_v2.php           统计
|   |   |-- versions.php                      版本管理
|   |   |-- announcements.php                 公告管理
|   |   |-- patch_*.php  patches.php          补丁管理
|   |   |-- file_manage.php                   文件管理
|   |   |-- device_logs.php                   设备日志
|   |   |-- log_view.php                      日志查看
|   |   |-- beta_testers.php  beta_auth.php   内测名单
|   |   |-- ops.php  sync.php  pull.php  pull_view.php
|   |   |-- components/navbar.php
|   |
|   |-- js/                     前端脚本（含 ffmpeg-core.wasm）
|   |-- uploads/                上传目录
|   |-- .htaccess  nginx.conf  nginx_site.conf  security.conf
|
|-- config/                     配置（含密钥，不入库）
|   |-- app_config.json
|   |-- api_config.json
|
|-- data/                       SQLite 数据与 session（不入库）
|   |-- bilidown.db
|   |-- init_db.php             建库脚本（入库）
|   |-- admin_config.php
|   |-- sessions/
|   |-- .htaccess  index.html
|
|-- .gitignore
```

---

## 部署

1. 站点根目录指向 `web/`
2. 复制配置模板并填写数据库路径、密钥等（`config/*.json` 已被 `.gitignore` 排除，**需手动创建**）
3. 执行建库：访问 `web/migrate_db.php`，或命令行 `php data/init_db.php`
4. 确保 `data/` 目录对 PHP 进程**可写**（SQLite 写入 + session 存储）
5. 确保 `web/uploads/` 可写
6. Web 服务器参考 `web/nginx.conf`、`web/nginx_site.conf`；`data/` 与 `config/` 必须禁止外部访问（见各自 `.htaccess`）

## 安全注意

- `data/bilidown.db`、`data/sessions/sess_*`、`config/api_config.json` 含**真实业务数据与密钥**，已列入 `.gitignore`，提交前务必用 `git status --ignored` 复核。
- `config.zip` 为配置打包产物，同样不入库。
- `web/uploads/` 下内容由用户上传，只保留 `.htaccess` 与 `index.html` 占位。
- 若密钥曾被提交过，请**轮换密钥**，仅删除文件不足以消除历史泄露。

---

## 与桌面端的接口约定

桌面端 `app_config.py` 中的 `CLOUD_DOWNLOAD_URLS` 指向：

```
https://www.bilidown.cn/api/v1/check?type=installer&version=<版本号>
https://gitee.com/api/v5/repos/nanblogink/bilibilidownloadtool/releases/latest
https://api.github.com/repos/NANblogink/bilibilidownloadtool/releases/latest
```

即**双轨策略**：自建 API 优先，失败后回退 Gitee / GitHub Releases。
改动接口时需同步桌面端 `cloud_service.py` 的解析逻辑与 `cloud_service.py` 中的字段名。

---

## 待补充

- [ ] 各 API 的请求/响应字段说明
- [ ] 数据库表结构与 `init_db.php` 对齐说明
- [ ] 管理后台登录与权限模型
- [ ] 本地开发环境搭建（PHP 版本要求、扩展依赖）
