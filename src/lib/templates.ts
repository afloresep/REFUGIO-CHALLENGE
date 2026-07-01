import { readFile } from "node:fs/promises";
import path from "node:path";

export type Template = {
  description: string;
  filename: string;
  label: string;
  source: string;
};

const templateMetadata = [
  {
    description: "The public submission contract example from the submit page.",
    filename: "starter-policy.py",
    label: "Starter policy",
  },
  {
    description: "Canonical rack blocks: dense two-wide columns and regular service aisles.",
    filename: "canonical-rack-blocks.py",
    label: "Canonical rack blocks",
  },
  {
    description: "Wide avenues: taller rack walls with broad north-south corridors.",
    filename: "wide-avenues.py",
    label: "Wide avenues",
  },
] as const;

export async function getTemplates(): Promise<Template[]> {
  return Promise.all(
    templateMetadata.map(async (template) => {
      const source = await readFile(path.join(process.cwd(), "templates", template.filename), "utf8");

      return {
        ...template,
        source,
      };
    }),
  );
}
