export enum TitleCreatedBy {
  Default = "default",
  User = "user",
  LLM = "llm",
}

export const WEB_TITLE = import.meta.env.VITE_WEB_TITLE || "Ai Assistant";
