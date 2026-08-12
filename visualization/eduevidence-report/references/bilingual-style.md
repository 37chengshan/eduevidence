# Bilingual Rendering Style

Chinese mode translates stable UI labels, section titles, methodology keys, flow labels and enumerations. It does not rewrite freeform research claims or evidence prose in the renderer.

Allowed to remain in English in Chinese mode: AI, RCT, DOI, Evidence ID, Claim ID, Source ID, and original paper titles. Original titles should be explicitly labeled `原文标题`.

If `result.zh.json` lacks a localized freeform field, preserve the source text and mark it as original text rather than silently generating a new translation.
