# 本地教学执行器的真实支持范围

tools/local_workflow.py 是本项目原创的受约束文档流水线，调用 python-docx 生成实际 Word 文件。不是所列第三方开源科研 Agent 的脚本集成，也没有调用模型。

输入：JSON 材料、DOCX 模板，Grant另需独立JSON教学指南。输出：章节对应的DOCX草稿、要求表、映射、问题清单、来源账本、Mermaid路线和运行日志。支持 grant、paper、patent。未实现任意PDF/OCR、真实查新、自动科研设计或科学结论真伪识别。

状态定义：specified 指仅有指令；installed 指资源已定位；smoke-tested 指依赖最小测试；integrated 指范围明确的实际链路；demo-verified 指存在可重复演示记录。状态必须附范围，不能把一个简化适配器推及全部第三方能力。

Word最终导出关口要求人类审批记录且绑定输入、模板、指南哈希。缺失研究基础等blocking问题阻止final输出。草稿允许保留问题，明确为待审核状态。JSON审批记录由受信任操作者提供，目前没有身份认证服务器，不能用于生产级签名或正式科研审批。

依赖：Python 3.11+，python-docx。运行测试：python -m unittest discover -s tests -v。跨仓教学输入在 ../University-Agent/training/demos/。安装指令和文档执行是不同验收项。
