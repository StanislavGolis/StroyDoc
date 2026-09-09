"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  App as AntApp,
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Space,
  Table,
  Typography,
} from "antd";
import { ReloadOutlined } from "@ant-design/icons";
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

export function PositionsTab({ objectId }: Props) {
  const { message } = AntApp.useApp();
  const [items, setItems] = useState<SourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [trackedFilter, setTrackedFilter] = useState<string>("tracked");
  const [q, setQ] = useState("");
  const [detail, setDetail] = useState<SourceItem | null>(null);
  const [detailForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await itemsApi.list(objectId, {
        tracked: trackedFilter === "all" ? undefined : trackedFilter === "tracked",
      });
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

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((it) =>
      [it.full_code, it.position, it.name, it.mark, it.product_code, it.supplier]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle))
    );
  }, [items, q]);

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
      fixed: "left",
      render: (_, row) => (
        <Checkbox
          checked={row.tracked}
          onChange={() => toggleTracked(row)}
          title={row.tracked ? "Отслеживаем" : "Скрыто из Мастер-списка"}
        />
      ),
    },
    {
      title: "Полный шифр",
      dataIndex: "full_code",
      width: 280,
      fixed: "left",
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
      fixed: "right",
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
            ]}
          />
        </Space>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>
          Обновить
        </Button>
      </Space>

      <Table<SourceItem>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={visible}
        size="small"
        scroll={{ x: 1400 }}
        pagination={{ pageSize: 50, showTotal: (t) => `Позиций: ${t}` }}
        locale={{ emptyText: "Позиций нет — загрузите спецификацию и нажмите «Распарсить» во вкладке «Файлы»" }}
      />

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
