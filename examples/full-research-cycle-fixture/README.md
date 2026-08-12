# Full Research Cycle software fixture

This dataset is **synthetic** and exists only to test Full Research Cycle
software mechanics (ingest → descriptive analysis → validated local
Study/Findings → graph revision → updated DecisionSnapshot). It is **not**
education research evidence and must never be cited as empirical support.

- `data.csv`: 40 synthetic students with `pre` / `post` scores and a `group`
  column (A = intervention, B = control). Column semantics are illustrative
  only.

Usage:

```bash
eduevidence project create --question "Effect of our AI tutor on local transfer?" --mode full_research_cycle
eduevidence research plan --project <PRJ-...>
eduevidence data ingest --project <PRJ-...> --design <DSN-...> --file data.csv --privacy confidential
eduevidence analyze --project <PRJ-...> --plan <APL-...>
eduevidence adjudicate --project <PRJ-...>
eduevidence report --project <PRJ-...>
```
