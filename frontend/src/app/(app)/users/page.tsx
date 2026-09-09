"use client";

import { useCallback, useEffect, useState } from "react";
import {
  App as AntApp,
  Button,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Table,
  Tag,
  Typography,
} from "antd";
import { PlusOutlined, ReloadOutlined, StopOutlined, CheckCircleOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { usersApi } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { ROLE_LABELS } from "@/lib/labels";
import type { Role, User } from "@/lib/types";

export default function UsersPage() {
  const { user: me } = useAuth();
  const { message } = AntApp.useApp();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [passwordModal, setPasswordModal] = useState<{ title: string; password: string } | null>(null);
  const [form] = Form.useForm<{ email: string; full_name: string; role: Role }>();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setUsers(await usersApi.list());
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось загрузить пользователей");
    } finally {
      setLoading(false);
    }
  }, [message]);

  useEffect(() => {
    void load();
  }, [load]);

  const createUser = async () => {
    const values = await form.validateFields();
    try {
      const resp = await usersApi.create(values);
      message.success("Пользователь создан");
      setCreateOpen(false);
      form.resetFields();
      await load();
      setPasswordModal({
        title: `Пароль для ${resp.user.email}`,
        password: resp.generated_password,
      });
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось создать пользователя");
    }
  };

  const resetPassword = async (id: number, email: string) => {
    try {
      const resp = await usersApi.resetPassword(id);
      message.success("Пароль сброшен");
      setPasswordModal({
        title: `Новый пароль для ${email}`,
        password: resp.generated_password,
      });
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось сбросить пароль");
    }
  };

  const toggleActive = async (user: User) => {
    try {
      await usersApi.update(user.id, { is_active: !user.is_active });
      message.success(user.is_active ? "Пользователь деактивирован" : "Пользователь активирован");
      await load();
    } catch (err) {
      message.error(err instanceof Error ? err.message : "Не удалось изменить статус");
    }
  };

  const columns: ColumnsType<User> = [
    { title: "ФИО", dataIndex: "full_name" },
    { title: "Email", dataIndex: "email" },
    {
      title: "Роль",
      dataIndex: "role",
      width: 180,
      render: (r: Role) => (
        <Tag color={r === "admin" ? "gold" : r === "pto_head" ? "blue" : "green"}>
          {ROLE_LABELS[r]}
        </Tag>
      ),
    },
    {
      title: "Активен",
      dataIndex: "is_active",
      width: 120,
      render: (v: boolean) => (v ? <Tag color="success">Да</Tag> : <Tag color="error">Нет</Tag>),
    },
    {
      title: "Действия",
      key: "actions",
      width: 260,
      render: (_, row) => (
        <Space>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => void resetPassword(row.id, row.email)}
          >
            Сброс пароля
          </Button>
          {row.id !== me?.id && (
            <Button
              size="small"
              danger={row.is_active}
              icon={row.is_active ? <StopOutlined /> : <CheckCircleOutlined />}
              onClick={() => void toggleActive(row)}
            >
              {row.is_active ? "Деактивировать" : "Активировать"}
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Space style={{ width: "100%", justifyContent: "space-between", marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Пользователи
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Новый пользователь
        </Button>
      </Space>

      <Table<User>
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={users}
        pagination={false}
        locale={{ emptyText: "Пользователей пока нет" }}
      />
      <Modal
        title="Новый пользователь"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={() => void createUser()}
        destroyOnHidden
      >
        <Form form={form} layout="vertical">
          <Form.Item name="full_name" label="ФИО" rules={[{ required: true, message: "Укажите ФИО" }]}>
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item
            name="email"
            label="Email"
            rules={[
              { required: true, message: "Укажите email" },
              { type: "email", message: "Некорректный email" },
            ]}
          >
            <Input maxLength={255} />
          </Form.Item>
          <Form.Item name="role" label="Роль" rules={[{ required: true, message: "Выберите роль" }]}>
            <Select
              options={[
                { value: "pto_engineer", label: "Инженер ПТО" },
                { value: "pto_head", label: "Руководитель ПТО" },
                { value: "admin", label: "Администратор" },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={passwordModal?.title}
        open={Boolean(passwordModal)}
        footer={
          <Button
            type="primary"
            onClick={() => void navigator.clipboard?.writeText(passwordModal?.password ?? "")}
          >
            Скопировать
          </Button>
        }
        onCancel={() => setPasswordModal(null)}
        destroyOnHidden
      >
        <Typography.Paragraph>Сохраните пароль — он показывается один раз:</Typography.Paragraph>
        <Typography.Text code copyable style={{ fontSize: 16 }}>
          {passwordModal?.password}
        </Typography.Text>
      </Modal>
    </div>
  );
}

