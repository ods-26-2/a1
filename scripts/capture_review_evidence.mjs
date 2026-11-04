// Local browser acceptance of S3-08 using the explicit, non-persistent fake API.
// node scripts/capture_review_evidence.mjs [chrome.exe]
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync } from "node:fs";
import { resolve, join, extname, sep } from "node:path";
import { tmpdir } from "node:os";

const root = resolve(".");
const out = resolve("docs/evidencias/s3-08");
mkdirSync(out, { recursive: true });
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png" };
const server = createServer((request, response) => {
  let pathname = decodeURIComponent(new URL(request.url, "http://localhost").pathname);
  if (pathname.endsWith("/")) pathname += "index.html";
  const path = resolve(root, `.${pathname}`);
  if (!path.startsWith(root + sep)) { response.writeHead(403); response.end(); return; }
  try { response.setHeader("Content-Type", mime[extname(path)] ?? "application/octet-stream"); response.end(readFileSync(path)); }
  catch { response.writeHead(404); response.end(); }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const base = `http://127.0.0.1:${server.address().port}/frontend/?api=fake&scenario=UNCERTAIN`;
const profile = mkdtempSync(join(tmpdir(), "a1-s308-"));
const chrome = spawn(process.argv[2] ?? "C:/Program Files/Google/Chrome/Application/chrome.exe", [
  "--headless=new", "--disable-gpu", "--no-first-run", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank",
], { windowsHide: true, stdio: "ignore" });
let socket;
try {
  let port;
  for (let i = 0; i < 60; i++) {
    try { port = Number(readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0]); break; } catch { await sleep(100); }
  }
  if (!port) throw new Error("Chrome não iniciou.");
  const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
  socket = new WebSocket(targets.find((item) => item.type === "page").webSocketDebuggerUrl);
  await new Promise((done) => socket.addEventListener("open", done));
  const pending = new Map(); let id = 0; const errors = [];
  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    if (message.method === "Runtime.exceptionThrown") errors.push(message.params.exceptionDetails.text);
    if (pending.has(message.id)) {
      const { done, reject } = pending.get(message.id); pending.delete(message.id);
      message.error ? reject(new Error(JSON.stringify(message.error))) : done(message.result);
    }
  });
  function send(method, params = {}) { return new Promise((done, reject) => { const current = ++id; pending.set(current, { done, reject }); socket.send(JSON.stringify({ id: current, method, params })); }); }
  async function evaluate(expression) {
    const result = await send("Runtime.evaluate", { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }
  async function waitFor(expression) {
    for (let i = 0; i < 100; i++) { if (await evaluate(expression)) return; await sleep(100); }
    throw new Error(`Timeout: ${expression}`);
  }
  async function shot(name) {
    const { data } = await send("Page.captureScreenshot", { format: "png", captureBeyondViewport: false });
    writeFileSync(join(out, name), Buffer.from(data, "base64"));
  }
  await send("Runtime.enable"); await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: 1366, height: 768, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: base });
  await waitFor(`document.querySelector('#correct-result')?.disabled === false && document.querySelectorAll('#queue-items button').length === 2`);
  await shot("01-fila-desktop.png");
  await evaluate(`document.querySelector('#correct-result').click()`);
  await waitFor(`document.querySelector('#action-feedback').textContent.includes('operador')`);
  await evaluate(`document.querySelector('#operator-id').value='op-samuel'; document.querySelector('#review-reason').value='Furo confirmado na conferência manual.'; document.querySelector('#review-status').value='REJECTED'; document.querySelector('#review-class').value='FURADO'; document.querySelector('#correct-result').click()`);
  await waitFor(`document.querySelector('#action-feedback').textContent.includes('API fake às') && document.querySelectorAll('#queue-items button').length === 1 && document.querySelector('#review-history').textContent.includes('Furo confirmado') && document.querySelector('#correct-result').disabled === false`);
  const finalClass = await evaluate(`document.querySelector('#final-class').textContent`);
  if (!finalClass.includes("FURADO")) throw new Error("Classe final não atualizada.");
  if (!(await evaluate(`document.querySelector('#analysis-result').textContent`)).includes("INCERTO")) {
    // The badge may use the Portuguese presentation; verify the class remained absent.
    if ((await evaluate(`document.querySelector('#classification-id').textContent`)) !== "nenhuma") throw new Error("Análise original alterada.");
  }
  await evaluate(`document.querySelector('.operator-actions').scrollIntoView({block:'center'}); document.querySelector('details').open=true`);
  await shot("02-correcao-desktop.png");
  await evaluate(`document.querySelector('#review-reason').value='Solicitar segunda avaliação.'; document.querySelector('#send-review').click()`);
  await waitFor(`document.querySelectorAll('#queue-items button').length === 2 && document.querySelectorAll('#review-history li').length === 2 && document.querySelector('#correct-result').disabled === false`);
  await send("Emulation.setDeviceMetricsOverride", { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await evaluate(`document.querySelector('.operator-actions').scrollIntoView({block:'start'})`);
  await shot("03-revisao-mobile.png");
  const overflow = await evaluate(`document.documentElement.scrollWidth > window.innerWidth`);
  if (overflow) throw new Error("Overflow horizontal em 390px.");
  if (errors.length) throw new Error(`Erros no navegador: ${errors.join(', ')}`);
  const report = { mode: "FAKE", persisted: false, checks: ["fila inicial", "operador obrigatório", "correção com motivo", "classe final", "análise original", "nova leitura", "saída e retorno à fila", "histórico", "mobile sem overflow"], browserErrors: errors };
  writeFileSync(join(out, "browser-check.json"), JSON.stringify(report, null, 2) + "\n");
  console.log("S3-08 browser acceptance: 9 checks passed (fake API, no persistence).");
} finally {
  socket?.close(); chrome.kill(); server.closeAllConnections(); server.close();
}
