import type { ToolRendererRegistry } from "../types";

export const weatherRenderers: ToolRendererRegistry[string] = {
  search_city: {},
  get_current_weather: {},
  get_weather_hourly_forecast: {},
  get_weather_daily_forecast: {},
  get_weather_alerts: {},
};
