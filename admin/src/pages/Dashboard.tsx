import React from 'react'
import {
  Layout,
  Menu,
  Card,
  Row,
  Col,
  Statistic,
  Table,
  Tag,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  Switch,
  Space,
  message,
  Typography,
  Popconfirm
} from 'antd'
import {
  DashboardOutlined,
  UserOutlined,
  HistoryOutlined,
  SettingOutlined,
  LogoutOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  DeleteOutlined,
  KeyOutlined,
  StopOutlined,
  PlayCircleOutlined,
  SearchOutlined,
  ClearOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { adminApi, User, Task } from '@/api'
import { useAdminAuthStore } from '@/stores/adminAuthStore'

const { Header, Sider, Content } = Layout
const { Title } = Typography

// 超级用户ID
const SUPER_USER_ID = 1

const AdminDashboard: React.FC = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { admin, logout, token } = useAdminAuthStore()
  const [activeMenu, setActiveMenu] = React.useState('dashboard')
  const [userModalVisible, setUserModalVisible] = React.useState(false)
  const [passwordModalVisible, setPasswordModalVisible] = React.useState(false)
  const [selectedUser, setSelectedUser] = React.useState<User | null>(null)
  const [form] = Form.useForm()
  const [passwordForm] = Form.useForm()

  // 任务搜索和选择
  const [searchUsername, setSearchUsername] = React.useState('')
  const [searchPrompt, setSearchPrompt] = React.useState('')
  const [selectedTaskIds, setSelectedTaskIds] = React.useState<number[]>([])
  const [promptModalVisible, setPromptModalVisible] = React.useState(false)
  const [selectedPrompt, setSelectedPrompt] = React.useState('')
  const [previewModalVisible, setPreviewModalVisible] = React.useState(false)
  const [previewTask, setPreviewTask] = React.useState<Task | null>(null)

  // 判断当前登录用户是否是管理员
  const isAdmin = admin?.is_admin === true
  // 判断当前登录用户是否是超级用户
  const isSuperUser = admin?.id === SUPER_USER_ID
  // 判断选中的用户是否是超级用户
  const isTargetSuperUser = (user: User) => user.id === SUPER_USER_ID

  // Queries
  const { data: stats } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => adminApi.getDashboard().then(r => r.data),
    refetchInterval: 30000,
  })

  const { data: users, isLoading: usersLoading } = useQuery({
    queryKey: ['users'],
    queryFn: () => adminApi.getUsers().then(r => r.data),
    enabled: activeMenu === 'users',
  })

  const { data: tasks, isLoading: tasksLoading, refetch: refetchTasks } = useQuery({
    queryKey: ['tasks', searchUsername, searchPrompt],
    queryFn: () => adminApi.getTasks({
      username: searchUsername || undefined,
      prompt: searchPrompt || undefined,
      limit: 100
    }).then(r => r.data),
    enabled: activeMenu === 'tasks',
  })

  const { data: configs, isLoading: configsLoading } = useQuery({
    queryKey: ['configs'],
    queryFn: () => adminApi.getConfigs().then(r => r.data),
    enabled: activeMenu === 'settings',
  })

  // Mutations
  const updateUserMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<User> }) => adminApi.updateUser(id, data),
    onSuccess: () => {
      message.success('更新成功')
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setUserModalVisible(false)
    },
    onError: () => message.error('更新失败'),
  })

  const deleteUserMutation = useMutation({
    mutationFn: (id: number) => adminApi.deleteUser(id),
    onSuccess: () => {
      message.success('用户已删除')
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '删除失败')
    },
  })

  const changePasswordMutation = useMutation({
    mutationFn: ({ id, password }: { id: number; password: string }) =>
      adminApi.changeUserPassword(id, password),
    onSuccess: () => {
      message.success('密码修改成功')
      setPasswordModalVisible(false)
      passwordForm.resetFields()
    },
    onError: () => message.error('密码修改失败'),
  })

  const initConfigsMutation = useMutation({
    mutationFn: () => adminApi.initConfigs(),
    onSuccess: () => {
      message.success('配置初始化成功')
      queryClient.invalidateQueries({ queryKey: ['configs'] })
    },
    onError: () => message.error('初始化失败'),
  })

  const deleteTaskMutation = useMutation({
    mutationFn: (id: number) => adminApi.deleteTask(id),
    onSuccess: () => {
      message.success('任务已删除')
      setSelectedTaskIds([])
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '删除失败')
    },
  })

  const clearAllTasksMutation = useMutation({
    mutationFn: () => adminApi.clearAllTasks(),
    onSuccess: () => {
      message.success('所有任务已清空')
      setSelectedTaskIds([])
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '清空失败')
    },
  })

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleEditUser = (user: User) => {
    setSelectedUser(user)
    form.setFieldsValue(user)
    setUserModalVisible(true)
  }

  const handleSaveUser = () => {
    form.validateFields().then((values) => {
      if (selectedUser) {
        updateUserMutation.mutate({ id: selectedUser.id, data: values })
      }
    })
  }

  const handleDeleteUser = (user: User) => {
    if (isTargetSuperUser(user)) {
      message.error('超级用户不能被删除')
      return
    }
    deleteUserMutation.mutate(user.id)
  }

  const handleToggleUserStatus = (user: User) => {
    if (isTargetSuperUser(user)) {
      message.error('超级用户不能被禁用')
      return
    }
    const newStatus = !user.is_active
    updateUserMutation.mutate({
      id: user.id,
      data: { is_active: newStatus }
    })
  }

  const handleChangePassword = (user: User) => {
    setSelectedUser(user)
    setPasswordModalVisible(true)
  }

  const handleSavePassword = () => {
    passwordForm.validateFields().then((values) => {
      if (selectedUser) {
        if (values.new_password !== values.confirm_password) {
          message.error('两次输入的密码不一致')
          return
        }
        changePasswordMutation.mutate({ id: selectedUser.id, password: values.new_password })
      }
    })
  }

  const getStatusTag = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'default',
      processing: 'processing',
      completed: 'success',
      failed: 'error',
    }
    const labels: Record<string, string> = {
      pending: '等待中',
      processing: '处理中',
      completed: '已完成',
      failed: '失败',
    }
    return <Tag color={colors[status]}>{labels[status]}</Tag>
  }

  const userColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '用户名', dataIndex: 'username', key: 'username' },
    { title: '邮箱', dataIndex: 'email', key: 'email' },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (v: boolean) => v
        ? <Tag icon={<CheckCircleOutlined />} color="success">活跃</Tag>
        : <Tag icon={<CloseCircleOutlined />} color="error">禁用</Tag>
    },
    {
      title: '管理员',
      dataIndex: 'is_admin',
      key: 'is_admin',
      render: (v: boolean) => v ? <Tag color="blue">是</Tag> : <Tag>否</Tag>
    },
    {
      title: '配额',
      key: 'quota',
      render: (_: unknown, record: User) => (
        <span>图片: {record.used_image_quota}/{record.daily_image_quota} | 视频: {record.used_video_quota}/{record.daily_video_quota}</span>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: User) => {
        const isSuper = isTargetSuperUser(record)
        return (
          <Space>
            <Button size="small" onClick={() => handleEditUser(record)}>编辑</Button>
            {isAdmin && (
              <Button size="small" icon={<KeyOutlined />} onClick={() => handleChangePassword(record)}>
                改密
              </Button>
            )}
            {!isSuper && isAdmin && (
              <>
                <Button
                  size="small"
                  danger={record.is_active}
                  icon={record.is_active ? <StopOutlined /> : <PlayCircleOutlined />}
                  onClick={() => handleToggleUserStatus(record)}
                >
                  {record.is_active ? '禁用' : '启用'}
                </Button>
                <Popconfirm
                  title="确定要删除该用户吗？"
                  description="此操作不可恢复"
                  onConfirm={() => handleDeleteUser(record)}
                  okText="确定"
                  cancelText="取消"
                >
                  <Button size="small" danger icon={<DeleteOutlined />}>
                    删除
                  </Button>
                </Popconfirm>
              </>
            )}
          </Space>
        )
      }
    },
  ]

  const taskColumns = [
    ...(isSuperUser ? [{
      title: (
        <input
          type="checkbox"
          checked={tasks && tasks.length > 0 && selectedTaskIds.length === tasks.length}
          onChange={(e) => {
            if (e.target.checked && tasks) {
              setSelectedTaskIds(tasks.map((t: Task) => t.id))
            } else {
              setSelectedTaskIds([])
            }
          }}
        />
      ),
      key: 'selection',
      width: 50,
      render: (_: unknown, record: Task) => (
        <input
          type="checkbox"
          checked={selectedTaskIds.includes(record.id)}
          onChange={(e) => {
            if (e.target.checked) {
              setSelectedTaskIds([...selectedTaskIds, record.id])
            } else {
              setSelectedTaskIds(selectedTaskIds.filter(id => id !== record.id))
            }
          }}
        />
      )
    }] : []),
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '用户名', dataIndex: 'username', key: 'username', width: 100 },
    {
      title: '类型',
      dataIndex: 'task_type',
      key: 'task_type',
      render: (v: string) => v === 'image_generation' ? '图像生成' : '视频生成'
    },
    { title: '状态', dataIndex: 'status', key: 'status', render: getStatusTag },
    {
      title: '提示词',
      dataIndex: 'input_data',
      key: 'prompt',
      render: (v: { prompt?: string }) => (
        <span
          style={{ cursor: 'pointer' }}
          onDoubleClick={() => {
            setSelectedPrompt(v?.prompt || '')
            setPromptModalVisible(true)
          }}
        >
          {v?.prompt?.slice(0, 30) + '...'}
        </span>
      )
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString()
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, record: Task) => (
        <Button
          size="small"
          type="link"
          onClick={() => {
            setPreviewTask(record)
            setPreviewModalVisible(true)
          }}
          disabled={record.status !== 'completed'}
        >
          显示
        </Button>
      )
    },
  ]

  const getPreviewUrl = (taskId: number) => {
    return adminApi.getTaskPreviewUrl(taskId, token || '')
  }

  const menuItems = [
    { key: 'dashboard', icon: <DashboardOutlined />, label: '仪表盘' },
    { key: 'users', icon: <UserOutlined />, label: '用户管理' },
    { key: 'tasks', icon: <HistoryOutlined />, label: '任务管理' },
    { key: 'settings', icon: <SettingOutlined />, label: '系统配置' },
  ]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Title level={3} style={{ color: 'white', margin: 0 }}>Img2Video Admin</Title>
        <Space>
          <span style={{ color: 'white' }}>欢迎, {admin?.username}</span>
          <Button type="link" onClick={handleLogout} icon={<LogoutOutlined />} style={{ color: 'white' }}>
            退出
          </Button>
        </Space>
      </Header>

      <Layout>
        <Sider width={200} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[activeMenu]}
            style={{ height: '100%', borderRight: 0 }}
            items={menuItems}
            onClick={(e) => setActiveMenu(e.key)}
          />
        </Sider>

        <Content style={{ padding: 24, background: '#f0f2f5', minHeight: 'calc(100vh - 64px)' }}>
          {activeMenu === 'dashboard' && (
            <>
              <Row gutter={16}>
                <Col span={6}>
                  <Card>
                    <Statistic title="总用户数" value={stats?.total_users || 0} prefix={<UserOutlined />} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card>
                    <Statistic title="活跃用户" value={stats?.active_users || 0} valueStyle={{ color: '#3f8600' }} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card>
                    <Statistic title="总任务数" value={stats?.total_tasks || 0} />
                  </Card>
                </Col>
                <Col span={6}>
                  <Card>
                    <Statistic title="完成率" value={
                      stats?.total_tasks
                        ? Math.round((stats.completed_tasks / stats.total_tasks) * 100)
                        : 0
                    } suffix="%" />
                  </Card>
                </Col>
              </Row>

              <Row gutter={16} style={{ marginTop: 16 }}>
                <Col span={12}>
                  <Card title="任务状态分布">
                    <Row gutter={16}>
                      <Col span={6}>
                        <Statistic title="等待中" value={stats?.pending_tasks || 0} />
                      </Col>
                      <Col span={6}>
                        <Statistic title="处理中" value={0} valueStyle={{ color: '#1890ff' }} />
                      </Col>
                      <Col span={6}>
                        <Statistic title="已完成" value={stats?.completed_tasks || 0} valueStyle={{ color: '#52c41a' }} />
                      </Col>
                      <Col span={6}>
                        <Statistic title="失败" value={stats?.failed_tasks || 0} valueStyle={{ color: '#ff4d4f' }} />
                      </Col>
                    </Row>
                  </Card>
                </Col>
                <Col span={12}>
                  <Card title="生成内容统计">
                    <Row gutter={16}>
                      <Col span={12}>
                        <Statistic title="生成图片" value={stats?.total_images || 0} />
                      </Col>
                      <Col span={12}>
                        <Statistic title="生成视频" value={stats?.total_videos || 0} />
                      </Col>
                    </Row>
                  </Card>
                </Col>
              </Row>
            </>
          )}

          {activeMenu === 'users' && (
            <Card title="用户列表">
              <Table
                columns={userColumns}
                dataSource={users}
                rowKey="id"
                loading={usersLoading}
                pagination={{ pageSize: 20 }}
              />
            </Card>
          )}

          {activeMenu === 'tasks' && (
            <Card
              title="任务列表"
              extra={isSuperUser && (
                <Space>
                  <Popconfirm
                    title="确定要删除选中的任务吗？"
                    description={`将删除 ${selectedTaskIds.length} 个任务`}
                    onConfirm={() => {
                      selectedTaskIds.forEach(id => deleteTaskMutation.mutate(id))
                    }}
                    okText="确定"
                    cancelText="取消"
                    disabled={selectedTaskIds.length === 0}
                  >
                    <Button
                      danger
                      icon={<DeleteOutlined />}
                      disabled={selectedTaskIds.length === 0}
                    >
                      删除选中 ({selectedTaskIds.length})
                    </Button>
                  </Popconfirm>
                  <Popconfirm
                    title="确定要清空所有任务吗？"
                    description="此操作不可恢复"
                    onConfirm={() => clearAllTasksMutation.mutate()}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button danger icon={<ClearOutlined />}>
                      清空所有
                    </Button>
                  </Popconfirm>
                </Space>
              )}
            >
              <Space style={{ marginBottom: 16 }}>
                <Input
                  placeholder="按用户名搜索"
                  value={searchUsername}
                  onChange={(e) => setSearchUsername(e.target.value)}
                  prefix={<SearchOutlined />}
                  style={{ width: 200 }}
                  allowClear
                />
                <Input
                  placeholder="按提示词搜索"
                  value={searchPrompt}
                  onChange={(e) => setSearchPrompt(e.target.value)}
                  prefix={<SearchOutlined />}
                  style={{ width: 200 }}
                  allowClear
                />
                <Button onClick={() => refetchTasks()}>搜索</Button>
                <Button icon={<ReloadOutlined />} onClick={() => refetchTasks()}>刷新</Button>
              </Space>
              <Table
                columns={taskColumns}
                dataSource={tasks}
                rowKey="id"
                loading={tasksLoading}
                pagination={{ pageSize: 20 }}
              />
            </Card>
          )}

          {activeMenu === 'settings' && (
            <Card
              title="系统配置"
              extra={<Button type="primary" onClick={() => initConfigsMutation.mutate()}>初始化默认配置</Button>}
            >
              <Table
                dataSource={configs}
                rowKey="id"
                loading={configsLoading}
                pagination={false}
                columns={[
                  { title: '配置键', dataIndex: 'key', key: 'key' },
                  { title: '配置值', dataIndex: 'value', key: 'value' },
                  { title: '描述', dataIndex: 'description', key: 'description' },
                  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', render: (v: string) => new Date(v).toLocaleString() },
                ]}
              />
            </Card>
          )}
        </Content>
      </Layout>

      <Modal
        title="编辑用户"
        open={userModalVisible}
        onOk={handleSaveUser}
        onCancel={() => setUserModalVisible(false)}
        confirmLoading={updateUserMutation.isPending}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="username" label="用户名">
            <Input disabled />
          </Form.Item>
          <Form.Item name="email" label="邮箱">
            <Input disabled={admin?.id !== SUPER_USER_ID} />
          </Form.Item>
          <Form.Item name="is_active" label="是否活跃" valuePropName="checked">
            <Switch disabled={selectedUser?.id === SUPER_USER_ID} />
          </Form.Item>
          <Form.Item name="is_admin" label="是否管理员" valuePropName="checked">
            <Switch disabled={selectedUser?.id === SUPER_USER_ID} />
          </Form.Item>
          <Form.Item name="daily_image_quota" label="每日图片配额">
            <InputNumber min={0} max={1000} />
          </Form.Item>
          <Form.Item name="daily_video_quota" label="每日视频配额">
            <InputNumber min={0} max={100} />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`修改用户密码 - ${selectedUser?.username}`}
        open={passwordModalVisible}
        onOk={handleSavePassword}
        onCancel={() => {
          setPasswordModalVisible(false)
          passwordForm.resetFields()
        }}
        confirmLoading={changePasswordMutation.isPending}
      >
        <Form form={passwordForm} layout="vertical">
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少6个字符' },
            ]}
          >
            <Input.Password placeholder="请输入新密码" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label="确认密码"
            rules={[{ required: true, message: '请确认新密码' }]}
          >
            <Input.Password placeholder="请再次输入新密码" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="提示词详情"
        open={promptModalVisible}
        onCancel={() => setPromptModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setPromptModalVisible(false)}>
            关闭
          </Button>,
        ]}
        width={600}
      >
        <Input.TextArea
          value={selectedPrompt}
          readOnly
          autoSize={{ minRows: 6, maxRows: 15 }}
          style={{ fontFamily: 'monospace' }}
        />
      </Modal>

      <Modal
        title={previewTask?.task_type === 'image_generation' ? '生成的图片' : '生成的视频'}
        open={previewModalVisible}
        onCancel={() => setPreviewModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setPreviewModalVisible(false)}>
            关闭
          </Button>,
        ]}
        width={800}
        centered
      >
        {previewTask && (
          previewTask.task_type === 'image_generation' ? (
            <img
              src={getPreviewUrl(previewTask.id)}
              alt="Generated"
              style={{ width: '100%', maxHeight: '70vh', objectFit: 'contain' }}
            />
          ) : (
            <video
              src={getPreviewUrl(previewTask.id)}
              controls
              style={{ width: '100%', maxHeight: '70vh' }}
            />
          )
        )}
      </Modal>
    </Layout>
  )
}

export default AdminDashboard
