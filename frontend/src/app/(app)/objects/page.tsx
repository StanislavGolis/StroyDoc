"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  App as AntApp,
  Button,
  Input,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { PlusOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { objectsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDate, STATUS_COLORS, STATUS_LABELS } from "@/lib/labels";
import type { ConstructionObject, ObjectStatus } from "@/lib/types";
import { ObjectFormModal } from "@/components/ObjectFormModal";

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
      const list = await objectsApi.list({ q, status });
      setData(list);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить объекты");
    } finally {
      setLoading(false);
    }
  }, [q, status, message]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: ColumnsType<ConstructionObject> = [
    {
      title: "Название",
      dataIndex: "name",
      render: (name: string, row) => (
        <a onClick={() => router.push(`/objects/${row.id}`)}>{name}</a>
      ),
    },
    { title: "Шифр", dataIndex: "code", width: 140, render: (v: string | null) => v ?? "—" },
    {
      title: "Период",
      width: 220,
      render: (_, row) => `${formatDate(row.start_date)} — ${formatDate(row.end_date)}`,
    },
    {
      title: "Статус",
      dataIndex: "status",
      width: 140,
      render: (s: ObjectStatus) => <Tag color={STATUS_COLORS[s]}>{STATUS_LABELS[s]}</Tag>,
    },
    {
      title: "Действия",
      width: 140,
      render: (_, row) =>
        isManager ? (
          <Button type="link" size="small" onClick={() => { setEditing(row); setModalOpen(true); }}>
            Редактировать
          </Button>
        ) : null,
    },
  ];

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Объекты
        </Typography.Title>
        {isManager && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { setEditing(null); setModalOpen(true); }}>
            Новый объект
          </Button>
        )}
      </Space>

      <Space style={{ marginBottom: 16 }}>
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

      <Table<ConstructionObject>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={data}
        pagination={{ pageSize: 20, showTotal: (t) => `Всего: ${t}` }}
        locale={{ emptyText: "Объектов пока нет" }}
        onRow={(row) => ({
          onClick: () => router.push(`/objects/${row.id}`),
          style: { cursor: "pointer" },
        })}
      />

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
