import dayjs from "dayjs";

export function isDaytime(time: string): boolean {
  try {
    const hour = dayjs(time).hour();
    return hour >= 6 && hour < 18;
  } catch {
    return true;
  }
}

/**
 * 根据天气图标代码获取对应的背景渐变类名
 */
export function getWeatherBackgroundClass(icon: string, styles: Record<string, string>): string {
  const iconNum = parseInt(icon, 10);

  // 晴天 (100, 150)
  if (iconNum === 100 || iconNum === 150) {
    return styles.bgSunny;
  }

  // 多云/少云/晴间多云 (101, 102, 103, 151, 152, 153)
  if ([101, 102, 103, 151, 152, 153].includes(iconNum)) {
    return styles.bgCloudy;
  }

  // 阴天 (104)
  if (iconNum === 104) {
    return styles.bgOvercast;
  }

  // 雨天 (300-399, 350-351)
  if ((iconNum >= 300 && iconNum <= 399) || iconNum === 350 || iconNum === 351) {
    return styles.bgRainy;
  }

  // 雪天 (400-499, 456-457)
  if ((iconNum >= 400 && iconNum <= 499) || iconNum === 456 || iconNum === 457) {
    return styles.bgSnowy;
  }

  // 雾/霾/沙尘 (500-515)
  if (iconNum >= 500 && iconNum <= 515) {
    return styles.bgFoggy;
  }

  // 热 (900)
  if (iconNum === 900) {
    return styles.bgHot;
  }

  // 冷 (901)
  if (iconNum === 901) {
    return styles.bgCold;
  }

  // 默认/未知 (999 或其他)
  return styles.bgDefault;
}

/**
 * 提取温度值和单位
 */
// 或者如果你想要更灵活的正则表达式（匹配更多格式）
export function extractTemperature(str: string): {
  value?: number;
  unit: string;
} {
  // 这个正则表达式更灵活，可以匹配更多格式
  const pattern = /(-?\d+(?:\.\d+)?)\s*([℃°C]|Celsius|centigrade)?/i;
  const match = str.match(pattern);

  if (!match) {
    return {
      value: undefined,
      unit: "",
    };
  }

  const value = parseFloat(match[1]);
  let unit = match[2] || null;

  // 标准化单位表示
  if (unit && (unit.toLowerCase() === "celsius" || unit.toLowerCase() === "centigrade")) {
    unit = "°C";
  }

  return { value, unit: unit || "°C" };
}
