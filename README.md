# IPTV List

自动从公开上游清单生成去重后的中国 IPTV 播放列表，供 Threadfin、VLC 或其他 IPTV 播放器使用。

## 输出地址

Threadfin 的 `Playlist URL` 填写：

```text
https://raw.githubusercontent.com/cherish9051-cloud/iptv-list/main/output/cn_best.m3u8
```

选择报告：

```text
https://raw.githubusercontent.com/cherish9051-cloud/iptv-list/main/output/selection-report.json
```

## 自动选择规则

同一频道的多个播放地址会先统一频道名，例如：

- `CCTV1`、`CCTV-1`、`CCTV-1 (1080p)` 统一为 `CCTV1`
- `CCTV-5+` 统一为 `CCTV5+`
- `CCTV-6电影` 统一为 `CCTV6`

然后按照以下顺序选择一个地址：

1. 优先更高分辨率；
2. 分辨率相同时，优先 `response-time` 更低的地址；
3. 条件完全相同时，保留上游清单中更靠前的地址。

当前上游：

```text
https://raw.githubusercontent.com/best-fan/iptv-sources/main/cn_all_status.m3u8
```

> 上游仓库当前默认分支是 `main`，旧的 `master` 地址不可用。

## 自动更新

GitHub Actions 每 6 小时运行一次，也可以在仓库的 **Actions** 页面选择 **Update optimized IPTV playlist**，点击 **Run workflow** 手动更新。

生成结果发生变化时，工作流会自动提交：

- `output/cn_best.m3u8`
- `output/selection-report.json`

## Threadfin 建议配置

```text
Playlist URL: https://raw.githubusercontent.com/cherish9051-cloud/iptv-list/main/output/cn_best.m3u8
EPG Source: XEPG
Stream Buffer: None
自动更新间隔: 6 小时
```

第一次导入后，在 Mapping 页面批量选择频道、启用 `Active`，并映射到 `Threadfin Dummy`。由于这个输出已经完成同名频道去重，不需要再逐个挑选重复源。

## 本地运行

只依赖 Python 3.10 及以上版本：

```bash
python scripts/build_playlist.py
```

使用本地源文件测试：

```bash
python scripts/build_playlist.py --source-file source.m3u8
```

配置位于 `config/settings.json`。

## 说明

本仓库只整理公开播放列表，不托管视频内容，也不保证上游地址持续可用。请仅在合法授权范围内使用相关内容。
