---
name: ethics-review
description: "Evaluates trial designs, intervention protocols, and student data collection against Institutional Review Board (IRB) and educational research ethics standards."
---

# ethics-review — Research Ethics & IRB Compliance Sub-Skill

## When to Use
Triggered prior to finalizing any 12-week Quasi-Experimental / DID field trial design involving human student cohorts, classroom telemetry, or control group assignment.

## Ethical Audit Checklist
1. **Control Group Harm Prevention**: Ensures the control group is not deprived of essential pedagogical learning opportunities (recommends delayed crossover or active alternative pedagogies).
2. **Student Privacy & Telemetry Protection**: Verifies that LLM interaction prompts, code logs, and exam scores are pseudonymized and compliant with FERPA/GDPR educational data privacy.
3. **Informed Consent & Voluntary Participation**: Enforces opt-out mechanisms without academic penalty.
4. **Algorithmic Bias & Equity Check**: Audits whether AI tools introduce unfair grading or accessibility barriers for underrepresented student groups.

## Output Schema
```json
{
  "ethics_status": "APPROVED_WITH_CONDITIONS",
  "irb_tier": "Exempt / Expedited Educational Research (Category 1)",
  "privacy_safeguards": ["Anonymized student IDs", "Zero prompt retention on commercial LLM endpoints"],
  "equity_protections": "Provide universal high-speed campus lab access to eliminate socioeconomic hardware disparities."
}
```
