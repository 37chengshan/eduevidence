import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Compass,
  FlaskConical,
  LayoutGrid,
  LockKeyhole,
  Menu,
  Moon,
  RefreshCw,
  Search,
  Sun,
  X,
} from "lucide-react";
import {
  config,
  getCatalog,
  getEvolution,
  navigate,
  projectTitle,
  type Catalog,
  type Locale,
} from "./data";
import { LocaleContext, useLocale } from "./i18n";
import {
  Badge,
  Empty,
  ErrorState,
  Loading,
  PageHeading,
  Section,
} from "./components";
import { Projects } from "./Projects";
import { ProjectView } from "./Project";
import { Reports } from "./Reports";
function safeRead(k: string, fallback: string) {
  try {
    return localStorage.getItem(k) || fallback;
  } catch {
    return fallback;
  }
}
function useRoute() {
  const [route, set] = useState(location.hash.slice(1) || "/projects");
  useEffect(() => {
    const h = () => {
      set(location.hash.slice(1) || "/projects");
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", h);
    return () => window.removeEventListener("hashchange", h);
  }, []);
  return route;
}
function Evolution() {
  const { t } = useLocale();
  const q = useQuery({
    queryKey: ["evolution"],
    queryFn: ({ signal }) => getEvolution(signal),
  });
  return (
    <>
      <PageHeading
        eyebrow="SKILL AUTOEVOLVE"
        title={t("evolveTitle")}
        lead={t("evolveLead")}
      />
      <div className="policy-strip">
        <LockKeyhole size={18} />
        <span>
          Baseline &rarr; Hypothesis &rarr; Evaluate &rarr; Keep / Revert
        </span>
        <Badge value="readonly" quiet />
      </div>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorState error={q.error} retry={() => q.refetch()} />
      ) : q.data.status === "unavailable" ? (
        <ErrorState
          error={new Error(t("unavailable"))}
          retry={() => q.refetch()}
        />
      ) : q.data.experiments.length ? (
        <div className="experiment-list">
          {q.data.experiments
            .slice()
            .reverse()
            .map((e) => (
              <article
                className="boundary-box"
                key={`${e.session_id}-${e.experiment_id}`}
              >
                <div className="section-heading">
                  <code>{e.experiment_id}</code>
                  <Badge value={e.status} />
                </div>
                <h3>{e.hypothesis}</h3>
                <p>{e.promotion_reason}</p>
                <code>{e.candidate_commit}</code>
              </article>
            ))}
        </div>
      ) : (
        <Empty />
      )}
      <p className="chart-note">{t("readOnlyNote")}</p>
    </>
  );
}
function Guide() {
  const { t, locale } = useLocale();
  const flows = [
    [
      "01",
      "Evidence Review",
      locale === "zh"
        ? "\u4e8c\u624b\u8bc1\u636e\u7efc\u8ff0\uff1a\u4ece\u95ee\u9898\u5b9a\u4e49\u5230\u53ef\u6eaf\u6e90\u7684\u88c1\u51b3\u3002"
        : "Review existing evidence, from framing to a traceable decision.",
    ],
    [
      "02",
      "Decision & Pilot",
      locale === "zh"
        ? "\u5c06\u672a\u89e3\u51b3\u7684\u8bc1\u636e\u7f3a\u53e3\u8f6c\u4e3a\u6709\u8fb9\u754c\u7684\u8bd5\u70b9\u65b9\u6848\u3002"
        : "Translate grounded gaps into bounded pilot designs.",
    ],
    [
      "03",
      "Evaluate & Update",
      locale === "zh"
        ? "\u65b0\u6570\u636e\u7ecf\u8fc7\u6821\u9a8c\u540e\u8fdb\u5165\u65b0\u7248\u672c\uff0c\u518d\u6b21\u8bc4\u4f30\u51b3\u5b9a\u3002"
        : "Validate new empirical data, create a revision, and reconsider the decision.",
    ],
  ];
  return (
    <>
      <PageHeading
        eyebrow="THE RESEARCH FLOW"
        title={t("guideTitle")}
        lead={t("guideLead")}
      />
      <div className="flow-grid">
        {flows.map(([n, title, desc]) => (
          <article key={n}>
            <span className="flow-number">{n}</span>
            <h2>{title}</h2>
            <p>{desc}</p>
          </article>
        ))}
      </div>
      <Section title={t("guide")} kicker="NINE SCIENTIFIC STAGES">
        <div className="protocol-grid">
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
          ].map((s, i) => (
            <div key={s}>
              <code>0{i + 1}</code>
              <strong>{t(s)}</strong>
              <span>{s}</span>
            </div>
          ))}
        </div>
      </Section>
      <div className="principles">
        <h2>{t("guardrails")}</h2>
        {(locale === "zh"
          ? [
              "\u4f18\u5316\u7814\u7a76\u8fc7\u7a0b\uff0c\u4e0d\u8ffd\u6c42\u7279\u5b9a\u7ed3\u8bba\u3002",
              "\u79d1\u5b66\u9636\u6bb5 \u2260 \u89d2\u8272 \u2260 \u80fd\u529b \u2260 \u5b50\u4ee3\u7406 \u2260 \u6a21\u578b\u3002",
              "\u5b50\u4ee3\u7406\u53ea\u8fd4\u56de\u5f85\u9a8c\u8bc1\u4ea7\u7269\uff1b\u4e3b\u5f15\u64ce\u7edf\u4e00\u63d0\u4ea4\u79d1\u5b66\u72b6\u6001\u3002",
              "\u8bc1\u636e\u7248\u672c\u4e0e Skill \u81ea\u8fdb\u5316\u7248\u672c\u4fdd\u6301\u72ec\u7acb\u3002",
              "\u7f3a\u5931\u8bc1\u636e\u4e0d\u662f\u96f6\u6548\u5e94\uff1b\u68c0\u7d22\u672a\u547d\u4e2d\u53ea\u63cf\u8ff0\u672c\u6b21\u8303\u56f4\u3002",
            ]
          : [
              "Optimize the research process, never the conclusion.",
              "Protocol stage \u2260 role \u2260 capability \u2260 worker \u2260 model.",
              "Workers return staging artifacts. Canonical state has a single writer.",
              "Evidence revisions and Skill revisions are separate histories.",
              "Missing evidence is not zero effect. Search failure is scope-bounded.",
            ]
        ).map((s) => (
          <p key={s}>
            <Check size={16} />
            {s}
          </p>
        ))}
      </div>
    </>
  );
}
function CommandPalette({
  catalog,
  open,
  onClose,
}: {
  catalog: Catalog;
  open: boolean;
  onClose: () => void;
}) {
  const { t, locale } = useLocale();
  const ref = useRef<HTMLDialogElement>(null);
  const [q, setQ] = useState("");
  useEffect(() => {
    if (open && !ref.current?.open) {
      setQ("");
      ref.current?.showModal();
    }
    if (!open && ref.current?.open) ref.current.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className="command-palette"
      aria-label={t("search")}
      onClose={onClose}
      onCancel={onClose}
    >
      <div className="command-input">
        <Search size={18} />
        <input
          autoFocus
          aria-label={t("search")}
          placeholder={t("search")}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button
          className="icon-button"
          aria-label={t("close")}
          onClick={onClose}
        >
          <X size={17} />
        </button>
      </div>
      <div className="command-results">
        {catalog.projects
          .filter((p) =>
            [p.title, p.title_en]
              .join(" ")
              .toLowerCase()
              .includes(q.toLowerCase()),
          )
          .map((p) => (
            <button
              key={p.id}
              onClick={() => {
                navigate(p.id);
                onClose();
              }}
            >
              <BookOpen size={16} />
              <span>{projectTitle(p, locale)}</span>
              <ArrowRight size={15} />
            </button>
          ))}
      </div>
    </dialog>
  );
}
export default function App() {
  const [locale, setLocale] = useState<Locale>(
    safeRead("studio-language", "zh") === "en" ? "en" : "zh",
  );
  const [dark, setDark] = useState(
    safeRead("studio-appearance", "light") === "dark",
  );
  useEffect(() => {
    document.documentElement.dataset.appearance = dark ? "dark" : "light";
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
    try {
      localStorage.setItem("studio-language", locale);
      localStorage.setItem("studio-appearance", dark ? "dark" : "light");
    } catch {}
  }, [dark, locale]);
  return (
    <LocaleContext.Provider value={locale}>
      <Shell
        dark={dark}
        toggleDark={() => setDark((v) => !v)}
        toggleLanguage={() => setLocale((v) => (v === "zh" ? "en" : "zh"))}
      />
    </LocaleContext.Provider>
  );
}
function Shell({
  dark,
  toggleDark,
  toggleLanguage,
}: {
  dark: boolean;
  toggleDark: () => void;
  toggleLanguage: () => void;
}) {
  const { t } = useLocale();
  const route = useRoute();
  const [menu, setMenu] = useState(false),
    [palette, setPalette] = useState(false);
  const client = useQueryClient();
  const query = useQuery({
    queryKey: ["catalog"],
    queryFn: ({ signal }) => getCatalog(signal),
    refetchInterval: config().mode === "local" ? 15_000 : false,
  });
  useEffect(() => {
    setMenu(false);
  }, [route]);
  useEffect(() => {
    const listener = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPalette((v) => !v);
      }
      if (e.key === "Escape") setMenu(false);
    };
    document.addEventListener("keydown", listener);
    return () => document.removeEventListener("keydown", listener);
  }, []);
  const page = route.startsWith("/project/")
    ? "projects"
    : route.split("/")[1] || "projects";
  let content: ReactNode;
  if (query.isPending) content = <Loading />;
  else if (query.isError)
    content = <ErrorState error={query.error} retry={() => query.refetch()} />;
  else if (route.startsWith("/project/")) {
    const pieces = route.split("/");
    let id = "";
    try {
      id = decodeURIComponent(pieces[2] || "");
    } catch {}
    content = <ProjectView key={id} id={id} tab={pieces[3] || "overview"} />;
  } else if (page === "reports") content = <Reports catalog={query.data} />;
  else if (page === "evolution") content = <Evolution />;
  else if (page === "guide") content = <Guide />;
  else content = <Projects catalog={query.data} />;
  return (
    <div className="app-shell">
      <a
        href="#main-content"
        className="skip-link"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        {t("skip")}
      </a>
      <aside className={`sidebar ${menu ? "is-open" : ""}`}>
        <a className="brand" href="#/projects">
          <span className="brand-mark">
            e<span />
          </span>
          <div>
            <strong>EduEvidence</strong>
            <span>RESEARCH STUDIO</span>
          </div>
        </a>
        <button className="sidebar-search" onClick={() => setPalette(true)}>
          <Search size={15} />
          <span>{t("search")}</span>
          <kbd>Ctrl K</kbd>
        </button>
        <p className="nav-label">{t("workspace")}</p>
        <nav aria-label={t("workspace")}>
          {[
            ["projects", LayoutGrid],
            ["reports", BookOpen],
            ["evolution", FlaskConical],
            ["guide", Compass],
          ].map(([key, Icon]) => {
            const k = key as string;
            const Glyph = Icon as typeof LayoutGrid;
            return (
              <a
                key={k}
                href={`#/${k}`}
                aria-current={page === k ? "page" : undefined}
              >
                <Glyph size={18} strokeWidth={1.65} />
                <span>{t(k)}</span>
                {page === k && <span className="active-dot" />}
              </a>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <span className="read-only-label">
            <LockKeyhole size={14} />
            {t("readonly")}
          </span>
          <p>{t("readOnlyNote")}</p>
          <div className="sidebar-version">
            <span>EduEvidence 6.0</span>
            <span>v1</span>
          </div>
        </div>
      </aside>
      {menu && (
        <button
          className="sidebar-shade"
          aria-label={t("close")}
          onClick={() => setMenu(false)}
        />
      )}
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button mobile-menu"
              aria-label={t("workspace")}
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              <Menu size={19} />
            </button>
            <span>Studio</span>
            <ChevronRight size={13} />
            <strong>{t(page)}</strong>
          </div>
          <div className="topbar-actions">
            <span className="connection">
              <span />
              {t(config().mode)}
            </span>
            <button
              className="icon-button"
              title={t("refresh")}
              aria-label={t("refresh")}
              disabled={query.isFetching}
              onClick={() => client.invalidateQueries()}
            >
              <RefreshCw
                size={16}
                className={query.isFetching ? "spinning" : ""}
              />
            </button>
            <button
              className="icon-button"
              title={t("dark")}
              aria-label={t("dark")}
              onClick={toggleDark}
            >
              {dark ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button className="language-button" onClick={toggleLanguage}>
              {t("language")}
            </button>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {content}
        </main>
        <footer className="app-footer">
          <span>
            <LockKeyhole size={12} />
            {t("readonly")}
          </span>
          <span>Evidence &rarr; Decision &rarr; Revision</span>
        </footer>
      </div>
      {query.data && (
        <CommandPalette
          catalog={query.data}
          open={palette}
          onClose={() => setPalette(false)}
        />
      )}
    </div>
  );
}
