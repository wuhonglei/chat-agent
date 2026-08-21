import { describe, expect, it } from "vite-plus/test";

import { parseSkillContent } from "./parseSkillContent";

describe("parseSkillContent", () => {
  it("keeps xml framing and extracts markdown body", () => {
    const content = [
      '<skill_content name="demo">',
      "<skill_resources>",
      "Base directory for this skill: /mnt/skills/public/demo",
      "</skill_resources>",
      "",
      "<skill_instructions>",
      "# Hello",
      "",
      "Body text",
      "</skill_instructions>",
      "</skill_content>",
    ].join("\n");

    const parsed = parseSkillContent(content);
    expect(parsed).not.toBeNull();
    expect(parsed?.prefix).toContain('<skill_content name="demo">');
    expect(parsed?.prefix).toContain("<skill_instructions>\n");
    expect(parsed?.body).toBe("# Hello\n\nBody text");
    expect(parsed?.suffix).toContain("</skill_instructions>");
    expect(parsed?.suffix).toContain("</skill_content>");
  });

  it("returns null for legacy bare markdown", () => {
    expect(parseSkillContent("# Just markdown")).toBeNull();
  });
});
