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
await new Promise((done) => server.listen(0, "127.0.0.1", done));

const profile = mkdtempSync(join(tmpdir(), "a1-sprint3-chrome-"));
const chrome = spawn(CHROME, [
  "--headless=new", "--disable-gpu", "--no-first-run", "--hide-scrollbars",
  "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank",
], { windowsHide: true, stdio: "ignore" });
let socket;

async function ffmpeg(args) {
  await new Promise((done, reject) => {
    const process = spawn(FFMPEG, args, { windowsHide: true, stdio: "inherit" });
    process.once("error", reject);
    process.once("exit", (code) => code === 0 ? done() : reject(new Error(`ffmpeg terminou com ${code}`)));
  });
}

try {
  let port;
  for (let attempt = 0; attempt < 80; attempt += 1) {
    try { port = Number(readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0]); break; }
    catch { await sleep(100); }
  }
  if (!port) throw new Error("Chrome não iniciou.");
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
  socket = new WebSocket(targets.find((item) => item.type === "page").webSocketDebuggerUrl);
  await new Promise((done) => socket.addEventListener("open", done));

  const pending = new Map();
  const errors = [];
  let id = 0;
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.text);
    if (message.method === "Log.entryAdded" && message.params.entry.level === "error") errors.push(message.params.entry.text);
    if (pending.has(message.id)) {
      const { done, reject } = pending.get(message.id); pending.delete(message.id);
      message.error ? reject(new Error(JSON.stringify(message.error))) : done(message.result);
    }
  });
  function send(method, params = {}) {
    return new Promise((done, reject) => {
      const current = ++id;
      pending.set(current, { done, reject });
      socket.send(JSON.stringify({ id: current, method, params }));
    });
  }
  async function evaluate(expression) {
    const response = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (response.exceptionDetails) throw new Error(JSON.stringify(response.exceptionDetails));
    return response.result.value;
  }
  async function waitFor(expression) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      if (await evaluate(expression)) return;
      await sleep(100);
    }
    throw new Error(`Timeout: ${expression}`);
  }
  async function screenshot(path) {
    const { data } = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    const buffer = Buffer.from(data, "base64");
    writeFileSync(path, buffer);
    return buffer;
  }
  let frame = 0;
  function addFrames(buffer, count = 12) {
    for (let index = 0; index < count; index += 1) {
      writeFileSync(join(frames, `frame-${String(frame++).padStart(5, "0")}.png`), buffer);
    }
  }
  async function record(path, count = 15) { addFrames(await screenshot(path), count); }
  async function scrollTo(selector) {
    const start = await evaluate("window.scrollY");
    const target = await evaluate(`document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect().top + window.scrollY - 20`);
    for (let step = 1; step <= 10; step += 1) {
      await evaluate(`window.scrollTo(0, ${start} + (${target} - ${start}) * ${step / 10})`);
      await sleep(50);
      addFrames(await screenshot(join(frames, "transition.png")), 1);
    }
  }

  await send("Runtime.enable"); await send("Log.enable"); await send("Page.enable");
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "reduce" }] });
  await send("Emulation.setDeviceMetricsOverride", { width: 1366, height: 768, deviceScaleFactor: 1, mobile: false });
  const base = `http://127.0.0.1:${server.address().port}/frontend/?api=fake&scenario=NON_CONFORMING&fault=NONE`;
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
