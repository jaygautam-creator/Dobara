// Copies the committed evidence/demo JSON from ../artifacts into web/data/ (gitignored,
// regenerated every dev/build start). Server Components read from web/data/ directly via
// fs -- this script exists only so the Next.js app is self-contained at build time inside
// a Vercel "Root Directory: web" monorepo checkout, without duplicating the committed
// files a second time in git. Never imported by client code; nothing here reaches the
// browser bundle.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webDir = dirname(dirname(fileURLToPath(import.meta.url)));
const artifactsDir = join(webDir, "..", "artifacts");
const dataDir = join(webDir, "data");

const FILES = [
  "summary.json",
  "sensitivity.json",
  "recovery_model_report.json",
  "hazard_model_report.json",
  "money_chart_data.json",
  "demo_batch.json",
];

mkdirSync(dataDir, { recursive: true });

for (const name of FILES) {
  const src = join(artifactsDir, name);
  const dest = join(dataDir, name);
  if (!existsSync(src)) {
    throw new Error(
      `${src} not found -- run \`make eval\` / \`make demo-fixture\` from the repo root first.`,
    );
  }
  copyFileSync(src, dest);
}

console.log(`synced ${FILES.length} artifact files into web/data/`);
