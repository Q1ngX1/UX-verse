# Waymark 测试站 / Waymark Test Site

Waymark 是供 UX-verse 使用的虚构湾区徒步目录。站点由 HTML、CSS、JavaScript 和本地 WebP 图片组成，使用浏览器存储收藏，表单只模拟提交结果。

Waymark is a fictional Bay Area hiking directory for UX-verse. The site uses HTML, CSS, JavaScript, and local WebP images. Saved routes use browser storage, and the contact form simulates submission.

## 启动 / Start

在 UX-verse 仓库根目录执行以下命令。`--bind 127.0.0.1` 将服务限定在本机。

Run the following from the UX-verse repository root. `--bind 127.0.0.1` limits the server to this machine.

```sh
uv run --locked python -m http.server 8765 --bind 127.0.0.1 --directory mock
```

- [正常版 / Baseline](http://127.0.0.1:8765/)
- [预置问题版 / Seeded issues](http://127.0.0.1:8765/?scenario=issues)

`scenario=issues` 通过站内导航保留。对照实验可从两个入口分别创建独立浏览器会话，使用相同的任务和视口。提交表单时请使用示例数据。

Internal navigation preserves `scenario=issues`. For comparisons, start separate browser sessions from the two entry points and use the same task and viewport. Use sample data for form submissions.

## 可测试流程 / Test journeys

| 任务 / Task | 正常版预期 / Baseline expectation |
| --- | --- |
| 从首页搜索 `redwoods`，再按 Easy 和距离筛选。 Search for `redwoods` from home, then filter by Easy and sort by distance. | 列表状态和结果数量更新，刷新后仍保留筛选条件。 Results and count update, and filters survive a reload. |
| 打开 Fern Creek Loop，查看停车信息、放大照片并回到列表。 Open Fern Creek Loop, view parking info, enlarge the photo, then return to the listing. | 详情区切换，照片弹窗可关闭，返回保留原筛选条件。 The panel updates, the photo dialog closes, and the listing filters are preserved. |
| 收藏并取消收藏一条路线。 Save and remove a route. | 显示可见确认，收藏页随之更新，刷新后依然保存。 The site confirms the action, updates Saved, and persists the shortlist across reloads. |
| 在 Field guide 查季节开放说明，展开 FAQ。 Find seasonal access notes and expand the FAQ. | 页面跳到对应段落，FAQ 可展开或收起。 The page jumps to the relevant section, and the FAQ expands and collapses. |
| 用示例信息填写联系表单。 Fill in the contact form with sample details. | 必填校验生效。通过校验后，按钮先显示 `Sending…`，随后出现确认。 Required-field validation runs. A valid submission shows `Sending…`, then a confirmation. |
| 切换到手机视口，打开菜单并查看详情。 Switch to a phone viewport, open the menu, and view a route. | 移动导航可展开，详情和页脚可以正常浏览。 The mobile menu opens, and both the route and footer remain reachable. |

## 预置问题 / Seeded issues

以下问题只在 `scenario=issues` 生效。这张表可用作比对 Agent 输出的基准。

These issues appear only with `scenario=issues`. Use this table as ground truth when comparing agent findings.

| 编号 / ID | 复现 / Reproduce | 预置结果 / Seeded outcome |
| --- | --- | --- |
| W01 | 从主导航寻找 Saved。 Look for Saved in the primary navigation. | 主导航隐藏入口，页脚仍可进入。 The primary link is hidden, and the footer link remains. |
| W02 | 在路线列表中点击路线卡片的照片。 Click a route card photo in the listing. | 点击照片没有反应，只有标题可进入详情。 The image does nothing, and the title still opens the route. |
| W03 | 选择一个难度，再点击 Clear filters。 Select a difficulty, then click Clear filters. | 难度筛选仍保留。 The difficulty filter remains active. |
| W04 | 从路线详情点击 All routes。 Click All routes on a detail page. | 链接回到首页。 The link opens the homepage. |
| W05 | 在详情点击 Parking & access。 Click Parking & access on a detail page. | 显示 What to bring 面板。 The What to bring panel opens. |
| W06 | 从 Field guide 点击 Check seasonal access。 Click Check seasonal access in the Field guide. | 链接返回本地 HTTP 404。 The link returns a local HTTP 404. |
| W07 | 用有效示例信息提交联系表单。 Submit the contact form with valid sample details. | 表单清空后无确认提示。 The form clears without confirmation. |
| W08 | 在手机视口打开路线详情并滚动到底部。 Open a route on a phone viewport and scroll to the bottom. | 固定收藏栏遮挡页脚链接。 The fixed Save panel covers footer links. |

## 配图 / Photography

使用内置 ImageGen 生成三张示例照片。网页使用以下 WebP 文件。

Three sample photographs were generated with built-in ImageGen. The site uses the following WebP files.

| 文件 / File | 生成提示词 / Generation prompt |
| --- | --- |
| [coast.webp](assets/coast.webp) | Photorealistic-natural editorial photograph for a fictional Bay Area trail guide. Wide landscape composition, a pale coastal trail curving between golden tall grasses and dark green coastal shrubs above the Pacific Ocean, hazy blue gray headlands in the distance, warm late-afternoon sun, deep natural colors, realistic fine texture. Eye-level from the trail, no humans, no text, no signs, no watermark. |
| [forest.webp](assets/forest.webp) | Photorealistic-natural editorial landscape photograph for a fictional Bay Area trail guide. A quiet trail among tall Northern California coastal redwoods with soft morning mist, fern-covered understory and warm bark. Natural in-camera depth and earthy green colors, wide landscape composition, no people, no text, no signs, no watermark. |
| [city.webp](assets/city.webp) | Photorealistic-natural editorial landscape photograph for a fictional Bay Area trail guide. San Francisco-inspired waterfront walking path along a peaceful bay, eucalyptus trees framing the paved path, low city buildings in the distance and soft clear morning light. Widescreen horizontal composition, natural colors, no readable lettering, no logo, no watermark. |
