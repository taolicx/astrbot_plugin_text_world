import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const htmlPath = path.join(root, "docs", "map-guide", "academy-city-annotated-art-map.html");
const outputDir = path.join(root, "docs", "map-guide");

const targets = [
  ["annotated-overview", "学园都市地图_美术详细标注版_总览.png"],
  ["annotated-inner", "学园都市地图_美术详细标注版_第七学区.png"],
];

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
});

try {
  const page = await browser.newPage({
    viewport: { width: 1980, height: 2650 },
    deviceScaleFactor: 2,
  });
  await page.goto(`file:///${htmlPath.replaceAll("\\", "/")}`, { waitUntil: "networkidle" });
  await page.evaluate(async () => {
    await document.fonts.ready;
    await Promise.all([...document.images].map((img) => img.complete ? null : new Promise((resolve) => {
      img.addEventListener("load", resolve, { once: true });
      img.addEventListener("error", resolve, { once: true });
    })));
  });

  for (const [id, filename] of targets) {
    await page.locator(`#${id}`).screenshot({
      path: path.join(outputDir, filename),
      animations: "disabled",
    });
    console.log(filename);
  }
} finally {
  await browser.close();
}
