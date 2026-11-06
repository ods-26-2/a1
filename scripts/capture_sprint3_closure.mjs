// Atividade 31: grava uma demonstração real do frontend com a API fake explícita.
import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { extname, join, resolve, sep } from "node:path";
import { inspectionReady } from "./capture_readiness.mjs";

const CHROME = process.argv[2] ?? "C:/Program Files/Google/Chrome/Application/chrome.exe";
const FFMPEG = process.argv[3] ?? "ffmpeg";
const OUT = resolve(process.argv[4] ?? "docs/evidencias/atividade-31");
const CAPTURES = join(OUT, "capturas");
const VIDEOS = join(OUT, "videos");
const root = resolve(".");
const frames = mkdtempSync(join(tmpdir(), "a1-sprint3-video-"));
mkdirSync(CAPTURES, { recursive: true });
mkdirSync(VIDEOS, { recursive: true });

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png" };
const server = createServer((request, response) => {
  let pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
  if (pathname === "/favicon.ico") { response.writeHead(204); response.end(); return; }
  if (pathname.endsWith("/")) pathname += "index.html";
  const path = resolve(root, `.${pathname}`);
  if (!path.startsWith(root + sep)) { response.writeHead(403); response.end(); return; }
  try { response.setHeader("Content-Type", mime[extname(path)] ?? "application/octet-stream"); response.end(readFileSync(path)); }
  catch { response.writeHead(404); response.end(); }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done…1017 tokens truncated…nario=NON_CONFORMING&fault=NONE`;
  await send("Page.navigate", { url: base });
  await waitFor(`(${inspectionReady.toString()})(document)`);
  addFrames(await screenshot(join(frames, "initial.png")), 12);

  await scrollTo("#history-title");
  await evaluate(`(() => { const form=document.querySelector('#history-filters'); form.elements.namedItem('captured_from').value='2026-10-01T00:00'; form.elements.namedItem('captured_to').value='2026-10-31T00:00'; form.elements.namedItem('result').value='NON_CONFORMING'; form.requestSubmit(); })()`);
  await waitFor(`document.querySelector('#history-summary').textContent.startsWith('1 inspeção')`);
  await record(join(CAPTURES, "01-historico-filtrado.png"));

  await scrollTo("#reports-title");
  await evaluate(`document.querySelector('#report-kind').value='recurrence'; document.querySelector('#report-generate').click()`);
  await waitFor(`document.querySelector('#report-summary').textContent.includes('inspeção(ões) no período') && document.querySelector('#report-results').textContent.length > 20`);
  await record(join(CAPTURES, "02-recorrencia.png"));

  await evaluate(`(() => { const details=document.querySelector('#cause-form').closest('details'); details.open=true; document.querySelector('#cause-use-current').click(); const form=document.querySelector('#cause-form'); form.elements.namedItem('operator').value='op-demonstracao'; form.elements.namedItem('cause').value='Alinhamento observado'; form.elements.namedItem('basis').value='Posição conferida manualmente na demonstração local.'; form.requestSubmit(); })()`);
  await waitFor(`document.querySelector('#cause-feedback').textContent.includes('Hipótese registrada')`);
  await evaluate(`document.querySelector('#report-kind').value='inspection'; document.querySelector('#report-kind').dispatchEvent(new Event('change')); document.querySelector('#report-generate').click()`);
  await waitFor(`document.querySelector('#report-results').textContent.includes('Causa provável declarada')`);
  await record(join(CAPTURES, "03-inspecao-causa.png"), 20);

  await ffmpeg(["-y", "-loglevel", "error", "-framerate", "10", "-i", join(frames, "frame-%05d.png"),
    "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    join(VIDEOS, "demonstracao-frontend.mp4")]);

  await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await evaluate(`document.querySelector('#reports-title').scrollIntoView({block:'start'})`);
  await sleep(200);
  await screenshot(join(CAPTURES, "04-mobile-relatorio.png"));
  const overflow = await evaluate("document.documentElement.scrollWidth > window.innerWidth");
  if (overflow) throw new Error("Overflow horizontal em 390px.");
  if (errors.length) throw new Error(`Erros no navegador: ${errors.join(" | ")}`);

  const files = ["01-historico-filtrado.png", "02-recorrencia.png", "03-inspecao-causa.png", "04-mobile-relatorio.png"];
  const report = {
    activity: 31, mode: "FAKE", persisted: false,
    checks: ["histórico filtrado", "recorrência", "causa declarada", "relatório de inspeção", "layout mobile sem overflow", "vídeo H.264"],
    browser_errors: errors,
    captures: files,
    video: "videos/demonstracao-frontend.mp4",
    sha256: Object.fromEntries(files.map((name) => [name, createHash("sha256").update(readFileSync(join(CAPTURES, name))).digest("hex")])),
    limits: ["API fake explícita", "causa sem persistência", "não demonstra inferência, S4 ou P7 reais"],
  };
  writeFileSync(join(OUT, "browser-check.json"), JSON.stringify(report, null, 2) + "\n");
  console.log(`Atividade 31: ${files.length} capturas e ${frame} quadros de vídeo aprovados.`);
} finally {
  socket?.close(); chrome.kill(); server.closeAllConnections(); server.close();
}
