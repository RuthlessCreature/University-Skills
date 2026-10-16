# University Skills

高校科研 AI 培训用的可复用 Agent Skills 仓库。面向科研选题、文献、项目申报、论文、专利交底、科研图表、结题与学术表达修订。

## 工程原则
- 课程按客户原定四个模块组织；Skill 遵循 Agent Skills 规范。
- 本仓库负责技能定义、参考资料、结构化输入输出及测试。运行时系统在 `RuthlessCreature/University-Agent`。
- 不捏造论文、数据、实验结果和项目条件；未验证内容必须提示。
- 本仓库为教学集成项目；第三方代码保留来源及许可说明。

从 `docs/SKILL-MATRIX.md` 阅读完整映射，`skills/` 获取可加载的技能。

2026-10-17 新增 `tools/local_workflow.py`，支持 Grant、Paper、Patent 的受约束 JSON/DOCX 教学流程。它填充已提供的内容，检查指南、模板、来源和目标映射，输出真实 Word 草稿与未决问题。没有调用模型，也不自动完成查新或科学审查。支持范围见 [本地集成说明](docs/LOCAL-INTEGRATION.md)，第三方文档的版本、许可和接入范围见 [集成台账](docs/ACADEMIC-SKILL-REGISTRY.json)。

安装 `requirements-teaching.txt` 后执行 `python -m unittest discover -s tests -v`。本地实际记录为 15 项通过。运行样例和 Word 预览在配套 University-Agent 仓库的 `training/demos/`。
