"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { App as AntApp, Button, Card, Col, Empty, Input, Row, Select, Space, Spin, Tag, Typography } from "antd";
import { ApartmentOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { objectsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate, STATUS_LABELS } from "@/lib/labels";
import type { ConstructionObject, ObjectStatus } from "@/lib/types";
import { ObjectFormModal } from "@/components/ObjectFormModal";

const STATUS_COLOR: Record<string, string> = {
  planning: "#94a3b8",
  active: "#3b82f6",
  closed: "#22c55e",
};

export default function ObjectsPage() {
  const { isManager } = useAuth();
  const { message } = AntApp.useApp();
  const router = useRouter();
  const [data, setData] = useState<ConstructionObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState<string>();
  const [status, setStatus] = useState<ObjectStatus>();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ConstructionObject | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await objectsApi.list({ q, status }));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить объекты");
    } finally {
      setLoading(false);
    }
  }, [q, status, message]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 20 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Объекты
        </Typography.Title>
        {isManager && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setModalOpen(true); }}>
            Создать объект
          </Button>
        )}
      </Space>

      <Space style={{ marginBottom: 20 }}>
        <Input.Search
          placeholder="Поиск по названию или шифру"
          allowClear
          style={{ width: 320 }}
          onSearch={(v) => setQ(v || undefined)}
        />
        <Select
          placeholder="Статус"
          allowClear
          style={{ width: 180 }}
          value={status}
          onChange={(v) => setStatus(v)}
          options={Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))}
        />
      </Space>

      {loading ? (
        <div style={{ padding: 60, textAlign: "center" }}>
          <Spin size="large" />
        </div>
      ) : data.length === 0 ? (
        <Empty description="Объектов пока нет — создайте первый" />
      ) : (
        <Row gutter={[16, 16]}>
          {data.map((o) => (
            <Col key={o.id} xs={24} sm={12} lg={8} xl={6}>
              <Card
                hoverable
                className="object-card"
                style={{ height: "100%" }}
                onClick={() => router.push(`/objects/${o.id}`)}
                title={
                  <Space>
                    <ApartmentOutlined style={{ color: "#3b82f6" }} />
                    <Typography.Text strong>{o.name}</Typography.Text>
                  </Space>
                }
                extra={<Tag style={{ color: "#fff", background: STATUS_COLOR[o.status] }}>{STATUS_LABELS[o.status]}</Tag>}
              >
                <Typography.Paragraph style={{ marginBottom: 8 }}>
                  <Typography.Text type="secondary">Шифр: </Typography.Text>
                  {o.code ?? "—"}
                </Typography.Paragraph>
                <Typography.Paragraph style={{ marginBottom: 4, fontSize: 13 }}>
                  {formatDate(o.start_date)} — {formatDate(o.end_date)}
                </Typography.Paragraph>
                <Space style={{ marginTop: 12 }} onClick={(e) => e.stopPropagation()}>
                  <Button size="small" type="primary">
                    Перейти
                  </Button>
                  {isManager && (
                    <Button
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => { setEditing(o); setModalOpen(true); }}
                    >
                      Редактировать
                    </Button>
                  )}
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <ObjectFormModal
        open={modalOpen}
        initial={editing}
        onCancel={() => setModalOpen(false)}
        onSaved={() => {
          setModalOpen(false);
          void load();
        }}
      />
    </div>
  );
}
