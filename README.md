# IPTV List

自动从公开上游清单生成去重后的中国 IPTV 播放列表，并同步生成与频道精确匹配的轻量 XMLTV，供 Threadfin、VLC 或其他 IPTV 播放器使用。

## 输出地址

Threadfin 的 `Playlist URL`：

```text
https://raw.githubusercontent.com/cherish9051-cloud/iptv-list/main/output/cn_best.m3u8
```

Threadfin 的 `XMLTV URL`：

```text
https://raw.githubusercontent.com/cherish9051-cloud/iptv-list/main/output/cn_dummy.xml
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

## XMLTV 说明

`cn_dummy.xml` 会为播放列表中的每个频道生成完全一致的 `tvg-id` 和占位节目。它的用途是让 Threadfin 能够批量映射并激活频道，不包含真实节目预告。

生成脚本还会把 XMLTV 地址写入 M3U 的 `url-tvg` 和 `x-tvg-url` 头部，兼容支持自动识别节目单的播放器。

## 自动更新

GitHub Actions 每 6 小时运行一次，也可以在仓库的 **Actions** 页面选择 **Update optimized IPTV playlist**，点击 **Run workflow** 手动更新。

生成结果发生变化时，工作流会自动提交：

- `output/cn_best.m3u8`
- `output/cn_dummy.xml`
- `output/selection-report.json`

## Threadfin 配置

1. 在 **Playlist** 中添加：

   ```text
   https://raw.githubusercontent.com/cherish9051-cloud/iptv-list/main/output/cn_best.m3u8
   ```

2. 在 **XMLTV** 中另外添加：

   ```text
   https://raw.githubusercontent.com/cherish9051-cloud/iptv-list/main/output/cn_dummy.xml
   ```

3. 确认 `Settings -> EPG Source` 为 `XEPG`。
4. 更新 XEPG 或重启 Threadfin。
5. 进入 **Mapping**，频道应按 `tvg-id` 自动匹配；批量启用 `Active` 后保存。
6. `Stream Buffer` 设为 `None` 时，视频流不会经过 Threadfin 服务器。

注意：只添加 Playlist 不会自动在 Threadfin 的 XMLTV 源列表中创建记录，XMLTV URL 需要在 XMLTV 页面单独添加一次。

## 本地运行

只依赖 Python 3.10 及以上版本：

```bash
python scripts/build_playlist.py
python scripts/build_xmltv.py
```

使用本地源文件测试：

```bash
python scripts/build_playlist.py --source-file source.m3u8
python scripts/build_xmltv.py
```

播放列表配置位于 `config/settings.json`。

## 说明

本仓库只整理公开播放列表，不托管视频内容，也不保证上游地址持续可用。请仅在合法授权范围内使用相关内容。
