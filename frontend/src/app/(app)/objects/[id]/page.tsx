"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  App as AntApp,
  Breadcrumb,
  Button,
  Descriptions,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import { ArrowLeftOutlined, DeleteOutlined, UserAddOutlined } from "@ant-design/icons";
import { objectsApi, usersApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDateTime, ROLE_LABELS, STATUS_COLORS, STATUS_LABELS } from "@/lib/labels";
import type { Assignment, ConstructionObject, User } from "@/lib/types";
import { ObjectFormModal } from "@/components/ObjectFormModal";
import { FilesTab } from "@/components/FilesTab";
import { PositionsTab } from "@/components/PositionsTab";
import { DocsTab } from "@/components/DocsTab";
import { BingoTab } from "@/components/BingoTab";
import { ActsTab } from "@/components/ActsTab";

export default function ObjectDetailPage() {
  const params = useParams<{ id: string }>();
  const objectId = Number(params?.id);
  const router = useRouter();
  const { isManager } = useAuth();
  const { message } = AntApp.useApp();

  const [object, setObject] = useState<ConstructionObject | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [engineers, setEngineers] = useState<User[]>([]);
  const [selectedEngineer, setSelectedEngineer] = useState<number>();
  const [loading, setLoading] = useState(true);
  const [editOpen, setEditOpen] = useState(false);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const obj = await objectsApi.get(objectId);
      setObject(obj);
      const assigned = await objectsApi.listAssignments(objectId);
      setAssignments(assigned);
      if (isManager) {
        const users = await usersApi.list();
        setEngineers(users);
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить объект");
      router.replace("/objects");
    } finally {
      setLoading(false);
    }
  }, [objectId, isManager, message, router]);

  useEffect(() => {
    if (Number.isFinite(objectId)) void loadAll();
  }, [objectId, loadAll]);

  const availableEngineers = useMemo(() => {
    const assignedIds = new Set(assignments.map((a) => a.user.id));
    return engineers.filter((u) => u.role === "pto_engineer" && !assignedIds.has(u.id));
  }, [engineers, assignments]);

  const addEngineer = async () => {
    if (!selectedEngineer) return;
    try {
      await objectsApi.addAssignment(objectId, selectedEngineer);
      message.success("Инженер назначен");
      setSelectedEngineer(undefined);
      void loadAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось назначить");
    }
  };

  const removeEngineer = async (userId: number) => {
    try {
      await objectsApi.removeAssignment(objectId, userId);
      message.success("Назначение снято");
      void loadAll();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось снять назначение");
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: 64 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!object) return null;

  const infoTab = (
    <Descriptions bordered column={1} size="middle">
      <Descriptions.Item label="Название">{object.name}</Descriptions.Item>
      <Descriptions.Item label="Шифр">{object.code ?? "—"}</Descriptions.Item>
      <Descriptions.Item label="Начало работ">
        {object.start_date ? formatDateTime(object.start_date) : "—"}
      </Descriptions.Item>
      <Descriptions.Item label="Окончание работ">
        {object.end_date ? formatDateTime(object.end_date) : "—"}
      </Descriptions.Item>
      <Descriptions.Item label="Статус">
        <Tag color={STATUS_COLORS[object.status]}>{STATUS_LABELS[object.status]}</Tag>
      </Descriptions.Item>
      <Descriptions.Item label="Создан">{formatDateTime(object.created_at)}</Descriptions.Item>
    </Descriptions>
  );

  const assignmentsTab = (
    <div>
      {isManager && (
        <Space style={{ marginBottom: 16 }}>
          <Select
            placeholder="Выберите инженера"
            style={{ width: 300 }}
            value={selectedEngineer}
            onChange={setSelectedEngineer}
            options={availableEngineers.map((u) => ({
              value: u.id,
              label: `${u.full_name} (${u.email})`,
            }))}
          />
          <Button
            type="primary"
            icon={<UserAddOutlined />}
            disabled={!selectedEngineer}
            onClick={() => void addEngineer()}
          >
            Назначить
          </Button>
        </Space>
      )}
      <Table<Assignment>
        rowKey="id"
        dataSource={assignments}
        pagination={false}
        locale={{ emptyText: "Инженеры не назначены" }}
        columns={[
          { title: "ФИО", dataIndex: ["user", "full_name"] },
          { title: "Email", dataIndex: ["user", "email"] },
          {
            title: "Роль",
            dataIndex: ["user", "role"],
            width: 160,
            render: (r: string) => ROLE_LABELS[r] ?? r,
          },
          {
            title: "Назначен",
            dataIndex: "created_at",
            width: 180,
            render: (v: string) => formatDateTime(v),
          },
          ...(isManager
            ? [
                {
                  title: "",
                  key: "actions",
                  width: 80,
                  render: (_: unknown, row: Assignment) => (
                    <Button
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => void removeEngineer(row.user.id)}
                    />
                  ),
                },
              ]
            : []),
        ]}
      />
    </div>
  );

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 8 }}
        items={[
          { title: <a onClick={() => router.push("/objects")}>Объекты</a> },
          { title: object.name },
        ]}
      />
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 12 }}>
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => router.push("/objects")}>
            Назад
          </Button>
          <Typography.Title level={4} style={{ margin: 0 }}>
            {object.name}
          </Typography.Title>
          {object.code && (
            <Tag>{object.code}</Tag>
          )}
        </Space>
        {isManager && (
          <Button type="primary" onClick={() => setEditOpen(true)}>
            Редактировать
          </Button>
        )}
      </Space>

      <Tabs
        destroyInactiveTabPane
        items={[
          { key: "info", label: "Информация", children: infoTab },
          { key: "assignments", label: "Назначения", children: assignmentsTab },
          { key: "files", label: "Файлы", children: <FilesTab objectId={object.id} /> },
          { key: "docs", label: "Документы (паспорта)", children: <DocsTab objectId={object.id} /> },
          { key: "items", label: "Позиции (РД)", children: <PositionsTab objectId={object.id} /> },
          { key: "bingo", label: "Бинго-карта", children: <BingoTab objectId={object.id} /> },
          { key: "acts", label: "Акты", children: <ActsTab objectId={object.id} /> },
        ]}
      />

      <ObjectFormModal
        open={editOpen}
        initial={object}
        onCancel={() => setEditOpen(false)}
        onSaved={(updated) => {
          setEditOpen(false);
          setObject(updated);
          message.success("Объект обновлён");
        }}
      />
    </div>
  );
}

