import dayjs from "dayjs";

/**
 * 返回当前时间，格式为 '2025-11-07T10:29:50+08:00'
 */
export function getDatetimeNow(): string {
  return dayjs().format(); // '2025-11-07T10:29:50+08:00'
}
