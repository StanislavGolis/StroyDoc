"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  App as AntApp,
  Card,
  Col,
  Progress,
  Row,
  Space,
  Spin,
  Statistic,
  Tag,
  Typography,
} from "antd";
import {
  ApartmentOutlined,
  CheckCircleOutlined,
  FileProtectOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { dashboardApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { STATUS_LABELS } from "@/lib/labels";
import type { DashboardSummary } from "@/lib/types";

const ACT_LABELS: Record<string, string> = { avk: "АВК", aosr: "АОСР", vso: "ВСО", vr: "ВР" };

export default function DashboardPage() {
  const { user, loading, isManager } = useAuth();
  const { message } = AntApp.useApp();
  const router = useRouter();
  const [data, setData] = useState<DashboardSummary | null>(null);

  useEffect(() => {
    if (loading) return;
    if (!isManager) {
      router.replace("/objects");
      return;
    }
    dashboardApi
      .summary()
      .then(setData)
      .catch((err: unknown) =>
        message.error(err instanceof Error ? err.message : "Не удалось загрузить дашборд")
      );
  }, [loading, isManager, router, message]);

  if (loading || !data) {
    return (
      <div style={{ padding: 80, textAlign: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  const t = data.totals;

  return (
    <div>
      <Typography.Title level={3} style={{ marginTop: 0 }}>
        Дашборд руководителя
      </Typography.Title>

      <Row gutter={[16, 16]} style={{ marginBottom: 8 }}>
        <Col xs={12} md={6}>
          <Card className="object-card">
            <Statistic title="Объекты" value={t.objects_total} suffix={`в работе: ${t.objects_active}`} prefix={<ApartmentOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="object-card">
            <Statistic title="Позиций отслеживается" value={t.tracked_items} prefix={<CheckCircleOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="object-card">
            <Statistic title="Без паспорта" value={t.items_without_docs} valueStyle={{ color: "#ef4444" }} prefix={<WarningOutlined />} />
          </Card>
        </Col>
        <Col xs={12} md={6}>
          <Card className="object-card">
            <Statistic title="Готовность по паспортам" value={t.ready_pct} suffix="%" valueStyle={{ color: t.ready_pct >= 80 ? "#22c55e" : "#eab308" }} />
          </Card>
        </Col>
      </Row>

      <Space style={{ marginBottom: 16 }} wrap>
        <Tag icon={<FileProtectOutlined />} color="blue">
          Паспортов загружено: {t.passports}
        </Tag>
        {Object.entries(t.acts_by_type).map(([k, v]) => (
          <Tag key={k} color={v > 0 ? "green" : "default"}>
            {ACT_LABELS[k] ?? k}: {v}
          </Tag>
        ))}
      </Space>

      <Typography.Title level={4}>Объекты</Typography.Title>
      <Row gutter={[16, 16]}>
        {data.objects.map((o) => (
          <Col key={o.object_id} xs={24} sm={12} lg={8}>
            <Card
              hoverable
              className="object-card"
              onClick={() => router.push(`/objects/${o.object_id}`)}
              title={
                <Space>
                  <ApartmentOutlined style={{ color: "#3b82f6" }} />
                  <Typography.Text strong>{o.name}</Typography.Text>
                </Space>
              }
              extra={<Tag>{STATUS_LABELS[o.status] ?? o.status}</Tag>}
            >
              <Typography.Paragraph style={{ marginBottom: 8 }} type="secondary">
                Шифр: {o.code ?? "—"} • позиций: {o.tracked_items}
              </Typography.Paragraph>
              <Progress percent={o.ready_pct} strokeColor={o.ready_pct >= 80 ? "#22c55e" : "#3b82f6"} />
              <Space wrap>
                <Tag color={o.items_without_docs > 0 ? "#ef4444" : "#22c55e"}>
                  {o.items_without_docs > 0 ? `Есть риски (${o.items_without_docs} поз. без паспорта)` : "Всё закрыто паспортами"}
                </Tag>
                {o.acts_total > 0 && <Tag color="blue">Актов: {o.acts_total}</Tag>}
              </Space>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
