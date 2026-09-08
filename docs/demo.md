# EduEvidence 当前演示入口

公开目录包含两个有独立问题的人工文献案例。它们用于演示如何阅读证据和决策；不能用报告的存在证明模型已经执行研究或试点已经实施。

| 案例 | 输入 | 当前制品 |
|---|---|---|
| 编程学习 | `examples/ai-coding-assistant-evidence/result.json` | 12 条发现、8 个来源，教学领域；PILOT |
| 企业客服 | `examples/workplace-ai-assistant/result.json` | 4 条发现、3 个来源，组织政策领域；PILOT |

两个案例都区分任务表现与目标结果、直接与间接证据、已经提取的数值与未知值。客服案例的来源版本、数量口径和局限见 [核验说明](demo-workplace-ai.md)。旧教学案例保存在 `tests/fixtures/legacy-examples/`，不进入公开案例列表。

## 启动与生成

```bash
python3 scripts/dashboard_server.py --host 127.0.0.1 --port 8765
# 浏览器访问 http://127.0.0.1:8765/studio/
```

Studio 是只读观察台。通过研究总览打开案例，依次阅读概览、证据工作台、溯源图谱、运行记录、版本和报告。没有执行历史时应显示缺失说明，不能填充虚构成功阶段。

源码开发者修改报告共享样式后重新生成：

```bash
python3 scripts/build_report_variants.py --examples examples
python3 examples/workplace-ai-assistant/validate.py
```

五主题 HTML 位于各案例的 `reports-5themes/`，分别为 claude、academic、datalab、datalab-dark、presentation。报告支持中英和简报/全文切换，也可以下载后离线阅读。分发包附带预构建 Studio，启动不要求 Node。

演示时只展示实际文件中的证据、结论和边界。图谱流动表示连线方向，不表示后台研究正在运行。基准评测必须单独说明输入、模型、运行记录和样本数量；本演示未开展新的真实模型评测。

参见 [录屏步骤](demo-storyboard.md) 和 [发布收尾验收](release-closeout/README.md)。
