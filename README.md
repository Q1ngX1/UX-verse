# UX-verse

## 浏览器基础 / Browser foundation

第一阶段提供一个本地 Playwright Worker。它按顺序执行浏览器操作，并保存每步的页面证据，供后续探索与评估使用。

Phase 1 provides a local Playwright worker that executes browser actions in order and saves page evidence for each step. Later phases use that evidence for exploration and evaluation.

## 项目架构 / Project architecture

实线方框表示已实现的模块和产物，虚线方框表示规划中的模块。箭头表示调用或数据流。

Solid boxes show implemented modules and artifacts. Dashed boxes show planned modules. Arrows show calls or data flow.

```mermaid
flowchart TB
    subgraph Entry["入口与配置 / Entry points and configuration"]
        direction LR
        CLI["命令行入口 / CLI<br/>python -m browser"]
        AgentAPI["单 Agent Python 入口<br/>run_agent"]
        Dashboard["本地控制台<br/>Local dashboard"]
        API["本地 API<br/>Local API"]
        Dashboard --> API
    end

    subgraph Runtime["Agent 运行时 / Agent runtime"]
        direction LR
        Personas["Persona 提示<br/>Persona prompt"]
        Orchestrator["评估编排<br/>Orchestrator"]
        Explorer["自主探索 Agent<br/>Explorer agent"]
        State["运行状态<br/>Run state"]
        Personas --> Explorer
        Orchestrator --> Explorer
        Explorer <--> State
    end

    subgraph Browser["浏览器执行 / Browser execution"]
        direction LR
        Actions["动作协议<br/>Action schema"]
        Worker["BrowserWorker"]
        Policy["执行约束<br/>Execution constraints"]
        Session["独立浏览器会话<br/>BrowserContext"]
        Observation["页面观测<br/>Page observation"]
        Actions --> Worker --> Session --> Observation
        Policy --> Worker
    end

    subgraph Model["模型接口 / Model access"]
        direction LR
        Decision["截图决策<br/>DecisionAdapter"]
        Temporal["多帧与视频分析<br/>TemporalAdapter"]
        Provider["模型提供方接口 / Model provider<br/>OpenAI + OpenRouter Responses"]
        Decision --> Provider
        Temporal --> Provider
    end

    subgraph Evidence["运行证据 / Run evidence"]
        direction LR
        Log["操作与错误日志 / Action log<br/>actions.jsonl"]
        AgentLog["Agent 决策日志 / Decision log<br/>agent.jsonl"]
        Screens["截图 / Screenshots<br/>screenshots/"]
        Trace["浏览器轨迹 / Trace<br/>trace.zip"]
    end

    subgraph Analysis["评价与交付 / Evaluation and delivery"]
        direction LR
        Evaluator["评价引擎<br/>Evaluation engine"]
        Aggregate["跨 Persona 汇总<br/>Cross-persona aggregation"]
        Report["交互报告 / Interactive report<br/>HTML + JSON"]
        Benchmark["基准评测<br/>Benchmarks"]
        Evaluator --> Aggregate --> Report
        Aggregate --> Benchmark
    end

    Entry -->|Agent 运行配置 / Run config| Runtime
    Entry -->|CLI 脚本动作 / Scripted actions| Browser
    Runtime -->|候选动作 / Proposed action| Browser
    Browser -.->|下一轮观测 / Next observation| Runtime
    Browser -->|保存 / Write| Evidence
    Runtime -->|决策与用量 / Decisions and usage| Evidence
    Evidence -->|读取日志与截图 / Read logs and screenshots| Analysis
    Runtime -.->|Explorer 模型调用 / Model call| Model
    Analysis -.->|Evaluator 模型调用 / Model call| Model

    classDef planned stroke-dasharray: 5 4
    class Dashboard,API,Orchestrator,Evaluator,Aggregate,Report,Benchmark planned
```

浏览器层接收结构化动作，返回页面观测并保存运行证据。单 Agent Explorer 将观测、任务和 Persona 提示交给模型接口，校验下一步动作，再交给浏览器执行。评价引擎将读取已保存的动作和截图，核对预期和实际结果。后续的多 Persona 编排会为每个 Agent 分配独立的浏览器会话。

The browser layer accepts structured actions, returns page observations, and saves run evidence. A single Explorer sends the observation, task, and Persona prompt through the model interface, validates the proposed action, then hands it to the browser. The planned evaluation engine will read saved actions and screenshots to compare expectations with outcomes. The future multi-persona orchestrator will assign a separate browser session to each agent.

| 模块 / Module | 职责 / Responsibility |
| --- | --- |
| 动作与执行 / Actions and execution | [`actions.py`](browser/actions.py) 定义并校验 Pydantic 动作模型。[`worker.py`](browser/worker.py) 用 Playwright 和 Chromium 执行动作，约束步数、超时与请求，并采集 URL、标题与截图。 `actions.py` defines and validates Pydantic action models. `worker.py` executes them with Playwright and Chromium, applies limits and request filters, and captures URLs, titles, and screenshots. |
| 编排与状态 / Orchestration and state | 单 Agent 引擎跟踪动作历史、预算、重试和模型用量。规划中的编排器按 Persona 分配任务、视口和预算。 The single-agent engine tracks action history, budgets, retries, and model usage. The planned orchestrator assigns tasks, viewports, and budgets by Persona. |
| 模型适配 / Model adapters | `DecisionAdapter` 为 Explorer 提议动作或停止。`TemporalAdapter` 从带时间戳的帧或视频提取页面变化。两者可独立选择模型，并共享 `ModelProvider` 接口。 `DecisionAdapter` proposes actions or stops for the Explorer. `TemporalAdapter` identifies visible changes from timestamped frames or video. Both select their model independently and share the `ModelProvider` interface. |
| 评价与交付 / Evaluation and delivery | 评价引擎按量表分析视觉与易用性，汇总器对发现去重并保留路径和分歧。基准评测衡量任务完成率、已知问题发现率与成本。 The evaluator applies visual and usability rubrics. Aggregation deduplicates findings and preserves paths and disagreements. Benchmarks measure task success, known-issue recall, and cost. |

更长期的扩展包括接入替代交互执行策略、调整探索预算分配，以及将本地任务迁移到托管的浏览器 Worker。

Longer-term extensions include alternative interaction strategies, adaptive exploration budgets, and moving local jobs to hosted browser workers.

## 运行 / Run

使用 Python 3.12 或更高版本及 `uv`。在仓库根目录安装依赖与 Chromium，然后用目标网址开启一次运行。

Use Python 3.12 or later and `uv`. From the repository root, install the dependencies and Chromium, then start a run with the target URL.

```sh
uv sync --locked
uv run --locked playwright install chromium
uv run --locked python -m browser https://example.com
```

用 `--actions actions.json` 提供初始导航后的动作列表。支持 `navigate`（`url`）、`click` 和 `hover`（`x`、`y`）、`type`（`x`、`y`、`text`）、`scroll`（`dx`、`dy`）、`back` 和 `wait`（`ms`）。`type` 点击指定位置的可编辑输入框，替换内容并触发输入事件，不按回车或提交表单。指针坐标以截图左上角为原点，单位为 CSS 像素。用 `--headed` 可以看到浏览器窗口。

Pass `--actions actions.json` to supply actions after initial navigation. Supported actions are `navigate` (`url`), `click` and `hover` (`x`, `y`), `type` (`x`, `y`, `text`), `scroll` (`dx`, `dy`), `back`, and `wait` (`ms`). `type` clicks an editable field at the supplied coordinates, replaces its contents, and fires input events without pressing Enter or submitting the form. Pointer coordinates use CSS pixels from the top-left corner of the screenshot. Use `--headed` to show the browser window.

```json
[
  {"type": "scroll", "dy": 600},
  {"type": "wait", "ms": 200}
]
```

Worker 面向本地或其他受信且已授权的站点。同源请求过滤和独立浏览器会话用于控制测试范围。运行不受信的站点需要在运行环境中提供独立网络隔离。

Use the worker on local or other trusted, authorized sites. Same-origin request filtering and an independent browser session scope each run. Testing untrusted sites requires separate network isolation in the runtime environment.

### 运行视口 / Run viewport

`python -m browser`、`python -m agent` 和 `python -m tools.explorer_benchmark` 都接受 `--viewport WIDTHxHEIGHT`，单位为 CSS 像素，默认 `1280x720`。Python 调用可在 `AgentConfig` 中设置 `viewport={"width": 1440, "height": 900}`，或向 `browser_worker` 传入 `browser.viewport.Viewport` 实例。运行日志保存初始宽高，每张截图的观测保存对应视口，录制视频使用初始视口作为输出画布。

`python -m browser`, `python -m agent`, and `python -m tools.explorer_benchmark` accept `--viewport WIDTHxHEIGHT` in CSS pixels, defaulting to `1280x720`. Python callers can set `viewport={"width": 1440, "height": 900}` in `AgentConfig` or pass a `browser.viewport.Viewport` instance to `browser_worker`. Run logs record the initial dimensions, each screenshot observation records its viewport, and video recording uses the initial viewport as its output canvas.

```sh
uv run --locked python -m tools.explorer_benchmark --group external --case iana-reserved --repeats 1 --record-input --viewport 390x844
```

窄视口可测试响应式排版。完整手机设备模拟还需要配置触控、移动设备模式和像素倍率；一次运行使用一个初始尺寸。

A narrow viewport can test responsive layout. Full phone emulation also requires touch, mobile mode, and device pixel ratio settings. Each run uses one initial size.

如果视口宽或高为奇数，对应的视频画布边长向上取整到偶数，网页和截图仍使用原始视口尺寸。

Odd viewport dimensions round up to the next even pixel for the video canvas. The page and screenshots retain the original viewport dimensions.

### 探索模式和设备 / Exploration mode and device

Agent 默认使用 `--mode task --device desktop`。任务模式要求 `--task` 提供明确目标。自由探索使用 `--mode explore`，此时 `--task` 可用于限定探索范围，完成时返回观察摘要。Python 调用可设置 `AgentConfig` 的 `mode` 和 `device` 字段。

The Agent defaults to `--mode task --device desktop`. Task mode requires a specific goal in `--task`. For open exploration, use `--mode explore`; an optional `--task` provides an exploration brief, and completion returns a summary of observations. Python callers can set the `mode` and `device` fields of `AgentConfig`.

`--device mobile` 启用 Chromium 移动布局和触控。Agent 可用轻点、滑动、在轻点聚焦后输入文字以及等待。输入文字使用浏览器键盘事件，原生手机软键盘和具体机型由独立的设备验证覆盖。视口仍可独立指定，例如 `--device mobile --viewport 390x844`。脚本浏览器和基准测试入口也接受 `--device`，基准测试按预设任务的验收条件检查结果。

`--device mobile` enables Chromium's mobile layout and touch input. The Agent can tap, swipe, enter text after tapping to focus, and wait. Text is entered through browser keyboard events. Native phone keyboards and specific handset behavior require separate device verification. The viewport remains independently configurable, for example `--device mobile --viewport 390x844`. The scripted browser and benchmark entry points also accept `--device`; benchmarks verify their predefined task criteria.

### 触控轨迹 / Touch trajectories

移动运行支持 `--touch-motion linear`（默认）、`phoneos-flick`（加速后抬指）和 `phoneos-drag`（加速后减速）。后两项将 phoneos 滑动算法移植到 Python，以固定的起终点生成带时间的曲线采样点，再交给 Chromium 触控输入。使用 `--touch-seed` 可以复现同一配置下的手势序列，基准测试每次重复将种子加一。

Mobile runs support `--touch-motion linear` (default), `phoneos-flick` (accelerate before lifting), and `phoneos-drag` (accelerate and decelerate). The latter two adapt phoneos's swipe algorithm to Python, generating timed curve samples between fixed endpoints and sending them through Chromium touch input. Use `--touch-seed` to reproduce a gesture sequence with the same configuration. The benchmark increments the seed for each repeat.

```sh
uv run --locked python -m tools.explorer_benchmark --group external --case iana-reserved --repeats 1 --device mobile --viewport 390x844 --touch-motion phoneos-flick --touch-seed 7 --record-input
```

移植参考 [phoneos 源码](https://github.com/mbatinefe/phoneos/blob/161910e11976ae88a3e6b000715a1694f3ce9794/src/humanize/humanizer.ts)，随项目附有 [Apache-2.0 许可证](licenses/phoneos-Apache-2.0.txt)。

The port is based on the [phoneos source](https://github.com/mbatinefe/phoneos/blob/161910e11976ae88a3e6b000715a1694f3ce9794/src/humanize/humanizer.ts) and includes the [Apache-2.0 license](licenses/phoneos-Apache-2.0.txt).

## 单 Agent 自主探索 / Single-agent exploration

也可以使用本地视觉模型，无需云端 API key。Hugging Face 权重下载、Windows CUDA 启动与 mock 实测复现步骤见 [本地模型说明](docs/local-model.md)。

Local vision models are also supported without a cloud API key. See [Local model setup](docs/local-model.md) for Hugging Face downloads, Windows CUDA startup, and reproducing the mock-site run.

在环境里设置 `OPENAI_API_KEY` 或 `OPENROUTER_API_KEY`，再通过 `UX_VERSE_DECISION_MODEL` 指定支持图片输入和 JSON 输出的模型 ID。把 `DecisionAdapter` 传给 `run_agent` 即可运行。自定义决策适配器也可以实现 [`ExplorerModel`](agent/model.py) 协议。`AgentConfig.model_timeout_seconds` 控制单次模型调用时限。

Set `OPENAI_API_KEY` or `OPENROUTER_API_KEY` in the environment. Set `UX_VERSE_DECISION_MODEL` to a model ID with image input and JSON output. Pass `DecisionAdapter` to `run_agent`. Custom decision adapters can implement the `ExplorerModel` protocol. `AgentConfig.model_timeout_seconds` controls the per-call model timeout.

打开 Waymark 测试站后，可以用命令行启动一轮 OpenRouter 决策测试。`--max-steps` 限制浏览器动作，`--max-output-tokens` 限制每次模型调用的输出长度。模型调用可能因临时失败或无效响应而重试。

With Waymark running, use the command line to start an OpenRouter decision test. `--max-steps` caps browser actions and `--max-output-tokens` caps each model response. The engine may retry a transient failure or invalid decision.

`--structured-output` 要求模型支持 JSON Schema。模型返回 0–1000 的指针坐标，适配器将其换算为 Playwright 使用的视口像素。滚动距离以像素表示。

`--structured-output` requires JSON Schema support from the model. The adapter converts pointer coordinates on a 0–1000 scale to Playwright viewport pixels. Scroll deltas use pixels.

```sh
uv run --locked python -m agent http://127.0.0.1:8765/ \
  --provider openrouter --model google/gemini-2.5-flash-lite \
  --task "Starting at Waymark's homepage, use the route directory to find and open the route named exactly Fern Creek Loop. On its detail page, read the first sentence under Parking & access. As soon as that sentence is visible, stop and report where to park in your reason." \
  --persona "First-time visitor checking trailhead parking" \
  --max-steps 8 --max-output-tokens 256 --structured-output
```

```python
import asyncio
import os
from pathlib import Path

import httpx

from agent.engine import AgentConfig, run_agent
from models.decision import DecisionAdapter
from models.responses import ResponsesProvider


async def explore():
    config = AgentConfig(
        target="https://example.com",
        task="Find the link for more information.",
        persona="First-time visitor",
        max_steps=5,
    )
    async with httpx.AsyncClient(timeout=30) as client:
        provider = ResponsesProvider("openai", client)
        model = DecisionAdapter(provider, os.environ["UX_VERSE_DECISION_MODEL"])
        return await run_agent(config, model, Path("runs/explorer-example"))


print(asyncio.run(explore()))
```

### 人类输入与截图观测 / Human input and screenshot observations

引擎打开调用方指定的起始页后，模型只收到页面视口截图、自己执行过的动作、从截图比较得出的变化，以及任务和预算。模型可以点击、悬停、滚动、逐键输入、按 Tab、Shift+Tab、Escape、上下方向键或 Enter，也可以等待、完成或放弃。连续重复且画面无变化的动作会触发一次改选。输出的 `answer` 和停止理由分别记录。

After the engine opens the caller's start page, the model receives only the viewport screenshot, its own actions, changes derived by comparing screenshots, and its task and budget. It can click, hover, scroll, type using key events, press Tab, Shift+Tab, Escape, Up, Down or Enter, wait, complete, or give up. Repeated actions with unchanged screenshots can trigger one retry. The reported `answer` and stopping reason are recorded separately.

Agent 运行入口禁用 DOM 控件和文本提示、自动定位、程序化查找与返回。截图范围是页面视口，浏览器地址栏、原生查找和原生返回尚未接入。文本输入目前支持最多 1000 个可打印 ASCII 字符，由虚拟键盘逐键执行。独立浏览器脚本仍可使用其原有工具。录制、诊断日志和基准验收可保存内部证据，模型决策输入保持截图范围。

The agent entry point disables DOM control and text hints, automatic link location, and programmatic find and back. Capture covers the page viewport. The address bar, native browser find, and native back are outside the current input surface. Text input currently supports up to 1000 printable ASCII characters through virtual key presses. The standalone browser runner retains its scripting tools. Recording, diagnostics, and benchmark verification can retain internal evidence while model input remains scoped to screenshots.

### Explorer 实测基准 / Explorer live benchmark

启动本地视觉模型后，从仓库根目录运行以下命令。工具会启动独立 Waymark 服务，并测试 Waymark、Python 3.12 文档和 IANA 公开页面。每轮交叉检查最终页面、视口中的预期内容和模型回答。运行结果及截图、浏览器日志和 trace 会保存在新建的 `runs/benchmark-*` 目录中。

Start the local vision model and run the following from the repository root. The tool starts an isolated Waymark server and tests Waymark, the Python 3.12 docs, and public IANA pages. Each run checks the final page, the expected content in the viewport, and the model answer. Results, screenshots, browser logs, and traces are saved in a new `runs/benchmark-*` directory.

```sh
uv run --locked python -m tools.explorer_benchmark --repeats 2
```

### 虚拟鼠标与键盘 / Virtual mouse and keyboard

Agent 和浏览器脚本共用虚拟输入设备。桌面模式使用虚拟鼠标和键盘，移动模式使用虚拟触控屏和键盘。鼠标轨迹和滚轮配置适用于桌面模式。

The agent and scripted browser share virtual input devices. Desktop mode uses a virtual mouse and keyboard. Mobile mode uses a virtual touchscreen and keyboard. Mouse trajectory and wheel settings apply to desktop mode.

- 桌面 Agent 在点击、悬停和聚焦输入框前移动到目标。`--pointer-mode continuous`（默认）使用直线缓动。`--pointer-mode cursory` 使用 [Cursory](https://github.com/Vinyzu/cursory) 根据真人记录生成带时间戳的轨迹，由 Playwright 在当前视口内执行。独立桌面浏览器脚本也支持这两种模式，它的默认值是 `--pointer-mode direct`。
- The desktop agent moves to its target before clicking, hovering, or focusing a text field. `--pointer-mode continuous` (default) follows an eased straight line. `--pointer-mode cursory` uses [Cursory](https://github.com/Vinyzu/cursory) to generate a timed path based on recorded human motion, which Playwright executes within the current viewport. The standalone desktop browser runner also supports both modes and defaults to `--pointer-mode direct`.
- 桌面 Agent 在当前指针位置发送先加速、后减速的滚轮事件。每段的速度有小幅变化，长距离滚动会分段并短暂停顿。双轴合成的滚轮输入速度上限是每秒 1,000 CSS 像素，每个轴单次最多请求 2,400 像素。接受的动作仍精确发送请求的总增量。独立桌面浏览器脚本每次发送单次滚轮事件，移动端通过触控滑动滚动。
- The desktop agent sends wheel events at the current pointer position, accelerating and easing to a stop. Speed varies between strokes, and longer scrolls include short pauses between strokes. Combined wheel input across both axes is capped at 1,000 CSS pixels per second, with up to 2,400 pixels per axis in one action. The deltas of an accepted action still sum to the requested distance. Scripted desktop runs send a single wheel event per scroll, and mobile runs use touch swipes.
- 独立浏览器脚本支持 `--text-input insert`（默认）与 `--text-input sequential`。Agent 聚焦输入框后按 450–700 毫秒的反应时间开始键盘操作，然后逐键输入。桌面键间隔为 160–250 毫秒，移动端为 195–275 毫秒，词与词之间会稍作停顿。如果剩余运行时间短于输入计划，Agent 会在输入前记录拒绝。较长输入的单步时限按计划用时延长，仍受 `--run-timeout` 限制。
- The standalone browser runner supports `--text-input insert` (default) and `--text-input sequential`. The agent waits 450–700 milliseconds after focusing a field before using the keyboard, then types one character at a time. Key intervals are 160–250 milliseconds on desktop and 195–275 milliseconds on mobile, with a short extra pause between words. If the plan exceeds the remaining run time, the agent records a rejection before typing. Longer input gets a larger per-action budget based on the plan, subject to `--run-timeout`.

桌面和移动端 Agent 都从新截图可用时开始为下一步计时。每步在 450–700 毫秒之间选一个最短反应时间，模型决策用时计入其中。只有未达到目标时才等待。`agent.jsonl` 的 `reaction_timing` 事件记录目标时长、截图到动作的实际间隔和补足的等待时间。

Desktop and mobile agents time each action from when its screenshot is available. The minimum reaction time is sampled between 450 and 700 milliseconds per action, counting model decision time toward it. The agent waits for any remaining time. The `reaction_timing` event in `agent.jsonl` records the target, elapsed time from observation to action, and added wait.

普通动作另有 750–1,100 毫秒的思考目标。视口中约有 48 个词以上的可见正文时，Agent 会为新内容安排更长的阅读停留，最长 10 秒。模型推理时间计入停留，已读的相同页面区域会复用阅读结果。浏览器只计算渲染后的正文量，模型仍根据截图决策。

Ordinary actions also have a thinking target of 750–1,100 milliseconds. When the viewport contains approximately 48 words of visible prose or more, the agent allows up to 10 seconds to read a new view. Model inference counts toward the dwell, and the agent reuses the dwell for the same visible content. The browser measures rendered text volume while the model still makes decisions from screenshots.

Agent 可从截图选定要读的段落、代码示例或表格。如果可见内容的中点偏离视口中央 30% 的区域，会先尝试一次 `center_reading`。桌面端把指针移到内容处并滚动鼠标滚轮，移动端用手指滑动。随后 Agent 根据新截图阅读，页面边界可能限制移动距离。

The agent can pick the paragraph, code example, or table it wants to read from the screenshot. If the midpoint of the visible content falls outside the middle 30% of the viewport, it can first try `center_reading` once. On desktop it moves the pointer to the content and scrolls the mouse wheel. On mobile it swipes. The agent then reads from the fresh screenshot. Page boundaries can limit the movement.

如果视口底部的点击或轻点改变了当前页面的画面，Agent 在原处再次操作前会先把下方区域移到视口中部。这能让它看清刚展开但被视口裁切的内容。`agent.jsonl` 的 `action_adjusted` 事件记录原动作和实际采用的动作。

If a click or tap near the bottom of the viewport changes the view on the same page, the agent brings the area below it toward the middle before activating the same point again. This can reveal newly expanded content cut off by the viewport. The `action_adjusted` event in `agent.jsonl` records the proposed action and the action used instead.

桌面指针通常停在原位。在较长的阅读停顿或显式等待里，指针偶尔在同一页面元素内随机往返约 6–22 个 CSS 像素。若阅读时的移动改变了画面，Agent 会先获取新截图再决策。`attention_timing` 记录思考或阅读用时，`--record-input` 会把阅读时的指针移动标为 `phase: idle`。移动端的阅读停顿保持静止。

The desktop pointer usually stays put. During longer reading pauses or explicit waits, it occasionally moves about 6–22 CSS pixels within the same page element and returns. If movement during a reading pause changes the view, the agent takes a fresh screenshot before deciding again. `attention_timing` records the thinking or reading dwell, and `--record-input` labels pointer movement during reading as `phase: idle`. Mobile reading pauses stay stationary.

启动本地视觉模型后，可运行以下 Waymark 任务。基准测试独立核对结果，并保存 `inputs.jsonl` 和带指针的视频以便检查轨迹。

With the local vision model running, use the following Waymark task. The benchmark independently checks the result and saves `inputs.jsonl` and a video with the pointer for trajectory inspection.

```sh
uv run --locked python -m tools.explorer_benchmark --group mock --case parking --repeats 1 --pointer-mode cursory --record-input
```

### 实跑视频与输入录制 / Live video and input recording

为 `python -m agent`、`python -m browser` 或 `python -m tools.explorer_benchmark` 加上 `--record-input`，即可在浏览器运行期间同步录制。无头和可见窗口都可以使用。录制依赖 Playwright 的视频组件，缺失时运行 `uv run --locked playwright install ffmpeg`。

Add `--record-input` to `python -m agent`, `python -m browser`, or `python -m tools.explorer_benchmark` to capture the live browser run. The recorder works in both headless and headed Chromium. If Playwright's video runtime is missing, run `uv run --locked playwright install ffmpeg`.

桌面录像显示鼠标箭头，移动录像用圆环标记手指触点，抬指后淡出。

Desktop video shows a mouse arrow. Mobile video shows a ring at the touch contact, which fades after release.

| 文件 / File | 内容 / Contents |
| --- | --- |
| `videos/*.webm` | Playwright 编码的页面视频。指针随浏览器产生的实际指针事件在录制时更新。 Playwright page video. The pointer overlay updates live from browser-generated pointer events. |
| `agent.jsonl`、`actions.jsonl` | 模型选中的决策和浏览器执行结果，包含所选输入文字和虚拟键。 Model decisions and executed actions, including chosen text and virtual keys. |
| `inputs.jsonl` | 下发命令和浏览器收到的指针、点击、滚轮、按键、文字插入及组合输入事件。 Dispatch commands and observed pointer, click, wheel, key, text input, and composition events. |
| `recording.json` | 录制状态、页面 ID 与视频轨道路径。 Recording status, page IDs, and video track paths. |

输入事件携带浏览器事件时间、页面与 frame ID，以及 frame 内 CSS 像素坐标。浏览器提供合并采样时，也会保存这些中间点。命令、浏览器动作和模型决定通过运行 ID、动作 ID 与决策 ID 关联。录制器独立采集 Chromium 实际收到的中间位置。视频按帧采样，验证细节时可查事件日志。模型截图会隐藏录制指针。采集范围是浏览器页面，包含在页面中收到的系统输入。

Input events carry browser event time, page and frame IDs, and frame-local CSS-pixel coordinates. Coalesced samples are preserved when Chromium supplies them. Commands, browser actions, and model decisions are linked by run, action, and decision IDs. The recorder independently captures intermediate positions received by Chromium. The event log preserves detail between video frames. Model screenshots hide the recording pointer. The capture covers browser pages, including native input delivered to them.

桌面指针有实际位置后，在停顿和同一页面窗口内导航时会保留其最后位置，直到收到新的输入或指针离开视口。

Once the recorder has observed a desktop pointer position, it retains that position during pauses and navigation in the same page window until new input arrives or the pointer leaves the viewport.

录制会保存实际输入的键和文字，请仅对可以保留此类输入的会话启用。

Recording stores actual keys and entered text. Enable it for sessions where those inputs can be retained.

### 时序分析与视频 / Temporal and video analysis

使用 [`TemporalAdapter`](models/temporal.py) 分析已有页面证据。至少两张带递增毫秒时间戳的帧可以走 OpenAI 或 OpenRouter 的图像模型。MP4 或 WebM 片段走 OpenRouter，所选模型及其路由须支持相应的原生视频输入和 JSON 输出。返回结果包含摘要、按时间排序的变化、实际模型 ID 和提供方报告的用量。帧分析的时间戳必须来自输入帧，视频中的时间戳是从片段开头估计的相对时间。

Use `TemporalAdapter` to analyze page evidence you have already captured. Two or more frames with increasing millisecond timestamps can go to an OpenAI or OpenRouter vision model. Use OpenRouter for an MP4 or WebM clip, with a model and route that support the video format and JSON output. Results include a summary, chronological changes, the resolved model ID, and usage reported by the provider. Frame-based results cite supplied timestamps. Video timestamps are estimates relative to the start of the clip.

```python
import os
from pathlib import Path

import httpx

from models.contracts import ImageInput, VideoInput
from models.responses import ResponsesProvider
from models.temporal import TemporalAdapter, TimedFrame


async def analyze_frames(before: Path, after: Path, after_ms: int):
    frames = (
        TimedFrame(0, ImageInput(before.read_bytes())),
        TimedFrame(after_ms, ImageInput(after.read_bytes())),
    )
    async with httpx.AsyncClient(timeout=60) as client:
        provider = ResponsesProvider("openai", client)
        model = TemporalAdapter(provider, os.environ["UX_VERSE_TIMELINE_MODEL"])
        return await model.analyze("Describe the feedback after the click.", frames)


async def analyze_recording(recording: Path):
    video = VideoInput(recording.read_bytes(), "video/webm")
    async with httpx.AsyncClient(timeout=90) as client:
        provider = ResponsesProvider("openrouter", client)
        model = TemporalAdapter(provider, os.environ["UX_VERSE_VIDEO_MODEL"])
        return await model.analyze("Describe the visible page transitions.", video)
```

模型接入层接收调用方提供的媒体。调用上述在线适配器时，截图、帧或视频会随请求发送到选定的模型服务。

The model layer accepts media supplied by the caller. When using the hosted adapters above, requests send screenshots, frames, or video to the selected model service.

## 运行产物 / Run outputs

默认写入 `runs/` 下的新目录。用 `--output` 可指定一个尚不存在的目录。

By default, each run writes to a new directory under `runs/`. Use `--output` to choose a directory that does not exist yet.

| 文件 / File | 内容 / Contents |
| --- | --- |
| `actions.jsonl` | 结构化操作、URL、耗时、结果、截图路径及浏览器错误事件。 Structured actions, URLs, durations, outcomes, screenshot paths, and browser errors. |
| `screenshots/` | 每次成功操作后的 1280 × 720 PNG。 A 1280 × 720 PNG after each successful action. |
| `trace.zip` | 用 Playwright Trace Viewer 查看浏览器轨迹。 Browser trace for the Playwright Trace Viewer. |
| `agent.jsonl` | Agent 运行的决策、模型请求、模型 ID、用量和停止原因，关联观测截图。 Explorer decisions, requests, model IDs, usage, and stop reasons linked to observation screenshots. |

### 关联运行事件 / Correlate run events

[`logs/`](logs/) 统一定义事件模型与 JSONL 读写。`RunEvents` 为同次运行的两份日志分配同一个 `run_id` 和跨文件连续的 `seq`，以 UTC 记录事件时间。`RunEvent` 校验来源、带时区的时间、版本和关联 ID。合并同一 `run_id` 的日志后按 `seq` 排序即可查看写入顺序。单独运行浏览器命令时，也会生成自己的运行 ID。

`logs/` owns the event models and JSONL I/O. `RunEvents` assigns a shared `run_id` and a sequence number `seq` that spans both files, and records timestamps in UTC. `RunEvent` validates the source, timezone-aware timestamp, schema version, and correlation IDs. Merge records with the same `run_id` and sort by `seq` to recover write order. Standalone browser runs get their own run ID.

`logs.read_log(path)` 支持带 `schema_version: 1` 的日志和早期未标版本的日志。早期事件保留已有字段和文件内顺序。新模块可以扩展事件类型和字段，读取时会保留这些附加字段。如果字段含义发生不兼容的变化，增加一个版本并保留对应读取规则。读取未知版本时会明确报错。

`logs.read_log(path)` reads logs with `schema_version: 1` and older unversioned logs. Legacy records retain their fields and order within each file. New modules can add event types and fields, which the reader preserves. Use a new version and retain the appropriate reader when a field changes incompatibly. The reader reports unsupported versions explicitly.

| 字段 / Field | 如何关联 / How to join |
| --- | --- |
| `decision_id` | 同一次决策的模型请求、重试和结果共享该 ID。 Model requests, retries, and the result for one decision share this ID. |
| `action_id` | 将已接受的 Agent 动作与 Worker 记录的实际执行关联起来。浏览器诊断在动作执行窗口内也会带上该 ID。 Links an accepted Agent action to its browser execution. Browser diagnostics within that action window also carry this ID. |
| `observation_id` | `model_requested` 引用模型看到的观测。浏览器动作的 `before_observation_id` 指向上一张截图，成功动作的 `observation` 含新 ID 和截图路径。 `model_requested` references the model input. A browser action's `before_observation_id` points to the previous screenshot, and a successful action carries the new ID and screenshot path inside `observation`. |

停止决定和超预算的动作提议仍记录为模型决定，浏览器执行记录只对应已派发的动作。初始导航是浏览器动作，第一张截图从这里产生。

Stop decisions and over-budget proposals are recorded as model decisions. Browser execution records correspond to dispatched actions. Initial navigation is a browser action and produces the first screenshot.

## 验证 / Verify

Waymark 测试站提供响应式路线目录、详情、收藏、FAQ 和模拟联系表单。可以比较正常版与预置问题版，启动命令和复现表见 [`mock/README.md`](mock/README.md)。

The Waymark test site includes a responsive route catalog, detail pages, favorites, FAQ, and a simulated contact form. Compare the baseline and seeded variants using the startup command and reproduction table in `mock/README.md`.

测试覆盖本地浏览器运行、Agent 决策循环、在线适配器请求格式、视频与多帧响应校验、错误分类和证据保存。模型服务用模拟 HTTP 响应验证。

Tests cover local browser runs, the agent loop, hosted adapter payloads, video and frame response validation, error classification, and evidence capture. Provider tests use mocked HTTP responses.

```sh
uv run --locked python -m unittest discover -s tests -v
```

[设计文档 / Design document](docs/design.md)
