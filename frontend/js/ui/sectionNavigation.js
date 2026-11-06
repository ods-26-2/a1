// Original A1 implementation of the useful navigation behavior evaluated in
// B6 AppShell. No B6 source/styles/dependencies copied; see activity 27 evidence.
export function setupSectionNavigation(root = document, browser = window) {
  const links = [...root.querySelectorAll("#section-navigation a[href^='#']")];
  const targetId = (hash) => {
    try { return decodeURIComponent(hash.replace(/^#/, "")); }
    catch { return ""; }
  };
  function sync(hash = browser.location.hash) {
    const id = targetId(hash);
    for (const link of links) {
      const linked = targetId(link.getAttribute("href"));
      if (id && id === linked && root.getElementById(id)) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
  }
  const handlers = links.map((link) => {
    const activate = (event) => {
      if (event.defaultPrevented || event.button > 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const hash = link.getAttribute("href"), target = root.getElementById(targetId(hash));
      if (!target) return;
      sync(hash);
      target.focus({ preventScroll: true });
      // Native anchor navigation retains URL/history, scrolling and no-JS support.
    };
    link.addEventListener("click", activate);
    return [link, activate];
  });
  const changed = () => sync();
  browser.addEventListener("hashchange", changed);
  sync();
  return () => {
    for (const [link, handler] of handlers) link.removeEventListener("click", handler);
    browser.removeEventListener("hashchange", changed);
  };
}
