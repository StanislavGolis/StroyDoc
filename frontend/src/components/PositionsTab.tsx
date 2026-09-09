"use client";

import { useCallback, useEffect, useState } from "react";
import { App as AntApp, Button, Space, Table, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { itemsApi } from "@/lib/api";
import type { SourceItem } from "@/lib/types";

interface Props {
  objectId: number;
}

export function PositionsTab({ objectId }: Props) {
  const { message } = AntApp.useApp();
  const [items, setItems] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await itemsApi.list(objectId));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить позиции");
    } finally {
      setLoading(false);
    }
  }, [objectId, message]);

  useEffect(() => {
    void load();
  }, [load]);

  const columns: ColumnsType<SourceItem> = [
    { title: "#", dataIndex: "row_number", width: 60 },
    { title: "Поз.", dataIndex: "position", width: 80 },
    { title: "Наименование", dataIndex: "name" },
    { title: "Тип / марка", dataIndex: "mark", width: 260, render: (v: string | null) => v ?? "—" },
    { title: "Код", dataIndex: "product_code", width: 110, render: (v: string | null) => v ?? "—" },
    { title: "Ед.", dataIndex: "unit", width: 80, render: (v: string | null) => v ?? "—" },
    { title: "Кол.", dataIndex: "quantity", width: 90, render: (v) => (v == null ? "—" : String(v)) },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 12, width: "100%", justifyContent: "space-between" }}>
        <Typography.Text strong>Позиции из РД (спецификаций)</Typography.Text>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>
          Обновить
        </Button>
      </Space>
      <Table<SourceItem>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={items}
        size="small"
        pagination={{ pageSize: 50, showTotal: (t) => `Всего: ${t}` }}
        locale={{ emptyText: "Нет позиций — загрузите спецификацию и нажмите «Распарсить» во вкладке «Файлы»" }}
      />
    </div>
  );
}
