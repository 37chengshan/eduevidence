import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, BookOpen, GitBranch, Info } from "lucide-react";
import {
  action,
  config,
  date,
  getDetail,
  navigate,
  projectTitle,
  text,
  type Detail,
  type Row,
} from "./data";
import { useLocale } from "./i18n";
import {
  ArtifactList,
  Badge,
  Definition,
  Diagnostic,
  Empty,
  ErrorState,
  EventList,
  EvidenceDialog,
  Loading,
  RunRow,
  SearchField,
  Section,
  SourceLink,
  Stat,
} from "./components";
import { EvidenceGraph, Forest } from "./Charts";
import { ReportReader } from "./Reports";
const tabs = [
  "overview",
  "evidence",
  "graph",
  "activity",
  "revisions",
  "reports",
];
function Findings({
  data,
  onSelect,
}: {
  data: Detail;
  onSelect: (r: Row) => void;
}) {
  const { t, locale } = useLocale();
  const [q, setQ] = useState(""),
    [relation, setRelation] = useState(""),
    [outcome, setOutcome] = useState("");
  const rows = data.evidence.filter(
    (e) =>
      (!relation || e.relation === relation) &&
      (!outcome || e.outcome_type === outcome) &&
      text(e).toLowerCase().includes(q.toLowerCase()),
  );
  return (
    <>
      <div className="filter-bar">
        <SearchField label={t("searchEvidence")} value={q} onChange={setQ} />
        <label>
          {t("relation")}
          <select
            value={relation}
            onChange={(e) => setRelation(e.target.value)}
          >
            <option value="">{t("any")}</option>
            {[...new Set(data.evidence.map((e) => e.relation))].map((v) => (
              <option key={v} value={v}>
                {t(v)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {t("outcome")}
          <select value={outcome} onChange={(e) => setOutcome(e.target.value)}>
            <option value="">{t("any")}</option>
            {[
              ...new Set(
                data.evidence.map((e) => e.outcome_type).filter(Boolean),
              ),
            ].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <span className="count-label" role="status">
          {rows.length} / {data.evidence.length}
        </span>
      </div>
      {rows.length ? (
        <div className="table-scroll">
          <table className="evidence-table">
            <thead>
              <tr>
                <th>{t("finding")}</th>
                <th>{t("outcome")}</th>
                <th>{t("effect")}</th>
                <th>{t("relation")}</th>
                <th>{t("sampleSize")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id}>
                  <td>
                    <button
                      className="evidence-title"
                      onClick={() => onSelect(e)}
                    >
                      <code>{e.id}</code>
                      <strong>
                        {locale === "zh" ? e.title_zh || e.title : e.title}
                      </strong>
                      <small>
                        {e.year || ""}{" "}
                        {e.study_type ? ` / ${e.study_type}` : ""}
                      </small>
                    </button>
                  </td>
                  <td>{e.outcome_type || t("not_recorded")}</td>
                  <td>
                    <Badge value={e.effect_direction} quiet />
                  </td>
                  <td>
                    <Badge value={e.relation} />
                  </td>
                  <td className="numeric-cell">{e.sample_size ?? "\u2014"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty title={t("noResults")} />
      )}
      <Section title={t("forest")} kicker="RECORDED ESTIMATES">
        <Forest evidence={data.evidence} />
      </Section>
      <Section title={t("sources")} kicker="SOURCE REGISTER">
        <div className="sources-grid">
          {data.sources.map((s) => (
            <article className="source-item" key={s.source_id}>
              <BookOpen size={17} />
              <div>
                <code>{s.source_id}</code>
                <h3>{s.title}</h3>
                <div className="source-meta">
                  <span>{s.year}</span>
                  {s.doi && <span>DOI {s.doi}</span>}
                  {s.retracted && <Badge value="RETRACTED" />}
                </div>
                <SourceLink url={s.canonical_url || s.source_location} />
              </div>
            </article>
          ))}
        </div>
      </Section>
    </>
  );
}
function Overview({ data }: { data: Detail }) {
  const { t, locale } = useLocale();
  const p = data.project,
    d = p.decision,
    local = locale === "zh" ? data.decision_zh : {};
  const support = local.supported_claims || d.supported || [],
    uncertain = local.uncertain_claims || d.uncertain || [];
  const rationale = local.decision_rationale || local.rationale || d.rationale;
  return (
    <>
      <section className="decision-surface">
        <div className="decision-main">
          <p className="eyebrow">{t("decision")}</p>
          <h2>{t(action(d.action))}</h2>
          <div className="row-badges">
            <Badge value={d.confidence} />
            {d.stale && <Badge value="stale" />}
            <span className="muted">
              {t("revision")} {d.graph_revision ?? "\u2014"}
            </span>
          </div>
          <p className="prose">{rationale || t("not_recorded")}</p>
          <a
            className="text-link"
            href={`#/project/${encodeURIComponent(p.id)}/reports`}
          >
            {t("readReport")}
            <ArrowRight size={15} />
          </a>
        </div>
        <div className="decision-facts">
          <Stat label={t("findings")} value={p.counts.findings} />
          <Stat label={t("sources")} value={p.counts.sources} />
          <Stat label={t("studies")} value={p.counts.studies} />
          <Stat label={t("claims")} value={p.counts.claims} />
        </div>
      </section>
      <div className="takeaway-grid">
        {[
          [t("supported"), support, "support"],
          [t("uncertain"), uncertain, "uncertain"],
        ].map(([title, items, cls]) => (
          <section key={String(cls)} className={`takeaway ${cls}`}>
            <div className="section-heading">
              <h2>{String(title)}</h2>
              <span className="count-label">{(items as Row[]).length}</span>
            </div>
            {(items as unknown[]).length ? (
              <ol>
                {(items as unknown[]).slice(0, 3).map((s, i) => (
                  <li key={i}>{text(s)}</li>
                ))}
              </ol>
            ) : (
              <p className="muted">{t("not_recorded")}</p>
            )}
            {(items as unknown[]).length > 3 && (
              <details>
                <summary>{t("details")}</summary>
                <ol start={4}>
                  {(items as unknown[]).slice(3).map((s, i) => (
                    <li key={i}>{text(s)}</li>
                  ))}
                </ol>
              </details>
            )}
          </section>
        ))}
      </div>
      <Section title={t("boundary")} kicker="FOR WHOM / WHEN / HOW">
        <div className="boundary-box">
          <Definition data={local.applicability || data.applicability} />
        </div>
      </Section>
      <div className="overview-bottom">
        <Section
          title={t("graph")}
          kicker="SOURCE TO CLAIM"
          action={
            <a
              href={`#/project/${encodeURIComponent(p.id)}/graph`}
              className="text-link"
            >
              {t("open")}
              <ArrowRight size={14} />
            </a>
          }
        >
          <EvidenceGraph data={data.graph} compact />
        </Section>
        <Section title={t("runs")} kicker="EXECUTION RECORDS">
          {data.runs.length ? (
            data.runs.slice(0, 3).map((r) => <RunRow key={r.run_id} run={r} />)
          ) : (
            <Empty title={p.kind === "example" ? t("noHistory") : undefined}>
              {t("noHistoryLead")}
            </Empty>
          )}
        </Section>
      </div>
      <Section title={t("pilotPlan")} kicker="EVIDENCE TO ACTION">
        <div className="takeaway-grid">
          <details className="boundary-box">
            <summary>{t("intervene")}</summary>
            <Definition data={data.intervention} />
          </details>
          <details className="boundary-box">
            <summary>{t("evaluate")}</summary>
            <Definition data={data.evaluation} />
          </details>
        </div>
      </Section>
    </>
  );
}
function Revisions({ data }: { data: Detail }) {
  const { t, locale } = useLocale();
  return (
    <>
      <p className="page-lead">{t("revisionLead")}</p>
      <div className="takeaway-grid">
        <Section title={t("revision")} kicker="GRAPH REVISION">
          {data.revisions.length ? (
            <div className="revision-list">
              {data.revisions
                .slice()
                .reverse()
                .map((r) => (
                  <details className="snapshot" key={r.revision}>
                    <summary>
                      <GitBranch size={20} />
                      <strong>Revision {r.revision}</strong>
                      {r.active && <Badge value="active" />}
                    </summary>
                    <Definition
                      data={{
                        reason: r.reason,
                        parent_revision: r.parent_revision,
                        created_at: date(r.created_at, locale),
                        touched_entities: r.touched_entities,
                      }}
                    />
                  </details>
                ))}
            </div>
          ) : (
            <Empty />
          )}
        </Section>
        <Section title={t("decision")} kicker="DECISION SNAPSHOT">
          {data.decisions.length ? (
            data.decisions.map((d) => (
              <details key={d.decision_snapshot_id} className="snapshot">
                <summary>
                  <code>{d.decision_snapshot_id}</code>
                  <Badge value={d.decision} />
                </summary>
                <p className="muted">
                  Revision {d.graph_revision} / {date(d.created_at, locale)}
                </p>
                <Definition
                  data={{
                    confidence: d.confidence_label,
                    applicability: d.applicability_boundary,
                    missing_evidence: d.missing_evidence,
                  }}
                />
              </details>
            ))
          ) : (
            <Empty />
          )}
        </Section>
      </div>
      <Section title="KnowledgeGap" kicker="RESEARCH ITERATIONS">
        {data.gaps.length ? (
          <div className="takeaway-grid">
            {data.gaps.map((g, i) => (
              <article className="boundary-box" key={g.gap_id || i}>
                <code>{g.gap_id}</code>
                <h3>{g.title || g.description || g.gap_type}</h3>
                <Badge value={g.status} />
              </article>
            ))}
          </div>
        ) : (
          <Empty />
        )}
        {data.iterations.length > 0 && (
          <div className="revision-list">
            {data.iterations.map((r) => (
              <details key={r.iteration_id} className="snapshot">
                <summary>
                  <code>{r.iteration_id}</code>
                  <Badge value={r.status} />
                </summary>
                <Definition data={r} />
              </details>
            ))}
          </div>
        )}
      </Section>
    </>
  );
}
export function ProjectView({ id, tab }: { id: string; tab: string }) {
  const { t, locale } = useLocale();
  const [inspected, setInspected] = useState<Row | null>(null);
  const [node, setNode] = useState<Row | null>(null);
  const query = useQuery({
    queryKey: ["project", id],
    queryFn: ({ signal }) => getDetail(id, signal),
    refetchInterval: config().mode === "local" ? 15_000 : false,
  });
  if (query.isPending) return <Loading />;
  if (query.isError)
    return <ErrorState error={query.error} retry={() => query.refetch()} />;
  const data = query.data,
    p = data.project;
  const selectedTab = tabs.includes(tab) ? tab : "overview";
  return (
    <>
      <a href="#/projects" className="back-link">
        <ArrowLeft size={14} />
        {t("projects")}
      </a>
      <header className="project-heading">
        <div className="row-badges">
          <span className="eyebrow">
            {p.kind === "example" ? "CASE STUDY" : "RESEARCH PROJECT"}
          </span>
          <Badge value={p.data_origin} quiet />
          <Badge value={p.status} quiet />
        </div>
        <h1>{projectTitle(p, locale)}</h1>
        <p className="muted">
          {p.project_id || p.id.replace("example--", "")}{" "}
          <span className="sep">/</span> {t("updated")}{" "}
          {date(p.updated_at, locale)} <span className="sep">/</span>{" "}
          {t("revision")} {p.active_revision ?? "\u2014"}
        </p>
      </header>
      <nav className="project-tabs" aria-label={t("workspace")}>
        {tabs.map((k) => (
          <a
            key={k}
            href={`#/project/${encodeURIComponent(id)}/${k}`}
            aria-current={selectedTab === k ? "page" : undefined}
          >
            {t(k)}
          </a>
        ))}
      </nav>
      <Diagnostic issues={data.issues} />
      {query.isRefetchError && (
        <div className="diagnostic" role="status">
          {t("error")} &middot;{" "}
          {locale === "zh"
            ? "\u4fdd\u7559\u4e0a\u6b21\u5feb\u7167"
            : "Showing the last snapshot"}
        </div>
      )}
      {selectedTab === "overview" && <Overview data={data} />}
      {selectedTab === "evidence" && (
        <Findings data={data} onSelect={setInspected} />
      )}
      {selectedTab === "graph" && (
        <div className="graph-workspace">
          <EvidenceGraph
            data={data.graph}
            onSelect={(n) => {
              setNode(n);
              const ev = data.evidence.find((r) => r.id === n.id);
              if (ev) setInspected(ev);
            }}
          />
          <aside className="graph-inspector">
            <p className="eyebrow">{t("related")}</p>
            {node ? (
              <>
                <code>{node.id}</code>
                <h3>{text(node.label)}</h3>
                <Badge value={node.kind} quiet />
                {data.graph.edges
                  .filter((e) => e.source === node.id || e.target === node.id)
                  .map((e, i) => (
                    <p key={i}>
                      <code>{e.source}</code>
                      <ArrowRight size={12} />
                      <code>{e.target}</code>
                      <small>{t(e.relation)}</small>
                    </p>
                  ))}
              </>
            ) : (
              <>
                <Info size={22} />
                <p className="muted">{t("graphLead")}</p>
              </>
            )}
          </aside>
        </div>
      )}
      {selectedTab === "activity" && (
        <>
          <Section title={t("runs")} kicker="RUN RECORDS">
            {data.runs.length ? (
              data.runs.map((r) => <RunRow key={r.run_id} run={r} />)
            ) : (
              <Empty
                title={p.kind === "example" ? t("noHistory") : undefined}
              />
            )}
          </Section>
          <div className="takeaway-grid">
            <Section title={t("events")} kicker="RECORDED EVENTS">
              <EventList events={data.events} />
            </Section>
            <Section title={t("artifacts")} kicker="IMMUTABLE ARTIFACTS">
              <ArtifactList artifacts={data.artifacts} />
            </Section>
          </div>
        </>
      )}
      {selectedTab === "revisions" && <Revisions data={data} />}
      {selectedTab === "reports" && <ReportReader project={p} />}
      <EvidenceDialog
        row={inspected}
        sources={data.sources}
        onClose={() => setInspected(null)}
      />
    </>
  );
}
