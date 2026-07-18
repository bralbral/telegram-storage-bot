import { createServer } from "node:http";
import { promises as dns } from "node:dns";
import { isIP } from "node:net";
import { createReadStream } from "node:fs";
import { mkdir, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { chromium } from "playwright-core";

const SNAPSHOT_DIR = "/snapshots";
const PORT = Number(process.env.PORT || 3000);
const PAGE_TIMEOUT = Number(process.env.PAGE_TIMEOUT_MS || 45000);
const execFileAsync = promisify(execFile);

function isPrivateAddress(address) {
  if (address === "::1" || address === "0.0.0.0") return true;
  if (address.includes(":")) {
    const value = address.toLowerCase();
    return value.startsWith("fc") || value.startsWith("fd") || value.startsWith("fe80:") || value.startsWith("::ffff:127.");
  }
  const [a, b] = address.split(".").map(Number);
  return a === 10 || a === 127 || a === 0 || (a === 169 && b === 254) || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168);
}

async function assertPublicUrl(value) {
  const url = new URL(value);
  if (!["http:", "https:"].includes(url.protocol) || !url.hostname) throw new Error("Only complete http(s) URLs are allowed");
  if (url.username || url.password || url.hostname === "localhost") throw new Error("This host is not allowed");
  const addresses = isIP(url.hostname) ? [{ address: url.hostname }] : await dns.lookup(url.hostname, { all: true });
  if (!addresses.length || addresses.some(({ address }) => isPrivateAddress(address))) throw new Error("Private network addresses are not allowed");
}

function safeName(title) {
  const normalized = (title || "web-page").replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_").trim();
  return (normalized || "web-page").slice(0, 100);
}

async function createSnapshot(url) {
  await assertPublicUrl(url);
  const jobId = randomUUID();
  const jobDir = path.join(SNAPSHOT_DIR, jobId);
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_EXECUTABLE_PATH || "/usr/bin/chromium-browser",
    args: ["--disable-dev-shm-usage", "--disable-gpu"],
  });
  try {
    await mkdir(jobDir, { recursive: true });
    const context = await browser.newContext({ acceptDownloads: false });
    const page = await context.newPage();
    page.setDefaultNavigationTimeout(PAGE_TIMEOUT);
    await page.route("**/*", async (route) => {
      try {
        await assertPublicUrl(route.request().url());
        await route.continue();
      } catch {
        await route.abort();
      }
    });
    await page.goto(url, { waitUntil: "networkidle" });
    await page.evaluate(async () => {
      for (const image of document.images) image.loading = "eager";
      const step = Math.max(window.innerHeight, 800);
      for (let index = 0; index < 30; index += 1) {
        const height = document.documentElement.scrollHeight;
        window.scrollTo(0, Math.min(height, (index + 1) * step));
        await new Promise((resolve) => setTimeout(resolve, 150));
        if (window.scrollY + window.innerHeight >= document.documentElement.scrollHeight) break;
      }
      window.scrollTo(0, 0);
      await Promise.all([...document.images].map((image) => {
        if (image.complete) return Promise.resolve();
        return new Promise((resolve) => {
          image.addEventListener("load", resolve, { once: true });
          image.addEventListener("error", resolve, { once: true });
          setTimeout(resolve, 10_000);
        });
      }));
      await document.fonts?.ready;
    });
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});
    const htmlName = `${safeName(await page.title())}.html`;
    const mhtmlPath = path.join(jobDir, "page.mhtml");
    const cdp = await context.newCDPSession(page);
    const { data: mhtml } = await cdp.send("Page.captureSnapshot", { format: "mhtml" });
    await writeFile(mhtmlPath, mhtml, "utf8");
    await cdp.detach();
    await execFileAsync(
      "node",
      [
        "./node_modules/mhtml-to-html/mhtml-to-html-node.js",
        mhtmlPath,
        "--output",
        path.join(jobDir, htmlName),
      ],
      { timeout: PAGE_TIMEOUT, maxBuffer: 1024 * 1024 },
    );
    await rm(mhtmlPath, { force: true });
    await context.close();
    return {
      jobId,
      artifacts: [
        { path: `${jobId}/${htmlName}`, filename: htmlName, file_type: "web_html", size: (await stat(path.join(jobDir, htmlName))).size }
      ]
    };
  } catch (error) {
    await rm(jobDir, { recursive: true, force: true });
    throw error;
  } finally {
    await browser.close();
  }
}

function artifactPath(jobId, filename) {
  if (!/^[0-9a-f-]{36}$/.test(jobId) || path.basename(filename) !== filename) return null;
  return path.join(SNAPSHOT_DIR, jobId, filename);
}

async function sendArtifact(response, jobId, filename) {
  const filePath = artifactPath(jobId, filename);
  if (!filePath) return sendJson(response, 404, { error: "Not found" });
  try {
    const file = await stat(filePath);
    if (!file.isFile()) return sendJson(response, 404, { error: "Not found" });
    response.writeHead(200, { "content-length": file.size, "content-type": "application/octet-stream" });
    createReadStream(filePath).pipe(response);
  } catch {
    sendJson(response, 404, { error: "Not found" });
  }
}

async function deleteSnapshot(response, jobId) {
  if (!/^[0-9a-f-]{36}$/.test(jobId)) return sendJson(response, 404, { error: "Not found" });
  await rm(path.join(SNAPSHOT_DIR, jobId), { recursive: true, force: true });
  sendJson(response, 204, {});
}

function sendJson(response, status, body) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(body));
}

createServer(async (request, response) => {
  const pathname = new URL(request.url, "http://localhost").pathname;
  if (request.method === "GET" && pathname === "/health") return sendJson(response, 200, { status: "ok" });
  const artifactMatch = pathname.match(/^\/artifacts\/([0-9a-f-]{36})\/([^/]+)$/);
  if (request.method === "GET" && artifactMatch) return sendArtifact(response, artifactMatch[1], decodeURIComponent(artifactMatch[2]));
  const snapshotMatch = pathname.match(/^\/snapshots\/([0-9a-f-]{36})$/);
  if (request.method === "DELETE" && snapshotMatch) return deleteSnapshot(response, snapshotMatch[1]);
  if (request.method !== "POST" || pathname !== "/snapshot") return sendJson(response, 404, { error: "Not found" });
  let body = "";
  for await (const chunk of request) {
    body += chunk;
    if (body.length > 10_000) return sendJson(response, 413, { error: "Request is too large" });
  }
  try {
    const { url } = JSON.parse(body);
    if (typeof url !== "string") throw new Error("url is required");
    sendJson(response, 200, await createSnapshot(url));
  } catch (error) {
    sendJson(response, 400, { error: error instanceof Error ? error.message : "Snapshot failed" });
  }
}).listen(PORT, "0.0.0.0");
