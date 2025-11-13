export function validateTitle(newTitle: string, oldTitle: string): string {
  const trimmedNewTitle = newTitle.trim();

  if (!trimmedNewTitle) {
    return "标题不能为空";
  }

  if (trimmedNewTitle === oldTitle) {
    return "标题不能与原标题相同";
  }

  if (trimmedNewTitle.length > 30) {
    return "标题不能超过30个字符";
  }

  return "";
}
