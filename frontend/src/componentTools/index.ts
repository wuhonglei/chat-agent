import { ComponentToolItem } from "@/interfaces";
import { createRequire } from "module";
import WeatherNow from "./components/WeatherNow";
const require = createRequire(import.meta.url);

const componentTools: ComponentToolItem[] = [
  {
    name: "weather_now",
    component: WeatherNow,
    typeSourceFile: require.resolve("./components/WeatherNow/type.ts"),
    when: {
      tool_names: ["weather"],
    },
  },
];

export default componentTools;
