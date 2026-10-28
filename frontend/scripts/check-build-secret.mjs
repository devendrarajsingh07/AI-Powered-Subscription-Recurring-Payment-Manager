// Build-only credential guard. Never print the value, file contents or provider responses.
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";

const credential = (process.env.GITHUB_RELEASE_READ_TOKEN || "").trim();
if (credential) {
  try {
    async function inspect(directory) {
      for (const entry of await readdir(directory, { withFileTypes: true })) {
        const path = join(directory, entry.name);
        if (entry.isSymbolicLink()) throw new Error("Unexpected build output link");
        if (entry.isDirectory()) await inspect(path);
        else if ((await readFile(path)).includes(Buffer.from(credential)))
          throw new Error("Build-only release credential found in compiled output");
      }
    }
    await inspect("dist");
    console.log("PASS build-only release credential absent from compiled output");
  } catch {
    console.error("Build blocked: compiled output credential check failed");
    process.exitCode = 1;
  }
} else {
  console.log("Build credential scan skipped: no release read credential configured");
}
