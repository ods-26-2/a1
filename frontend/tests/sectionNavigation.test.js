import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { it } from "node:test";
import { setupSectionNavigation } from "../js/ui/sectionNavigation.js";

function fixture(hash = "") {
  const ids = ["history-title", "reports-title", "queue-title", "inspection-section-title"];
  const targets = Object.fromEntries(ids.map((id) => [id, { focused: 0, focus(options) { this.focused++; assert.equal(options.preventScroll, true); } }]));
  const links = ids.map((id) => ({ attrs: { href: `#${id}` }, handlers: {},
    getAttribute(key) { return this.attrs[key]; }, setAttribute(key, value) { this.attrs[key] = value; }, removeAttribute(key) { delete this.attrs[key]; },
    addEventListener(name, fn) { this.handlers[name] = fn; }, removeEventListener(name, fn) { if (this.handlers[name] === fn) delete this.handlers[name]; } }));
  const root = { querySelectorAll: () => links, getElementById: (id) => targets[id] ?? null };
  const browser = { location: { hash }, handlers: {}, addEventListener(name, fn) { this.handlers[name] = fn; }, removeEventListener(name, fn) { if (this.handlers[name] === fn) delete this.handlers[name]; } };
  return { root, browser, links, targets };
}

it("navegação inicial e voltar/avançar refletem a seção no aria-current", () => {
  const state = fixture("#history-title");
  const destroy = setupSectionNavigation(state.root, state.browser);
  assert.equal(state.links[0].attrs["aria-current"], "location");
  state.browser.location.hash = "#reports-title";
  state.browser.handlers.hashchange();
  assert.equal(state.links[0].attrs["aria-current"], undefined);
  assert.equal(state.links[1].attrs["aria-current"], "location");
  assert.ok(Object.values(state.targets).every((target) => target.focused === 0));
  destroy();
  assert.equal(state.browser.handlers.hashchange, undefined);
  assert.ok(state.links.every((link) => !link.handlers.click));
});

it("ativação por teclado/clique foca título sem bloquear a âncora nativa", () => {
  const state = fixture();
  setupSectionNavigation(state.root, state.browser);
  let prevented = false;
  state.links[0].handlers.click({ button: 0, preventDefault: () => { prevented = true; } });
  assert.equal(prevented, false);
  assert.equal(state.targets["history-title"].focused, 1);
  assert.equal(state.links[0].attrs["aria-current"], "location");
});

it("modificadores, hash inválido e destino ausente não roubam foco", () => {
  const state = fixture("#%bad");
  setupSectionNavigation(state.root, state.browser);
  assert.ok(state.links.every((link) => !link.attrs["aria-current"]));
  for (const event of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }, { defaultPrevented: true }]) state.links[0].handlers.click(event);
  assert.equal(state.targets["history-title"].focused, 0);
  delete state.targets["history-title"];
  state.links[0].handlers.click({ button: 0 });
  assert.ok(state.links.every((link) => !link.attrs["aria-current"]));
});

it("HTML fornece navegação nativa rotulada e destinos únicos focáveis sem depender de API", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
  const nav = html.match(/<nav id="section-navigation"[^>]*>([\s\S]*?)<\/nav>/);
  assert.ok(nav);
  assert.match(nav[0], /aria-label="Seções do A1"/);
  const targets = [...nav[1].matchAll(/href="#([^"]+)"/g)].map((match) => match[1]);
  assert.equal(targets.length, 4);
  const documentOrder = targets.map((id) => html.indexOf(`id="${id}"`));
  assert.deepEqual(documentOrder, [...documentOrder].sort((a, b) => a - b));
  for (const id of targets) {
    assert.equal([...html.matchAll(new RegExp(`id="${id}"`, "g"))].length, 1);
    assert.match(html, new RegExp(`<h2[^>]*id="${id}"[^>]*tabindex="-1"`));
  }
  const source = await readFile(new URL("../js/ui/sectionNavigation.js", import.meta.url), "utf8");
  assert.doesNotMatch(source, /fetch\(|innerHTML|import\s|\.submitReview\(|\.recordCause\(/);
});
