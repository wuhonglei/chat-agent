import { TitleCreatedBy } from "@/constants";

export function isTitleCreatedByDefault(createdBy: TitleCreatedBy | undefined) {
  return createdBy === TitleCreatedBy.Default;
}
