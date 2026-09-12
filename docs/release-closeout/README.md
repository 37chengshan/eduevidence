# EduEvidence 6.1 发布收尾

本目录记录本地确定性验证与实际前端验收，不代表真实模型研究已通过。完整提交目录为 `dist/eduevidence-submission/`，根目录即 `SKILL.md`；交付目录而非压缩包。

- [修复与范围](issues.md)
- [前端验收](frontend-acceptance.md)
- [验证记录与分发检查](verification.md)
- [当前演示说明](../demo.md)
- [企业客服来源核验](../demo-workplace-ai.md)

中英文 README 使用同一组实际截图与可再生成的 SVG。Logo 使用用户提供的原图，以小尺寸显示。`scripts/build_readme_diagrams.py` 从 `engine/workflows.py` 读取九阶段顺序，更新流程 SVG；截图来自本地 Studio 的公开案例。

仅重建源码对应的运行资源和演示投影。保留原有 `benchmarks/evidence-library.json` 修改、安装路径修改和本地研究目录。未推送、合并、远端部署或发起付费模型研究。

## 最终状态

Skill 与前端在记录的本机确定性及实际浏览器覆盖范围内合格；真实模型研究与企业试点仍未验证。Python 3.10/3.12 各 928 通过、1 个可选依赖检查跳过；浏览器 29 通过。详细边界见验证记录。
