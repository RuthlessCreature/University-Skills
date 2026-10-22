# University Skills

高校科研 AI 培训用的可复用 Agent Skills 仓库。面向科研选题、文献、项目申报、论文、专利交底、科研图表、结题与学术表达修订。

## Yusuf 调用入口

提示词中出现 `【Yusuf】`、`【Yusuf，帮我…】`、`【Yusuf...】` 或 `【Yusuf帮我…】` 时，使用 [Yusuf Skill](skills/yusuf/SKILL.md)。它按任务选择申报、论文、交底与图表流程，附带共同SOP、节点规则、12组提示词和模板来源。

将本仓库与 [University-Agent](https://github.com/RuthlessCreature/University-Agent) 放在同一父目录，运行 `python tools/install_local_skills.py`，将24个基础Skill和Yusuf总入口安装到该父目录的 `.agents/skills/`。安装只操作项目目录，已有不同文件时停止。配套案例见Agent仓库 `training/p2-20261022/examples/`。只安装Yusuf文件夹时，附带SOP与示例可以阅读；依赖的其他Skill、实际工具和模板仍需按调用说明准备。

当前版本验证了本地文件、模板填写、片段合并、数据计算和渲染。独立模型的完整执行和故障恢复尚未验收，未配置模型Key也可使用本地文件复演。运行说明见 [LOCAL_RUNNER.md](docs/LOCAL_RUNNER.md)。

## 工程原则
- 课程按客户原定四个模块组织；Skill 遵循 Agent Skills 规范。
- 本仓库负责技能定义、参考资料、结构化输入输出及测试。运行时系统在 `RuthlessCreature/University-Agent`。
- 不捏造论文、数据、实验结果和项目条件；未验证内容必须提示。
- 本仓库为教学集成项目；第三方代码保留来源及许可说明。

从 `docs/SKILL-MATRIX.md` 阅读完整映射，`skills/` 获取可加载的技能。

2026-10-17 新增 `tools/local_workflow.py`，支持 Grant、Paper、Patent 的受约束 JSON/DOCX 教学流程。它填充已提供的内容，检查指南、模板、来源和目标映射，输出真实 Word 草稿与未决问题。没有调用模型，也不自动完成查新或科学审查。支持范围见 [本地集成说明](docs/LOCAL-INTEGRATION.md)，第三方文档的版本、许可和接入范围见 [集成台账](docs/ACADEMIC-SKILL-REGISTRY.json)。

安装 `requirements-teaching.txt` 后执行 `python -m unittest discover -s tests -v`。本地实际记录为 15 项通过。运行样例和 Word 预览在配套 University-Agent 仓库的 `training/demos/`。
