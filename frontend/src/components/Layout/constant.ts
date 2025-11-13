import dayjs from "dayjs";

export const dateGroups = [
  {
    label: "今天",
    value: dayjs().startOf("day"),
  },
  {
    label: "昨天",
    value: dayjs().subtract(1, "day").startOf("day"),
  },
  {
    label: "7 天内",
    value: dayjs().subtract(7, "day").startOf("day"),
  },
  {
    label: "1 个月内",
    value: dayjs().subtract(1, "month").startOf("day"),
  },
  {
    label: "1 年内",
    value: dayjs().subtract(1, "year").startOf("year"),
  },
  {
    label: "更早",
    value: dayjs().subtract(50, "year").startOf("year"),
  },
];
