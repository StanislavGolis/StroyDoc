"use client";

import { useCallback, useEffect, useState } from "react";
import {
  App as AntApp,
  Button,
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
  ReloadOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { filesApi } from "@/lib/api";
import { formatDateTime } from "@/lib/labels";
import type { DocKind, ObjectFile } from "@/lib/types";

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
  const [files, setFiles] = useState<ObjectFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [parsingId, setParsingId] = useState<number>();
  const [kind, setKind] = useState<DocKind>("spec");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setFiles(await filesApi.list(objectId));
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить файлы");
    } finally {
      setLoading(false);
    }
  }, [objectId, message]);

  useEffect(() => {
    void load();
  }, [load]);

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
    { title: "Вид", dataIndex: "kind", width: 130, render: (k: DocKind) => KIND_LABELS[k] ?? k },
    { title: "Размер", dataIndex: "size_bytes", width: 100, render: (b: number) => fmtSize(b) },
    {
      title: "Статус",
      dataIndex: "status",
      width: 170,
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
    { title: "Загружен", dataIndex: "created_at", width: 160, render: (v: string) => formatDateTime(v) },
    {
      title: "Действия",
      key: "actions",
      width: 180,
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
        <Space wrap>
          <Upload.Dragger
            multiple={false}
            showUploadList={false}
            style={{ width: 250, padding: 6 }}
            customRequest={async ({ file, onSuccess, onError }) => {
              try {
                await filesApi.upload(objectId, kind, file as File);
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
            style={{ width: 170 }}
            options={[
              { value: "spec", label: "Спецификация РД" },
              { value: "passport", label: "Паспорта (PDF/ZIP)" },
              { value: "other", label: "Прочее" },
            ]}
          />
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
        locale={{ emptyText: "Файлы не загружены" }}
      />
    </div>
  );
}
