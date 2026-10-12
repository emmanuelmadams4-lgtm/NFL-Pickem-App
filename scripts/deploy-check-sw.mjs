// Used by deploy-check.sh: opens the page in headless Chromium and checks the service worker registers
// inside the manifest scope. 127.0.0.1 counts as a secure context, so this stands in for HTTPS.
//   node scripts/deploy-check-sw.mjs <base url> <access token>
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { chromium } from "playwright-core";

// The pinned playwright-core may want a browser build that is not installed. Use the newest installed headless shell instead.
function installedChromium() {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? join(homedir(), process.platform === "darwin" ? "Library/Caches/ms-playwright" : ".cache/ms-playwright");
  if (!existsSync(root)) return undefined;
  const shells = readdirSync(root).filter((d) => d.startsWith("chromium_headless_shell-")).sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
  for (const dir of shells) {
    for (const sub of readdirSync(join(root, dir)).filter((d) => d.startsWith("chrome-"))) {
      const bin = join(root, dir, sub, process.platform === "win32" ? "chrome-headless-shell.exe" : "chrome-headless-shell");
      if (existsSync(bin)) return bin;
    }
  }
  return undefined;
}

const [base, token] = process.argv.slice(2);
const browser = await chromium.launch().catch(() => chromium.launch({ executablePath: installedChromium() }));
try {
  const context = await browser.newContext();
  await context.addInitScript((t) => {
    try {
      localStorage.setItem("nflpi_token", t);
    } catch {}
  }, token);
  const page = await context.newPage();
  await page.goto(base, { waitUntil: "load" });
  const scope = await page.evaluate(
    () => Promise.race([
      navigator.serviceWorker.ready.then((r) => r.scope),
      new Promise((_, no) => setTimeout(() => no(new Error("no service worker after 20 s")), 20000)),
    ]),
  );
  const manifest = await (await fetch(`${base}/manifest.webmanifest`)).json();
  const want = new URL(manifest.scope ?? manifest.start_url ?? "/", base).href;
  if (!want.startsWith(scope) && !scope.startsWith(want)) throw new Error(`worker scope ${scope} is outside manifest scope ${want}`);
  console.log(`service worker scope ${scope}, manifest scope ${want}`);
} catch (error) {
  console.error(String(error));
  process.exitCode = 1;
} finally {
  await browser.close();
}
