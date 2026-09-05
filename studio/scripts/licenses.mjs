import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
const require = createRequire(import.meta.url);
const packages = [
  "react",
  "react-dom",
  "scheduler",
  "@tanstack/react-query",
  "@tanstack/query-core",
  "lucide-react",
];
let output = "EduEvidence Research Studio - runtime dependency notices\n\n";
for (const name of packages) {
  let directory = path.dirname(require.resolve(name));
  while (
    !existsSync(path.join(directory, "package.json")) &&
    path.dirname(directory) !== directory
  )
    directory = path.dirname(directory);
  let metadata = JSON.parse(
    readFileSync(path.join(directory, "package.json"), "utf8"),
  );
  while (metadata.name !== name && path.dirname(directory) !== directory) {
    directory = path.dirname(directory);
    if (existsSync(path.join(directory, "package.json")))
      metadata = JSON.parse(
        readFileSync(path.join(directory, "package.json"), "utf8"),
      );
  }
  if (metadata.name !== name)
    throw new Error(`Package metadata unavailable: ${name}`);
  const license = ["LICENSE", "LICENSE.txt", "LICENSE.md"]
    .map((f) => path.join(directory, f))
    .find(existsSync);
  if (!license) throw new Error(`License unavailable: ${name}`);
  output += `${name} ${metadata.version}\n${"=".repeat(70)}\n${readFileSync(license, "utf8")}\n\n`;
}
writeFileSync("../web/studio/THIRD_PARTY_LICENSES.txt", output);
