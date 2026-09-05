import { useEffect, useRef, type ReactNode } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  Clock3,
  Database,
  Inbox,
  Search,
  X,
} from "lucide-react";
import { action, date, safeUrl, text, type Row } from "./data";
import { useLocale } from "./i18n";

export function Badge({
  value,
  quiet = false,
}: {
  value: unknown;
  quiet?: boolean;
}) {
  const { t } = useLocale();
  const k = action(value);
  return (
    <span className={`badge ${quiet ? "quiet" : k}`}>
      <span className="badge-dot" />
      {t(k)}
    </span>
  );
}
export function Empty({
  title,
  children,
}: {
  title?: string;
  children?: ReactNode;
}) {
  const { t } = useLocale();
  return (
    <div className="empty">
      <Inbox size={27} strokeWidth={1.3} />
      <h3>{title || t("noData")}</h3>
      <p>{children || t("emptyLead")}</p>
    </div>
  );
}
export function Loading() {
  const { t } = useLocale();
  return (
    <div className="loading" role="status">
      <span className="loader" />
      {t("loading")}
      <div className="skeleton" />
      <div className="skeleton short" />
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry: () => void;
}) {
  const { t } = useLocale();
  return (
    <div className="error-state" role="alert">
      <AlertCircle />
      <h3>{t("error")}</h3>
      <p>{error.message}</p>
      <button className="button" onClick={retry}>
        {t("retry")}
      </button>
    </div>
  );
}
export function PageHeading({
  eyebrow,
  title,
  lead,
  children,
}: {
  eyebrow: string;
  title: string;
  lead?: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {lead && <p className="page-lead">{lead}</p>}
      </div>
      {children}
    </header>
  );
}
export function Stat({
  label,
  value,
  detail,
}: {
  label: string;
  value: number | string;
  detail?: string;
}) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}
export function SearchField({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (s: string) => void;
  label: string;
}) {
  return (
    <label className="search-field">
      <Search size={16} />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={label}
        aria-label={label}
      />
    </label>
  );
}
export function Section({
  title,
  kicker,
  children,
  action: extra,
}: {
  title: string;
  kicker?: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className="section">
      <div className="section-heading">
        <div>
          {kicker && <p className="eyebrow">{kicker}</p>}
          <h2>{title}</h2>
        </div>
        {extra}
      </div>
      {children}
    </section>
  );
}
export function Diagnostic({ issues }: { issues: Row[] }) {
  const { t } = useLocale();
  if (!issues.length) return null;
  return (
    <details className="diagnostic">
      <summary>
        <AlertCircle size={15} />
        {t("diagnostics")} <span>{issues.length}</span>
      </summary>
      <ul>
        {issues.map((issue, i) => (
          <li key={i}>
            <code>{issue.code}</code> {issue.message}
          </li>
        ))}
      </ul>
    </details>
  );
}
export function Definition({ data }: { data: Row | string }) {
  const { t } = useLocale();
  if (typeof data === "string") return <p className="prose">{data}</p>;
  const rows = Object.entries(data || {}).filter(
    ([, v]) => v !== null && v !== undefined && text(v) !== "",
  );
  if (!rows.length) return <p className="muted">{t("not_recorded")}</p>;
  return (
    <dl className="definition">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{t(k)}</dt>
          <dd>{text(v)}</dd>
        </div>
      ))}
    </dl>
  );
}
export function SourceLink({
  url,
  children,
}: {
  url: unknown;
  children?: ReactNode;
}) {
  const { t } = useLocale();
  const href = safeUrl(url);
  return href ? (
    <a
      className="text-link"
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children || t("viewSource")}
      <ArrowUpRight size={14} />
    </a>
  ) : (
    <span className="muted">{t("not_recorded")}</span>
  );
}
export function EvidenceDialog({
  row,
  sources,
  onClose,
}: {
  row: Row | null;
  sources: Row[];
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const { t, locale } = useLocale();
  useEffect(() => {
    if (row && !ref.current?.open) ref.current?.showModal();
    if (!row && ref.current?.open) ref.current.close();
  }, [row]);
  const source = sources.find((s) => s.source_id === row?.source_id);
  return (
    <dialog
      ref={ref}
      className="inspector"
      aria-label={t("inspect")}
      onCancel={onClose}
      onClose={onClose}
    >
      <div className="inspector-top">
        <span className="eyebrow">{t("inspect")}</span>
        <button
          className="icon-button"
          aria-label={t("close")}
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </div>
      {row && (
        <>
          <code className="entity-id">
            {row.id || row.source_id || row.claim_id}
          </code>
          <h2>
            {locale === "zh"
              ? row.title_zh || row.title || row.label
              : row.title || row.label}
          </h2>
          <div className="row-badges">
            <Badge value={row.relation} />
            <Badge value={row.effect_direction} quiet />
          </div>
          <p className="prose">
            {locale === "zh"
              ? row.claim_zh || row.claim || row.effect
              : row.claim || row.effect}
          </p>
          <Definition
            data={{
              outcome: row.outcome_type,
              sampleSize: row.sample_size,
              method: row.study_type,
              provenance: row.source_id,
              study_id: row.study_id,
            }}
          />
          {row.audits?.length > 0 && (
            <section className="source-callout">
              <Definition data={{ audit: row.audits }} />
            </section>
          )}
          {source && (
            <section className="source-callout">
              <BookOpen size={18} />
              <div>
                <h3>{source.title}</h3>
                <SourceLink
                  url={source.canonical_url || source.source_location}
                />
              </div>
            </section>
          )}
          <details className="raw-record">
            <summary>{t("raw")}</summary>
            <pre>{JSON.stringify(row, null, 2)}</pre>
          </details>
        </>
      )}
    </dialog>
  );
}
export function RunRow({ run }: { run: Row }) {
  const { t, locale } = useLocale();
  return (
    <details className="run-row">
      <summary>
        <span className="run-icon">
          {run.status === "completed" ? (
            <CheckCircle2 size={18} />
          ) : (
            <Clock3 size={18} />
          )}
        </span>
        <div>
          <strong>{run.purpose || run.run_id}</strong>
          <small>
            {run.run_id} &middot; {date(run.started_at, locale)}
          </small>
        </div>
        <Badge value={run.status} />
      </summary>
      <div className="run-body">
        <Definition
          data={{
            execution_backend: run.execution_backend,
            capabilities: run.capabilities,
            graph_revision_before: run.graph_revision_before,
            graph_revision_after: run.graph_revision_after,
          }}
        />
        {Object.keys(run.gate_report || {}).length > 0 && (
          <details>
            <summary>{t("guardrails")}</summary>
            <Definition data={run.gate_report} />
          </details>
        )}
        {Object.keys(run.execution_plan || {}).length > 0 && (
          <details>
            <summary>{t("executionPlan")}</summary>
            <Definition data={run.execution_plan} />
          </details>
        )}
        <div className="stage-track">
          {[
            "frame",
            "retrieve",
            "extract",
            "challenge",
            "audit",
            "adjudicate",
            "applicability",
            "intervene",
            "evaluate",
          ].map((s) => (
            <div key={s}>
              <span>{t(s)}</span>
              <Badge value={run.stage_state?.stages?.[s]?.status} quiet />
            </div>
          ))}
        </div>
      </div>
    </details>
  );
}
export function EventList({ events }: { events: Row[] }) {
  const { locale, t } = useLocale();
  return events.length ? (
    <ol className="event-list">
      {events.map((e) => (
        <li key={e.seq}>
          <span className="event-dot" />
          <div>
            <div className="event-header">
              <strong>{t(e.type)}</strong>
              <time>{date(e.created_at, locale)}</time>
            </div>
            <small className="muted">
              #{e.seq} {e.run_id || ""}
            </small>
            <details className="raw-record">
              <summary>{t("details")}</summary>
              <pre>{JSON.stringify(e.payload, null, 2)}</pre>
            </details>
          </div>
        </li>
      ))}
    </ol>
  ) : (
    <Empty />
  );
}
export function ArtifactList({ artifacts }: { artifacts: Row[] }) {
  const { t } = useLocale();
  return artifacts.length ? (
    <div className="artifact-list">
      {artifacts.map((a) => (
        <div key={a.artifact_id}>
          <Database size={16} />
          <div>
            <strong>{a.artifact_type}</strong>
            <code>{a.artifact_id}</code>
          </div>
          <details className="raw-record">
            <summary>{t("details")}</summary>
            <pre>{JSON.stringify(a, null, 2)}</pre>
          </details>
        </div>
      ))}
    </div>
  ) : (
    <Empty />
  );
}
