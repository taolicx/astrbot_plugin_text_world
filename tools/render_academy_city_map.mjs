import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const htmlPath = path.join(root, "docs", "map-guide", "academy-city-map.html");
const outputDir = path.join(root, "docs", "map-guide");
const pluginMapDir = path.join(root, "assets", "maps");

const targets = [
  ["map-overview", "学园都市地图_总览.png"],
  ["map-routes", "学园都市地图_路线图.png"],
  ["map-inner", "学园都市地图_第七学区细节.png"],
];

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
});

try {
  const page = await browser.newPage({
    viewport: { width: 1780, height: 2500 },
    deviceScaleFactor: 2,
  });
  await page.goto(`file:///${htmlPath.replaceAll("\\", "/")}`, { waitUntil: "networkidle" });
  await page.evaluate(async () => {
    await document.fonts.ready;
  });

  for (const [id, filename] of targets) {
    const locator = page.locator(`#${id}`);
    const outPath = path.join(outputDir, filename);
    await locator.screenshot({
      path: outPath,
      animations: "disabled",
    });
    if (filename === "学园都市地图_路线图.png") {
      fs.mkdirSync(pluginMapDir, { recursive: true });
      fs.copyFileSync(outPath, path.join(pluginMapDir, "academy_city_route_map.png"));
    }
    console.log(filename);
  }
} finally {
  await browser.close();
}
