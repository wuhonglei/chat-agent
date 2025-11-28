import { XProvider } from "@ant-design/x";
import { App as AntdApp } from "antd";
import dayjs from "dayjs";
import isSameOrAfter from "dayjs/plugin/isSameOrAfter";
import timezone from "dayjs/plugin/timezone";
import utc from "dayjs/plugin/utc";
import ReactDOM from "react-dom/client";
import { Provider } from "react-redux";
import "simplebar-react/dist/simplebar.min.css";
import App from "./App";
import { store } from "./store";
import "./styles/index.css";
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
