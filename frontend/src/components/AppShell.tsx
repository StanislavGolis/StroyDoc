"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { App as AntApp, Avatar, Button, Layout, Menu, Spin, Tag, Typography } from "antd";
import {
  ApartmentOutlined,
  DashboardOutlined,
  LogoutOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { objectsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { ROLE_LABELS } from "@/lib/labels";
import type { ConstructionObject } from "@/lib/types";

const { Sider, Content } = Layout;

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, isManager, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const { message } = AntApp.useApp();
  const [objects, setObjects] = useState<ConstructionObject[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  const loadObjects = useCallback(async () => {
    if (!user) return;
    try {
      setObjects(await objectsApi.list());
    } catch {
      /* список объектов в сайдбаре — не критичен */
    }
  }, [user]);

  useEffect(() => {
    void loadObjects();
  }, [loadObjects]);

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

  const mainMenu = [
    ...(isManager ? [{ key: "/dashboard", icon: <DashboardOutlined />, label: "Дашборд" }] : []),
    { key: "/objects", icon: <ApartmentOutlined />, label: "Объекты" },
    ...(isManager ? [{ key: "/users", icon: <TeamOutlined />, label: "Пользователи" }] : []),
  ];

  const go = (to: string) => router.push(to);
  const selectedTop =
    pathname === "/objects" || pathname.startsWith("/objects/") ? "/objects" : pathname;

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={240} theme="dark" style={{ overflow: "auto" }}>
        <div
          style={{
            color: "#fff",
            fontSize: 18,
            fontWeight: 700,
            padding: "16px 20px",
            display: "flex",
            alignItems: "center",
            gap: 8,
            letterSpacing: 0.2,
          }}
        >
          🏗 <span>Бинго-Док</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          items={mainMenu}
          selectedKeys={[selectedTop]}
          onClick={({ key }) => go(key)}
        />
        <div
          style={{
            color: "#94a3b8",
            fontSize: 12,
            textTransform: "uppercase",
            letterSpacing: 0.6,
            padding: "14px 20px 4px",
          }}
        >
          Мои объекты
        </div>
        <div style={{ padding: "0 8px" }}>
          {objects.slice(0, 10).map((o) => (
            <div
              key={o.id}
              onClick={() => go(`/objects/${o.id}`)}
              style={{
                padding: "8px 12px",
                borderRadius: 6,
                cursor: "pointer",
                color: pathname === `/objects/${o.id}` ? "#fff" : "#cbd5e1",
                background: pathname === `/objects/${o.id}` ? "#3b82f6" : "transparent",
                fontSize: 13,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                marginBottom: 2,
              }}
              title={o.name}
            >
              {o.name}
            </div>
          ))}
          {objects.length === 0 && (
            <div style={{ color: "#64748b", fontSize: 13, padding: "6px 12px" }}>
              Объектов пока нет
            </div>
          )}
        </div>
        <div style={{ marginTop: "auto", padding: 16, color: "#cbd5e1", fontSize: 13 }}>
          <SpaceBlock
            fullName={user.full_name}
            role={user.role}
            onLogout={async () => {
              await logout();
              message.success("Вы вышли из системы");
            }}
          />
        </div>
      </Sider>
      <Layout>
        <Content style={{ padding: 24 }}>{children}</Content>
      </Layout>
    </Layout>
  );
}

function SpaceBlock({
  fullName,
  role,
  onLogout,
}: {
  fullName: string;
  role: string;
  onLogout: () => void;
}) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Avatar size={28} icon={<UserOutlined />} style={{ background: "#3b82f6" }} />
        <div>
          <Typography.Text style={{ color: "#fff", display: "block", fontSize: 13 }}>
            {fullName}
          </Typography.Text>
          <Tag style={{ fontSize: 11, margin: 0 }}>{ROLE_LABELS[role]}</Tag>
        </div>
      </div>
      <Button size="small" icon={<LogoutOutlined />} onClick={onLogout}>
        Выйти
      </Button>
    </div>
  );
}
