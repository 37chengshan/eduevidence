---
name: literature-review
description: "Executes multi-source academic and web retrieval across OpenAlex, Semantic Scholar, CrossRef, AIHot, AgentSearch, and user-configured providers (Tavily, Brave, SerpAPI)."
---
# Literature Review Skill

## 1. When to Use
Trigger after research intent is established to gather candidate empirical studies, peer-reviewed papers, and verified grey literature.

## 2. Multi-Channel Search Routing
1. **Zero-Config Academic Providers**:
   - OpenAlex: Search 250M+ scholarly works for peer-reviewed studies with DOIs.
   - Semantic Scholar: Graph-based citation and abstract retrieval.
   - CrossRef: Official DOI resolution and metadata extraction.
   - AIHot: Real-time AI research trends and technical reports.
   - AgentSearch: SciPhi open academic and vector search.
2. **Configured API Key Providers**:
   - Tavily, Brave Search, SerpAPI, Exa, Bocha.
3. **Fetch & Validation**:
   - Pass candidate URLs through retrieval/fetch.py and validate via retrieval/validate.py.
   - Strictly reject ungrounded snippet hallucinations.
