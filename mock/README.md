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

## 扩展体验 / Extended experience

站点保留无构建依赖的静态架构，现有 15 条虚构路线、4 个专题、3 篇完整示例游记，以及目录、详情、收藏、指南、联系、专题、游记和行程规划共 9 类页面。所有图片均来自本地文件，无地图、字体或分析服务的外部请求。

The site keeps its buildless static architecture, with 15 fictional routes, four collections, three full sample stories, and nine page types: home, directory, detail, saved, guide, contact, collections, journal, and planner. Images are local files; maps, fonts, and analytics require no external services.

| 入口 / Entry | 交互与状态 / Interaction and state |
| --- | --- |
| 首页 / Home | 地形与心情推荐、三步路线选择器（可返回修改、显示空结果）、精选路线、专题和游记入口。 Terrain and mood suggestions, a three-step trail finder with backtracking and empty results, featured routes, collections, and stories. |
| `routes.html` | 实时搜索、地形、难度、步行时间与设施筛选、距离排序、快捷筛选、网格与示意地图切换、地图点选预览。筛选及视图保存在 URL，刷新和详情返回后可恢复。 Live search; terrain, difficulty, walking-time, and facilities filters; distance sorting; quick filters; grid/map switching; and selectable map pins. URL state restores filters and view after reload or return from detail. |
| 路线比较 / Comparison | 任意路线卡片可选择最多 3 条路线，选择至少 2 条后打开比较表。支持清除、Escape 关闭、键盘焦点恢复。比较选择仅保留在当前页面。 Select up to three routes on cards, then compare at least two in a modal table. Clear selection, Escape dismissal, and focus restoration are supported. Selection lasts for the current page. |
| `route.html?id=fern-creek` | 原有信息切换和照片弹窗之外，新增示意海拔、沿途站点、设施摘要、私人笔记、示例评论及添加行程。新评论只存本地，用户输入按文本显示。 Adds an illustrative elevation profile, trail stops, amenities, private notes, sample reviews, and a planner link alongside the original panels and photo dialog. New reviews stay local and user input renders as text. |
| `collections.html` | 专题索引、详情、关联路线、其他专题推荐，以及将整组路线加入日程。 Collection index, details, related routes, other collections, and adding a collection to the planner. |
| `journal.html` | 分类筛选、完整文章、章节目录、复制文章链接和关联专题。 Category filters, full articles, chapter navigation, copying a story link, and related collections. |
| `planner.html` | 添加最多 8 条不重复路线、调整顺序、移除、日期与出发时间、累计里程/时间/爬升、备注、确认清空路线、打印和文本下载。行程在此浏览器中持久化。 Add up to eight unique routes, reorder or remove them, set a date and start time, inspect distance/time/gain totals, add notes, confirm clearing routes, print, and download a text itinerary. Plans persist in this browser. |
| 装备清单 / Packing checklist | 指南与行程页共享 8 项勾选状态、进度与重置操作；下载行程包含当前勾选状态。 The guide and planner share an eight-item checklist, progress indicator, and reset action. The itinerary download includes current checkbox state. |

地图坐标和海拔剖面都是示意数据；日程只累计步行时间，不估算交通或休息。示例评论和文章有演示标识。表单不发送网络请求，行程和评论不跨浏览器同步。

Map positions and elevation profiles are illustrative. Itinerary times sum walking only, excluding transit and breaks. Sample reviews and stories are marked as demo content. Forms send no network requests, and plans and reviews do not sync across browsers.

视觉层沿用 Waymark 的森林绿、衬线标题和本地摄影，扩展了编辑式首页、专题大图、卡片悬停、入场动效与原生对话框。布局覆盖 320px 手机、390px 手机、768px 平板和桌面；开启 `prefers-reduced-motion` 时关闭动画和平滑滚动。桌面比较表在手机上切换为纵向路线摘要，关闭按钮固定在弹窗顶部，主页面不产生横向溢出。

The design extends Waymark’s forest green palette, serif headings, and local photography with an editorial home page, collection photography, card hover states, entrance motion, and native dialogs. Layouts cover 320px and 390px phones, 768px tablets, and desktop. `prefers-reduced-motion` disables animation and smooth scrolling. Desktop comparison tables become stacked route summaries on phones, with the close control pinned to the dialog header and no page overflow.

## 扩展验证 / Extended verification

从仓库根目录运行全部测试（需已安装 Playwright Chromium）。新增测试覆盖筛选与地图状态、比较数量限制与弹窗、专题和游记导航、三步推荐、行程重排与下载、笔记与评论持久化和文本转义，并检查 12 个代表性 URL 在四种宽度下的溢出、图片和浏览器异常。原有 W01–W08 对照测试保留。

Run the full suite from the repository root after installing Playwright Chromium. Added tests cover filter and map state, comparison limits and dialogs, collection/story navigation, the three-step finder, itinerary reordering and download, note/review persistence and text escaping, and overflow, images, and browser exceptions for 12 representative URLs at four widths. Existing W01–W08 comparison tests remain intact.

```sh
uv run --locked python -m unittest discover -s tests -v
```

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
