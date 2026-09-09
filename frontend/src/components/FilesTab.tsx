"use client";

import { useCallback, useEffect, useState } from "react";
import {
  App as AntApp,
  Button,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
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
  PlayCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { filesApi, sectionsApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { formatDateTime } from "@/lib/labels";
import type { DocKind, ObjectFile, Section } from "@/lib/types";

const KIND_LABELS: Record<DocKind, string> = {
  spec: "Спецификация",
  estimate: "Смета",
  passport: "Паспорта",
  other: "Прочее",
};

const STATUS_TAGS: Record<string, string> = {
  uploaded: "default",
  parsing: "processing",
  done: "success",
  error: "error",
};

function fmtSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${bytes} Б`;
}

interface Props {
  objectId: number;
}

export function FilesTab({ objectId }: Props) {
  const { message } = AntApp.useApp();
  const { isManager } = useAuth();
  const [files, setFiles] = useState<ObjectFile[]>([]);
  const [sections, setSections] = useState<Section[]>([]);
  const [loading, setLoading] = useState(true);
  const [parsingId, setParsingId] = useState<number>();
  const [kind, setKind] = useState<DocKind>("spec");
  const [sectionId, setSectionId] = useState<number>();
  const [addOpen, setAddOpen] = useState(false);
  const [sectionForm] = Form.useForm<{ code: string; name?: string }>();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [fs, ss] = await Promise.all([filesApi.list(objectId), sectionsApi.list(objectId)]);
      setFiles(fs);
      setSections(ss);
      setSectionId((prev) => prev ?? ss[0]?.id);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  }, [objectId, message]);

  useEffect(() => {
    void load();
  }, [load]);

  const createSection = async () => {
    const values = await sectionForm.validateFields();
    try {
      await sectionsApi.create(objectId, {
        code: values.code.trim(),
        name: values.name?.trim() || undefined,
        sort_order: sections.length,
      });
      message.success("Шифр добавлен");
      setAddOpen(false);
      sectionForm.resetFields();
      await load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось создать шифр");
    }
  };

  const runParse = async (file: ObjectFile) => {
    setParsingId(file.id);
    try {
      const updated = await filesApi.parse(objectId, file.id);
      message.success(
        updated.parsed_items > 0 ? `Разобрано позиций: ${updated.parsed_items}` : "Позиции не найдены"
      );
      await load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось разобрать файл");
    } finally {
      setParsingId(undefined);
    }
  };

  const moveFile = async (file: ObjectFile, target: number | null) => {
    try {
      await filesApi.move(objectId, file.id, target);
      await load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось перенести файл");
    }
  };

  const columns: ColumnsType<ObjectFile> = [
    {
      title: "Файл",
      dataIndex: "original_filename",
      render: (v: string, row) => (
        <Space>
          <DownloadOutlined style={{ cursor: "pointer" }} onClick={() => void filesApi.download(objectId, row)} />
          <Typography.Text>{v}</Typography.Text>
        </Space>
      ),
    },
    { title: "Вид", dataIndex: "kind", width: 120, render: (k: DocKind) => KIND_LABELS[k] ?? k },
    {
      title: "Шифр (СО)",
      key: "section",
      width: 180,
      render: (_, row) => (
        <Select
          size="small"
          style={{ width: 165 }}
          value={row.section?.id}
          placeholder="без шифра"
          allowClear
          onChange={(v) => void moveFile(row, v ?? null)}
          options={sections.map((s) => ({ value: s.id, label: s.code }))}
        />
      ),
    },
    { title: "Размер", dataIndex: "size_bytes", width: 90, render: (b: number) => fmtSize(b) },
    {
      title: "Статус",
      dataIndex: "status",
      width: 150,
      render: (s: string, row) => (
        <Space size={4} direction="vertical">
          <Tag color={STATUS_TAGS[s]}>{s === "done" ? `Разобран (${row.parsed_items})` : s}</Tag>
          {row.status === "error" && (
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              {row.error_message}
            </Typography.Text>
          )}
        </Space>
      ),
    },
    { title: "Загружен", dataIndex: "created_at", width: 150, render: (v: string) => formatDateTime(v) },
    {
      title: "Действия",
      key: "actions",
      width: 160,
      render: (_, row) => (
        <Space>
          {row.kind === "spec" && row.original_filename.toLowerCase().endsWith(".pdf") && (
            <Button
              size="small"
              icon={<PlayCircleOutlined />}
              loading={parsingId === row.id}
              onClick={() => void runParse(row)}
            >
              Распарсить
            </Button>
          )}
          <Popconfirm
            title="Удалить файл?"
            okText="Удалить"
            cancelText="Отмена"
            onConfirm={async () => {
              try {
                await filesApi.remove(objectId, row.id);
                message.success("Файл удалён");
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
                if (kind === "spec" && !sectionId) {
                  message.error("Выберите шифр (СО) для спецификации");
                  onError?.(new Error("no section"));
                  return;
                }
                await filesApi.upload(objectId, kind, file as File, sectionId);
                message.success("Файл загружен");
                onSuccess?.({});
                await load();
              } catch (err) {
                message.error(err instanceof Error ? err.message : "Ошибка загрузки");
                onError?.(err as Error);
              }
            }}
          >
            <Typography.Text>
              <CloudUploadOutlined /> Загрузить файл
            </Typography.Text>
          </Upload.Dragger>
          <Select
            value={kind}
            onChange={setKind}
            style={{ width: 150 }}
            options={[
              { value: "spec", label: "Спецификация РД" },
              { value: "passport", label: "Паспорта" },
              { value: "other", label: "Прочее" },
            ]}
          />
          {kind === "spec" && (
            <>
              <Select
                style={{ width: 165 }}
                value={sectionId}
                onChange={setSectionId}
                placeholder="Шифр (СО)"
                options={sections.map((s) => ({ value: s.id, label: s.code }))}
              />
              {isManager && (
                <Button icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>
                  Новый шифр
                </Button>
              )}
            </>
          )}
        </Space>
        <Button icon={<ReloadOutlined />} onClick={() => void load()}>
          Обновить
        </Button>
      </Space>

      <Table<ObjectFile>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={files}
        pagination={false}
        size="small"
        scroll={{ x: 1000 }}
        locale={{ emptyText: "Файлы не загружены" }}
      />

      <Modal
        title="Новый шифр (СО)"
        open={addOpen}
        onCancel={() => setAddOpen(false)}
        onOk={() => void createSection()}
        destroyOnHidden
      >
        <Form form={sectionForm} layout="vertical">
          <Form.Item name="code" label="Код" rules={[{ required: true, message: "Укажите код, напр. ТСО.СО1" }]}>
            <Input placeholder="ТСО.СО1" maxLength={100} />
          </Form.Item>
          <Form.Item name="name" label="Расшифровка (необязательно)">
            <Input placeholder="Спецификация поставки Заказчика" maxLength={255} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
