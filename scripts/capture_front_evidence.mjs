// Captura as evidências visuais de S3-03 com Chrome headless via CDP.
// Uso (com o frontend servido em http://localhost:5500):
//   node scripts/capture_front_evidence.mjs [chrome.exe] [base-url]
// Saída: docs/evidencias/s3-03/*.png
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const CHROME =
  process.argv[2] ?? "C:/Program Files/Google/Chrome/Application/chrome.exe";
const BASE = process.argv[3] ?? "http://localhost:5500/frontend/";
const OUT = resolve("docs/evidencias/s3-03");
const PORT = 9333;

const SHOTS = [
  { name: "01-resultado-conforming", query: "scenario=CONFORMING&fault=NONE" },
  { name: "01-resultado-non-conforming", query: "scenario=NON_CONFORMING&fault=NONE" },
  { name: "01-resultado-anomaly", query: "scenario=ANOMALY&fault=NONE" },
  { name: "01-resultado-uncertain", query: "scenario=UNCERTAIN&fault=NONE" },
  { name: "02-falha-api-offline", query: "scenario=CONFORMING&fault=OFFLINE" },
  { name: "02-falha-s4-indisponivel", query: "scenario=NON_CONFORMING&fault=S4_UNAVAILABLE" },
  { name: "02-falha-contrato-invalido", query: "scenario=CONFORMING&fault=INVALID_CONTRACT" },
  { name: "02-carregando-api-lenta", query: "scenario=CONFORMING&fault=SLOW", waitMs: 600 },
  {
    name: "04-revisao-operador",
    query: "scenario=NON_CONFORMING&fault=NONE",
    action: `document.querySelector('#operator-id').value = 'op-samuel';
             document.querySelector('#send-review').click();`,
  },
  { name: "03-mobile-390-nao-conforme", query: "scenario=NON_CONFORMING&fault=NONE", width: 390, height: 844 },
  { name: "03-desktop-1920-incerto", query: "scenario=UNCERTAIN&fault=NONE", width: 1920, height: 1080 },
];

const sleep = (ms) => new Promise((done) => setTimeout(done, ms));

async function connect() {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    try {
      const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
      const page = targets.find((target) => target.type === "page");
      if (page) {
        return page.webSocketDebuggerUrl;
      }
    } catch {
      // Chrome ainda iniciando.
    }
    await sleep(200);
  }
  throw new Error("Chrome não abriu a porta de depuração.");
}

function client(url) {
  const socket = new WebSocket(url);
  const pending = new Map();
  let nextId = 0;

  socket.addEventListener("message", ({ data }) => {
    const message = JSON.parse(data);
    pending.get(message.id)?.(message);
    pending.delete(message.id);
  });

  return new Promise((ready) =>
    socket.addEventListener("open", () =>
      ready({
        send(method, params = {}) {
          const id = ++nextId;
          socket.send(JSON.stringify({ id, method, params }));
          return new Promise((done) => pending.set(id, done));
        },
        close: () => socket.close(),
      }),
    ),
  );
}

const profile = mkdtempSync(join(tmpdir(), "a1-evidence-"));
const chrome = spawn(CHROME, [
  "--headless=new",
  "--disable-gpu",
  "--hide-scrollbars",
  `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${profile}`,
  "about:blank",
]);

try {
  mkdirSync(OUT, { recursive: true });
  const cdp = await client(await connect());
  await cdp.send("Page.enable");
  await cdp.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });

  for (const shot of SHOTS) {
    const width = shot.width ?? 1366;
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width,
      height: shot.height ?? 768,
      deviceScaleFactor: 1,
      mobile: width < 768,
    });
    await cdp.send("Page.navigate", { url: `${BASE}?${shot.query}` });
    await sleep(shot.waitMs ?? 1500);
    if (shot.action) {
      await cdp.send("Runtime.evaluate", { expression: shot.action });
      await sleep(1000);
    }
    const { result } = await cdp.send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
    });
    writeFileSync(join(OUT, `${shot.name}.png`), Buffer.from(result.data, "base64"));
    console.log(`ok ${shot.name}`);
  }
  cdp.close();
} finally {
  chrome.kill();
}
