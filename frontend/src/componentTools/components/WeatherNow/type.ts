/**
 * 和风天气实时天气数据接口
 * 参考文档: https://dev.qweather.com/docs/api/weather/weather-now/
 */
export interface WeatherNowData {
  /** 观测时间 */
  obsTime: string;
  /** 温度 */
  temp: string;
  /** 体感温度 */
  feelsLike: string;
  /** 天气图标代码 */
  icon: string;
  /** 天气状况文字描述 */
  text: string;
  /** 风向360度 */
  wind360: string;
  /** 风向 */
  windDir: string;
  /** 风力等级 */
  windScale: string;
  /** 风速 */
  windSpeed: string;
  /** 相对湿度 */
  humidity: string;
  /** 降水量 */
  precip: string;
  /** 大气压强 */
  pressure: string;
  /** 能见度 */
  vis: string;
  /** 云量 */
  cloud: string;
  /** 露点温度 */
  dew: string;
  /** 最低温度 */
  tempMin?: string;
  /** 最高温度 */
  tempMax?: string;
}

/**
 * 天气组件 Props
 */
export interface WeatherNowProps {
  /** 位置信息 */
  location: string;
  /** 天气数据 */
  data: WeatherNowData;
  /** 空气质量指数（可选） */
  aqi?: {
    /** 空气质量等级 */
    level: string;
    /** 空气质量类别 */
    category: string;
    /** 空气质量指数 */
    aqi: string;
  };
}
