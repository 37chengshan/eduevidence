export type Row = Record<string, any>;
export type Locale = "zh" | "en";
export type Report = {
  theme: string;
  title: string;
  tone: string;
  available: boolean;
  url: string | null;
};
export type Project = {
  id: string;
  project_id: string | null;
  kind: "example" | "project";
  title: string;
  title_en: string;
  question: string;
  domain: string;
  status: string;
  data_origin: string;
  updated_at: string | null;
  active_revision: number | null;
  decision: Row;
  counts: {
    sources: number;
    findings: number;
    claims: number;
    studies: number;
    runs: number;
  };
  reports: Report[];
};
export type Catalog = {
  schema_version: number;
  mode: "local" | "static";
  readonly: true;
  generated_at: string;
  projects: Project[];
  issues: Row[];
};
export type Detail = {
  schema_version: number;
  project: Project;
  sources: Row[];
  studies: Row[];
  evidence: Row[];
  claims: Row[];
  graph: { nodes: Row[]; edges: Row[] };
  decisions: Row[];
  revisions: Row[];
  runs: Row[];
  events: Row[];
  artifacts: Row[];
  gaps: Row[];
  iterations: Row[];
  applicability: Row | string;
  intervention: Row;
  evaluation: Row;
  decision_zh: Row;
  issues: Row[];
};
export type Config = {
  mode: "local" | "static";
  api_base: string;
  readonly: true;
};
let configuration: Config;
export async function configure(): Promise<Config> {
  const response = await fetch(new URL("./config.json", document.baseURI), {
    cache: "no-store",
  });
  if (!response.ok) throw new Error("Studio configuration unavailable");
  const data = await response.json();
  if (
    !["local", "static"].includes(data.mode) ||
    data.readonly !== true ||
    typeof data.api_base !== "string"
  )
    throw new Error("Invalid read-only Studio configuration");
  const api = new URL(data.api_base, document.baseURI);
  if (api.origin !== location.origin)
    throw new Error("Cross-origin data endpoints are not permitted");
  configuration = data;
  return data;
}
export function config() {
  return configuration;
}
async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const base = configuration.api_base.replace(/\/$/, "");
  const url = new URL(
    base + "/" + path + (configuration.mode === "static" ? ".json" : ""),
    document.baseURI,
  );
  const r = await fetch(url, {
    signal,
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${path}`);
  if (!(r.headers.get("content-type") || "").includes("json"))
    throw new Error("Expected JSON, not an HTML fallback");
  return r.json();
}
export async function getCatalog(signal?: AbortSignal) {
  const d = await read<Catalog>("catalog", signal);
  if (
    d.schema_version !== 1 ||
    !Array.isArray(d.projects) ||
    d.readonly !== true
  )
    throw new Error("Unsupported catalog contract");
  return d;
}
export async function getDetail(id: string, signal?: AbortSignal) {
  const d = await read<Detail>("projects/" + encodeURIComponent(id), signal);
  if (
    d.schema_version !== 1 ||
    d.project?.id !== id ||
    !Array.isArray(d.evidence)
  )
    throw new Error("Invalid project projection");
  return d;
}
export const getEvolution = (signal?: AbortSignal) =>
  read<{ experiments: Row[]; status: string }>("evolution", signal);
export function safeUrl(value: unknown): string | undefined {
  if (typeof value !== "string" || !value.trim()) return;
  try {
    const u = new URL(value);
    return ["https:", "http:"].includes(u.protocol) ? u.href : undefined;
  } catch {
    return;
  }
}
export function reportUrl(value: string): string {
  const u = new URL(value, document.baseURI);
  if (u.origin !== location.origin)
    throw new Error("Cross-origin report refused");
  return u.href;
}
export function text(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value))
    return value.map(text).filter(Boolean).join(" \u00b7 ");
  if (typeof value === "object")
    return Object.entries(value)
      .map(([k, v]) => `${k}: ${text(v)}`)
      .join("\n");
  return String(value);
}
export function date(value: string | null | undefined, locale: Locale) {
  if (!value) return "\u2014";
  const d = new Date(value);
  return Number.isNaN(d.valueOf())
    ? value
    : new Intl.DateTimeFormat(locale === "zh" ? "zh-CN" : "en", {
        year: "numeric",
        month: "short",
        day: "numeric",
      }).format(d);
}
export function action(value: unknown): string {
  return String(value || "not_recorded").toLowerCase();
}
export function navigate(id: string, tab = "overview") {
  location.hash = "/project/" + encodeURIComponent(id) + "/" + tab;
}
export function projectTitle(p: Project, locale: Locale) {
  return locale === "en" ? p.title_en : p.title;
}
