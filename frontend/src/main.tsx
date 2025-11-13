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
import "simplebar-react/dist/simplebar.min.css";
dayjs.extend(utc);
dayjs.extend(timezone);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <Provider store={store}>
    <XProvider
      theme={{
        token: {
          colorPrimary: "#2356F6",
          fontFamily: "inherit",
          fontFamilyCode: "inherit",
        },
      }}
    >
      <AntdApp>
        <App />
      </AntdApp>
    </XProvider>
  </Provider>
);
