# 任务路由

先加载共同的research-intake；其余按当前任务选择，不要一次读完24个Skill。各节点的准确输入、产物、必需工具与对应Skill，见示例task.json的node_contracts。

| 用户任务 | 主要Skill及顺序 | 材料与成果 |
| --- | --- | --- |
| Grant申报 | document-parsing、grant-template、grant-background、grant-research-content、grant-technical-route、citation-verification、claim-audit、academic-humanizer、grant-review | 指南、模板、研究设想与真实基础；要求映射、分段正文、路线、核验表、Word草稿 |
| Paper论文 | literature-discovery、literature-synthesis、data-analysis、paper-drafting、citation-verification、claim-audit、academic-humanizer、paper-review；返修用rebuttal | 原始数据、实际分析和原始文献；可复算方法与结果、引文定位、限制、可编辑工作稿 |
| Patent交底 | patent-search、patent-disclosure、diagram、claim-audit、academic-humanizer | 发明人材料、实际技术实现与高校交底模板；特征对照、实施例、附图、交底草稿与缺口 |
| Figure图表 | data-analysis、data-figure或diagram、claim-audit；机制草案可用nano-banana-figure | 数据图保存CSV与计算；流程图保存依赖；机制图逐条区分依据与假说，未接图像服务要明说 |
| 选题与方案 | topic-evaluation、literature-discovery、literature-synthesis、experiment-design | 具体问题、已有证据、研究条件；问题定义、证据矩阵、可检验假说与设计 |
| 结题 | research-closeout、claim-audit、academic-humanizer | 任务书、执行记录、成果与经费凭据；逐项对应和待补材料，不编证明或签核 |
| 表达修订 | academic-humanizer与可用Humanizer | 修改表达，保留事实、数字、限定与引文；缺乏依据的句子不能靠润色变成已证实事实 |

示例目录使用固定编号。`01-*`通常提供可起草的教学材料，其他组覆盖缺材料、无依据主张或研究假说；这是材料条件分类，不是模型已通过的证明。选择案例后先读PROMPT.md和input，再读task.json。
