import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const htmlPath = path.join(root, "docs", "player-guide", "player-guide.html");
const outputDir = path.join(root, "docs", "player-guide");

const targets = [
  ["poster-complete", "玩家图文说明书_完整长图.png"],
  ["card-start", "玩家图文说明书_01_开局流程.png"],
  ["card-character", "玩家图文说明书_02_角色卡.png"],
  ["card-action", "玩家图文说明书_03_行动写法.png"],
  ["card-commands", "玩家图文说明书_04_指令速查.png"],
];

const browser = await chromium.launch({
  headless: true,
  executablePath: "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
});

try {
  const page = await browser.newPage({
    viewport: { width: 1220, height: 4200 },
    deviceScaleFactor: 2,
  });
  await page.goto(`file:///${htmlPath.replaceAll("\\", "/")}`, { waitUntil: "networkidle" });
  await page.evaluate(async () => {
    await document.fonts.ready;
  });

  for (const [id, filename] of targets) {
    const locator = page.locator(`#${id}`);
    await locator.screenshot({
      path: path.join(outputDir, filename),
      animations: "disabled",
    });
    console.log(filename);
  }
} finally {
  await browser.close();
}
