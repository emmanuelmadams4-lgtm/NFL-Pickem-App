import { readFile, writeFile } from "node:fs/promises";

try {
  const id = (await readFile(new URL("../.next/BUILD_ID", import.meta.url), "utf8")).trim();
  if (!/^[A-Za-z0-9._-]{6,}$/.test(id)) throw new Error(".next/BUILD_ID is missing or invalid");
  const path = new URL("../out/sw.js", import.meta.url);
  const worker = await readFile(path, "utf8");
  if (!worker.includes('const BUILD_ID = "__BUILD_ID__";')) throw new Error("out/sw.js is missing the build ID placeholder");
  await writeFile(path, worker.replaceAll("__BUILD_ID__", id));
} catch (error) {
  console.error(`Could not stamp service worker: ${error.message}`);
  process.exitCode = 1;
}
