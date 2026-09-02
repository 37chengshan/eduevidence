import { state } from './state.js';

function getPagesBase() {
  // GitHub Pages project site lives under /eduevidence/; local dev is at /
  const path = window.location.pathname || "/";
  if (path.startsWith("/eduevidence/")) return "/eduevidence/";
  return "/";
}

function toStaticPath(path) {
  // /api/projects -> api/projects.json, /api/projects/<id>/viz -> api/projects/<id>/viz.json
  let s = path.replace(/^\/api\//, "api/").replace(/^api\//, "api/");
  if (s === "api/projects") return "api/projects.json";
  if (s === "api/labels") return "api/labels.json";
  if (s.startsWith("api/projects/") && s.endsWith("/viz")) return s + ".json";
  return s;
}
function staticUrl(path) {
  const base = getPagesBase();
  const rel = toStaticPath(path);
  // Use origin + base to avoid relative resolution under /studio/ subdir
  return window.location.origin + base + rel;
}

export function api(path) {
  if (state.dataCache[path]) return Promise.resolve(state.dataCache[path]);
  // Try live API first (dashboard_server), then fall back to static JSON for GitHub Pages
  return fetch(path).then(res => {
    if (!res.ok) throw new Error("HTTP " + res.status + " for " + path);
    return res.json();
  }).then(d => {
    state.dataCache[path] = d;
    return d;
  }).catch(err => {
    // Fallback: static JSON under /api/*.json (works on GitHub Pages)
    const fallback = staticUrl(path);
    if (fallback !== path) {
      return fetch(fallback).then(r => {
        if (!r.ok) throw err;
        return r.json();
      }).then(d => {
        state.dataCache[path] = d;
        return d;
      });
    }
    // Retry once for transient live-API errors (non-static mode)
    return fetch(path).then(res2 => {
      if (!res2.ok) throw err;
      return res2.json();
    }).then(d => {
      state.dataCache[path] = d;
      return d;
    });
  });
}
