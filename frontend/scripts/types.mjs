import fs from "node:fs/promises";
import openapiTS, { astToString } from "openapi-typescript";

const schema =
  process.env.SUBTRACK_SCHEMA ||
  new URL("../../backend/openapi/openapi.json", import.meta.url);
const target = new URL("../src/api/schema.ts", import.meta.url);
const output =
  "// Generated from backend/openapi/openapi.json. Run make types; do not edit.\n" +
  astToString(await openapiTS(JSON.parse(await fs.readFile(schema, "utf8"))));
if (process.argv.includes("--check")) {
  if (
    (await fs.readFile(target, "utf8").catch(() => "")).replaceAll(
      "\r\n",
      "\n",
    ) !== output
  ) {
    throw new Error(
      "API types have drifted. Run make types and commit the generated file.",
    );
  }
} else {
  await fs.mkdir(new URL("../src/api/", import.meta.url), { recursive: true });
  await fs.writeFile(target, output);
}
