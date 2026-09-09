"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { App as AntApp, Button, Layout, Menu, Spin, Tag, Typography } from "antd";
import {
  LogoutOutlined,
  ProjectOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { useAuth } from "@/lib/auth-context";
import { ROLE_LABELS } from "@/lib/labels";

const { Header, Sider, Content } = Layout;

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, isManager, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { message } = AntApp.useApp();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Spin size="large" tip="Загрузка…">
          <div style={{ width: 120, height: 40 }} />
        </Spin>
      </div>
    );
  }

  const menuItems = [
    { key: "/objects", icon: <ProjectOutlined />, label: "Объекты" },
    ...(isManager
      ? [{ key: "/users", icon: <TeamOutlined />, label: "Пользователи" }]
      : []),
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider theme="dark" width={220}>
        <div
          style={{
            color: "#fff",
            fontSize: 18,
            fontWeight: 600,
            padding: "16px 20px",
          }}
        >
          StroyDoc
        </div>
        <Menu
          theme="dark"
          mode="inline"
          items={menuItems}
          selectedKeys={[pathname]}
          onClick={({ key }) => router.push(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 12,
            paddingInline: 24,
          }}
        >
          <Typography.Text strong>{user.full_name}</Typography.Text>
          <Tag color={user.role === "admin" ? "gold" : user.role === "pto_head" ? "blue" : "green"}>
            {ROLE_LABELS[user.role]}
          </Tag>
          <Button
            icon={<LogoutOutlined />}
            onClick={async () => {
              await logout();
              message.success("Вы вышли из системы");
            }}
          >
            Выйти
          </Button>
        </Header>
        <Content style={{ padding: 24 }}>{children}</Content>
      </Layout>
    </Layout>
  );
}
