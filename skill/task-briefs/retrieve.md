# Task Brief — stage: retrieve（角色：evidence-retriever）

## 目标
按 Frame 的 scope 与 inclusion criteria 检索支持证据与独立反方证据；只检索，不下结论。
Fetch/Validate 是 Retrieve 内部强制 gate（RULE 2：snippet ≠ 证据内容）。

## 输入
- frame.json（检索边界、纳排标准）

## 产出
- sources.jsonl：每行一个 Source Object（source_id/title/canonical_url/authority_level），
  经 retrieval/validate.py 校验；抓取内容存 fetch/（raw + clean + provenance + fallback_chain）。

## 规则
- 来源权威等级可验证（DOI/期刊/机构），禁止编造 canonical URL；检索记录真实来源。