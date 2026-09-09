"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  App as AntApp,
  Button,
  Collapse,
  Empty,
  Input,
  Segmented,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { itemsApi } from "@/lib/api";
import type { SourceItem } from "@/lib/types";

const DOC_COLUMNS = [
  { key: "avk", field: "act_avk", title: "АВК" },
  { key: "aosr", field: "act_aosr", title: "АОСР" },
  { key: "vso", field: "act_vso", title: "ВСО" },
  { key: "vr", field: "act_vr", title: "ВР" },
];

function prefixOf(item: SourceItem): string {
  const fc = item.full_code?.trim() ?? "";
  const m = fc.match(/^(.*?)\.(СО\d+)$/i);
  return m ? m[1] : fc || "Без шифра";
}

interface Group {
  key: string;
  items: SourceItem[];
  withDoc: number;
}

interface Props {
  objectId: number;
}

export function BingoTab({ objectId }: Props) {
  const { message } = AntApp.useApp();
  const [items, setItems] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useState<string>("tracked");
  const [docFilter, setDocFilter] = useState<string>("all");
  const [q, setQ] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const tracked = scope === "tracked" ? true : undefined;
      setItems(await itemsApi.list(objectId, { tracked }));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить позиции");
    } finally {
      setLoading(false);
    }
  }, [objectId, scope, message]);

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const base = items.filter((it) => {
      if (docFilter === "no" && it.docs_count > 0) return false;
      if (docFilter === "yes" && it.docs_count === 0) return false;
      return true;
    });
    if (!needle) return base;
    return base.filter((it) =>
      [it.full_code, it.position, it.name, it.mark, it.supplier]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle))
    );
  }, [items, docFilter, q]);

  const groups = useMemo<Group[]>(() => {
    const map = new Map<string, Group>();
    for (const it of visible) {
      const key = prefixOf(it);
      let g = map.get(key);
      if (!g) {
        g = { key, items: [], withDoc: 0 };
        map.set(key, g);
      }
      g.items.push(it);
      if (it.docs_count > 0) g.withDoc += 1;
    }
    return [...map.values()].sort((a, b) => a.key.localeCompare(b.key, "ru"));
  }, [visible]);

  const totals = useMemo(
    () => ({
      total: items.length,
      withDoc: items.filter((i) => i.docs_count > 0).length,
    }),
    [items]
  );

  const baseColumns: ColumnsType<SourceItem> = [
    { title: "Поз.", dataIndex: "position", width: 70, render: (v: string | null) => v ?? "—" },
    { title: "Наименование", dataIndex: "name", width: 340 },
    { title: "Тип / марка", dataIndex: "mark", width: 220, render: (v: string | null) => v ?? "—" },
    { title: "Ед.", dataIndex: "unit", width: 60, render: (v: string | null) => v ?? "—" },
    { title: "Кол.", dataIndex: "quantity", width: 80, render: (v) => (v == null ? "—" : String(v)) },
  ];

  const gridColumns: ColumnsType<SourceItem> = [
    {
      title: "Полный шифр",
      dataIndex: "full_code",
      width: 280,
      render: (v: string | null) => (v ? <Typography.Text style={{ fontFamily: "monospace" }}>{v}</Typography.Text> : "—"),
    },
    ...baseColumns,
    {
      title: "Паспорт/Сертификат",
      key: "passport",
      width: 150,
      render: (_, row) =>
        row.docs_count > 0 ? (
          <Tag color="green">✓ {row.docs_count}</Tag>
        ) : (
          <Tag color="red">нет</Tag>
        ),
    },
    ...DOC_COLUMNS.map((c) => ({
      title: c.title,
      key: c.key,
      width: 90,
      render: (_: unknown, row: SourceItem) => {
        const n = row[c.field as keyof SourceItem] as number;
        return n > 0 ? <Tag color="green">{n}</Tag> : <Tag>—</Tag>;
      },
    })),
  ];

  return (
    <div>
      <Space style={{ marginBottom: 12, width: "100%", justifyContent: "space-between" }} wrap>
        <Space wrap>
          <Segmented
            value={scope}
            onChange={(v) => setScope(String(v))}
            options={[
              { label: "Отслеживаем", value: "tracked" },
              { label: "Все", value: "all" },
            ]}
          />
          <Segmented
            value={docFilter}
            onChange={(v) => setDocFilter(String(v))}
            options={[
              { label: "Все статусы", value: "all" },
              { label: "Без паспорта", value: "no" },
              { label: "С паспортом", value: "yes" },
            ]}
          />
          <Input.Search
            placeholder="Поиск…"
            allowClear
            style={{ width: 300 }}
            onSearch={(v) => setQ(v)}
            onChange={(e) => !e.target.value && setQ("")}
          />
        </Space>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>
          Обновить
        </Button>
      </Space>

      <Space style={{ marginBottom: 12 }}>
        <Typography.Text strong>
          Бинго-карта: {totals.total} позиций • с паспортом {totals.withDoc} • без паспорта{" "}
          {totals.total - totals.withDoc}
        </Typography.Text>
      </Space>

      {loading ? (
        <div style={{ padding: 40, textAlign: "center" }}>
          <Spin />
        </div>
      ) : groups.length === 0 ? (
        <Empty description="Нет позиций по выбранным фильтрам" />
      ) : (
        <Collapse
          ghost
          className="bingo-collapse"
          expandIconPosition="end"
          items={groups.map((g) => ({
            key: g.key,
            label: (
              <div style={{ display: "flex", alignItems: "center", gap: 12, width: "100%" }}>
                <Typography.Text strong style={{ fontSize: 15, fontFamily: "monospace" }}>
                  {g.key}
                </Typography.Text>
                <Tag color="blue">всего {g.items.length}</Tag>
                <Tag color={g.withDoc === g.items.length ? "green" : g.withDoc > 0 ? "orange" : "red"}>
                  с паспортом {g.withDoc}
                </Tag>
                {g.withDoc < g.items.length && <Tag color="red">без {g.items.length - g.withDoc}</Tag>}
              </div>
            ),
            children: (
              <Table<SourceItem>
                rowKey="id"
                columns={gridColumns}
                dataSource={g.items}
                size="small"
                scroll={{ x: 1400 }}
                pagination={{ pageSize: 50 }}
              />
            ),
          }))}
        />
      )}
    </div>
  );
}
