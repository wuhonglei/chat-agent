import { App as AntdApp } from "antd";
import { XProvider } from "@ant-design/x";
import ReactDOM from "react-dom/client";
import { Provider } from "react-redux";
import App from "./App";
import { store } from "./store";
import "./styles/index.css";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";
import isSameOrAfter from "dayjs/plugin/isSameOrAfter";
import "simplebar-react/dist/simplebar.min.css";
dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(isSameOrAfter);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <Provider store={store}>
    <XProvider
      theme={{
        token: {
          colorPrimary: "#2356F6",
          fontFamily: "inherit",
          fontFamilyCode: "inherit",
          colorText: "rgba(0,0,0,0.85)",
        },
      }}
    >
      <AntdApp>
        <App />
      </AntdApp>
    </XProvider>
  </Provider>
);
