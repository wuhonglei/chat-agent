import { WeatherNowProps } from "@/interfaces/weather";
import { formatTime } from "@/utils";
import styles from "./index.module.css";

export default function WeatherNow({ data, location }: WeatherNowProps) {
  const { tempMin, tempMax, temp, icon, text, obsTime } = data;

  return (
    <div className={styles.container}>
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
          <img src={`/weatherIcon/weather-icon-S2/64/${icon}.png`} alt={text} />
        </div>
      </div>

      {/* 温度范围 */}
      {(tempMin || tempMax) && (
        <div className={styles.tempRange}>
          {tempMax && <span className={styles.tempMax}>{tempMax}°C</span>}
          {tempMin && tempMax && <span className={styles.separator}> / </span>}
          {tempMin && <span className={styles.tempMin}>{tempMin}°C</span>}
        </div>
      )}

      {/* 预报时间 */}
      <div className={styles.time}>更新时间: {formatTime(obsTime)}</div>
    </div>
  );
}
