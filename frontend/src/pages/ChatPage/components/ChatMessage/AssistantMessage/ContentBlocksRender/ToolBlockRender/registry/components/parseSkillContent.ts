const SKILL_INSTRUCTIONS_RE =
  /^(?<prefix>[\s\S]*?<skill_instructions>\n?)(?<body>[\s\S]*?)(?<suffix>\n?<\/skill_instructions>[\s\S]*)$/;

export type ParsedSkillContent = {
  prefix: string;
  body: string;
  suffix: string;
};

/** Split load_skill XML so framing stays raw and instructions body can use Markdown. */
export function parseSkillContent(content: string): ParsedSkillContent | null {
  const match = SKILL_INSTRUCTIONS_RE.exec(content);
  if (!match?.groups) {
    return null;
  }
  const { prefix, body, suffix } = match.groups;
  if (prefix == null || body == null || suffix == null) {
    return null;
  }
  return { prefix, body, suffix };
}
