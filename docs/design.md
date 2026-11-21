# UX-verse

[简体中文](#zh-cn) · [English](#en)

<a id="zh-cn"></a>

## 简体中文

**Multi-Agent Visual Experience & Usability Evaluation**

**项目构思文档 · Project Concept Document**

版本：v0.1 — Concept Draft  
日期：2026 年 11 月 20 日  
状态：概念设计 / MVP 规划

---

## 1. 项目概述

### 1.1 核心理念

UX-verse 是一个基于多 Agent 协作的 Web 用户体验与视觉设计评估系统。

系统通过模拟具有不同目标、行为习惯、网页使用经验和审美偏好的虚拟访客，自主浏览目标网站，记录其探索路径、交互行为、操作预期和模拟体验反馈，最终生成一份包含定量指标、视觉审美评价、交互问题和改进建议的综合报告。

不同于传统 Web Testing 工具，UX-verse 不仅关注网站功能是否正常，还尝试分析：

- 一个首次访问者会如何探索网站？
- 用户能否自然地发现网站的主要功能？
- 网页的视觉元素会让用户形成怎样的操作预期？
- 实际交互是否符合这些预期？
- 页面在构图、排版、色彩和视觉层级上表现如何？
- 不同类型的模拟用户是否会对相同设计产生不同评价？
- 美学表达与交互易用性之间是否存在冲突？

**核心目标：通过多种模拟用户的自主探索，发现传统功能测试难以识别的视觉、认知与交互问题。**

### 1.2 项目定位

项目涉及四个主要技术领域：

1. AI Agent Engineering：自主决策、工具调用、状态管理和多 Agent 协作。
2. Human-Computer Interaction（HCI）：用户行为、可用性、交互预期及体验分析。
3. Computational Aesthetics：计算机视觉、主观审美建模和视觉设计评价。
4. Data Science：实验设计、评价指标、结果聚合和统计分析。

UX-verse 首先是一个用于展示工程与研究能力的个人开源项目，不以短期商业化为主要目标。

**开发周期：** 初期 1–2 周完成可运行 MVP。

**主要用途：** SWE、AI Agent Engineer、ML Engineer 等实习申请中的技术项目与作品展示。

---

## 2. 市场现状与差异化

### 2.1 已有相关产品与研究

目前已有多种产品或研究涉及自动化用户体验测试：

| 产品 / 项目             | 主要能力                                          |
| ----------------------- | ------------------------------------------------- |
| Versive                 | AI Persona 自动浏览网站、录制操作、生成可用性报告 |
| Uxia                    | AI 模拟用户测试、任务执行、问题与评分报告         |
| UXAgent                 | 研究型模拟用户、自动浏览及行为反馈                |
| UXCascade               | 多模拟用户轨迹聚合与设计问题分析                  |
| Momentic / mabl         | AI 自动化软件测试、Bug 检测及回归测试             |
| Maze                    | 基于真实参与者的 UX 测试和行为分析                |
| Browser Use / Stagehand | 基于 LLM 的浏览器操作与自动化框架                 |

因此，单纯实现“输入网址 → Agent 浏览 → 生成报告”并不具有足够的差异化。

### 2.2 UX-verse 的主要差异化方向

**A. Vision-Constrained Exploration（视觉约束探索）**

模拟访客不应默认拥有完整 DOM 信息，因为真实用户只能看到当前界面呈现的内容。

系统可以设置两种探索模式：

- Vision-Constrained：根据当前截图及视觉可见信息进行决策。
- DOM-Aware：允许读取页面结构与可交互元素。

通过对照实验，研究两种感知策略对交互问题发现率、任务完成率和探索效率的影响。

**B. Expectation Gap Detection（交互预期落差检测）**

Agent 在操作前预测结果，在操作后观察实际状态：

1. 观察当前页面。
2. 预测某个操作的预期结果。
3. 执行浏览器操作。
4. 记录实际结果。
5. 比较预期与实际状态。
6. 判断是否存在潜在交互阻力。

预期不一致不直接等于设计缺陷，而是一个需要进一步验证的 UX 问题候选。

**C. Multi-Perspective Evaluation（多视角评价）**

不同模拟访客可能对同一个设计产生截然不同的感受。

例如，设计敏感型 Agent 可能欣赏隐藏式导航带来的极简美感，而任务导向型 Agent 可能因此无法迅速找到目标内容。

系统应保留这些分歧，而不是简单平均所有评价。

**D. Evidence-Based Reporting（证据驱动评价）**

所有关键问题应关联：

- 浏览器截图或录像。
- 对应页面与操作步骤。
- 操作前的预期。
- 操作后的实际状态。
- 相关 Agent 的模拟反馈。
- 可复现性与评价置信度。

系统应尽可能避免脱离证据的泛泛评价。

---

## 3. 多 Agent 用户模拟系统

### 3.1 整体设计

采用 **User Simulation Pool + Central Evaluator** 架构。

一个中央 Orchestrator 创建不同的模拟用户，分别分配目标、行为参数和浏览环境。

各 Agent 在独立浏览器会话中探索网站，生成结构化行为记录。

测试完成后，独立评价模块汇总路径、问题、审美评价与不同 Agent 之间的差异。

### 3.2 初始 Persona

MVP 建议使用四类：

| Persona                  | 主要目的     | 行为特征                             |
| ------------------------ | ------------ | ------------------------------------ |
| Casual Explorer          | 自由浏览     | 根据兴趣探索，不追求特定任务         |
| Goal-Oriented User       | 完成指定目标 | 优先寻找目标内容，关注效率           |
| Design Enthusiast        | 观察视觉设计 | 关注排版、构图、图像与页面氛围       |
| First-Time / Novice User | 初次访问网站 | 依赖明显的视觉提示，容易遇到导航困难 |

后续可以扩展：

- Impatient Visitor：低耐心，失败后倾向退出。
- Experienced User：熟悉复杂 Web 交互。
- Mobile-First User：主要使用移动端视口。
- Accessibility-Focused User：使用明确的无障碍任务和交互条件。

### 3.3 行为参数化

不通过简单描述“低智商”“高智商”模拟不同用户，而是定义可测量的行为参数。

核心参数包括：

| 参数                 | 含义                     |
| -------------------- | ------------------------ |
| Patience             | 连续失败后的容忍程度     |
| Web Familiarity      | 对网页交互模式的熟悉程度 |
| Exploration Tendency | 探索未知内容的倾向       |
| Goal Priority        | 完成指定任务的优先程度   |
| Max Steps            | 最大浏览操作次数         |
| Device / Viewport    | 浏览设备和屏幕尺寸       |
| Perception Mode      | 截图模式或结构化页面模式 |
| Starting Point       | 主页或指定深层页面       |

这些参数直接影响 Agent 的决策策略和退出条件。

需要明确：Persona 是模拟实验条件，不等于真实人类的人格、认知能力或人口群体代表。

### 3.4 自主探索循环

每个 Agent 持续执行：

**Observe → Interpret → Predict → Act → Verify → Reflect**

- Observe：读取当前截图和允许的环境信息。
- Interpret：理解页面内容与当前目标。
- Predict：预测候选操作可能产生的结果。
- Act：执行点击、滚动、Hover、返回等操作。
- Verify：读取新的页面状态并比较操作结果。
- Reflect：更新探索历史、模拟评价和问题记录。

直到完成目标、主动退出、达到操作限制或触发异常终止。

---

## 4. 视觉设计与用户体验评价

### 4.1 评价体系

系统不应仅生成一个不透明的综合 UX Score。

建议区分三个主要维度。

**I. Visual Craft — 视觉设计质量**

评价页面的视觉组织与呈现：

- Visual Hierarchy：视觉层级与信息焦点。
- Composition & Balance：构图、平衡和留白。
- Typography：排版、字体层级与可读性。
- Color & Contrast：色彩关系与对比度。
- Visual Consistency：跨页面的视觉一致性。
- Image Presentation：图片裁切、尺寸、排列与展示效果。

部分指标可以通过 DOM、CSS 和确定性算法验证，其他维度由视觉模型结合截图进行评价。

**II. Aesthetic Experience — 主观审美体验**

评价设计可能带来的主观视觉感受：

- Aesthetic Appeal：视觉吸引力。
- Originality：设计个性与独特性。
- Emotional Tone：情绪、氛围和视觉表达。
- Immersion：内容呈现的沉浸程度。
- Identity Fit：设计与网站定位的一致性。
- Visual Memorability：视觉元素的潜在辨识度。

这些指标属于模型估计的主观评价，不应宣称为真实用户感受。

原创性需要参考对象，记忆度最好通过专门实验验证。无法有效判断时应标注 N/A，而不是强制赋分。

**III. Interaction Experience — 交互体验**

评价网站的实际使用过程：

- Navigation Clarity：导航清晰度。
- Discoverability：交互入口的可发现性。
- Interaction Feedback：点击后的状态反馈。
- Exploration Flow：浏览路径的流畅程度。
- Recovery & Control：返回、撤销和错误恢复。
- Task Completion：目标任务的完成情况。
- Technical Reliability：可观测的页面错误和交互失败。

### 4.2 评分方法

采用固定评价 Rubric，每个维度输出分数、解释和证据。

综合维度分数可使用加权计算：

**Score = Σ(weight × dimension score)**

不过最终报告应优先显示 Visual Craft、Aesthetic Experience 和 Usability 三个独立维度。

不同维度之间不应被一个总分掩盖。

自由探索没有固定任务时，Task Completion 应标记为不适用，而不是零分。

### 4.3 Aesthetic–Usability Tension

重点研究网站视觉表达与交互易用性之间的潜在权衡。

例如：

> 大面积负空间增强了摄影作品的视觉表现，但也可能降低导航入口的可发现性。

系统应识别这类设计权衡，而不是把所有不符合传统设计规范的元素直接标记为问题。

---

## 5. 强化学习与自适应探索

### 5.1 初期不训练 RL 模型

MVP 采用 Reward-Guided Exploration（奖励引导探索），不进行真正的强化学习训练。

Agent 根据当前状态、探索历史和预设行为参数选择操作。

可以设计以下奖励：

**Reward = α × Novelty + β × Goal Progress + γ × Verified Findings − δ × Repetition − ε × Cost**

其中：

- Novelty：发现新页面或交互状态。
- Goal Progress：任务推进程度。
- Verified Findings：经过独立检查的有效问题。
- Repetition：重复操作或无进展。
- Cost：时间、Token 和浏览器调用消耗。

不能仅因为 Agent 生成更多负面评价就给予更高奖励，避免系统倾向于虚构问题。

### 5.2 Adaptive Agent Allocation

后期可以借鉴 Multi-Armed Bandit。

系统初期平均分配探索预算，之后根据不同 Persona 的覆盖率、有效问题发现率和成本，动态分配后续测试次数。

研究问题：

> 在固定浏览器操作与模型调用预算下，自适应探索是否比平均分配测试预算发现更多有效 UX 问题？

初期可以先使用简单的 Novelty-Based Scheduler。

真正的 Bandit 策略和强化学习训练作为后续扩展，而不是两周 MVP 的必要条件。

---

## 6. 技术架构

### 6.1 推荐形态

**Local-First Web Application**

系统在本地执行 Agent 和浏览器操作，通过 Web Dashboard 配置测试、观察状态并查看报告。

核心架构：

**Next.js Dashboard → FastAPI → Evaluation Orchestrator → Persona Agents → Playwright → Event / Evidence Store → Evaluation Engine → Interactive Report**

系统分为三个主要模块。

**A. Web UI**

负责输入 URL、配置测试参数、展示运行状态、查看历史测试和报告。

技术：Next.js、TypeScript、Tailwind CSS。

**B. Agent Engine**

负责创建模拟用户、管理运行状态、调用模型、执行浏览器操作和保存交互历史。

技术：Python、Pydantic、asyncio、Playwright。

**C. Evaluation & Report Engine**

负责整合不同 Agent 的问题记录，进行评分、去重、分歧分析与可视化。

技术：Python、SQLite、JSON、Next.js。

### 6.2 Agent Runtime

项目应拥有自己实现的轻量 Agent Runtime。

不将 Codex 或 Claude Code 作为核心执行引擎。

核心逻辑包括：

- Agent 决策循环。
- Persona 行为策略。
- 浏览器工具白名单。
- 运行状态与历史记录。
- 错误恢复和重试。
- 模型调用与成本统计。
- 结构化输出验证。

这种实现方式有利于控制模型可见信息、比较探索策略，并展示独立的 Agent Engineering 能力。

### 6.3 LLM Provider Layer

Agent Runtime 与模型提供商解耦。

模型负责视觉理解、行动选择、交互解释和审美评价，但不直接拥有任意执行权限。

建议支持：

| Provider                 | 计划                    |
| ------------------------ | ----------------------- |
| OpenAI API               | MVP 首批支持            |
| OpenRouter               | MVP 首批支持，允许 BYOK |
| Anthropic API            | 后期增加原生适配        |
| Ollama                   | 后期支持本地模型        |
| Codex / Claude Agent SDK | 非优先的实验性 Backend  |

可通过统一的 Model Adapter 接口接入不同模型。

### 6.4 Explorer 与 Evaluator 分离

建议区分两类模型角色。

**Explorer Model**

高频调用，负责观察页面、选择动作、预测结果和更新探索状态。

**Evaluator Model**

低频调用，负责视觉审美分析、问题验证、跨 Persona 比较及报告生成。

两者可以使用相同模型，也可以独立配置。

不同 Persona 的行为比较应优先固定底层模型，以排除模型能力差异；模型 Benchmark 则应固定 Persona 和测试任务。

### 6.5 浏览器执行与安全

Playwright 负责：

- 网页导航。
- 点击、滚动、Hover、等待。
- 截图。
- URL 与页面状态采集。
- Console Error 和网络错误记录。
- Trace 保存。

各 Agent 使用独立 BrowserContext。

初期限制：

- 每个 Agent 的最大操作次数。
- 单域名或明确允许的站点范围。
- 只读或低风险交互。
- 网络请求频率和运行时间。
- 不允许未经授权的购买、发信、删除数据等操作。
- 防止网页内容中的提示注入改变 Agent 的权限。
- 隔离浏览器对本地网络、凭据和文件的访问。

若后续开放公网测试，应进一步使用容器或其他可靠隔离机制，并对测试授权与资源访问进行限制。

---

## 7. 产品交付形式

### 7.1 Dashboard

主要功能：

1. 输入目标网站 URL。
2. 选择探索模式和 Persona。
3. 配置模型、设备、操作预算。
4. 启动 Evaluation。
5. 查看各 Agent 的执行状态。
6. 打开最终报告。

### 7.2 Interactive UX Report

报告是项目的主要展示成果。

建议包含：

**Overview**

- 测试网站、时间、模型与配置。
- Agent 数量、执行状态、操作总数。
- Visual Craft、Aesthetic Experience、Usability 评分。
- 潜在问题数量与验证状态。

**User Journey Map**

- 浏览过的页面与交互状态。
- 不同 Persona 的探索路径。
- 访问覆盖率与重复路径。
- 可点击的操作记录和截图。

**Visual Evaluation**

- 各维度设计评分。
- 页面截图。
- 视觉优点与不足。
- 不同 Persona 的审美评价差异。

**UX Issues**

- 问题描述与严重程度。
- 触发问题的 Persona。
- 预期与实际交互结果。
- 复现步骤和截图证据。
- 可能的改善方向。

**Cross-Persona Analysis**

- 不同测试条件的评价差异。
- 共同发现的问题。
- 特定 Persona 更容易遇到的问题。
- 审美与易用性的潜在冲突。

报告可以导出为 JSON 和独立 HTML 页面。

### 7.3 Open-Source Repository

GitHub 仓库包含：

- Agent Engine 源代码。
- Browser Adapter。
- Model Provider Adapter。
- 测试及评分逻辑。
- 示例配置。
- Benchmark 数据及脚本。
- README 和架构文档。
- 真实运行结果与演示素材。

核心 Agent Engine 应不依赖 Dashboard 独立运行，以便未来支持 CLI 和 CI/CD。

### 7.4 公开 Demo

本地运行完整系统，同时发布一个无需安装即可访问的只读示例报告。

未来可以扩展为公开 Web SaaS，但不作为最初的交付目标。

---

## 8. MVP 范围与开发计划

### 8.1 首版必须完成的功能

**P0 — Core MVP**

- 一个自主浏览器 Agent Loop。
- 4 种可配置 Persona。
- Playwright 点击、滚动、返回和截图。
- 截图驱动的视觉观察。
- 操作前预期与操作后结果记录。
- Agent 探索历史和结构化事件日志。
- 基础视觉美学与交互体验评分。
- 多 Agent 结果汇总。
- 可访问的 HTML/Web 报告。

**P1 — 优先扩展**

- Vision-Constrained 与 DOM-Aware 模式对比。
- 结果去重和问题聚类。
- Journey Coverage 可视化。
- Explorer / Evaluator 独立模型配置。
- 基础动态探索预算分配。

**P2 — 长期方向**

- 真正的 Multi-Armed Bandit。
- 大规模 Persona 模拟。
- 本地视觉模型。
- 基于真人评分的审美校准。
- 网站修改前后的对照分析。
- 云端并发浏览器服务。
- 自动生成或维护回归测试。

### 8.2 两周时间安排

两周 MVP 对应[项目总体开发路线](#roadmap-zh)的第 1–4 阶段。第 1–2 天搭建浏览器执行环境，第 3–5 天完成单 Agent 自主探索，第 6–8 天完成带证据的 UX 评价，第 9–14 天完成多 Agent 汇总、最小 Dashboard、测试和公开演示。

时间紧时，优先保证 Agent Engine、证据记录、评估结果和复现测试的可靠性，再压缩 Dashboard 的范围。

---

## 9. 测试与实验设计

### 9.1 初始测试对象

建议使用个人摄影网站作为首个测试对象。

原因包括：

- 拥有可实际运行的 Web 项目。
- 图片密集，适合视觉模型评价。
- 包含非传统页面布局和横向滚动。
- 可以自行修改网站并设计已知测试案例。
- 不依赖第三方测试授权。

另外准备一个布局较传统的测试网站，避免研究结果完全依赖单一设计风格。

### 9.2 Ground Truth Benchmark

在受控测试网站中植入 8–10 个已知 UX 问题：

- 导航入口不明显。
- 点击区域与视觉表现不一致。
- 无状态反馈。
- 错误或失效链接。
- 移动端元素遮挡。
- 难以返回上一层。
- 不清晰的交互结果。
- 重复或无效导航路径。

记录真实的预期行为与问题位置。

### 9.3 核心指标

| 指标                      | 目的                             |
| ------------------------- | -------------------------------- |
| Issue Recall              | 已知问题被发现的比例             |
| Issue Precision           | 提出的问题中经验证成立的比例     |
| Journey Coverage          | 探索覆盖的页面和交互状态         |
| Path Diversity            | 不同 Agent 路径的差异程度        |
| Task Success Rate         | 指定目标完成比例                 |
| Expectation Gap Precision | 预期落差中具有实际 UX 意义的比例 |
| Reproducibility           | 多次运行发现相同问题的稳定性     |
| Cost per Valid Issue      | 每发现一个有效问题的成本         |
| Latency / Token Usage     | 执行效率和推理消耗               |

问题发现率需要考虑 Agent 是否实际遇到相关交互。不同 Persona 的结果不能直接解释为真实用户群体的统计比例。

### 9.4 主要对照实验

**实验 A：Vision-Constrained vs DOM-Aware**

研究视觉信息限制是否影响 UX 问题检测能力。

**实验 B：Heterogeneous vs Homogeneous Personas**

比较多种 Persona 与重复运行同一种 Persona，在相同操作预算下的路径覆盖和有效问题发现数量。

**实验 C：Adaptive vs Uniform Exploration**

比较动态预算分配与平均预算分配的效率。

**实验 D：AI vs Human Evaluation**

如果条件允许，邀请少量真实参与者完成相同任务，并与模拟 Agent 的问题发现和视觉评价进行探索性比较。

建议首先完成 A、B，C、D 作为后续研究方向。

---

## 10. 局限性与研究风险

### 10.1 模拟用户不等于真实用户

LLM 生成的主观体验不能被称为真实人类感受。

系统应明确标注：

- AI-Simulated Feedback。
- Model-Estimated Aesthetic Score。
- Observed Browser Behavior。
- Verified Interaction Issue。

这四种信息的证据性质不同。

### 10.2 多 Agent 不必然意味着多样性

相同模型即使使用不同 Persona Prompt，也可能产生高度相似的行为与评价。

需要通过路径覆盖率、行为差异和独立问题发现数量验证多样化策略是否真正有效。

### 10.3 审美评价具有文化和个人偏好

不能将模型偏好直接等同于设计质量。

尤其不能自动惩罚：

- 极简或实验性布局。
- 大面积负空间。
- 非对称构图。
- 暗色调和低饱和度。
- 有意打破传统设计规范的表现方式。

评价应结合网站的设计目标和内容语境。

### 10.4 评分可能不稳定

相同网站在不同运行中可能得到不同分数。

应固定 Rubric、模型版本和测试条件，并记录运行间的波动。评分与真实用户体验之间的关系需要独立验证。

### 10.5 Agent 能力和 UX 问题可能混淆

Agent 无法完成操作，并不一定说明网站设计有问题。

它可能是模型感知失败、定位不准确或工具执行异常。

报告必须区分：

- Website Issue。
- Agent Limitation。
- Browser / Tool Failure。
- Unverified Finding。

---

<a id="roadmap-zh"></a>

## 11. 项目总体开发路线

这是初步计划。第 1–4 阶段构成约两周的 MVP，第 5–6 阶段留作后续研究与产品化。

### 阶段 1 · 浏览器基础（第 1–2 天）

建立可控制、可观察、可记录的浏览器执行环境。

**产出**为 Playwright Worker、页面截图和结构化操作日志。

### 阶段 2 · 自主探索（第 3–5 天）

接入视觉模型，实现单个 Agent 的 Observe → Decide → Act 循环。

**产出**为能根据页面截图自主探索网站的 Agent。

### 阶段 3 · UX 评价（第 6–8 天）

记录操作前的预期与操作后的反馈，加入基础视觉与审美评价、交互问题候选检测。

**产出**为结构化评价和附有截图及操作步骤的问题报告。

### 阶段 4 · 多 Agent 与报告（第 9–14 天）

运行不同 Persona，汇总路径、评价分歧和评分。完成最小 Dashboard、复现测试和至少一组基准对照，并整理 README 与演示结果。

**产出**为可本地运行和复现的 UX-verse MVP，以及可公开访问的只读示例报告。

### 阶段 5 · 人类交互启发（后续）

研究拟人化鼠标运动、基于视觉反馈的重规划，以及用小型 GUI Grounding Model 将操作意图定位到页面目标。

**产出**为 Human Interaction Controller 原型和对照实验。

### 阶段 6 · 进阶研究与产品化（长期）

研究基于 Bandit 的探索预算分配和基于真实用户行为的校准，扩充模型适配与基准测试，加入本地模型。若需要托管运行，再引入云端浏览器 Worker、任务队列、用户管理、报告分享和自动化测试集成。

**产出**为支持扩展实验的研究平台，以及按需求发展的托管产品。

---

## 12. 项目成功标准

对于初期个人项目，成功不意味着超过成熟 UX Testing 商业产品，而是交付一个能够独立运行、具有明确技术贡献、可复现实验结果的系统。

最低成功标准：

1. 4 个不同 Persona 能够在独立会话中自主探索同一网站。
2. 系统可以记录每个 Agent 的操作路径、截图、预期结果和实际结果。
3. 系统能输出有具体证据的 UX 问题和视觉审美评价。
4. 多 Agent 的结果可以汇总、去重和比较。
5. 至少完成一个有确定性 Baseline 的对照实验。
6. GitHub 仓库能复现系统运行，并提供公开 Demo 报告。

**最终的核心研究问题：**

_Can heterogeneous, vision-based browsing agents identify and explain visual and interaction friction in web interfaces more effectively than a single generic browser agent?_

即：

**具有不同目标、感知限制和行为策略的浏览器 Agent，能否比单一通用 Agent 更有效地识别和解释网站中的视觉与交互问题？**

---

## 13. 最终项目定义

**Name:** UX-verse

**Category:** Multi-Agent Systems / HCI / Computational Aesthetics

**Product:** Local-First AI UX Evaluation Web Application

**Core Stack:** Python, Playwright, FastAPI, Next.js, OpenAI / OpenRouter, SQLite

**Core Features:** Autonomous Browsing, Synthetic Personas, Vision-Based Evaluation, Expectation Gap Detection, Journey Analysis, Evidence-Based UX Reporting

**Primary Deliverables:** Open-Source Repository, Functional Local Web App, Interactive Demo Report, Reproducible Evaluation Results

**Primary Objective:** 构建一个具有独立 Agent Runtime、可验证 UX 评价能力和清晰实验设计的个人工程项目，展示 AI Agent Engineering、Web Automation、视觉感知和统计分析方面的综合技术能力。

**项目原则：**

UX-verse 不试图宣称 AI 可以替代真实用户研究，而是将多 Agent 模拟作为一种可扩展、可验证、可复现的辅助设计评估方法。

其价值不是制造更多评价，而是让网站设计者理解：**不同的观察者可能如何理解、探索和体验同一个界面，以及哪些设计决策值得进一步验证。**

---

<a id="en"></a>

## English

**Multi-Agent Visual Experience & Usability Evaluation**

**Project Concept Document**

Version v0.1 · Concept Draft  
November 20, 2026  
Status · Concept design and MVP planning

## 1. Project Overview

### 1.1 Core Idea

UX-verse is a multi-agent system for evaluating web user experience and visual design. Simulated visitors with different goals, browsing habits, levels of web experience, and aesthetic preferences explore a target website autonomously. The system records paths, actions, expectations, and simulated feedback, then produces a report with quantitative metrics, visual assessments, interaction findings, and suggestions for improvement.

Alongside basic functionality, UX-verse examines these questions.

- How does a first-time visitor explore the site?
- Can visitors discover the site's main features naturally?
- What do visual elements lead visitors to expect from an interaction?
- Does the actual behavior match those expectations?
- How effective are the composition, typography, color, and visual hierarchy?
- How do assessments differ across types of simulated visitors?
- Where do aesthetic expression and ease of use come into tension?

**Core goal** · Use autonomous exploration by a variety of simulated visitors to surface visual, cognitive, and interaction friction that functional testing can miss.

### 1.2 Project Positioning

The project combines four areas.

1. **AI Agent Engineering** covers autonomous decisions, tool calls, state management, and multi-agent coordination.
2. **Human–Computer Interaction (HCI)** covers user behavior, usability, expectations, and experience analysis.
3. **Computational Aesthetics** covers computer vision, subjective aesthetic modeling, and visual design evaluation.
4. **Data Science** covers experimental design, metrics, aggregation, and statistical analysis.

UX-verse is a personal open-source project for demonstrating engineering and research skills. Commercial development is a longer-term option. The initial target is a working MVP in one to two weeks. The project primarily serves as portfolio work for software engineering, AI agent engineering, and ML engineering internships.

## 2. Existing Work and Differentiation

### 2.1 Related Products and Research

| Product or project | Main capabilities |
| --- | --- |
| Versive | Automated AI personas, action recordings, and usability reports |
| Uxia | Simulated user tests, task execution, findings, and scores |
| UXAgent | Research-oriented simulated users, automated browsing, and behavioral feedback |
| UXCascade | Aggregation of simulated user trajectories and analysis of design issues |
| Momentic / mabl | AI-assisted software testing, bug detection, and regression testing |
| Maze | UX testing and behavioral analysis with real participants |
| Browser Use / Stagehand | LLM-based browser control and automation |

Automated browsing and report generation are established capabilities. The project differentiates itself through the evaluation methods below.

### 2.2 Differentiation

**A. Vision-Constrained Exploration**

Real visitors act on information presented in the interface. The system supports two conditions for studying how available information changes exploration.

- **Vision-Constrained** uses the current screenshot and visible information to make decisions.
- **DOM-Aware** gives the agent access to page structure and interactive elements.

Controlled comparisons evaluate issue detection, task completion, and exploration efficiency across the two conditions.

**B. Expectation Gap Detection**

1. Observe the current page.
2. Predict the result of a proposed action.
3. Execute the browser action.
4. Record the resulting state.
5. Compare the prediction with what happened.
6. Assess whether the gap indicates interaction friction.

A mismatch is a candidate finding that requires verification before it can be treated as a design defect.

**C. Multi-Perspective Evaluation**

A design-focused agent may appreciate the minimalism of hidden navigation, while a goal-oriented agent may struggle to find the target content. The report preserves individual assessments and highlights disagreements.

**D. Evidence-Based Reporting**

Tie each significant finding to a screenshot or recording, a page and action step, the pre-action expectation, the observed outcome, and the agent's simulated feedback. Record reproducibility and confidence so readers can evaluate each claim.

## 3. Multi-Agent User Simulation

### 3.1 System Design

The architecture uses a **User Simulation Pool + Central Evaluator**. An orchestrator initializes each simulated visitor with goals, behavioral parameters, and a browsing environment. Each agent explores in an independent session and emits structured behavioral records. A separate evaluator summarizes journeys, findings, aesthetic assessments, and differences across agents.

### 3.2 Initial Personas

| Persona | Goal | Behavior |
| --- | --- | --- |
| Casual Explorer | Browse freely | Follows interests without a fixed task |
| Goal-Oriented User | Complete a specified task | Prioritizes finding the target efficiently |
| Design Enthusiast | Observe the visual design | Pays attention to typography, composition, images, and atmosphere |
| First-Time / Novice User | Visit a site for the first time | Relies on visible cues and may encounter navigation difficulties |

Later personas can include an Impatient Visitor with a low tolerance for repeated failures, an Experienced User familiar with complex interactions, a Mobile-First User with a mobile viewport, and an Accessibility-Focused User with specified accessibility tasks and conditions.

### 3.3 Behavioral Parameters

Use measurable behavioral parameters to define the simulation conditions and exit rules.

| Parameter | Meaning |
| --- | --- |
| Patience | Tolerance for consecutive failures |
| Web Familiarity | Familiarity with web interaction patterns |
| Exploration Tendency | Willingness to explore unfamiliar content |
| Goal Priority | Priority assigned to the specified goal |
| Max Steps | Maximum number of browser actions |
| Device / Viewport | Device and viewport size |
| Perception Mode | Screenshot-based or structured page observation |
| Starting Point | Homepage or a specified deep link |

Personas are experimental conditions. Claims about actual personalities, cognitive abilities, and demographic groups require separate evidence.

### 3.4 Autonomous Exploration Loop

Each agent repeats **Observe → Interpret → Predict → Act → Verify → Reflect**.

- **Observe** collects the screenshot and permitted environment information.
- **Interpret** relates the current page to the agent's goal.
- **Predict** describes the likely result of a candidate action.
- **Act** performs a browser operation such as clicking, scrolling, hovering, or going back.
- **Verify** observes the new page state and checks the result.
- **Reflect** updates exploration history, simulated feedback, and candidate findings.

The loop ends when the agent completes its goal, chooses to exit, reaches its action limit, or encounters a terminating error.

## 4. Visual Design and UX Evaluation

### 4.1 Evaluation Dimensions

The report presents three dimensions independently and makes the basis for each score visible.

**I. Visual Craft** evaluates page organization and presentation.

- **Visual Hierarchy** covers the order and focus of information.
- **Composition & Balance** covers layout, balance, and negative space.
- **Typography** covers typesetting, type hierarchy, and readability.
- **Color & Contrast** covers color relationships and contrast.
- **Visual Consistency** covers consistency across pages.
- **Image Presentation** covers crops, sizing, and placement.

Some indicators can be verified with DOM or CSS inspection and deterministic checks. Visual models can evaluate other indicators using screenshots.

**II. Aesthetic Experience** estimates subjective responses to the design.

- **Aesthetic Appeal** captures perceived visual appeal.
- **Originality** captures distinctiveness and design personality.
- **Emotional Tone** captures mood and visual expression.
- **Immersion** captures the sense of engagement with the content.
- **Identity Fit** captures alignment with the site's purpose and identity.
- **Visual Memorability** captures potentially recognizable visual elements.

These assessments represent model estimates. Originality requires a reference, and a dedicated study is preferable for assessing memorability. Use N/A when the available evidence cannot support a score.

**III. Interaction Experience** evaluates the browsing journey.

- **Navigation Clarity** covers how clearly the site communicates navigation options.
- **Discoverability** covers how easily users can find interactive elements.
- **Interaction Feedback** covers the feedback after an action.
- **Exploration Flow** covers the continuity of the browsing experience.
- **Recovery & Control** covers going back, undoing actions, and recovering from errors.
- **Task Completion** covers whether the agent reached the specified goal.
- **Technical Reliability** covers observable errors and interaction failures.

### 4.2 Scoring

Use a fixed rubric to produce a score, explanation, and evidence for each dimension. A weighted aggregate can be computed as **Score = Σ(weight × dimension score)**. The report gives priority to the separate Visual Craft, Aesthetic Experience, and Usability results. Mark Task Completion as N/A for free exploration without a fixed task.

### 4.3 Tension Between Aesthetics and Usability

For example, generous negative space may help photographs stand out while making navigation harder to discover. Report such trade-offs in the context of the site's design goals. An unconventional layout warrants an issue only when the evidence supports one.

## 5. Reinforcement Learning and Adaptive Exploration

### 5.1 Reward-Guided Exploration in the MVP

The MVP uses reward-guided exploration. The agent chooses actions using the current state, exploration history, and preset behavioral parameters. Reinforcement learning training is a later extension.

**Reward = α × Novelty + β × Goal Progress + γ × Verified Findings − δ × Repetition − ε × Cost**

- **Novelty** rewards discovering new pages or interaction states.
- **Goal Progress** rewards progress toward the task.
- **Verified Findings** rewards findings that have passed an independent check.
- **Repetition** penalizes repeated actions and lack of progress.
- **Cost** accounts for time, tokens, and browser calls.

Reward verified findings to avoid incentivizing fabricated negative feedback.

### 5.2 Adaptive Agent Allocation

Begin with an even allocation of exploration budget. Later runs can adapt their allocation based on Persona coverage, verified issue discovery, and cost, drawing on multi-armed bandits. Use a simple novelty-based scheduler for early experiments. Bandit strategies and reinforcement learning training belong to later phases.

> Under equal browser action and model call budgets, does adaptive exploration discover more valid UX issues than uniform allocation?

## 6. Technical Architecture

### 6.1 Application Architecture

**Local-First Web Application**

Agents and browsers run locally. A web dashboard configures tests, shows run status, and opens reports.

**Next.js Dashboard → FastAPI → Evaluation Orchestrator → Persona Agents → Playwright → Event / Evidence Store → Evaluation Engine → Interactive Report**

| Module | Responsibilities | Technologies |
| --- | --- | --- |
| Web UI | Accept a target URL, configure tests, show progress, and display past runs and reports | Next.js, TypeScript, Tailwind CSS |
| Agent Engine | Create simulated visitors, manage run state, call models, execute browser operations, and save interaction history | Python, Pydantic, asyncio, Playwright |
| Evaluation & Report Engine | Aggregate findings, score and deduplicate them, analyze disagreements, and visualize results | Python, SQLite, JSON, Next.js |

### 6.2 Agent Runtime

Implement a lightweight runtime within the project. It owns the decision loop, Persona policies, allowlisted browser tools, state and history, error recovery and retries, model cost tracking, and structured-output validation. Owning this layer makes it possible to control what models can observe, compare exploration strategies, and demonstrate agent engineering. Codex and Claude Code can be explored as optional backends later.

### 6.3 LLM Provider Layer

Use a shared Model Adapter interface to decouple providers from the runtime. Models interpret visuals, select actions, explain interactions, and assess aesthetics. The runtime controls which actions can execute.

| Provider | Plan |
| --- | --- |
| OpenAI API | Initial MVP support |
| OpenRouter | Initial MVP support with bring-your-own-key access |
| Anthropic API | Native integration later |
| Ollama | Local model support later |
| Codex / Claude Agent SDK | Optional experimental backends |

### 6.4 Explorer and Evaluator Roles

The **Explorer Model** runs frequently. It observes pages, selects actions, predicts outcomes, and updates exploration state. The **Evaluator Model** runs less frequently. It assesses visual design, verifies findings, compares personas, and generates reports. The roles may share a model or be configured independently.

Hold the underlying model fixed when comparing personas. For model benchmarks, hold the Persona and task fixed.

### 6.5 Browser Execution and Safety

Playwright handles navigation, clicking, scrolling, hovering, waiting, screenshots, URL and state capture, console and network error capture, and trace recording. Give each agent an independent `BrowserContext`.

- Cap the number of actions per agent, request rate, and run time.
- Allow navigation only within a single domain or an explicitly approved set of sites.
- Limit actions to read-only or low-risk interactions. Purchases, messages, and data deletion require authorization.
- Keep browser permissions under runtime control when page content contains instructions.
- Isolate browser access to local networks, credentials, and files.

If hosted testing becomes publicly available, use containers or equivalent isolation and enforce authorization and resource limits.

## 7. Product Deliverables

### 7.1 Dashboard

1. Enter the target URL.
2. Select exploration modes and personas.
3. Configure the model, device, and action budget.
4. Start an evaluation.
5. View progress for each agent.
6. Open the resulting report.

### 7.2 Interactive UX Report

The report is the project's primary showcase.

| Section | Contents |
| --- | --- |
| Overview | Target site, run time, model and configuration, agent counts and status, total actions, separate dimension scores, and candidate issue counts and verification status |
| User Journey Map | Pages and interaction states visited, paths by Persona, coverage and repeated paths, and clickable action records and screenshots |
| Visual Evaluation | Rubric scores, screenshots, strengths and weaknesses, and differences in aesthetic assessments across personas |
| UX Issues | Issue description and severity, triggering Persona, expected and observed outcomes, reproduction steps, screenshot evidence, and possible improvements |
| Cross-Persona Analysis | Differences across conditions, shared findings, Persona-specific findings, and tensions between aesthetics and usability |

Support exports as JSON and standalone HTML.

### 7.3 Open-Source Repository

Include the agent engine, browser and model adapters, testing and scoring logic, sample configurations, benchmark data and scripts, README, architecture documentation, real run outputs, and demo material. Keep the engine runnable independently of the dashboard to support future CLI and CI/CD integrations.

### 7.4 Public Demo

Run the full system locally and publish a read-only example report that opens without installation. Public SaaS is a possible later extension.

## 8. MVP Scope and Development Plan

### 8.1 Initial Scope

**P0 · Core MVP**

- An autonomous browser agent loop and four configurable personas.
- Playwright clicks, scrolling, back navigation, and screenshots.
- Screenshot-driven observation.
- Expectations before actions and observed outcomes afterward.
- Exploration history and structured events.
- Basic visual and interaction assessment.
- Multi-agent result aggregation.
- An accessible HTML or web report.

**P1 · Priority Extensions**

- Compare Vision-Constrained and DOM-Aware modes.
- Deduplicate and cluster findings.
- Visualize journey coverage.
- Configure Explorer and Evaluator models independently.
- Introduce basic adaptive exploration budgets.

**P2 · Long-Term Directions**

- Multi-armed bandits.
- Large-scale Persona simulation.
- Local vision models.
- Aesthetic calibration against human ratings.
- Before-and-after comparisons for site changes.
- Concurrent cloud browser services.
- Automated generation or maintenance of regression tests.

### 8.2 Two-Week Schedule

The two-week MVP covers the first four phases in the [development roadmap](#roadmap-en). Days 1–2 establish browser execution, days 3–5 implement single-agent exploration, days 6–8 add evidence-based evaluation, and days 9–14 cover multi-agent reporting, a minimal dashboard, tests, and the public demo.

If time is limited, prioritize the reliability of the agent engine, evidence capture, evaluation outputs, and reproducibility checks, then reduce the scope of the dashboard.

## 9. Testing and Experimental Design

### 9.1 Initial Test Sites

Use the personal photography site as the first test target. It is a working project with image-heavy pages, unconventional layouts, and horizontal scrolling. The project owner can modify it and prepare known test cases independently. Add a more conventionally structured site to test whether findings generalize beyond one design style.

### 9.2 Ground Truth Benchmark

Seed eight to ten known UX issues in a controlled test site. Examples include hard-to-find navigation, click targets that differ from their visual bounds, missing feedback, broken links, mobile elements that obscure content, difficult return navigation, unclear outcomes, and redundant or ineffective navigation paths. Record the intended behavior and location for each known issue.

### 9.3 Core Metrics

| Metric | Meaning |
| --- | --- |
| Issue Recall | Fraction of known issues identified |
| Issue Precision | Fraction of reported issues independently verified |
| Journey Coverage | Pages and interaction states explored |
| Path Diversity | Degree to which agents take different paths |
| Task Success Rate | Fraction of specified tasks completed |
| Expectation Gap Precision | Fraction of mismatches that indicate meaningful UX friction |
| Reproducibility | Consistency of findings across repeated runs |
| Cost per Valid Issue | Cost of discovering one verified issue |
| Latency / Token Usage | Execution time and inference usage |

Account for whether each agent encountered the relevant interaction when interpreting discovery rates. Report differences across personas as results of the specified simulation conditions. Estimating proportions for real user groups requires separate data.

### 9.4 Controlled Experiments

| Experiment | Question |
| --- | --- |
| A · Vision-Constrained vs. DOM-Aware | How do visual information constraints affect UX issue detection? |
| B · Heterogeneous vs. Homogeneous Personas | Under equal action budgets, how do diverse personas and repeated runs of the same Persona compare on path coverage and verified issue discovery? |
| C · Adaptive vs. Uniform Exploration | How does adaptive budget allocation affect exploration efficiency? |
| D · AI vs. Human Evaluation | In a small exploratory study, how do simulated and human participants compare on issue discovery and visual evaluation for the same tasks? |

Prioritize A and B. Treat C and D as later research directions.

## 10. Limitations and Research Risks

### 10.1 Simulated Feedback and Human Experience

LLM-generated feedback describes a simulation. Claims about human experience require evidence from real users. Use explicit labels for the different types of evidence in the report.

- AI-Simulated Feedback.
- Model-Estimated Aesthetic Score.
- Observed Browser Behavior.
- Verified Interaction Issue.

### 10.2 Behavioral Diversity Across Agents

A shared model may produce similar choices and assessments across different Persona prompts. Evaluate diversity through path coverage, behavioral differences, and the number of distinct issues discovered.

### 10.3 Cultural and Individual Aesthetic Preferences

Model preferences can reflect cultural and individual biases. Assess aesthetics in light of the site's goals and content. Minimal or experimental layouts, generous negative space, asymmetry, dark and muted palettes, and deliberate departures from design conventions need contextual interpretation.

### 10.4 Score Stability

Scores may vary across runs on the same site. Fix the rubric, model version, and testing conditions, and track variation across repeated runs. Validate the relationship between model scores and human experience separately.

### 10.5 Distinguishing Agent Failures from UX Issues

An incomplete action may arise from a model perception error, inaccurate localization, or a browser tool failure. Label findings according to the evidence.

- Website Issue.
- Agent Limitation.
- Browser / Tool Failure.
- Unverified Finding.

<a id="roadmap-en"></a>

## 11. Development Roadmap

This roadmap is preliminary. Phases 1–4 cover the roughly two-week MVP. Phases 5–6 cover subsequent research and product development.

### Phase 1 · Browser Foundation (Days 1–2)

Build a controllable browser environment with observable, recordable execution.

**Deliverable** · A Playwright worker, page screenshots, and structured action logs.

### Phase 2 · Autonomous Explorer (Days 3–5)

Integrate a vision model and implement the single-agent Observe → Decide → Act loop.

**Deliverable** · An agent that can explore websites autonomously using screenshots.

### Phase 3 · UX Intelligence (Days 6–8)

Record expectations before actions and feedback afterward. Add basic visual and aesthetic assessment and detection of candidate interaction issues.

**Deliverable** · Structured assessments and issue reports linked to screenshots and action steps.

### Phase 4 · Multi-Agent & Reporting (Days 9–14)

Run different personas and aggregate paths, disagreements, and scores. Complete a minimal dashboard, reproducibility checks, and at least one benchmark comparison. Prepare the README and demo results.

**Deliverable** · A runnable and reproducible local UX-verse MVP and a public read-only example report.

### Phase 5 · Human-Inspired Interaction (Later)

Explore human-like pointer movement, replanning from visual feedback, and a small GUI grounding model that maps an action intent to a target in the interface.

**Deliverable** · A Human Interaction Controller prototype and controlled experiments.

### Phase 6 · Advanced Research and Product Development (Long Term)

Study bandit-based exploration budget allocation and calibration against real user behavior. Expand model adapters and benchmarks, and add local models. If demand calls for a hosted service, add cloud browser workers, a job queue, user management, report sharing, and automated test integrations.

**Deliverable** · An extensible research platform and a hosted product developed as demand warrants.

## 12. Project Success Criteria

For an initial personal project, success means delivering a standalone system with clear technical contributions and reproducible experimental results.

1. Four different personas can independently explore the same site in separate sessions.
2. Each agent's path, screenshots, expectations, and observed outcomes are recorded.
3. The system produces UX findings and visual assessments supported by concrete evidence.
4. Multi-agent results can be aggregated, deduplicated, and compared.
5. At least one controlled experiment includes a deterministic baseline.
6. The GitHub repository supports reproducible runs and links to a public demo report.

**Core research question**

_Can heterogeneous, vision-based browsing agents identify and explain visual and interaction friction in web interfaces more effectively than a single generic browser agent?_

## 13. Project Definition

| Item | Definition |
| --- | --- |
| Name | UX-verse |
| Category | Multi-Agent Systems / HCI / Computational Aesthetics |
| Product | Local-First AI UX Evaluation Web Application |
| Core Stack | Python, Playwright, FastAPI, Next.js, OpenAI / OpenRouter, SQLite |
| Core Features | Autonomous Browsing, Synthetic Personas, Vision-Based Evaluation, Expectation Gap Detection, Journey Analysis, Evidence-Based UX Reporting |
| Primary Deliverables | Open-Source Repository, Functional Local Web App, Interactive Demo Report, Reproducible Evaluation Results |

**Primary objective** · Build a system with an independent Agent Runtime, verifiable UX evaluation, and a clear experimental design. Demonstrate skills in agent engineering, web automation, visual perception, and statistical analysis.

**Project principle** · Use multi-agent simulation as a scalable, verifiable, and reproducible complement to human user research. Help designers understand how different observers may interpret, explore, and experience the same interface, and identify design decisions that warrant further testing.
