"use client";

import { App as AntApp, ConfigProvider } from "antd";
import ruRU from "antd/locale/ru_RU";
import "antd/dist/reset.css";
import "../app/globals.css";
import { AuthProvider } from "@/lib/auth-context";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ConfigProvider
      locale={ruRU}
      theme={{
        token: {
          colorPrimary: "#3b82f6",
          colorInfo: "#3b82f6",
          colorSuccess: "#22c55e",
          colorWarning: "#eab308",
          colorError: "#ef4444",
          colorBgLayout: "#f8fafc",
          borderRadius: 6,
          fontFamily:
            '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        },
        components: {
          Layout: {
            siderBg: "#1e293b",
            headerBg: "#ffffff",
            bodyBg: "#f8fafc",
          },
          Menu: {
            darkItemBg: "#1e293b",
            darkItemColor: "#cbd5e1",
            darkItemHoverBg: "#334155",
            darkItemSelectedBg: "#3b82f6",
            darkItemSelectedColor: "#ffffff",
          },
          Table: {
            headerBg: "#f1f5f9",
            headerColor: "#0f172a",
            rowHoverBg: "#e0f2fe",
            borderColor: "#e2e8f0",
            headerSplitColor: "#e2e8f0",
          },
          Tabs: {
            inkBarColor: "#3b82f6",
            itemSelectedColor: "#3b82f6",
          },
        },
      }}
    >
      <AntApp>
        <AuthProvider>{children}</AuthProvider>
      </AntApp>
    </ConfigProvider>
  );
}
