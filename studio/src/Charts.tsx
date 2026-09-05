import { useMemo, useState } from "react";
import { Minus, Plus, RotateCcw } from "lucide-react";
import { text, type Detail, type Row } from "./data";
import { useLocale } from "./i18n";
import { Empty } from "./components";

export function EvidenceGraph({
  data,
  onSelect,
  compact = false,
}: {
  data: Detail["graph"];
  onSelect?: (r: Row) => void;
  compact?: boolean;
}) {
  const { t } = useLocale();
  const [selected, setSelected] = useState<string>("");
  const [zoom, setZoom] = useState(1);
  const groups = ["source", "finding", "claim"];
  const limit = compact ? 4 : 12;
  const nodes = useMemo<Array<Row & { x: number; y: number }>>(
    () =>
      groups.flatMap((kind, col) =>
        data.nodes
          .filter((n) => n.kind === kind)
          .slice(0, limit)
          .map((n, i, arr) => ({
            ...n,
            x: compact ? 90 + col * 210 : 110 + col * 260,
            y:
              68 +
              ((i + 0.5) * (compact ? 150 : Math.max(280, arr.length * 45))) /
                arr.length,
          })),
      ),
    [data, compact],
  );
  const height = compact
    ? 280
    : Math.max(
        380,
        ...groups.map(
          (k) =>
            data.nodes.filter((n) => n.kind === k).slice(0, limit).length * 45 +
            140,
        ),
      );
  const map = new Map(nodes.map((n) => [n.id, n]));
  const edges = data.edges.filter(
    (e) => map.has(e.source) && map.has(e.target),
  );
  const neighbors = new Set([
    selected,
    ...edges
      .filter((e) => e.source === selected || e.target === selected)
      .flatMap((e) => [e.source, e.target]),
  ]);
  const choose = (n: Row) => {
    setSelected(n.id);
    onSelect?.(data.nodes.find((v) => v.id === n.id) || n);
  };
  return (
    <div className={`graph-panel ${compact ? "compact" : ""}`}>
      {!compact && (
        <div className="graph-toolbar">
          <p>{t("graphLead")}</p>
          <div className="button-group">
            <button
              className="icon-button"
              aria-label={t("zoomOut")}
              onClick={() => setZoom(Math.max(0.8, zoom - 0.2))}
            >
              <Minus size={15} />
            </button>
            <button
              className="icon-button"
              aria-label={t("reset")}
              onClick={() => {
                setZoom(1);
                setSelected("");
              }}
            >
              <RotateCcw size={15} />
            </button>
            <button
              className="icon-button"
              aria-label={t("zoomIn")}
              onClick={() => setZoom(Math.min(1.8, zoom + 0.2))}
            >
              <Plus size={15} />
            </button>
          </div>
        </div>
      )}
      <div className="graph-scroll">
        <svg
          role="img"
          aria-label={t("graph")}
          viewBox={`0 0 ${compact ? 620 : 860} ${height}`}
          style={{ minWidth: compact ? undefined : 700 * zoom }}
        >
          <defs>
            <pattern
              id={compact ? "dots-mini" : "dots"}
              width="18"
              height="18"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="1" cy="1" r=".65" fill="currentColor" opacity=".13" />
            </pattern>
          </defs>
          <rect
            width="100%"
            height="100%"
            fill={`url(#${compact ? "dots-mini" : "dots"})`}
          />
          {groups.map((kind, col) => (
            <text
              key={kind}
              x={compact ? 90 + col * 210 : 110 + col * 260}
              y="30"
              textAnchor="middle"
              className="graph-label"
            >
              {t(kind)}
            </text>
          ))}
          {edges.map((e, i) => {
            const s = map.get(e.source)!;
            const d = map.get(e.target)!;
            return (
              <path
                key={i}
                d={`M ${s.x + 14} ${s.y} C ${(s.x + d.x) / 2} ${s.y}, ${(s.x + d.x) / 2} ${d.y}, ${d.x - 14} ${d.y}`}
                fill="none"
                className={`graph-edge ${e.relation}`}
                opacity={
                  !selected ||
                  (neighbors.has(e.source) && neighbors.has(e.target))
                    ? 0.65
                    : 0.1
                }
              />
            );
          })}
          {nodes.map((n) => (
            <g
              key={n.id}
              role={compact ? undefined : "button"}
              tabIndex={compact ? undefined : 0}
              aria-label={`${t(n.kind)} ${n.id}: ${text(n.label)}`}
              onClick={() => choose(n)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  choose(n);
                }
              }}
              className={`graph-node ${n.kind} ${selected === n.id ? "selected" : ""}`}
              opacity={!selected || neighbors.has(n.id) ? 1 : 0.25}
            >
              <title>{text(n.label)}</title>
              <rect
                x={n.x - 16}
                y={n.y - 13}
                width="32"
                height="26"
                rx={n.kind === "source" ? 4 : 13}
              />
              <text
                x={n.x}
                y={n.y + 3}
                textAnchor="middle"
                className="node-letter"
              >
                {n.kind === "source" ? "S" : n.kind === "finding" ? "F" : "C"}
              </text>
              <text
                x={n.x}
                y={n.y + 28}
                textAnchor="middle"
                className="node-id"
              >
                {String(n.id).length > 21
                  ? String(n.id).slice(0, 18) + "..."
                  : n.id}
              </text>
            </g>
          ))}
        </svg>
      </div>
      {!compact && (
        <>
          <p className="chart-note">
            {nodes.length} / {data.nodes.length} &middot; {t("graphSubset")}
          </p>
          <div className="graph-node-index">
            {nodes.map((n) => (
              <button
                key={n.id}
                className={selected === n.id ? "active" : ""}
                onClick={() => choose(n)}
              >
                {n.id}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
export function Forest({ evidence }: { evidence: Row[] }) {
  const { t } = useLocale();
  const [group, setGroup] = useState("");
  const valid = evidence.filter(
    (e) =>
      typeof e.numeric?.value === "number" && Number.isFinite(e.numeric.value),
  );
  const groupKey = (e: Row) =>
    `${e.numeric.metric} | ${e.outcome_type || "not_recorded"} | ${e.timepoint || ""} | ${e.numeric.metric === "unspecified" ? e.id : ""}`;
  const groups = [...new Set(valid.map(groupKey))];
  const current = groups.includes(group) ? group : groups[0];
  const rows = valid.filter((e) => groupKey(e) === current);
  if (!rows.length)
    return <Empty title={t("noEffect")}>{t("noInference")}</Empty>;
  const values = rows.flatMap((e) => [
    e.numeric.value,
    ...(e.numeric.interval_status === "reported"
      ? [e.numeric.ci_lower, e.numeric.ci_upper]
      : []),
  ]);
  const metric = rows[0].numeric.metric.toLowerCase().replace(/[\s-]+/g, "_");
  const nullValue = [
    "or",
    "rr",
    "hr",
    "odds_ratio",
    "risk_ratio",
    "hazard_ratio",
  ].includes(metric)
    ? 1
    : [
          "g",
          "d",
          "smd",
          "md",
          "hedges_g",
          "cohens_d",
          "mean_difference",
          "log_odds_ratio",
          "log_or",
        ].includes(metric)
      ? 0
      : null;
  const extents = nullValue === null ? values : [...values, nullValue];
  const min = Math.min(...extents),
    max = Math.max(...extents),
    pad = (max - min || 1) * 0.14;
  if (!Number.isFinite(max - min + 2 * pad))
    return <Empty title={t("noEffect")}>{t("noInference")}</Empty>;
  const number = (n: number) =>
    new Intl.NumberFormat("en", { maximumSignificantDigits: 5 }).format(n);
  const x = (v: number) =>
    210 + ((v - min + pad) / (max - min + 2 * pad)) * 410;
  return (
    <div className="forest">
      <div className="filter-bar">
        <label>
          {t("outcome")}
          <select value={current} onChange={(e) => setGroup(e.target.value)}>
            {groups.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
        </label>
      </div>
      <div className="table-scroll">
        <svg
          viewBox={`0 0 820 ${rows.length * 46 + 62}`}
          role="img"
          aria-label={t("forest")}
          className="forest-svg"
        >
          {nullValue !== null && (
            <line
              x1={x(nullValue)}
              x2={x(nullValue)}
              y1="8"
              y2={rows.length * 46 + 18}
              className="zero-line"
            />
          )}
          {rows.map((e, i) => {
            const y = i * 46 + 30,
              n = e.numeric;
            return (
              <g key={e.id}>
                <text x="12" y={y + 4} className="forest-label">
                  {e.id}
                </text>
                {n.interval_status === "reported" && (
                  <>
                    <line
                      x1={x(n.ci_lower)}
                      x2={x(n.ci_upper)}
                      y1={y}
                      y2={y}
                      className="ci-line"
                    />
                    <line
                      x1={x(n.ci_lower)}
                      x2={x(n.ci_lower)}
                      y1={y - 5}
                      y2={y + 5}
                      className="ci-line"
                    />
                    <line
                      x1={x(n.ci_upper)}
                      x2={x(n.ci_upper)}
                      y1={y - 5}
                      y2={y + 5}
                      className="ci-line"
                    />
                  </>
                )}
                <circle cx={x(n.value)} cy={y} r="5" className="effect-dot" />
                <text x="650" y={y + 4} className="forest-label">
                  {number(n.value)}{" "}
                  {n.interval_status === "reported"
                    ? `[${number(n.ci_lower)}, ${number(n.ci_upper)}]`
                    : n.interval_status === "not_reported"
                      ? t("noCI")
                      : t("interval_" + n.interval_status)}
                </text>
              </g>
            );
          })}
          {nullValue !== null && (
            <text
              x={x(nullValue)}
              y={rows.length * 46 + 42}
              textAnchor="middle"
              className="forest-label"
            >
              {nullValue}
            </text>
          )}
        </svg>
      </div>
      <p className="chart-note">{t("noInference")}</p>
    </div>
  );
}
