# KnowledgeOS 0.3.0 升级说明

## 1. 两种并行的沉淀单元

本版保留完整项目单元，同时保留可独立复用的问题—机制单元。两者并行，
不是必须依次升级的等级，也不要求每个项目都拆出三条全局机制。

| 单元 | 职责 | 保存位置 |
|---|---|---|
| 项目单元 | 保留任务、真实方案、配置、评价、失败、决策和项目经验的完整上下文 | 原 `vault/projects/`；项目级 Learning 仍可放在 `vault/learning/` |
| 问题—机制单元 | 描述问题签名、干预、改变的变量、适用条件、反例、迁移方式 | 原 `vault/learning/` |

对于 `type: learning`，新增可选属性：

```yaml
type: learning
learning_kind: project  # 或 mechanism
aliases: []
projects:
  - "[[Project A]]"
  - "[[Project B]]"
derived_from:
  - "[[projects/Project A/solution-space#Mechanism]]"
source_refs:
  - source:stable-source-id
```

旧 Learning 缺少 `learning_kind` 时保留原样，不根据项目数量自动猜测。
`type: project` 和 `type: project-doc` 无需新增该字段。模板位于
`templates/project-learning.md` 和 `templates/mechanism-learning.md`；
模板是写作起点，不是已核验的知识，不能将占位内容直接视为正式结论。

不新增领域目录、数据库、常驻服务或第三套笔记分类。项目文档不因提炼
机制而被删薄；机制页不复制一遍项目方案。已有机制优先补强证据、收窄
边界、吸收反例，不为一次新阅读自动再建一份近义笔记。

## 2. 写入保护与定向更新

正式写入必须在规划前绑定目标及其哈希：

```bash
python3 tools/knowledgeos.py research init <run-id> \
  --project <project> --scope <scope> --target vault/projects/<project>/<note>.md
```

已有早期运行可在 INIT、EVIDENCE_READY 或 FACTS_READY 阶段执行：

```bash
python3 tools/knowledgeos.py research bind-target <run-id> <target.md>
```

绑定不可重新指向另一个文件或无声更新旧哈希。目标发生变化时，重新读取
并建立新计划，不覆盖并发修改。后续仍保留 Evidence、Coverage、Fact、Claim、
Mechanism、Draft 的门禁；哈希检查不是语义正确性的证明。

| origin | 写入规则 |
|---|---|
| 缺失或 human | 阻止生成式覆盖；保留人工所有权 |
| codex | 允许绑定后替换全文；也可只更新指定区域 |
| mixed | 必须明确指定已存在的具名管理区域，保留区域外字节 |
| 重复、未知或无法可靠解析 | 拒绝写入，而不是猜测为 codex |

混合笔记由人审阅后明确指定可更新范围。例如：

```markdown
人工开头保持不动。
<!-- KOS:managed:synthesis:start -->
这里是允许定向更新的综合部分。
<!-- KOS:managed:synthesis:end -->
人工尾注保持不动。
```

```bash
python3 tools/knowledgeos.py research init <run-id> \
  --project <project> --scope focused \
  --target vault/projects/<project>/<note>.md --region synthesis
```

该运行的 `draft.md` 只包含区域内的新内容。不能嵌套管理区域，也不能将
现有 mixed/human 文件批量改成 codex 来绕开保护。

小更新可缩小本次证据、Coverage Plan 和目标区域，不必重新研究整个项目。
它不提供跳过证据与语义核验的快速通道。锁只协调 KnowledgeOS 自己的写入者；
外部编辑器不参与锁协议，因此仍在落盘前复查目标版本。

## 3. 持久证据与可重建索引分开

```text
sources/research/<run-id>/   已验收证据包：必须保留与备份
.knowledgeos/runs/           工作运行与尚未验收的中间状态
.knowledgeos/*index*         可重建的检索、图谱、追踪投影
```

成功 finalize 会保存验收后的事实、断言、机制、核验文件、证据绑定与摘录、
草稿追踪、状态记录、目标绑定、最终正文和校验清单。清理索引不会再删除
这些验收记录。重新让模型研究一次不是恢复当年的证据链。

旧版本 COMMITTED 运行需要先迁移，不能先删除 `.knowledgeos/`：

```bash
python3 tools/knowledgeos.py research archive <old-run-id>          # 预览
python3 tools/knowledgeos.py research archive <old-run-id> --apply  # 显式保存
python3 tools/knowledgeos.py research rebuild-provenance
python3 tools/knowledgeos.py provenance
```

缺失、漂移、无法恢复最终正文的旧记录会被拒绝迁移，不编造证据。
`legacy-anchor-only` 只表示保存了旧式来源定位，不被升级成精确绑定核验。
`bound`/`mixed` 是存储结构标签，也不证明核验结论正确。

已有笔记和原始资料可继续阅读；没有对应验收包时，不声称精确追踪已经恢复。
`.pending-*` 表示中断的验收操作。应核对其中的 acceptance、最终文件和运行
状态，不能为了消除告警而直接清理。工具会区分“写入前阻止”和“正文已经
落盘但后续封存中断”。

原 `.gitignore` 对 `vault/`、`sources/` 和 `.knowledgeos/` 的保护保持不变。
公开 GitHub 仓库不是私有笔记与证据的备份；请单独备份这些目录。

## 4. claims.yaml 的显式导出

它仍是可选投影，不是手工维护的第二套事实源。部分区域更新不会自动覆写
整个项目的 Claim Ledger。需要导出时：

```bash
python3 tools/knowledgeos.py research export-claims <run-id>          # 预览
python3 tools/knowledgeos.py research export-claims <run-id> --apply
```

只接受当前、未漂移、完整 `solution-space.md` 的验收运行。无生成标识的
手工 ledger 会受到保护；过期 ledger 仍由 maintain 报告。

## 5. 检索、关系和质量检查

```bash
python3 tools/knowledgeos.py search "问题或机制"
python3 tools/knowledgeos.py graph
python3 tools/knowledgeos.py projects
python3 tools/knowledgeos.py trace "笔记别名#章节"
python3 tools/knowledgeos.py reuse
python3 tools/knowledgeos.py eval <suite.json>
python3 tools/knowledgeos.py lint
python3 tools/knowledgeos.py maintain
python3 tools/knowledgeos.py rebuild
```

别名参与检索与链接解析。图谱保留章节/块定位、来源行与链接上下文；重名
标题的分块标识包含标题层级和出现次序。标题重命名会改变自动分块标识，
需要跨改名稳定引用时使用显式 Obsidian block ID。带完整路径的错误链接不再
退回另一个目录的同名笔记。代码示例中的伪链接不作为真实关系。

向量分块先按笔记取最佳命中，再与 BM25 做排名融合；结果保留章节、片段和
命中说明。向量的模型、维度、内容或文件校验不一致时，报告原因并回退 BM25。
未安装可选 numpy/embedding provider 不影响纯 BM25。旧向量索引需 rebuild。

Frontmatter 解析器明确只支持顶层标量与扁平列表、常规引号和注释，不声称
支持全部 YAML。嵌套 YAML、复杂标签等不支持的形式会显式报告。

Project Home 的已知中英文标题变体按知识角色识别，不因把 `Overview`
写成 `Project Overview` 而产生重复工作。它是结构检查，不代替内容审阅。

`projects` 表示关联，`derived_from` 表示来源；不是实际复用的计数。
需要记录应用时，在项目的 `Applications` 或 `应用记录` 章节中解释：
采用哪条 Learning、如何适配、观察到什么、哪些仍未验证。`reuse` 只抽取
声明过的应用记录，不将它们包装成受控实验或成功率。

评测文件示例：

```json
{
  "top_k": 5,
  "cases": [
    {
      "id": "project-specific-question",
      "query": "实际会询问的问题",
      "expected_ids": ["projects/ProjectName/solution-space"],
      "required_terms": ["必须随结果保留的边界用语"]
    }
  ]
}
```

建议用项目事实、机制迁移、反例边界、当前与历史四类真实问题建立小型
人工标注集。召回和关键词保留不等于语义正确性；本版没有测量私有库的
实际知识密度、检索准确率或跨项目成功复用率。字数与完全重复段落检查仍
只作为 smoke test，不作为写作目标。

## 6. 测试与迁移边界

```bash
python3 -m unittest discover -s tests/knowledgeos -v
```

工具测试使用隔离临时 vault，公开 Golden 测试读取 showcase，而不是要求
存在作者的私有笔记。新增测试中的虚构证据与模拟 embedding 仅用于软件
契约，不是现实世界证据。

0.3.0 更新不重组目录、不批量改写旧笔记、不修改 source repositories，
也不自动编辑 `.obsidian/` 或 `.base` 文件。先保留原有知识，再逐步按实际
使用补充可选属性和受控更新区域。
