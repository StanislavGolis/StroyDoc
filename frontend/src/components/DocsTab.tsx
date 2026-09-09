"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  App as AntApp,
  Button,
  Input,
  Modal,
  Popconfirm,
  Space,
  Table,
  Tag,
  Typography,
  Upload,
} from "antd";
import {
  CloudUploadOutlined,
  DeleteOutlined,
  DownloadOutlined,
  LinkOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { docsApi, itemsApi } from "@/lib/api";
import { formatDateTime } from "@/lib/labels";
import type { IncomingDoc, SourceItem } from "@/lib/types";

function fmtSize(bytes: number | null): string {
  if (bytes == null) return "—";
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  return `${Math.ceil(bytes / 1024)} КБ`;
}

interface Props {
  objectId: number;
}

export function DocsTab({ objectId }: Props) {
  const { message } = AntApp.useApp();
  const [docs, setDocs] = useState<IncomingDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [docNumber, setDocNumber] = useState("");
  const [docTitle, setDocTitle] = useState("");
  const [picker, setPicker] = useState<IncomingDoc | null>(null);
  const [items, setItems] = useState<SourceItem[]>([]);
  const [itemQ, setItemQ] = useState("");
  const [selectedKeys, setSelectedKeys] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDocs(await docsApi.list(objectId, { q: q || undefined }));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить документы");
    } finally {
      setLoading(false);
    }
  }, [objectId, q, message]);

  useEffect(() => {
    void load();
  }, [load]);

  const openPicker = async (doc: IncomingDoc) => {
    setPicker(doc);
    setSelectedKeys([]);
    try {
      setItems(await itemsApi.list(objectId, { tracked: undefined }));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить позиции");
    }
  };

  const pickerRows = useMemo(() => {
    const needle = itemQ.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((it) =>
      [it.full_code, it.name, it.mark, it.position, it.supplier]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(needle))
    );
  }, [items, itemQ]);

  const attachToDoc = async () => {
    if (!picker || selectedKeys.length === 0) return;
    setSaving(true);
    try {
      const res = await docsApi.attach(objectId, picker.id, selectedKeys);
      message.success(`Документ привязан к ${res.linked_items} позициям`);
      setPicker(null);
      await load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Ошибка привязки");
    } finally {
      setSaving(false);
    }
  };

  const columns: ColumnsType<IncomingDoc> = [
    { title: "№ документа", dataIndex: "doc_number", width: 150, render: (v: string | null) => v ?? "—" },
    {
      title: "Наименование / файл",
      dataIndex: "doc_title",
      render: (v: string | null, row) => (
        <Space>
          <DownloadOutlined
            style={{ cursor: "pointer" }}
            onClick={() => void docsApi.download(objectId, row)}
          />
          <Typography.Text>{v ?? row.original_filename}</Typography.Text>
        </Space>
      ),
    },
    { title: "Размер", dataIndex: "size_bytes", width: 90, render: (v: number | null) => fmtSize(v) },
    {
      title: "Привязано",
      dataIndex: "linked_items",
      width: 110,
      render: (v: number) => (v > 0 ? <Tag color="green">{v} поз.</Tag> : <Tag color="default">нет</Tag>),
    },
    { title: "Загружен", dataIndex: "created_at", width: 160, render: (v: string) => formatDateTime(v) },
    {
      title: "Действия",
      key: "actions",
      width: 210,
      render: (_, row) => (
        <Space>
          <Button size="small" icon={<LinkOutlined />} onClick={() => void openPicker(row)}>
            Привязать позиции
          </Button>
          <Popconfirm
            title="Удалить документ и файл?"
            okText="Удалить"
            cancelText="Отмена"
            onConfirm={async () => {
              try {
                await docsApi.remove(objectId, row.id);
                message.success("Документ удалён");
                await load();
              } catch (err) {
                message.error(err instanceof Error ? err.message : "Не удалось удалить");
              }
            }}
          >
            <Button size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ marginBottom: 12, width: "100%", justifyContent: "space-between" }} wrap>
        <Space wrap align="start">
          <Upload.Dragger
            multiple={false}
            showUploadList={false}
            style={{ width: 250, padding: 6 }}
            customRequest={async ({ file, onSuccess, onError }) => {
              try {
                await docsApi.upload(objectId, file as File, {
                  doc_number: docNumber || undefined,
                  doc_title: docTitle || undefined,
                });
                message.success("Документ загружен");
                setDocNumber("");
                setDocTitle("");
                onSuccess?.({});
                await load();
              } catch (err) {
                message.error(err instanceof Error ? err.message : "Ошибка загрузки");
                onError?.(err as Error);
              }
            }}
          >
            <Typography.Text>
              <CloudUploadOutlined /> Загрузить паспорт (PDF)
            </Typography.Text>
          </Upload.Dragger>
          <Input
            placeholder="№ документа"
            style={{ width: 150 }}
            value={docNumber}
            onChange={(e) => setDocNumber(e.target.value)}
          />
          <Input
            placeholder="Наименование (необязательно)"
            style={{ width: 200 }}
            value={docTitle}
            onChange={(e) => setDocTitle(e.target.value)}
          />
        </Space>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>
          Обновить
        </Button>
      </Space>

      <Input.Search
        placeholder="Поиск по номеру, наименованию, файлу"
        allowClear
        style={{ width: 380, marginBottom: 12 }}
        onSearch={(v) => setQ(v)}
      />

      <Table<IncomingDoc>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={docs}
        pagination={false}
        size="small"
        locale={{ emptyText: "Документов нет — загрузите паспорта/сертификаты" }}
      />

      <Modal
        title={picker ? `Привязать документ «${picker.doc_title ?? picker.original_filename}» к позициям` : ""}
        open={Boolean(picker)}
        onCancel={() => setPicker(null)}
        onOk={() => void attachToDoc()}
        confirmLoading={saving}
        width={880}
        okText="Привязать"
      >
        <Input.Search
          placeholder="Поиск по наименованию, полному шифру, марке…"
          allowClear
          style={{ marginBottom: 8 }}
          onSearch={(v) => setItemQ(v)}
        />
        <Table<SourceItem>
          rowKey="id"
          size="small"
          dataSource={pickerRows}
          pagination={{ pageSize: 10 }}
          rowSelection={{ selectedRowKeys: selectedKeys, onChange: (keys) => setSelectedKeys(keys as number[]) }}
          columns={[
            { title: "Шифр", dataIndex: "full_code", width: 260, render: (v: string | null) => v ?? "—" },
            { title: "Поз.", dataIndex: "position", width: 60 },
            { title: "Наименование", dataIndex: "name" },
            { title: "Ед.", dataIndex: "unit", width: 60 },
            { title: "Кол.", dataIndex: "quantity", width: 70 },
          ]}
        />
      </Modal>
    </div>
  );
}
