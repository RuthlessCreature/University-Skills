# 本地运行器与模型适配

本入口把 Skill 文件、工具执行和模型接口分开。当前实现 Chat Completions 工具循环；DeepSeek 使用官方接口与显式模型名称，其他兼容服务需要自行提供配置并实际测试。MiniMax 依照工作区要求禁用，不参与回退。没有修改现有网页模型配置。

## 已有能力与未完成部分

本地工具可以读取明确登记的材料、核对文件指纹、计算 CSV 分组描述统计、在输出目录写入新草稿。工具不会覆盖已有文件，不执行模型给出的任意系统命令。每次模型请求、响应、工具执行和失败都保存事件；不保存鉴权头。

能力探测要求模型实际读取随机文本、通过summarize_csv计算随机CSV的计数和均值，再保存这些原值和结果。实际工具事件、文件内容与计算同时匹配才通过。一次探测通过仍不能证明四条科研流程全部可用。

正常任务按 task.json 的节点依次执行。每节点必须实际读取任务、提示词、输入及相关 Skill，保存实质产物，再保存检查点。检查点中的文件指纹与原文摘录要与实际材料一致。摘录一致只证明文本匹配，不证明科学论断正确。缺少材料进入 NEEDS_INPUT，节点之间不增加人工确认。

已实现检查点续跑入口：核对输入、Skill、SOP、配置、已完成节点与产物的 hash 后，在新的尝试子目录继续，保留失败文件。输入或配置改变时要求另建运行，避免将不同条件混成一次执行。该入口尚未完成真实模型故障恢复实测。

Word模板填写、分段合并、PDF和页面渲染、CSV数据图已接入运行器工具分派。桌面Codex已直接调用相同工具生成真实文件；这项验证没有Provider调用。节点检查点格式错误时，保留旧文件，向模型提供原节点要求和具体错误，只允许一次修正；真实模型是否能修好仍待实测。细节见[分节点规程](LOCAL_NODE_SOP.md)。

Grant第一组案例拆成九个节点，其中四步分别写正文与声明片段，最后由工具读取实际片段合并。Paper、Patent、Figure各有六步。十二组task.json均含节点目的、具体产物和必需工具。最终Word节点必须有实际导出、对应版本渲染和文件指纹；数据图节点必须有真实绘图事件及对应图件。不得将这些文件检查标为四路模型端到端已验收。

当前Word渲染依赖准备好的Python、python-docx、lxml、LibreOffice、Poppler和文档渲染脚本；数据图依赖ReportLab及Node/sharp。换电脑时先验证这些依赖，再进行模型能力探测。路径与版本记录在实际渲染日志里，不把当前Windows环境当成已验证的跨平台安装包。

## 本机配置

调用模型前可以独立检查任务文件，不需要Key，也不会访问网络：

```powershell
& $coursePython 'E:/20261024/University-Skills/tools/task_preflight.py' --task 'E:/20261024/University-Agent/training/p2-20261022/examples/grant/01-complete-teaching/task.json' --report 'E:/20261024/University-Agent/training/p2-20261022/evidence/grant-task-preparation-new.json'
```

报告检查文件可读性、大小、节点与Skill对应、模板指纹及别名冲突。READY_FOR_PROVIDER_PROBE只表示这些文件检查通过，数据是否足够和论断是否成立仍由材料登记、核验节点判断。正常任务运行也会在第一次模型请求前执行同项检查。

每步必须实际读取本节点skill_ids中的至少一个Skill。读取无关Skill不能通过检查。Python代码、SVG和Mermaid均只作为材料文本读取，不会因为读到文件就执行其中代码。续跑还核对运行器和工具代码hash；旧运行没有这项记录或代码已变动时，保留旧记录并新建运行。

示例配置在 examples/deepseek-local-adapter.json，不含密钥。模型名称为 deepseek-flash；需要其他服务时另建配置，分别指定服务商、模型、HTTPS 接口和密钥环境变量名称，不改 Skill 正文。将 Key 设置在本机进程环境中，不能写入任务、聊天或 Git。

先用准备好的 Python 运行能力探测：

```powershell
& $coursePython 'E:/20261024/University-Skills/tools/local_skill_runner.py' --config 'E:/20261024/University-Skills/examples/deepseek-local-adapter.json' --probe --output 'E:/20261024/University-Agent/training/p2-20261022/evidence/provider-probe-new'
```

其中 `$coursePython` 是 bundled Python 的绝对路径。输出目录必须不存在，以保留旧运行。没有 Key 时退出码为 2，run.json 标为 NOT_CONFIGURED，并记录未发生网络调用。HTTP 成功后还要检查真实工具往返，不能只看返回文本。

能力探测通过后，再运行具体案例：

```powershell
& $coursePython 'E:/20261024/University-Skills/tools/local_skill_runner.py' --config 'E:/20261024/University-Skills/examples/deepseek-local-adapter.json' --task 'E:/20261024/University-Agent/training/p2-20261022/examples/grant/01-complete-teaching/task.json' --output 'E:/20261024/University-Agent/training/p2-20261022/evidence/grant-model-run-new'
```

任务只会得到可审阅草稿。模型请求失败、截断、工具循环超限、摘录不匹配、产物不存在或指纹不符都会中止并保存错误。保持输入与配置不变时，可对原运行目录添加 `--resume` 继续；其执行证据必须显示已完成节点被校验和跳过，才能称为实测续跑。缺失材料补齐或模板改变后，应另建运行并保存版本关系。

## 接口依据与实测状态

- DeepSeek 官方工具调用文档：https://api-docs.deepseek.com/guides/tool_calls/
- DeepSeek Chat Completions 文档：https://api-docs.deepseek.com/api/create-chat-completion/
- 当前本机状态：未配置 DeepSeek Key，未发出模型请求。
- Codex CLI 0.124.0 已尝试默认模型及单次 gpt-5.4 参数，两次均被登录接口拒绝；与 Codex 桌面当前文件工具执行分别记录。

本地文件工具的测试使用真实临时文件，没有模拟模型服务。它们验证文件范围、禁止覆盖、输入变化检测、CSV 算术和配置拒绝，不能据此宣布模型接入成功。
