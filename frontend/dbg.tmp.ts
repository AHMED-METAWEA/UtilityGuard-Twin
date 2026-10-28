const real = globalThis.fetch;
globalThis.fetch = ((u: string, i: RequestInit) => { console.log("GET", u); return real("http://127.0.0.1:8080" + u, i); }) as typeof fetch;
const { loadReplay } = await import("./src/app/api.ts");
const r = await loadReplay();
console.log("reason:", r.reason, "| run:", r.replay?.runId, "| series:", r.replay?.series.length);
