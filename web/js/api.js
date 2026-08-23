import { state } from './state.js';

export function api(path) {
  if (state.dataCache[path]) return Promise.resolve(state.dataCache[path]);
  return fetch(path).then(res => {
    if (!res.ok) throw new Error("HTTP " + res.status + " for " + path);
    return res.json();
  }).then(d => {
    state.dataCache[path] = d;
    return d;
  }).catch(err => {
    // Retry once
    return fetch(path).then(res2 => {
      if (!res2.ok) throw err;
      return res2.json();
    }).then(d => {
      state.dataCache[path] = d;
      return d;
    });
  });
}
