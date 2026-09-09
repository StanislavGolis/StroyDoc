"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  App as AntApp,
  Button,
  Checkbox,
  Collapse,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  EyeInvisibleOutlined,
  EyeOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { itemsApi } from "@/lib/api";
import type { SourceItem } from "@/lib/types";

interface TextEditProps {
  value: string | null;
  onCommit: (next: string) => void;
  width?: number;
}

function TextEdit({ value, onCommit, width }: TextEditProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");

  useEffect(() => {
    setDraft(value ?? "");
  }, [value]);

  const commit = () => {
    setEditing(false);
    const next = draft.trim();
    if (next !== (value ?? "")) onCommit(next);
  };

  if (editing) {
    return (
      <Input
        autoFocus
        size="small"
        style={{ width: width ?? 160 }}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onPressEnter={commit}
        onBlur={commit}
      />
    );
  }
  return (
    <span
      style={{ cursor: "text", display: "block", minHeight: 20 }}
      title="Двойной клик — редактировать"
      onDoubleClick={() => setEditing(true)}
    >
      {value || "—"}
    </span>
  );
}

interface Props {
  objectId: number;
}

function normKey(s: string | null): string {
  return (s ?? "").toLowerCase().replace(/[^0-9a-zа-яё]/gi, "");
}

function prefixOf(item: SourceItem): string {
  const fc = item.full_code?.trim() ?? "";
  const m = fc.match(/^(.*?)\.(СО\d+)$/i);
  return m ? m[1] : fc || "Без шифра";
}

export function PositionsTab({ objectId }: Props) {
  const { message } = AntApp.useApp();
  const [items, setItems] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [trackedFilter, setTrackedFilter] = useState<string>("tracked");
  const [q, setQ] = useState("");
  const [expanded, setExpanded] = useState<string[]>([]);
  const [detail, setDetail] = useState<SourceItem | null>(null);
  const [detailForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const tracked =
        trackedFilter === "all" || trackedFilter === "dups" ? undefined : trackedFilter === "tracked";
      const list = await itemsApi.list(objectId, { tracked });
      setItems(list);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить позиции");
    } finally {
      setLoading(false);
    }
  }, [objectId, trackedFilter, message]);

  useEffect(() => {
    void load();
  }, [load]);

  // Словарь «возможных дублей»: одинаковое наименование+марка+ед. в разных шифрах
  const dupMap = useMemo(() => {
    const buckets = new Map<string, { ids: number[]; prefixes: Set<string> }>();
    for (const it of items) {
      const key = [normKey(it.name), normKey(it.mark), normKey(it.unit)].join("#");
      let b = buckets.get(key);
      if (!b) {
        b = { ids: [], prefixes: new Set<string>() };
        buckets.set(key, b);
      }
      b.ids.push(it.id);
      b.prefixes.add(prefixOf(it));
    }
    const map = new Map<number, number>();
    for (const b of buckets.values()) {
      if (b.prefixes.size > 1) {
        for (const id of b.ids) map.set(id, b.prefixes.size);
      }
    }
    return map;
  }, [items]);

  const visible = useMemo(() => {
    let base = items;
    if (trackedFilter === "dups") base = items.filter((it) => dupMap.has(it.id));
    const needle = q.trim().toLowerCase();
    if (!needle) return base;
    return base.filter((it) =>
      [it.full_code, it.position, it.name, it.mark, it.product_code, it.supplier]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle))
    );
  }, [items, q, dupMap, trackedFilter]);

  interface Group {
    key: string;
    label: string;
    subs: string[];
    items: SourceItem[];
  }

  const groups = useMemo<Group[]>(() => {
    const map = new Map<string, Group>();
    for (const it of visible) {
      const fc = it.full_code?.trim();
      const m = fc ? fc.match(/^(.*?)\.(СО\d+)$/i) : null;
      const prefix = m ? m[1] : fc || "Без шифра";
      const suffix = m ? m[2] : null;
      let g = map.get(prefix);
      if (!g) {
        g = { key: prefix, label: prefix, subs: [], items: [] };
        map.set(prefix, g);
      }
      g.items.push(it);
      if (suffix && !g.subs.includes(suffix)) g.subs.push(suffix);
    }
    return [...map.values()].sort((a, b) => a.label.localeCompare(b.label, "ru"));
  }, [visible]);

  const groupTracked = (group: Group, tracked: boolean) => {
    const ids = group.items.map((i) => i.id);
    void itemsApi
      .setTracked(objectId, { tracked, ids })
      .then((r) => {
        message.success(`Обновлено позиций: ${r.updated}`);
        void load();
      })
      .catch((err: unknown) => message.error(err instanceof Error ? err.message : "Ошибка"));
  };

  const applyPatch = async (id: number, patch: Record<string, unknown>) => {
    try {
      const updated = await itemsApi.update(objectId, id, patch);
      setItems((prev) => prev.map((it) => (it.id === id ? updated : it)));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось сохранить");
    }
  };

  const toggleTracked = (item: SourceItem) => void applyPatch(item.id, { tracked: !item.tracked });

  const openDetail = (item: SourceItem) => {
    setDetail(item);
    detailForm.setFieldsValue({
      doc_ref: item.doc_ref,
      product_code: item.product_code,
      supplier: item.supplier,
      mass: item.mass,
      notes: item.notes,
      quantity: item.quantity == null ? null : Number(item.quantity),
    });
  };

  const saveDetail = async () => {
    const values = await detailForm.validateFields();
    const patch: Record<string, unknown> = {};
    for (const key of ["doc_ref", "product_code", "supplier", "mass", "notes"] as const) {
      const v = values[key];
      if (typeof v === "string") patch[key] = v.trim() || null;
    }
    patch["quantity"] = values.quantity == null ? null : Number(values.quantity);
    if (detail) {
      await applyPatch(detail.id, patch);
      setDetail(null);
    }
  };

  const columns: ColumnsType<SourceItem> = [
    {
      title: "",
      key: "tracked",
      width: 40,
      render: (_, row) => (
        <Checkbox
          checked={row.tracked}
          onChange={() => toggleTracked(row)}
          title={row.tracked ? "Отслеживаем" : "Скрыто из Мастер-списка"}
        />
      ),
    },
    {
      title: "⚑",
      key: "dup",
      width: 44,
      render: (_, row) => {
        const n = dupMap.get(row.id);
        return n ? (
          <Tag color="orange" style={{ cursor: "help" }} title={`Возможный дубль — встречается в ${n} шифрах`}>
            {n}
          </Tag>
        ) : null;
      },
    },
    {
      title: "Полный шифр",
      dataIndex: "full_code",
      width: 280,
      render: (v: string | null, row) => (
        <TextEdit value={v} width={270} onCommit={(s) => void applyPatch(row.id, { full_code: s || null })} />
      ),
    },
    {
      title: "Поз.",
      dataIndex: "position",
      width: 60,
      render: (v: string | null, row) => (
        <TextEdit value={v} width={60} onCommit={(s) => void applyPatch(row.id, { position: s || null })} />
      ),
    },
    {
      title: "Наименование",
      dataIndex: "name",
      width: 320,
      render: (v: string, row) => (
        <TextEdit value={v} width={320} onCommit={(s) => void applyPatch(row.id, { name: s })} />
      ),
    },
    {
      title: "Тип / марка",
      dataIndex: "mark",
      width: 220,
      render: (v: string | null, row) => (
        <TextEdit value={v} width={210} onCommit={(s) => void applyPatch(row.id, { mark: s || null })} />
      ),
    },
    {
      title: "Ед.",
      dataIndex: "unit",
      width: 70,
      render: (v: string | null, row) => (
        <TextEdit value={v} width={60} onCommit={(s) => void applyPatch(row.id, { unit: s || null })} />
      ),
    },
    {
      title: "Кол.",
      dataIndex: "quantity",
      width: 90,
      render: (v, row) => (
        <InputNumber
          size="small"
          value={v == null ? null : Number(v)}
          style={{ width: 80 }}
          onChange={(n) => {
            if (n != null) void applyPatch(row.id, { quantity: n });
          }}
        />
      ),
    },
    {
      title: "Подробнее",
      key: "detail",
      width: 120,
      render: (_, row) => (
        <Button size="small" onClick={() => openDetail(row)}>
          ТУ/код/поставщик
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 12, width: "100%", justifyContent: "space-between" }} wrap>
        <Space wrap>
          <Input.Search
            placeholder="Поиск по полному шифру, наименованию, марке…"
            allowClear
            style={{ width: 360 }}
            onSearch={(v) => setQ(v)}
            onChange={(e) => !e.target.value && setQ("")}
          />
          <Segmented
            value={trackedFilter}
            onChange={(v) => setTrackedFilter(String(v))}
            options={[
              { label: "Отслеживаем", value: "tracked" },
              { label: "Все", value: "all" },
              { label: "Скрытые", value: "untracked" },
              { label: "⚑ Дубли", value: "dups" },
            ]}
          />
        </Space>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>
          Обновить
        </Button>
      </Space>

      {loading ? (
        <div style={{ padding: 40, textAlign: "center" }}>
          <Spin />
        </div>
      ) : groups.length === 0 ? (
        <Empty description="Позиций нет — загрузите спецификацию и нажмите «Распарсить» во вкладке «Файлы»" />
      ) : (
        <Collapse
          ghost
          expandIconPosition="end"
          activeKey={q.trim() || trackedFilter === "dups" ? groups.map((g) => g.key) : expanded}
          onChange={(keys) => setExpanded((keys as string[]) ?? [])}
          items={groups.map((g) => ({
            key: g.key,
            label: (
              <div style={{ display: "flex", alignItems: "center", gap: 12, width: "100%" }}>
                <Typography.Text strong style={{ fontSize: 15, fontFamily: "monospace" }}>
                  {g.label}
                </Typography.Text>
                <Tag color="blue">позиций: {g.items.length}</Tag>
                {g.subs.map((s) => (
                  <Tag key={s} color="geekblue">
                    {s}
                  </Tag>
                ))}
                <div style={{ marginLeft: "auto" }} onClick={(e) => e.stopPropagation()}>
                  <Space>
                    <Button size="small" icon={<EyeOutlined />} title="Показывать в Мастер-списке" onClick={() => groupTracked(g, true)}>
                      Показать
                    </Button>
                    <Button size="small" danger icon={<EyeInvisibleOutlined />} title="Скрыть из Мастер-списка" onClick={() => groupTracked(g, false)}>
                      Скрыть
                    </Button>
                  </Space>
                </div>
              </div>
            ),
            children: (
              <Table<SourceItem>
                rowKey="id"
                columns={columns}
                dataSource={g.items}
                size="small"
                scroll={{ x: 1400 }}
                pagination={{ pageSize: 50 }}
              />
            ),
          }))}
        />
      )}

      <Modal
        title={detail ? `Позиция ${detail.position ?? detail.row_number} — доп. поля` : ""}
        open={Boolean(detail)}
        onCancel={() => setDetail(null)}
        onOk={() => void saveDetail()}
        destroyOnHidden
        width={520}
      >
        <Form form={detailForm} layout="vertical">
          <Form.Item name="doc_ref" label="ГОСТ / ТУ / обозначение документа">
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item name="product_code" label="Код продукции">
            <Input />
          </Form.Item>
          <Form.Item name="supplier" label="Поставщик">
            <Input />
          </Form.Item>
          <Form.Item name="mass" label="Масса 1 ед.">
            <Input />
          </Form.Item>
          <Form.Item name="quantity" label="Количество">
            <InputNumber style={{ width: "100%" }} />
          </Form.Item>
          <Form.Item name="notes" label="Примечания">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
