# 本地视觉模型 / Local vision model

## 选择与来源 / Selection and sources

本机使用 RTX 5070 Ti Laptop GPU（12,227 MiB 显存）。选择官方 [Qwen3-VL-8B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF) 的 Q4_K_M 主模型和 F16 视觉编码器，以便直接读取浏览器截图并生成坐标操作。权重共 6,186,814,624 字节，另需便携运行时及解压空间。

This machine has an RTX 5070 Ti Laptop GPU with 12,227 MiB of VRAM. The official [Qwen3-VL-8B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF) Q4_K_M language weights and F16 vision encoder were selected to read browser screenshots and generate coordinate actions. The weights total 6,186,814,624 bytes; the portable runtime and extraction require additional space.

模型固定到 Hugging Face revision `f982a07559d4a2f6c8744d840bf6fccab30eea96`。运行时来自官方 [llama.cpp b12613](https://github.com/ggml-org/llama.cpp/releases/tag/b12613) 的 Windows CUDA 13.5 x64 二进制和 CUDA DLL 包。下载脚本校验所有文件的大小及官方 SHA-256，并把来源清单保存在 `.cache/local-models/qwen3-vl-8b/manifest.json`。权重、运行时和测试日志均在 Git 忽略目录中。

The model is pinned to Hugging Face revision `f982a07559d4a2f6c8744d840bf6fccab30eea96`. The runtime uses the official [llama.cpp b12613](https://github.com/ggml-org/llama.cpp/releases/tag/b12613) Windows CUDA 13.5 x64 binaries and CUDA DLL package. The setup script checks sizes and official SHA-256 hashes, saving provenance to `.cache/local-models/qwen3-vl-8b/manifest.json`. Weights, runtime binaries, and run logs are Git-ignored.

## 下载与启动 / Download and start

在仓库根目录使用 PowerShell 执行。下载支持断点续传，大文件使用最多 8 个 HTTP 分段连接。便携运行时不修改系统驱动，也不需要安装 Ollama 或 PyTorch。

Run these commands in PowerShell from the repository root. Downloads support resuming; large files use up to eight HTTP range connections. The portable runtime does not modify system drivers or require Ollama or PyTorch.

```powershell
uv sync --locked
uv run --locked playwright install chromium
uv run --locked python tools/setup_local_model.py
powershell -ExecutionPolicy Bypass -File tools/start_local_model.ps1
```

模型服务监听 `http://127.0.0.1:8081`，使用单个 8192-token 上下文、GPU 卸载和 1024–2048 个图像 token。在另一个终端启动 mock：

The model server listens at `http://127.0.0.1:8081`, with one 8192-token context, GPU offload, and 1024–2048 image tokens. Start the mock site in another terminal:

```powershell
uv run --locked python -m http.server 8765 --bind 127.0.0.1 --directory mock
```

显存余量不足时，可以给启动脚本传入 `-GpuLayers 22` 等较低值。若推理较慢，可在 Agent CLI 中用 `--run-timeout 180 --model-timeout 45` 调整预算。

If free VRAM is limited, pass a lower value such as `-GpuLayers 22` to the startup script. For slower inference, adjust the Agent CLI budgets with `--run-timeout 180 --model-timeout 45`.

## 自主探索 / Autonomous exploration

`local` 提供方调用本机 `/v1/chat/completions`，不使用 OpenAI/OpenRouter API key。截图以图像输入发送至回环地址。使用 JSON Schema 约束动作，并由现有 `DecisionAdapter` 将 0–1000 坐标转换为截图像素；浏览器操作仍由真实模型逐步选择。

The `local` provider calls the local `/v1/chat/completions` endpoint without an OpenAI/OpenRouter API key. Screenshots are sent as image inputs to the loopback address. JSON Schema constrains decisions, and the existing `DecisionAdapter` converts 0–1000 coordinates to screenshot pixels. The real model chooses browser actions one step at a time.

```powershell
uv run --locked python -m agent http://127.0.0.1:8765/ `
  --provider local --base-url http://127.0.0.1:8081/v1 `
  --model qwen3-vl-8b-local --structured-output `
  --task "Starting at Waymark's homepage, use the route directory to find and open the route named exactly Fern Creek Loop. On its detail page, read the first sentence under Parking & access. As soon as that sentence is visible, stop and report where to park in your reason." `
  --persona "First-time visitor checking trailhead parking" `
  --max-steps 8 --max-output-tokens 512 --model-timeout 45
```

默认总运行预算仍为 90 秒。低速机器可能耗尽预算，应区分超时、模型主动放弃和真实任务完成。`completed` 只代表模型自报完成；需要结合最终截图核对目标页面与回答。一次任务不能证明模型的总体探索质量。

The overall runtime budget remains 90 seconds. Slower machines may exhaust it; distinguish timeouts, model abandonment, and actual task completion. `completed` is the model’s own claim, so verify the target page and answer against the final screenshot. A single task does not establish overall exploration quality.

运行产物位于 CLI 打印的 `runs/agent-*` 目录：`agent.jsonl` 保存模型决策与 token 用量，`actions.jsonl` 保存实际操作，`screenshots/` 保存每步截图，`trace.zip` 保存浏览器轨迹。结束后在两个服务终端使用 Ctrl+C，释放显存和端口；模型文件可复用。

Outputs are stored in the `runs/agent-*` directory printed by the CLI: `agent.jsonl` contains decisions and token usage, `actions.jsonl` contains executed actions, `screenshots/` contains step images, and `trace.zip` contains the browser trace. Stop both services with Ctrl+C to release VRAM and ports; downloaded files remain reusable.

## 2026-11-21 修复前实测 / Pre-fix tests on 2026-11-21

已实际下载并校验权重，在本机 GPU 启动模型，再由真实 `DecisionAdapter` 和 `BrowserWorker` 访问本地 mock。任务为从首页经路线目录打开 Fern Creek Loop，并读取 Parking & access 的第一句话。步数预算为 8；输入始终为当前页面截图、任务和操作历史，没有 DOM 文本或预先指定的点击坐标。

The weights were downloaded and verified, the model was started on the local GPU, and the real `DecisionAdapter` and `BrowserWorker` explored the local mock. The task was to open Fern Creek Loop via the directory and read the first sentence of Parking & access. The action budget was eight; inputs were the current screenshot, task, and action history, without DOM text or predetermined click coordinates.

| 运行 / Run | 状态 / Status | 操作 / Actions | 调用 / Calls | 耗时 / Elapsed | 输入 / Input tokens | 输出 / Output tokens |
| --- | --- | --- | --- | --- | --- | --- |
| `local-qwen3-vl-8b-20261121-01` | `step_limit` | 8 | 9 | 17.196 s | 16,272 | 543 |
| `local-qwen3-vl-8b-20261121-02` | `step_limit` | 8 | 9 | 17.348 s | 16,785 | 544 |

两轮均未完成任务。模型能点击 Browse all routes 进入目录，但之后反复点击搜索框并表示准备输入；执行器不支持键盘输入。首轮之后，已把现有动作限制明确加入决策提示，随后用完全相同的任务与预算复测一次，仍出现同样的重复点击。两轮均无无效 JSON 决策，最终截图停留在路线目录，没有打开目标详情或显示停车说明。

Neither run completed the task. The model clicked Browse all routes successfully, then repeatedly clicked the search input while proposing to type, although keyboard input is unavailable. After the first run, the existing action limitations were made explicit in the decision instructions, and the exact same task and budget were retried once. Repeated clicking persisted. Both runs had zero invalid JSON decisions, and final screenshots remained in the directory without opening the target detail or parking notes.

因此，该配置已验证可在本机进行截图推理并接入现有执行链，但此任务中的探索策略未通过验证。模型加载后，`nvidia-smi` 记录整张显卡总显存占用为 8,679 MiB（包含桌面等其他进程，不是模型独占值）。性能或策略改进需要另行验证；这里保留失败结果，不推断更多任务的成功率。

This configuration therefore demonstrates local screenshot inference and integration with the existing execution pipeline, but its exploration policy failed this task. After loading, `nvidia-smi` recorded 8,679 MiB total GPU memory use, including the desktop and other processes rather than model-only memory. Performance or policy improvements require further validation; these failures do not establish success rates on other tasks.

修复前的摘要、复测日志及最终截图随仓库保存在 `docs/evidence/`；完整运行目录保留在本地，均未覆盖：

Pre-fix summaries, the retest log, and the final screenshot are included in `docs/evidence/`. Full run directories remain local without overwriting either run:

- [首轮摘要 / First-run summary](evidence/local-qwen3-vl-8b-20261121-01/summary.json)
- [复测摘要 / Retest summary](evidence/local-qwen3-vl-8b-20261121-02/summary.json)
- [复测决策日志 / Retest decision log](evidence/local-qwen3-vl-8b-20261121-02/agent.jsonl)
- [复测最终截图 / Retest final screenshot](evidence/local-qwen3-vl-8b-20261121-02/screenshots/009.png)
第 02 轮完整轨迹保留在本地 `runs/local-qwen3-vl-8b-20261121-02/trace.zip`。 / The full trace for run 02 remains local at `runs/local-qwen3-vl-8b-20261121-02/trace.zip`.

## 输入修复与最终核验 / Text-entry repair and final verification

后续诊断确认，动作限制提示已正确送达模型，但仅改写提示未解决搜索框循环。已在浏览器动作协议、Explorer 决策协议、结构化输出和执行器中补齐坐标输入动作：`{"type":"type","x":288,"y":360,"text":"query"}`。模型自行选择输入框位置和查询内容；执行器点击该坐标、检查目标可编辑、全选替换并触发原生输入事件，不按回车或提交表单。坐标需在视口内，文本长度为 1–1000 字符。

Further diagnostics confirmed that capability instructions reached the model, but prompt rewrites alone did not fix the search-input loop. Coordinate-targeted text entry was added to the browser action protocol, Explorer decisions, structured output, and executor: `{"type":"type","x":288,"y":360,"text":"query"}`. The model chooses the target and query; the executor clicks the coordinates, checks editability, selects and replaces the contents, and triggers native input events without pressing Enter or submitting. Coordinates must be within the viewport, and text must contain 1–1000 characters.

执行器只检查目标是否可编辑，不向模型返回输入框或其他 DOM 文本。模型继续根据截图、URL、标题和动作历史做决定。结构化决策的 `text` 字段为必填，非输入动作填写空字符串，以满足严格 JSON Schema 要求；`reason` 调整为首先生成，并明确要求先打开与任务相关的可见标签再继续滚动。

The executor checks only target editability and returns no input or other DOM text to the model. Decisions still use screenshots, URL, title, and action history. The structured decision’s `text` field is required, using an empty string for non-typing actions to satisfy strict JSON Schema requirements. `reason` is generated first, with an explicit policy to open a task-relevant visible tab before scrolling past it.

所有迭代都使用相同任务、相同 8 步预算和同一个本地模型，未提供停车答案或预设点击坐标：

All iterations used the same task, eight-action budget, and local model, without supplying the parking answer or predetermined click coordinates:

| 运行 / Run | 修改 / Change | 模型报告 / Model report | 截图核验 / Screenshot review | 操作 / Actions | 调用 / Calls | 耗时 / Elapsed |
| --- | --- | --- | --- | --- | --- | --- |
| `…-03` | 仅向已聚焦字段输入 / Focus-only typing | `step_limit` | 失败：模型未先聚焦 / Failed: input was not focused | 8 | 9 | 17.206 s |
| `…-04` | 坐标定位后替换输入 / Coordinate-targeted replacement | `completed` | 通过 / Passed | 7 | 8 | 15.765 s |
| `…-05` | 严格 schema 字段 / Strict schema field | `completed` | 失败：未打开停车面板且编造回答 / Failed: parking panel unopened, answer fabricated | 7 | 8 | 15.449 s |
| `…-06` | 先描述再决策，优先可见标签 / Reason first, prioritize visible tabs | `completed` | 通过 / Passed | 5 | 6 | 13.772 s |

最终 `local-qwen3-vl-8b-20261121-06` 的真实路径为：Routes → 在搜索框输入 Fern Creek Loop → 打开搜索结果 → 滚动 300px → 点击 Parking & access → 报告第一句。最终 URL 指向 `route.html?id=fern-creek`，页面标题为 Fern Creek Loop，最终截图可读到 **“Parking is beside the picnic area.”**。这一轮输入 11,602 token、输出 541 token，无无效决策或浏览器动作失败。

The final run, `local-qwen3-vl-8b-20261121-06`, followed this real path: Routes → type Fern Creek Loop in the search input → open the result → scroll 300px → click Parking & access → report the first sentence. The final URL identifies `route.html?id=fern-creek`, the page title is Fern Creek Loop, and the final screenshot visibly reads **“Parking is beside the picnic area.”** This run used 11,602 input and 541 output tokens, with no invalid decisions or failed browser actions.

`summary.json` 将模型自报的 `reported_status` 与截图核验的 `task_success` 分开记录，并保存最终截图 SHA-256。误报的第 05 轮保留为失败样例；第 04、06 轮经截图核验通过。运行时的 `completed` 仍为模型自报，本次结果由最终截图另行核验，不能据此推断其他任务的稳定成功率。

`summary.json` separates the model’s `reported_status` from screenshot-reviewed `task_success`, and records the final screenshot SHA-256. Run 05 remains a preserved false-completion example; runs 04 and 06 passed visual review. Runtime `completed` remains a model claim. These results were separately verified against final screenshots and do not establish reliable success rates on other tasks.

- [最终运行摘要 / Final run summary](evidence/local-qwen3-vl-8b-20261121-06/summary.json)
- [最终决策日志 / Final decision log](evidence/local-qwen3-vl-8b-20261121-06/agent.jsonl)
- [最终操作日志 / Final action log](evidence/local-qwen3-vl-8b-20261121-06/actions.jsonl)
- [最终截图 / Final screenshot](evidence/local-qwen3-vl-8b-20261121-06/screenshots/006.png)
- [最终浏览器轨迹 / Final browser trace](evidence/local-qwen3-vl-8b-20261121-06/trace.zip)

上述最终运行证据已随源码归档到 `docs/evidence/`，可直接从仓库查看。模型权重、运行时和其他完整运行目录仍由 Git 忽略；下载脚本可重建本地推理环境。

The final run evidence above is archived alongside the source in `docs/evidence/` for inspection directly from the repository. Model weights, runtime binaries, and other full run directories remain Git-ignored; the setup script recreates the local inference environment.

新增回归测试验证文字替换、中文及引号按字面保留、不提交表单、不可编辑目标的失败证据、坐标换算和严格 schema 字段；全量 30 项测试通过。

Added regression tests verify text replacement, literal Unicode and quotes, no form submission, failure evidence for noneditable targets, coordinate conversion, and strict schema fields. All 30 project tests pass.
