# 安装与调用

本Skill的公开源位于University-Skills仓库的skills/yusuf。配套模板、12组提示词和教学材料位于University-Agent仓库training/p2-20261022。将两个仓库放在同一父目录，保持它们的目录名称。

有Python时，可运行University-Skills/tools/install_local_skills.py，将manifest里的Skill安装到该父目录的.agents/skills。安装只操作此项目；已有不同版本时停止，不强制覆盖。运行器、依赖与模型的状态见仓库docs/LOCAL_RUNNER.md。

在能发现本地Skill的Agent中，使用以下写法：

- `【Yusuf】按这份指南和模板整理申报草稿，缺少团队材料的地方列出来。`
- `【Yusuf，帮我处理这份CSV】先复算统计，再画图，并保留原始数据点和计算文件。`
- `【Yusuf...】检查这份技术交底书，指出实施方案和效果证据还缺什么。`
- `【Yusuf帮我改论文】保留数字与引用，检查结论是否超出数据。`

不支持自动发现Skill的Agent，需要先由操作者明确让它读取skills/yusuf/SKILL.md，再提交上述任务。安装Skill不会给该Agent新增文件、网络或计算权限，缺少工具时应报告对应限制。

自动发现列表可能在会话开始时加载；新安装后若当前会话还看不到Skill，重新打开项目或新建会话。没有工具调用记录和文件输出时，不能把响应文字当作工作流已执行。
