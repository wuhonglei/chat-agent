import { formatTime, reportError } from "@/utils";
import styles from "./index.module.css";
import daytimeStyles from "./theme/daytime.module.css";
import nighttimeStyles from "./theme/night.module.css";
import type { WeatherNowProps } from "./type";
import { getWeatherBackgroundClass, isDaytime } from "./utils";

export default function WeatherNow({ data, location }: WeatherNowProps) {
  const { temp, icon, text, obsTime } = data;
  const bgStyles = isDaytime(obsTime) ? daytimeStyles : nighttimeStyles;
  const backgroundClass = getWeatherBackgroundClass(icon, bgStyles);

  function handleIconError(e: React.SyntheticEvent<HTMLImageElement>) {
    e.currentTarget.remove();
    reportError("Weather Icon Error", {
      icon,
    });
  }

  return (
    <div className={`${styles.container} ${backgroundClass}`}>
      {/* 位置 */}
      <div className={styles.location}>{location}</div>

      {/* 当前温度和天气描述 */}
      <div className={styles.mainInfo}>
        <div className={styles.temperature}>
          <span className={styles.tempValue}>{temp || "-"}</span>
          <span className={styles.tempUnit}>°C</span>
        </div>
        <div className={styles.description}>
          {text || "-"}
          <img
            alt={text}
            src={`/weatherIcon/weather-icon-S2/64/${icon}.png`}
            onError={handleIconError}
          />
        </div>
      </div>

      {/* 预报时间 */}
      <div className={styles.time}>更新时间: {formatTime(obsTime)}</div>
    </div>
  );
}
