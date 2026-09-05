import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Download, FileText } from "lucide-react";
import {
  projectTitle,
  reportUrl,
  type Catalog,
  type Project,
  type Report,
} from "./data";
import { useLocale } from "./i18n";
import { Empty, ErrorState, PageHeading } from "./components";

const THEME_DESC: Record<string, [string, string]> = {
  claude: [
    "\u6e29\u6696\u7eb8\u611f \u00b7 \u6c89\u6d78\u9605\u8bfb",
    "Warm paper / considered reading",
  ],
  academic: [
    "\u5b66\u672f\u6392\u7248 \u00b7 \u4e25\u8c28\u5f15\u7528",
    "Scholarly typography / citations",
  ],
  datalab: [
    "\u6e05\u6670\u5bc6\u5ea6 \u00b7 \u6570\u636e\u63a2\u7d22",
    "Analytical clarity / exploration",
  ],
  "datalab-dark": [
    "\u6df1\u8272\u5de5\u4f5c\u53f0 \u00b7 \u4e13\u6ce8\u8bc1\u636e",
    "Dark workbench / focused evidence",
  ],
  presentation: [
    "\u91cd\u70b9\u7a81\u51fa \u00b7 \u51b3\u7b56\u9605\u8bfb",
    "Decision-first / editorial contrast",
  ],
};
function ThemeCard({
  report,
  selected,
  onClick,
}: {
  report: Report;
  selected: boolean;
  onClick: () => void;
}) {
  const { t, locale } = useLocale();
  return (
    <button
      className={`theme-card theme-${report.theme} ${selected ? "selected" : ""}`}
      onClick={onClick}
      disabled={!report.available}
      aria-pressed={selected}
    >
      <div className="theme-miniature" aria-hidden="true">
        <div className="mini-kicker">EDUEVIDENCE</div>
        <div className="mini-heading" />
        <div className="mini-heading small" />
        <div className="mini-rule" />
        <div className="mini-decision">
          <span />
          <div />
          <div />
        </div>
        <div className="mini-lines">
          <i />
          <i />
          <i />
        </div>
      </div>
      <strong>{report.title}</strong>
      <span>
        {report.available
          ? THEME_DESC[report.theme]?.[locale === "zh" ? 0 : 1] ||
            t("readReport")
          : t("notGenerated")}
      </span>
    </button>
  );
}
export function ReportReader({ project }: { project: Project }) {
  const { t } = useLocale();
  const [theme, setTheme] = useState(
    project.reports.find((r) => r.available)?.theme || "claude",
  );
  useEffect(
    () => setTheme(project.reports.find((r) => r.available)?.theme || "claude"),
    [project.id],
  );
  const report = project.reports.find((r) => r.theme === theme && r.available);
  const url = report?.url ? reportUrl(report.url) : null;
  const query = useQuery({
    queryKey: ["report", url],
    enabled: !!url,
    staleTime: 60_000,
    queryFn: async ({ signal }) => {
      const r = await fetch(url!, { signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      if (!(r.headers.get("content-type") || "").includes("text/html"))
        throw new Error("Invalid report content type");
      const html = await r.text();
      if (!/<html[\s>]/i.test(html)) throw new Error("Missing HTML document");
      if (html.length > 16 * 1024 * 1024)
        throw new Error("Report exceeds viewer size limit");
      return html;
    },
  });
  function download() {
    if (!query.data) return;
    const blobUrl = URL.createObjectURL(
      new Blob([query.data], { type: "text/html;charset=utf-8" }),
    );
    const a = document.createElement("a");
    a.href = blobUrl;
    a.download = `EduEvidence-${project.id}-${theme}.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
  }
  return (
    <>
      <div className="theme-gallery">
        {project.reports.map((r) => (
          <ThemeCard
            key={r.theme}
            report={r}
            selected={theme === r.theme}
            onClick={() => setTheme(r.theme)}
          />
        ))}
      </div>
      {report && url ? (
        <section className="reader">
          <div className="reader-toolbar">
            <span>
              <FileText size={16} />
              {report.title}
            </span>
            <div>
              <button
                className="button small-button"
                onClick={download}
                disabled={!query.data}
              >
                <Download size={14} />
                {t("download")}
              </button>
              <a
                className="button small-button"
                href={url}
                target="_blank"
                rel="noopener noreferrer"
              >
                <ArrowUpRight size={14} />
                {t("openTab")}
              </a>
            </div>
          </div>
          {query.isPending ? (
            <div className="reader-loading" role="status">
              <span className="loader" />
              {t("reportLoading")}
            </div>
          ) : query.isError ? (
            <ErrorState error={query.error} retry={() => query.refetch()} />
          ) : (
            <iframe
              key={url}
              title={`${project.title} - ${report.title}`}
              srcDoc={query.data}
              sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox"
              referrerPolicy="no-referrer"
            />
          )}
        </section>
      ) : (
        <Empty title={t("notGenerated")} />
      )}
    </>
  );
}
export function Reports({ catalog }: { catalog: Catalog }) {
  const { t, locale } = useLocale();
  const [id, setId] = useState(catalog.projects[0]?.id || "");
  const project = catalog.projects.find((p) => p.id === id);
  return (
    <>
      <PageHeading
        eyebrow="REPORT LIBRARY"
        title={t("reportTitle")}
        lead={t("reportLead")}
      />
      <label className="project-select">
        {t("selectProject")}
        <select value={id} onChange={(e) => setId(e.target.value)}>
          {catalog.projects.map((p) => (
            <option key={p.id} value={p.id}>
              {projectTitle(p, locale)}
            </option>
          ))}
        </select>
      </label>
      {project ? <ReportReader project={project} /> : <Empty />}
    </>
  );
}
