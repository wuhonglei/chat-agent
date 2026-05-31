import { WeatherIcon, renderIcon } from "../icons";
import type { ToolRendererRegistry } from "../types";

const weatherIcon = renderIcon(WeatherIcon);

export const weatherRenderers: ToolRendererRegistry[string] = {
  search_city: { icon: weatherIcon },
  get_current_weather: { icon: weatherIcon },
  get_weather_hourly_forecast: { icon: weatherIcon },
  get_weather_daily_forecast: { icon: weatherIcon },
  get_weather_alerts: { icon: weatherIcon },
};
