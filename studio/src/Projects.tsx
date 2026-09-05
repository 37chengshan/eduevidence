import { useMemo, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Layers,
  ShieldCheck,
} from "lucide-react";
import {
  action,
  date,
  navigate,
  projectTitle,
  type Catalog,
  type Project,
} from "./data";
import { useLocale } from "./i18n";
import {
  Badge,
  Diagnostic,
  Empty,
  PageHeading,
  SearchField,
  Stat,
} from "./components";

function MiniTrace({ p }: { p: Project }) {
  return (
    <div className="mini-trace" aria-hidden="true">
      <div className="trace-column">
        {["S", "S", "S"].slice(0, Math.min(3, p.counts.sources)).map((v, i) => (
          <span key={i}>{v}</span>
        ))}
      </div>
      <svg viewBox="0 0 150 90">
        <path d="M0 10 C70 10 70 45 150 45 M0 45 L150 45 M0 80 C70 80 70 45 150 45" />
      </svg>
      <span className="trace-center">
        <Layers size={23} />
      </span>
      <svg viewBox="0 0 85 90">
        <path d="M0 45 L85 45" />
      </svg>
      <span className={`trace-outcome ${action(p.decision.action)}`}>
        {String(p.decision.action || "\u2014")
          .toUpperCase()
          .replaceAll("_", " ")}
      </span>
    </div>
  );
}
export function Projects({ catalog }: { catalog: Catalog }) {
  const { t, locale } = useLocale();
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("all");
  const [order, setOrder] = useState("recent");
  const filtered = useMemo(
    () =>
      catalog.projects
        .filter(
          (p) =>
            (kind === "all" || kind === p.kind) &&
            [p.title, p.title_en, p.question, p.domain]
              .join(" ")
              .toLowerCase()
              .includes(query.toLowerCase()),
        )
        .sort((a, b) =>
          order === "recent"
            ? (b.updated_at || "").localeCompare(a.updated_at || "")
            : projectTitle(a, locale).localeCompare(projectTitle(b, locale)),
        ),
    [catalog, query, kind, order, locale],
  );
  const featured =
    catalog.projects.find(
      (p) => p.id === "example--ai-coding-assistant-evidence",
    ) || catalog.projects[0];
  const total = (key: "sources" | "findings") =>
    catalog.projects.reduce((sum, p) => sum + p.counts[key], 0);
  return (
    <>
      <PageHeading
        eyebrow="RESEARCH WORKSPACE"
        title={t("homeTitle")}
        lead={t("homeLead")}
      />
      <Diagnostic issues={catalog.issues} />
      <div className="stats-grid">
        <Stat label={t("projectCount")} value={catalog.projects.length} />
        <Stat label={t("findings")} value={total("findings")} />
        <Stat label={t("sources")} value={total("sources")} />
        <Stat
          label={t("local")}
          value={catalog.projects.filter((p) => p.kind === "project").length}
        />
      </div>
      {featured && (
        <section className="feature-grid">
          <article className="feature-case">
            <p className="eyebrow">
              {t("featured")} <ArrowUpRight size={14} />
            </p>
            <h2>{projectTitle(featured, locale)}</h2>
            <div className="row-badges">
              <Badge value={featured.decision.action} />
              <span className="muted">
                {t("confidence")} &middot;{" "}
                {t(action(featured.decision.confidence))}
              </span>
            </div>
            <MiniTrace p={featured} />
            <button
              className="button primary"
              onClick={() => navigate(featured.id)}
            >
              {t("open")}
              <ArrowRight size={16} />
            </button>
          </article>
          <aside className="principle-card">
            <ShieldCheck size={26} strokeWidth={1.25} />
            <p className="eyebrow">DECISION INTEGRITY</p>
            <h2>
              {locale === "zh"
                ? "\u8bc1\u636e\u6709\u8fb9\u754c\uff0c\u51b3\u5b9a\u6709\u4f9d\u636e\u3002"
                : "Evidence has limits. Decisions need reasons."}
            </h2>
            <p>
              {locale === "zh"
                ? "\u6b63\u5411\u7ed3\u679c\u3001\u53cd\u8bc1\u548c\u672a\u77e5\uff0c\u90fd\u662f\u7814\u7a76\u7684\u4e00\u90e8\u5206\u3002"
                : "Positive findings, counter-evidence, and uncertainty all belong in the research."}
            </p>
            <a href="#/guide" className="text-link">
              {t("guide")}
              <ArrowRight size={15} />
            </a>
            <span className="principle-caption">
              Optimize the process.
              <br />
              Never the conclusion.
            </span>
          </aside>
        </section>
      )}
      <section className="project-library">
        <div className="section-heading">
          <h2>{t("all")}</h2>
          <span className="count-label">
            {filtered.length} / {catalog.projects.length}
          </span>
        </div>
        <div className="library-toolbar">
          <div className="segmented" aria-label={t("filter")}>
            {[
              ["all", "all"],
              ["project", "local"],
              ["example", "examples"],
            ].map(([v, k]) => (
              <button
                key={v}
                aria-pressed={kind === v}
                onClick={() => setKind(v)}
              >
                {t(k)}
              </button>
            ))}
          </div>
          <SearchField label={t("search")} value={query} onChange={setQuery} />
          <select
            aria-label={locale === "zh" ? "\u6392\u5e8f" : "Sort"}
            value={order}
            onChange={(e) => setOrder(e.target.value)}
          >
            <option value="recent">{t("updated")}</option>
            <option value="title">
              {locale === "zh" ? "\u6807\u9898" : "Title"}
            </option>
          </select>
        </div>
        {filtered.length ? (
          <div className="project-grid">
            {filtered.map((p) => (
              <article className="project-card" key={p.id}>
                <div className="project-card-top">
                  <span className="project-symbol">
                    <BookOpen size={18} />
                  </span>
                  <span className="origin-label">{t(p.data_origin)}</span>
                </div>
                <a
                  className="project-title"
                  href={`#/project/${encodeURIComponent(p.id)}/overview`}
                >
                  <h3>{projectTitle(p, locale)}</h3>
                  <ArrowUpRight size={16} />
                </a>
                <div className="row-badges">
                  <Badge value={p.decision.action} />
                  {p.decision.stale && <Badge value="stale" />}
                </div>
                <div className="project-card-footer">
                  <span>
                    {p.counts.findings} {t("findings")}{" "}
                    <span className="sep">/</span> {p.counts.sources}{" "}
                    {t("sources")}
                  </span>
                  <time>{date(p.updated_at, locale)}</time>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <Empty title={t("noResults")}>
            <button
              className="button"
              onClick={() => {
                setQuery("");
                setKind("all");
              }}
            >
              {t("clear")}
            </button>
          </Empty>
        )}
      </section>
    </>
  );
}
