"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  App as AntApp,
  Button,
  Checkbox,
  DatePicker,
  Form,
  Input,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import {
  DownloadOutlined,
  EyeOutlined,
  PlusOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import { actsApi, itemsApi } from "@/lib/api";
import { formatDate, ITEM_TYPE_COLORS, ITEM_TYPE_LABELS } from "@/lib/labels";
import type { Act, ActType, ItemType, SourceItem } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

const ACT_TYPE_LABELS: Record<ActType, string> = {
  avk: "Акт входного контроля",
  aosr: "Акт освидетельствования скрытых работ",
  vso: "Ведомость смонтированного оборудования",
  vr: "Ведомость выполненных работ",
};

/** Какие типы позиций закрывает акт (матрица закрытия, см. backend/app/services/closure.py). */
const ACT_ITEM_TYPES: Record<ActType, ItemType[]> = {
  avk: ["material", "equipment"],
  aosr: ["material"],
  vso: ["equipment"],
  vr: ["work"],
};

/** Допускаются ли в акт позиции с неопределённым типом. */
const ACT_ALLOWS_UNTYPED: Record<ActType, boolean> = {
  avk: true,
  aosr: true,
  vso: true,
  vr: false,
};

/** Подходит ли позиция для акта данного вида. */
function matchesAct(item: SourceItem, actType: ActType): boolean {
  if (!item.item_type) return ACT_ALLOWS_UNTYPED[actType];
  return ACT_ITEM_TYPES[actType].includes(item.item_type);
}

interface Props {
  objectId: number;
}

export function ActsTab({ objectId }: Props) {
  const { message } = AntApp.useApp();
  const [acts, setActs] = useState<Act[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<ActType>();

  const [createOpen, setCreateOpen] = useState(false);
  const [allItems, setAllItems] = useState<SourceItem[]>([]);
  const [itemQ, setItemQ] = useState("");
  const [itemKeys, setItemKeys] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);
  // «Показать все типы» — по умолчанию модалка показывает только допустимые типы позиций
  const [showAll, setShowAll] = useState(false);
  const [createForm] = Form.useForm<{
    act_type: ActType;
    doc_number?: string;
    doc_date?: Dayjs;
  }>();
  const watchedActType = Form.useWatch("act_type", createForm) as ActType | undefined;
  const currentActType: ActType = watchedActType ?? "avk";

  const [viewAct, setViewAct] = useState<Act | null>(null);
  const [actItems, setActItems] = useState<SourceItem[]>([]);
  const [addKeys, setAddKeys] = useState<number[]>([]);
  const [addQ, setAddQ] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setActs(await actsApi.list(objectId, typeFilter));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить акты");
    } finally {
      setLoading(false);
    }
  }, [objectId, typeFilter, message]);

  useEffect(() => {
    void load();
  }, [load]);

  const openCreate = async () => {
    setCreateOpen(true);
    createForm.setFieldsValue({ act_type: "avk" });
    setItemKeys([]);
    try {
      setAllItems(await itemsApi.list(objectId, { tracked: undefined }));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить позиции");
    }
  };

  const submitCreate = async () => {
    const values = await createForm.validateFields();
    setSaving(true);
    try {
      await actsApi.create(objectId, {
        act_type: values.act_type,
        doc_number: values.doc_number?.trim() || undefined,
        doc_date: values.doc_date ? values.doc_date.format("YYYY-MM-DD") : null,
        item_ids: itemKeys,
      });
      message.success("Акт создан");
      setCreateOpen(false);
      await load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Ошибка создания");
    } finally {
      setSaving(false);
    }
  };

  const openView = async (act: Act) => {
    setViewAct(act);
    setAddKeys([]);
    setActItems(await actsApi.items(objectId, act.id));
  };

  const reloadView = async () => {
    if (!viewAct) return;
    setActItems(await actsApi.items(objectId, viewAct.id));
    const fresh = await actsApi.list(objectId, typeFilter);
    const updated = fresh.find((a) => a.id === viewAct.id);
    if (updated) setViewAct(updated);
    await load();
  };

  const addToAct = async () => {
    if (!viewAct || addKeys.length === 0) return;
    try {
      await actsApi.addItems(objectId, viewAct.id, addKeys);
      setAddKeys([]);
      await reloadView();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Ошибка добавления");
    }
  };

  const removeFromAct = async (itemId: number) => {
    if (!viewAct) return;
    try {
      await actsApi.removeItems(objectId, viewAct.id, [itemId]);
      await reloadView();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Ошибка удаления");
    }
  };

  const pickerRows = useMemo(() => {
    const allowed = allItems.filter((it) => showAll || matchesAct(it, currentActType));
    const needle = itemQ.trim().toLowerCase();
    if (!needle) return allowed;
    return allowed.filter((it) =>
      [it.full_code, it.name, it.mark, it.supplier, it.position]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle))
    );
  }, [allItems, itemQ, showAll, currentActType]);

  const addRows = useMemo(() => {
    const needle = addQ.trim().toLowerCase();
    const inAct = new Set(actItems.map((i) => i.id));
    // в акт можно добавить только позиции, подходящие по виду акта (проверяет и сервер)
    const base = allItems.filter(
      (i) => !inAct.has(i.id) && (viewAct ? matchesAct(i, viewAct.act_type) : true)
    );
    if (!needle) return base;
    return base.filter((it) =>
      [it.full_code, it.name, it.mark, it.supplier, it.position]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle))
    );
  }, [allItems, actItems, addQ, viewAct]);

  const columns: ColumnsType<Act> = [
    { title: "Тип", dataIndex: "act_type", width: 200, render: (t: ActType) => ACT_TYPE_LABELS[t] ?? t },
    { title: "№", dataIndex: "doc_number", width: 130, render: (v: string | null) => v ?? "—" },
    { title: "Дата", dataIndex: "doc_date", width: 110, render: (v: string | null) => formatDate(v) },
    {
      title: "Статус",
      dataIndex: "status",
      width: 150,
      render: (s: Act["status"], row) => (
        <Button
          size="small"
          onClick={() =>
            void actsApi
              .update(objectId, row.id, { status: s === "draft" ? "ready" : "draft" })
              .then(() => void load())
              .catch((err: unknown) => message.error(err instanceof Error ? err.message : "Ошибка"))
          }
        >
          {s === "draft" ? <StatusBadge tone="warn">Черновик</StatusBadge> : <StatusBadge tone="done">Готов</StatusBadge>}
        </Button>
      ),
    },
    {
      title: "Позиций",
      dataIndex: "linked_items",
      width: 100,
      render: (v: number) => <Tag color={v > 0 ? "blue" : "default"}>{v}</Tag>,
    },
    { title: "Создан", dataIndex: "created_at", width: 160, render: (v: string) => formatDate(v) },
    {
      title: "Действия",
      key: "actions",
      width: 240,
      render: (_, row) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => void openView(row)}>
            Позиции
          </Button>
          <Button
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => void actsApi.generate(objectId, row)}
          >
            DOCX
          </Button>
          <Popconfirm
            title="Удалить акт?"
            okText="Удалить"
            cancelText="Отмена"
            onConfirm={async () => {
              await actsApi.remove(objectId, row.id);
              await load();
            }}
          >
            <Button size="small" danger>
              Удалить
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const itemColumns: ColumnsType<SourceItem> = [
    { title: "Шифр", dataIndex: "full_code", width: 260, render: (v: string | null) => v ?? "—" },
    { title: "Поз.", dataIndex: "position", width: 70 },
    { title: "Наименование", dataIndex: "name" },
    {
      title: "Тип",
      dataIndex: "item_type",
      width: 120,
      render: (v: ItemType | null) =>
        v ? <Tag color={ITEM_TYPE_COLORS[v]}>{ITEM_TYPE_LABELS[v]}</Tag> : <Tag>не задан</Tag>,
    },
    { title: "Тип/марка", dataIndex: "mark", width: 200, render: (v: string | null) => v ?? "—" },
    { title: "Ед.", dataIndex: "unit", width: 70 },
    { title: "Кол.", dataIndex: "quantity", width: 80 },
  ];

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }}>
        <Space>
          <Select
            placeholder="Все типы"
            allowClear
            style={{ width: 260 }}
            value={typeFilter}
            onChange={(v) => setTypeFilter(v)}
            options={Object.entries(ACT_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
          />
        </Space>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => void load()}>
            Обновить
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => void openCreate()}>
            Создать акт
          </Button>
        </Space>
      </Space>

      <Table<Act>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={acts}
        pagination={false}
        size="small"
        scroll={{ x: 1100 }}
        locale={{ emptyText: "Актов нет — создайте первый" }}
      />

      {/* Создание акта: тип + реквизиты + выбор позиций (большая модалка) */}
      <Modal
        title="Создать акт"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => void submitCreate()}
        confirmLoading={saving}
        width="80%"
        okText="Создать"
      >
        <Form form={createForm} layout="vertical">
          <Form.Item name="act_type" label="Тип акта" rules={[{ required: true }]}>
            <Radio.Group
              options={Object.entries(ACT_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
            />
          </Form.Item>
          <Space>
            <Form.Item name="doc_number" label="Номер">
              <Input placeholder="АВК-2026-1" style={{ width: 220 }} />
            </Form.Item>
            <Form.Item name="doc_date" label="Дата">
              <DatePicker style={{ width: 160 }} />
            </Form.Item>
          </Space>
          <Typography.Paragraph strong>Выберите позиции из Мастер-списка:</Typography.Paragraph>
          <Space style={{ marginBottom: 8 }} wrap>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              Под этот акт подходят:{" "}
              {ACT_ITEM_TYPES[currentActType].map((t) => ITEM_TYPE_LABELS[t]).join(", ")}
              {ACT_ALLOWS_UNTYPED[currentActType] ? " и позиции без типа" : ""}
            </Typography.Text>
            <Checkbox checked={showAll} onChange={(e) => setShowAll(e.target.checked)}>
              Показать все типы
            </Checkbox>
          </Space>
          <Input.Search
            placeholder="Поиск по наименованию, шифру, марке…"
            allowClear
            style={{ marginBottom: 8 }}
            onSearch={(v) => setItemQ(v)}
          />
          <Table<SourceItem>
            rowKey="id"
            size="small"
            dataSource={pickerRows}
            pagination={{ pageSize: 8 }}
            rowSelection={{ selectedRowKeys: itemKeys, onChange: (keys) => setItemKeys(keys as number[]) }}
            columns={itemColumns}
          />
        </Form>
      </Modal>

      {/* Просмотр акта: позиции + добавление */}
      <Modal
        title={
          viewAct
            ? `${ACT_TYPE_LABELS[viewAct.act_type]} № ${viewAct.doc_number ?? ""} — позиции (${actItems.length})`
            : ""
        }
        open={Boolean(viewAct)}
        onCancel={() => setViewAct(null)}
        footer={null}
        width="80%"
      >
        <Typography.Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 8 }}>
          В список добавления попадают только позиции, подходящие под вид акта.
        </Typography.Paragraph>
        <Space style={{ marginBottom: 8 }} wrap>
          <Input.Search
            placeholder="Добавить: поиск по наименованию/шифру…"
            allowClear
            style={{ width: 360 }}
            onSearch={(v) => setAddQ(v)}
          />
          <Button type="primary" disabled={addKeys.length === 0} onClick={() => void addToAct()}>
            Добавить выбранные ({addKeys.length})
          </Button>
        </Space>
        <Table<SourceItem>
          rowKey="id"
          size="small"
          dataSource={addRows}
          pagination={false}
          rowSelection={{ selectedRowKeys: addKeys, onChange: (keys) => setAddKeys(keys as number[]) }}
          columns={itemColumns}
          locale={{ emptyText: "Все позиции уже в акте" }}
        />
        <Typography.Title level={5} style={{ marginTop: 16 }}>
          В акте
        </Typography.Title>
        <Table<SourceItem>
          rowKey="id"
          size="small"
          dataSource={actItems}
          pagination={{ pageSize: 10 }}
          columns={[
            ...itemColumns,
            {
              title: "",
              key: "x",
              width: 70,
              render: (_, row) => (
                <Button size="small" danger onClick={() => void removeFromAct(row.id)}>
                  Убрать
                </Button>
              ),
            },
          ]}
        />
      </Modal>
    </div>
  );
}
