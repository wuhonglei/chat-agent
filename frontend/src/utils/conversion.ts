import { TitleCreatedBy } from "@/constants";

export function isTitleCreatedByDefault(createdBy: TitleCreatedBy | undefined) {
  return createdBy === TitleCreatedBy.Default;
}

export function isConversationNotFound(
  code: number,
  api: string | undefined
): boolean {
  return code === 404 && (api || "").startsWith("/conversation/detail/");
}

export function isUserDetailApi(api: string | undefined): boolean {
  return (api || "").startsWith("/user/detail");
}
