# Research Studio

Read-only project observation and five-theme report reading. Research execution
remains in the existing Skill/CLI. No research mutations or worker dispatch UI.

## Development

```sh
npm ci
npm run typecheck
npm run build
```

Vite emits `../web/studio`; these prebuilt assets ship with the Python Skill.
The browser configuration is `config.json`: local API mode by default; the
Pages builder writes a static mode configuration with relative data URLs.

## Browser validation

```sh
python ../scripts/build_gh_pages.py
npx playwright install chromium
npm run test:e2e
```

The test harness creates an explicitly synthetic temporary project, starts two
HTTP servers, and covers local/static paths, read-only constraints, real report
HTTP validation, data inspection, keyboard focus, five-theme rendering, and
responsive accessibility. It never uses user research as test data.

See `../docs/research-studio-guide.zh-CN.md` for workflows and data authority.
