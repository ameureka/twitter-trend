# 8. 基于 Playwright 的端到端（E2E）测试框架与实践

端到端（E2E）测试是确保整个系统（前端、后端、数据库）协同工作正常的关键环节。本文档旨在为“Twitter 自动发布管理系统”建立一套基于 Playwright 的标准化 E2E 测试框架，详细说明如何使用 Trae AI 的 `mcp playwright` 工具集进行高效的自动化测试。

---

### 一、 为什么选择 Playwright 进行 E2E 测试？

Playwright 是由微软开发的新一代浏览器自动化工具，相比 Selenium 等传统工具，它具有以下显著优势：

*   **速度与可靠性**: Playwright 的自动等待机制（Auto-Waits）能智能地等待元素变为可操作状态，极大地减少了因时序问题导致的测试不稳定（flakiness）。
*   **跨浏览器**: 一套代码可以同时在 Chromium (Chrome, Edge), Firefox 和 WebKit (Safari) 上运行。
*   **强大的能力**: 支持网络拦截、模拟地理位置、设置时区、模拟移动设备等高级功能。
*   **与 Trae AI (mcp) 集成**: Trae AI 内置了对 Playwright 的封装，允许我们通过自然语言或简单的指令来执行复杂的浏览器操作，极大地降低了编写和执行测试的门槛。

### 二、 E2E 测试框架设计

我们的测试框架遵循“Arrange-Act-Assert” (AAA) 模式，并结合页面对象模型（Page Object Model, POM）的思想来组织测试代码，以提高可读性和可维护性。

#### 1. 测试环境准备

*   **启动应用**: 在执行任何测试之前，必须确保后端 API 服务和前端服务已经启动。这通常通过 `start_api.sh` 或类似的脚本完成。
*   **干净的数据库**: 为了保证测试的独立性和可重复性，每次运行完整的 E2E 测试套件前，都应该将数据库恢复到一个已知的初始状态（例如，通过加载一个预置的 `test_db.sqlite` 文件）。

#### 2. 测试脚本结构 (使用 `mcp playwright`)

我们将使用一系列 `mcp playwright` 命令来构成一个完整的测试用例。一个典型的测试用例脚本看起来像一个“剧本”，描述了用户的操作流程。

**核心 `mcp playwright` 命令:**

*   `playwright_navigate`: 打开指定的 URL。
*   `playwright_fill`: 在输入框中填写内容。
*   `playwright_click`: 点击一个按钮或链接。
*   `playwright_get_visible_text`: 获取页面上所有可见的文本，用于断言。
*   `playwright_screenshot`: 截取当前页面，用于调试和验证 UI。
*   `playwright_close`: 关闭浏览器，结束测试。

#### 3. 标准测试用例模板

以下是一个测试“创建新任务”功能的标准用例脚本模板：

```yaml
# 测试用例: 成功创建一个新的发布任务

# 1. Arrange (准备环境)
- server_name: mcp.config.usrlocalmcp.playwright
  tool_name: playwright_navigate
  args:
    url: "http://localhost:8080/#tasks" # 导航到任务页面 (前端界面)

# 2. Act (执行操作)
- server_name: mcp.config.usrlocalmcp.playwright
  tool_name: playwright_click
  args:
    selector: "#create-task-btn" # 点击“创建任务”按钮

- server_name: mcp.config.usrlocalmcp.playwright
  tool_name: playwright_fill
  args:
    selector: "#task-name-input"
    value: "E2E 测试任务"

- server_name: mcp.config.usrlocalmcp.playwright
  tool_name: playwright_fill
  args:
    selector: "#media-path-input"
    value: "/path/to/test/video.mp4"

- server_name: mcp.config.usrlocalmcp.playwright
  tool_name: playwright_click
  args:
    selector: "#submit-create-task-btn" # 提交表单

# 3. Assert (断言结果)
- server_name: mcp.config.usrlocalmcp.playwright
  tool_name: playwright_get_visible_text
  # 在此步骤后，我们需要检查返回的文本中是否包含 "E2E 测试任务"
  # 以及 "任务创建成功" 的提示信息。

- server_name: mcp.config.usrlocalmcp.playwright
  tool_name: playwright_screenshot
  args:
    name: "create_task_success_test"
    savePng: true

# 4. Teardown (清理)
- server_name: mcp.config.usrlocalmcp.playwright
  tool_name: playwright_close
```

### 三、 如何使用 Trae AI (mcp) 进行测试

Trae AI 的强大之处在于，你可以直接用自然语言描述测试场景，它会自动为你生成并执行上述的 `mcp` 指令序列。

#### 场景1: 快速冒烟测试

**你的指令:**
> “使用 playwright 帮我测试一下任务页面。打开任务页面，检查页面标题是否是‘任务管理’，然后看看任务列表是否至少有一条数据，最后截图并关闭浏览器。”

**Trae AI 的执行流程:**
1.  `playwright_navigate` 到 `http://localhost:8080/#tasks` (前端界面)。
2.  `playwright_get_visible_text` 获取页面文本。
3.  **内部逻辑**: 分析文本中是否包含“任务管理”。
4.  `playwright_evaluate` 执行 `document.querySelectorAll('.task-row').length` 来获取任务行数。
5.  **内部逻辑**: 判断行数是否 `>= 1`。
6.  `playwright_screenshot` 保存截图。
7.  `playwright_close` 关闭浏览器。
8.  向你报告测试结果：“测试通过，页面标题正确，任务列表非空。”

#### 场景2: 调试失败的测试

如果一个测试失败了，例如“创建任务后，列表中没有出现新任务”。

**你的指令:**
> “创建任务的测试失败了。帮我重新跑一遍，但在每次点击和填写的操作后都截一张图，并且把浏览器network的console log打印出来，看看 API 请求有没有报错。”

**Trae AI 的执行流程:**
1.  在每个 `playwright_click` 和 `playwright_fill` 之后自动插入一个 `playwright_screenshot` 命令。
2.  在测试流程的最后，调用 `playwright_console_logs` 并设置 `type: "error"`。
3.  将所有的截图和错误日志呈现给你，帮助你快速定位问题是出在前端逻辑还是后端 API。

### 四、 建立标准测试套件

为了系统化地进行测试，我们应该创建一系列的测试“剧本”文件（可以是 YAML 或 JSON 格式），每个文件代表一个功能模块的测试集。

**`tests/e2e/tasks.test.yaml`:**
*   测试用例1: 成功创建任务。
*   测试用例2: 创建重复任务时应失败并显示错误信息。
*   测试用例3: 测试筛选功能，输入“测试”关键字，应只显示包含“测试”的任务。
*   测试用例4: 测试删除功能。

**`tests/e2e/logs.test.yaml`:**
*   测试用例1: 切换日志标签页，检查内容是否正确更新。
*   测试用例2: 测试日志筛选功能。
*   测试用例3: 测试导出日志功能（可能需要检查下载的文件）。

通过这种方式，我们可以建立一个完整的 E2E 测试套件。当代码有任何变更时，都可以运行整个套件，以确保没有引入新的 bug（回归测试）。

### 五、 总结

结合 Trae AI 的 `mcp playwright` 工具，我们可以建立一个强大、灵活且易于使用的 E2E 测试框架。这个框架的核心优势在于：

*   **自然语言驱动**: 大大降低了编写测试用例的复杂性。
*   **标准化与可复用**: 通过测试“剧本”文件，沉淀和固化测试流程。
*   **强大的调试能力**: 能够轻松获取截图、控制台日志、网络请求等信息，快速定位问题。

将这套框架融入日常开发流程，将极大地提升项目的质量和开发效率。