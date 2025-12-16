import { ComponentToolItem } from "@/interfaces";
import type { JSONSchema7 } from "json-schema";
import { WeatherNow } from "./components/Weather";

// WeatherNow 组件的 JSON Schema
const weatherNowSchema: JSONSchema7 = {
  type: "object",
  properties: {
    location: { type: "string", description: "位置信息" },
    data: {
      type: "object",
      description: "天气数据",
      properties: {
        obsTime: { type: "string" },
        temp: { type: "string" },
        feelsLike: { type: "string" },
        icon: { type: "string" },
        text: { type: "string" },
        wind360: { type: "string" },
        windDir: { type: "string" },
        windScale: { type: "string" },
        windSpeed: { type: "string" },
        humidity: { type: "string" },
        precip: { type: "string" },
        pressure: { type: "string" },
        vis: { type: "string" },
        cloud: { type: "string" },
        dew: { type: "string" },
        tempMin: { type: "string" },
        tempMax: { type: "string" },
      },
      required: [
        "obsTime",
        "temp",
        "feelsLike",
        "icon",
        "text",
        "wind360",
        "windDir",
        "windScale",
        "windSpeed",
        "humidity",
        "precip",
        "pressure",
        "vis",
        "cloud",
        "dew",
      ],
    },
    aqi: {
      type: "object",
      properties: {
        level: { type: "string" },
        category: { type: "string" },
        aqi: { type: "string" },
      },
    },
  },
  required: ["location", "data"],
};

const componentTools: ComponentToolItem[] = [
  {
    name: "weather_now",
    component: WeatherNow,
    schema: weatherNowSchema,
    when: {
      tool_names: ["weather"],
    },
  },
];

export default componentTools;
