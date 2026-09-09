"use client";

import { useCallback, useEffect, useState } from "react";
import {
  App as AntApp,
  Button,
  Checkbox,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { EyeInvisibleOutlined, EyeOutlined, ReloadOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { itemsApi, sectionsApi } from "@/lib/api";
import type { Section, SourceItem } from "@/lib/types";

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
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [sectionFilter, setSectionFilter] = useState<number>();
  const [trackedFilter, setTrackedFilter] = useState<string>("tracked");
  const [detail, setDetail] = useState<SourceItem | null>(null);
  const [detailForm] = Form.useForm();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [list, ss] = await Promise.all([
        itemsApi.list(objectId, {
          section: sectionFilter,
          tracked: trackedFilter === "all" ? undefined : trackedFilter === "tracked",
        }),
        sectionsApi.list(objectId),
      ]);
      setItems(list);
      setSections(ss);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить позиции");
    } finally {
      setLoading(false);
    }
  }, [objectId, sectionFilter, trackedFilter, message]);

  useEffect(() => {
    void load();
  }, [load]);

  const applyPatch = async (id: number, patch: Record<string, unknown>) => {
    try {
      const updated = await itemsApi.update(objectId, id, patch);
      setItems((prev) => prev.map((it) => (it.id === id ? updated : it)));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось сохранить");
    }
  };

  const toggleTracked = (item: SourceItem) => {
    void applyPatch(item.id, { tracked: !item.tracked });
  };

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

  const bulkSection = (tracked: boolean) => {
    if (!sectionFilter) {
      message.warning("Сначала выберите шифр в фильтре");
      return;
    }
    void itemsApi
      .setTracked(objectId, { tracked, section_id: sectionFilter })
      .then((r) => {
        message.success(`Обновлено позиций: ${r.updated}`);
        void load();
      })
      .catch((err: unknown) => message.error(err instanceof Error ? err.message : "Ошибка"));
  };

  const columns: ColumnsType<SourceItem> = [
    {
      title: "",
      key: "tracked",
      width: 40,
      render: (_, row) => (
        <Checkbox checked={row.tracked} onChange={() => toggleTracked(row)} title={row.tracked ? "Отслеживаем" : "Скрыто из Мастер-списка"} />
      ),
    },
    {
      title: "Шифр",
      key: "section",
      width: 110,
      render: (_, row) => (row.section ? <Tag>{row.section.code}</Tag> : <Tag>—</Tag>),
    },
    { title: "Поз.", dataIndex: "position", width: 60, render: (v: string | null, row) => (
      <TextEdit value={v} width={60} onCommit={(s) => void applyPatch(row.id, { position: s || null })} />
    ) },
    { title: "Наименование", dataIndex: "name", width: 320, render: (v: string, row) => (
      <TextEdit value={v} width={320} onCommit={(s) => void applyPatch(row.id, { name: s })} />
    ) },
    { title: "Тип / марка", dataIndex: "mark", width: 220, render: (v: string | null, row) => (
      <TextEdit value={v} width={210} onCommit={(s) => void applyPatch(row.id, { mark: s || null })} />
    ) },
    { title: "Ед.", dataIndex: "unit", width: 70, render: (v: string | null, row) => (
      <TextEdit value={v} width={60} onCommit={(s) => void applyPatch(row.id, { unit: s || null })} />
    ) },
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
      title: "Полный шифр",
      dataIndex: "full_code",
      width: 230,
      render: (v: string | null, row) => (
        <TextEdit value={v} width={220} onCommit={(s) => void applyPatch(row.id, { full_code: s || null })} />
      ),
    },
    {
      title: "Подробнее",
      key: "detail",
      width: 110,
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
          <Select
            placeholder="Все шифры"
            allowClear
            style={{ width: 180 }}
            value={sectionFilter}
            onChange={(v) => setSectionFilter(v)}
            options={sections.map((s) => ({ value: s.id, label: s.code }))}
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
          <Button icon={<ReloadOutlined />} onClick={() => void load()}>
            Обновить
          </Button>
        </Space>
        {sectionFilter && (
          <Space>
            <Button icon={<EyeOutlined />} onClick={() => bulkSection(true)}>
              Показывать в шифре
            </Button>
            <Button danger icon={<EyeInvisibleOutlined />} onClick={() => bulkSection(false)}>
              Скрыть шифр из Мастер-списка
            </Button>
          </Space>
        )}
      </Space>

      <Table<SourceItem>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={items}
        size="small"
        scroll={{ x: 1500 }}
        pagination={{ pageSize: 50, showTotal: (t) => `Позиций: ${t}` }}
        locale={{
          emptyText: sectionFilter ? "В выбранном шифре нет позиций" : "Загрузите спецификацию и нажмите «Распарсить» во вкладке «Файлы»",
        }}
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
