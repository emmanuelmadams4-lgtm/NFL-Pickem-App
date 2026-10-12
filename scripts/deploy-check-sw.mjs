// Used by deploy-check.sh: opens the page in headless Chromium and checks the service worker registers
// inside the manifest scope. 127.0.0.1 counts as a secure context, so this stands in for HTTPS.
//   node scripts/deploy-check-sw.mjs <base url> <access token>
import { chromium } from "playwright-core";

const [base, token] = process.argv.slice(2);
const browser = await chromium.launch();
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
