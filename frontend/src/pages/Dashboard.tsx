import React from 'react'
import {
  Layout,
  Menu,
  Typography,
  Card,
  Row,
  Col,
  Upload,
  Button,
  Input,
  Tag,
  Space,
  message,
  Empty,
  Spin,
  Modal,
  Image,
  Select,
  Form
} from 'antd'
import {
  UploadOutlined,
  DeleteOutlined,
  PictureOutlined,
  VideoCameraOutlined,
  HistoryOutlined,
  LogoutOutlined,
  UserOutlined,
  DownloadOutlined,
  PlayCircleOutlined,
  ExclamationCircleOutlined,
  EyeOutlined,
  SettingOutlined,
  LockOutlined
} from '@ant-design/icons'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { imageApi, authApi } from '@/api'
import { useAuthStore } from '@/stores/authStore'
import { useNavigate } from 'react-router-dom'

const { Header, Content, Sider } = Layout
const { Title, Text } = Typography
const { TextArea } = Input

const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user, logout, token, updateUser } = useAuthStore()

  // State
  const [selectedReferences, setSelectedReferences] = React.useState<number[]>([])
  const [prompt, setPrompt] = React.useState('')
  const [negativePrompt, setNegativePrompt] = React.useState('')
  const [activeTab, setActiveTab] = React.useState<'generate' | 'video' | 'history' | 'settings'>('generate')
  const [selectedImageForVideo, setSelectedImageForVideo] = React.useState<number | null>(null)
  const [videoPrompt, setVideoPrompt] = React.useState('')
  const [videoDuration, setVideoDuration] = React.useState<number>(5)
  const [previewVisible, setPreviewVisible] = React.useState(false)
  const [previewWork, setPreviewWork] = React.useState<{id: number, work_type: string, url: string, filename: string} | null>(null)
  const [previewReference, setPreviewReference] = React.useState<{id: number, url: string, filename: string} | null>(null)
  const [changePasswordVisible, setChangePasswordVisible] = React.useState(false)
  const [changePasswordLoading, setChangePasswordLoading] = React.useState(false)

  // Queries
  const { data: references, isLoading: refLoading } = useQuery({
    queryKey: ['references'],
    queryFn: () => imageApi.listReferences().then(r => r.data),
  })

  const { data: tasks, isLoading: tasksLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: async () => {
      const res = await imageApi.listTasks()
      // If any task just completed, refresh user quota
      const tasks = res.data
      const hasCompletedTask = tasks.some(
        t => t.status === 'completed' && t.task_type === 'video_generation'
      )
      if (hasCompletedTask) {
        try {
          const userRes = await authApi.getMe()
          updateUser(userRes.data)
        } catch {
          // Ignore errors
        }
      }
      return tasks
    },
    refetchInterval: 5000, // Poll every 5 seconds
  })

  const { data: works, isLoading: worksLoading, refetch: refetchWorks } = useQuery({
    queryKey: ['works'],
    queryFn: () => imageApi.listWorks().then(r => r.data),
    refetchInterval: 5000, // Poll every 5 seconds
  })

  // Mutations
  const uploadMutation = useMutation({
    mutationFn: (file: File) => imageApi.uploadReference(file),
    onSuccess: () => {
      message.success('上传成功')
      queryClient.invalidateQueries({ queryKey: ['references'] })
    },
    onError: () => message.error('上传失败'),
  })

  const deleteRefMutation = useMutation({
    mutationFn: (id: number) => imageApi.deleteReference(id),
    onSuccess: () => {
      message.success('删除成功')
      queryClient.invalidateQueries({ queryKey: ['references'] })
      setSelectedReferences(prev => prev.filter(id => id !== id))
    },
    onError: () => message.error('删除失败'),
  })

  const generateMutation = useMutation({
    mutationFn: imageApi.generateImage,
    onSuccess: async () => {
      message.success('任务已创建，正在生成中...')
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      setPrompt('')
      // Fetch updated user quota
      try {
        const res = await authApi.getMe()
        updateUser(res.data)
      } catch {
        // Ignore quota update errors
      }
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '创建任务失败')
    },
  })

  const videoMutation = useMutation({
    mutationFn: imageApi.generateVideo,
    onSuccess: async () => {
      message.success('视频生成任务已创建')
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      setVideoPrompt('')
      setSelectedImageForVideo(null)
      // Fetch updated user quota
      try {
        const res = await authApi.getMe()
        updateUser(res.data)
      } catch {
        // Ignore quota update errors
      }
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '创建视频任务失败')
    },
  })

  const deleteWorkMutation = useMutation({
    mutationFn: (id: number) => imageApi.deleteWork(id),
    onSuccess: () => {
      message.success('删除成功')
      queryClient.invalidateQueries({ queryKey: ['works'] })
    },
    onError: () => message.error('删除失败'),
  })

  const handleDeleteReference = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      icon: <ExclamationCircleOutlined />,
      content: '确定要删除这张参考图片吗？',
      okText: '确定',
      cancelText: '取消',
      onOk: () => deleteRefMutation.mutate(id),
    })
  }

  const handleDeleteWork = (id: number) => {
    Modal.confirm({
      title: '确认删除',
      icon: <ExclamationCircleOutlined />,
      content: '确定要删除这个作品吗？删除后无法恢复。',
      okText: '确定',
      cancelText: '取消',
      onOk: () => deleteWorkMutation.mutate(id),
    })
  }

  const handleUpload = (file: File) => {
    uploadMutation.mutate(file)
    return false
  }

  const handleGenerate = () => {
    if (!user?.is_active) {
      Modal.warning({
        title: '提示',
        content: '账户已被禁用，无法使用生成功能',
      })
      return
    }
    if (!prompt.trim()) {
      Modal.warning({
        title: '提示',
        content: '请输入提示词',
      })
      return
    }

    // 检查是否选择了参考图片
    if (selectedReferences.length === 0) {
      Modal.confirm({
        title: '提示',
        icon: <ExclamationCircleOutlined />,
        content: '您没有选择参考图片，生成的图像将不会参考任何风格。确定要继续吗？',
        okText: '确定',
        cancelText: '取消',
        onOk: () => {
          generateMutation.mutate({
            prompt,
            negative_prompt: negativePrompt || undefined,
            reference_image_ids: selectedReferences,
          })
        },
      })
      return
    }

    generateMutation.mutate({
      prompt,
      negative_prompt: negativePrompt || undefined,
      reference_image_ids: selectedReferences,
    })
  }

  const handleGenerateVideo = () => {
    if (!user?.is_active) {
      Modal.warning({
        title: '提示',
        content: '账户已被禁用，无法使用生成功能',
      })
      return
    }
    if (!selectedImageForVideo) {
      Modal.warning({
        title: '提示',
        content: '请选择一张图片作为视频源',
      })
      return
    }
    if (!videoPrompt.trim()) {
      Modal.warning({
        title: '提示',
        content: '请输入动画指令',
      })
      return
    }
    videoMutation.mutate({
      image_id: selectedImageForVideo,
      prompt: videoPrompt,
      duration: videoDuration,
    })
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const handleChangePassword = async (values: { old_password: string; new_password: string; confirm_password: string }) => {
    if (values.new_password !== values.confirm_password) {
      message.error('两次输入的新密码不一致')
      return
    }

    setChangePasswordLoading(true)
    try {
      await authApi.changePassword({
        old_password: values.old_password,
        new_password: values.new_password
      })
      message.success('密码修改成功')
      setChangePasswordVisible(false)
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '密码修改失败')
    } finally {
      setChangePasswordLoading(false)
    }
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

  // Refetch works when switching to history tab
  React.useEffect(() => {
    if (activeTab === 'history') {
      refetchWorks()
    }
  }, [activeTab, refetchWorks])

  const handlePreview = (work: {id: number, work_type: string, url: string, filename: string}) => {
    setPreviewWork(work)
    setPreviewVisible(true)
  }

  const handleDownload = async (workId: number, filename?: string) => {
    try {
      const res = await imageApi.downloadWork(workId)
      const blob = new Blob([res.data])
      const url = window.URL.createObjectURL(blob)
      const link = window.document.createElement('a')
      link.href = url
      link.download = filename || 'download'
      window.document.body.appendChild(link)
      link.click()
      window.document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch {
      message.error('下载失败')
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Title level={3} style={{ color: 'white', margin: 0 }}>Img2Video</Title>
        <Space>
          <Text style={{ color: 'white' }}>
            <UserOutlined /> {user?.username}
          </Text>
          <Text style={{ color: 'white' }}>
            图片配额: {user?.used_image_quota}/{user?.daily_image_quota}
          </Text>
          <Text style={{ color: 'white' }}>
            视频配额: {user?.used_video_quota}/{user?.daily_video_quota}
          </Text>
          <Button type="link" onClick={handleLogout} icon={<LogoutOutlined />} style={{ color: 'white' }}>
            退出
          </Button>
        </Space>
      </Header>

      <Layout>
        <Sider width={220} theme="light">
          <Menu
            mode="inline"
            selectedKeys={[activeTab]}
            style={{ height: '100%', borderRight: 0 }}
            items={[
              { key: 'generate', icon: <PictureOutlined />, label: '图像生成' },
              { key: 'video', icon: <VideoCameraOutlined />, label: '视频生成' },
              { key: 'history', icon: <HistoryOutlined />, label: '历史记录' },
              { key: 'settings', icon: <SettingOutlined />, label: '系统设置' },
            ]}
            onClick={(e) => setActiveTab(e.key as typeof activeTab)}
          />
        </Sider>

        <Content style={{ padding: 24, background: '#f0f2f5' }}>
          {activeTab === 'generate' && (
            <Row gutter={24}>
              {/* Reference Images */}
              <Col span={8}>
                <Card title="参考图片" extra={
                  <Upload
                    accept=".jpg,.jpeg,.png"
                    showUploadList={false}
                    beforeUpload={handleUpload}
                  >
                    <Button icon={<UploadOutlined />} loading={uploadMutation.isPending}>
                      上传
                    </Button>
                  </Upload>
                }>
                  <Spin spinning={refLoading}>
                    {references && references.length > 0 ? (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                        {references.map((ref) => (
                          <div
                            key={ref.id}
                            onClick={() => {
                              setSelectedReferences(prev =>
                                prev.includes(ref.id)
                                  ? prev.filter(id => id !== ref.id)
                                  : [...prev, ref.id].slice(-3) // Max 3
                              )
                            }}
                            style={{
                              position: 'relative',
                              cursor: 'pointer',
                              border: selectedReferences.includes(ref.id) ? '2px solid #1890ff' : '2px solid transparent',
                              borderRadius: 4,
                            }}
                          >
                            <div style={{
                              position: 'relative',
                              width: '100%',
                              paddingTop: '100%',
                              background: '#f0f0f0',
                              borderRadius: 4,
                              overflow: 'hidden',
                            }}>
                              {ref.url && token ? (
                                <img src={`${ref.url}?token=${token}`} alt={ref.original_filename} style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain' }} />
                              ) : (
                                <PictureOutlined style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', fontSize: 32, color: '#999' }} />
                              )}
                            </div>
                            <div style={{ position: 'absolute', top: 4, right: 4, display: 'flex', gap: 4 }}>
                              <Button
                                size="small"
                                icon={<EyeOutlined />}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setPreviewReference({id: ref.id, url: ref.url || '', filename: ref.original_filename})
                                }}
                              />
                              <Button
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  handleDeleteReference(ref.id)
                                }}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Empty description="暂无参考图片" />
                    )}
                  </Spin>
                  <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                    最多选择3张参考图片用于风格克隆
                  </Text>
                </Card>
              </Col>

              {/* Generation Form */}
              <Col span={16}>
                <Card title="生成设置">
                  <Space direction="vertical" style={{ width: '100%' }} size="large">
                    <div>
                      <Text strong>提示词</Text>
                      <TextArea
                        rows={4}
                        value={prompt}
                        onChange={(e) => setPrompt(e.target.value)}
                        placeholder="描述你想要生成的图像，例如：一个可爱的女孩，粉色头发，穿着白色连衣裙..."
                      />
                    </div>

                    <div>
                      <Text strong>负面提示词（可选）</Text>
                      <TextArea
                        rows={2}
                        value={negativePrompt}
                        onChange={(e) => setNegativePrompt(e.target.value)}
                        placeholder="描述不想出现的内容，例如：模糊, 低质量, 变形..."
                      />
                    </div>

                    <Button
                      type="primary"
                      size="large"
                      block
                      onClick={handleGenerate}
                      loading={generateMutation.isPending}
                      disabled={!prompt.trim()}
                    >
                      生成图像
                    </Button>
                  </Space>
                </Card>

                {/* Recent Tasks */}
                <Card title="近期任务" style={{ marginTop: 24 }}>
                  <Spin spinning={tasksLoading}>
                    {tasks && tasks.filter(t => t.task_type === 'image_generation').length > 0 ? (
                      <Space direction="vertical" style={{ width: '100%' }}>
                        {tasks.filter(t => t.task_type === 'image_generation').slice(0, 5).map((task) => (
                          <div key={task.id} style={{
                            padding: 12,
                            background: '#fafafa',
                            borderRadius: 4,
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}>
                            <div>
                              <Text>图像生成</Text>
                              <br />
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                {(task.input_data as { prompt?: string })?.prompt?.slice(0, 50)}...
                              </Text>
                            </div>
                            {getStatusTag(task.status)}
                          </div>
                        ))}
                      </Space>
                    ) : (
                      <Empty description="暂无任务" />
                    )}
                  </Spin>
                </Card>
              </Col>
            </Row>
          )}

          {activeTab === 'video' && (
            <Row gutter={24}>
              {/* Select Image */}
              <Col span={8}>
                <Card title="选择源图片" style={{ height: '100%' }} styles={{ body: { maxHeight: 500, overflow: 'auto' } }}>
                  <Spin spinning={worksLoading}>
                    {works && works.filter(w => w.work_type === 'image').length > 0 ? (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                        {works.filter(w => w.work_type === 'image').map((work) => (
                          <div
                            key={work.id}
                            onClick={() => setSelectedImageForVideo(work.id)}
                            style={{
                              position: 'relative',
                              width: '100%',
                              paddingTop: '100%',
                              background: '#f0f0f0',
                              cursor: 'pointer',
                              border: selectedImageForVideo === work.id ? '2px solid #1890ff' : '2px solid transparent',
                              borderRadius: 4,
                              overflow: 'hidden'
                            }}
                          >
                            {work.url && token ? (
                              <img
                                src={`${work.url}?token=${token}`}
                                alt={work.filename}
                                style={{
                                  position: 'absolute',
                                  top: 0,
                                  left: 0,
                                  width: '100%',
                                  height: '100%',
                                  objectFit: 'contain'
                                }}
                              />
                            ) : (
                              <PictureOutlined style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', fontSize: 32, color: '#999' }} />
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Empty description="暂无可用的图片，请先生成图片" />
                    )}
                  </Spin>
                </Card>
              </Col>

              {/* Video Settings */}
              <Col span={16}>
                <Card title="动画设置">
                  <Space direction="vertical" style={{ width: '100%' }} size="large">
                    <div>
                      <Text strong>动画指令</Text>
                      <TextArea
                        rows={4}
                        value={videoPrompt}
                        onChange={(e) => setVideoPrompt(e.target.value)}
                        placeholder="描述想要的动画效果，例如：让角色挥手，头发被风吹动..."
                      />
                    </div>

                    <div>
                      <Text strong>视频时长（秒）</Text>
                      <Select
                        value={videoDuration}
                        onChange={(value) => setVideoDuration(value)}
                        style={{ width: 120 }}
                        options={[
                          { value: 5, label: '5' },
                          { value: 10, label: '10' },
                        ]}
                      />
                    </div>

                    <Button
                      type="primary"
                      size="large"
                      block
                      onClick={handleGenerateVideo}
                      loading={videoMutation.isPending}
                      disabled={!selectedImageForVideo || !videoPrompt.trim()}
                    >
                      生成视频
                    </Button>
                  </Space>
                </Card>

                {/* Recent Video Tasks */}
                <Card title="近期任务" style={{ marginTop: 24 }}>
                  <Spin spinning={tasksLoading}>
                    {tasks && tasks.filter(t => t.task_type === 'video_generation').length > 0 ? (
                      <Space direction="vertical" style={{ width: '100%' }}>
                        {tasks.filter(t => t.task_type === 'video_generation').slice(0, 5).map((task) => (
                          <div key={task.id} style={{
                            padding: 12,
                            background: '#fafafa',
                            borderRadius: 4,
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}>
                            <div>
                              <Text>视频生成</Text>
                              <br />
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                {(task.input_data as { prompt?: string })?.prompt?.slice(0, 50)}...
                              </Text>
                            </div>
                            {getStatusTag(task.status)}
                          </div>
                        ))}
                      </Space>
                    ) : (
                      <Empty description="暂无任务" />
                    )}
                  </Spin>
                </Card>
              </Col>
            </Row>
          )}

          {activeTab === 'history' && (
            <Row gutter={24}>
              <Col span={12}>
                <Card title="生成的图片">
                  <Spin spinning={worksLoading}>
                    {works && works.filter(w => w.work_type === 'image').length > 0 ? (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                        {works.filter(w => w.work_type === 'image').map((work) => (
                          <div
                            key={work.id}
                            style={{
                              position: 'relative',
                              border: '1px solid #f0f0f0',
                              borderRadius: 4,
                              overflow: 'hidden',
                              background: '#fafafa'
                            }}
                          >
                            <div
                              style={{
                                position: 'relative',
                                width: '100%',
                                paddingTop: '100%',
                                background: '#f0f0f0',
                                cursor: 'pointer',
                                overflow: 'hidden'
                              }}
                              onClick={() => handlePreview({id: work.id, work_type: work.work_type, url: work.url || '', filename: work.filename})}
                            >
                              {work.url && token ? (
                                <img
                                  src={`${work.url}?token=${token}`}
                                  alt={work.filename}
                                  style={{
                                    position: 'absolute',
                                    top: 0,
                                    left: 0,
                                    width: '100%',
                                    height: '100%',
                                    objectFit: 'contain'
                                  }}
                                />
                              ) : (
                                <PictureOutlined style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', fontSize: 48, color: '#999' }} />
                              )}
                            </div>
                            <div style={{ padding: '8px' }}>
                              <Text ellipsis style={{ fontSize: 12, display: 'block' }}>
                                {work.prompt}
                              </Text>
                              <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                <Button
                                  size="small"
                                  icon={<DownloadOutlined />}
                                  onClick={() => handleDownload(work.id, work.filename)}
                                >
                                  下载
                                </Button>
                                <Button
                                  size="small"
                                  onClick={() => {
                                    setSelectedImageForVideo(work.id)
                                    setActiveTab('video')
                                  }}
                                >
                                  生成视频
                                </Button>
                                <Button
                                  size="small"
                                  danger
                                  icon={<DeleteOutlined />}
                                  onClick={() => handleDeleteWork(work.id)}
                                >
                                  删除
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Empty description="暂无生成的图片" />
                    )}
                  </Spin>
                </Card>
              </Col>

              <Col span={12}>
                <Card title="生成的视频">
                  <Spin spinning={worksLoading}>
                    {works && works.filter(w => w.work_type === 'video').length > 0 ? (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                        {works.filter(w => w.work_type === 'video').map((work) => (
                          <div
                            key={work.id}
                            style={{
                              position: 'relative',
                              border: '1px solid #f0f0f0',
                              borderRadius: 4,
                              overflow: 'hidden',
                              background: '#fafafa'
                            }}
                          >
                            <div
                              style={{
                                position: 'relative',
                                width: '100%',
                                paddingTop: '100%',
                                background: '#f0f0f0',
                                cursor: 'pointer',
                                overflow: 'hidden'
                              }}
                              onClick={() => handlePreview({id: work.id, work_type: work.work_type, url: work.url || '', filename: work.filename})}
                            >
                              {work.url && token ? (
                                <video
                                  src={`${work.url}?token=${token}`}
                                  style={{
                                    position: 'absolute',
                                    top: 0,
                                    left: 0,
                                    width: '100%',
                                    height: '100%',
                                    objectFit: 'contain'
                                  }}
                                />
                              ) : (
                                <PlayCircleOutlined style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', fontSize: 48, color: '#999' }} />
                              )}
                            </div>
                            <div style={{ padding: '8px' }}>
                              <Text ellipsis style={{ fontSize: 12, display: 'block' }}>
                                {work.prompt}
                              </Text>
                              <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
                                <Button
                                  size="small"
                                  icon={<DownloadOutlined />}
                                  onClick={() => handleDownload(work.id, work.filename)}
                                >
                                  下载
                                </Button>
                                <Button
                                  size="small"
                                  danger
                                  icon={<DeleteOutlined />}
                                  onClick={() => handleDeleteWork(work.id)}
                                >
                                  删除
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <Empty description="暂无生成的视频" />
                    )}
                  </Spin>
                </Card>
              </Col>
            </Row>
          )}

          {activeTab === 'settings' && (
            <Row gutter={24}>
              <Col span={12}>
                <Card title="账户设置">
                  <Space direction="vertical" style={{ width: '100%' }} size="large">
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: 16, background: '#fafafa', borderRadius: 4 }}>
                      <div>
                        <Text strong>修改密码</Text>
                        <br />
                        <Text type="secondary">定期修改密码可以提高账户安全性</Text>
                      </div>
                      <Button
                        type="primary"
                        icon={<LockOutlined />}
                        onClick={() => setChangePasswordVisible(true)}
                      >
                        修改密码
                      </Button>
                    </div>
                  </Space>
                </Card>
              </Col>
            </Row>
          )}
        </Content>
      </Layout>

      {/* Preview Modal */}
      <Modal
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={[
          <Button key="download" type="primary" icon={<DownloadOutlined />} onClick={() => previewWork && handleDownload(previewWork.id, previewWork.filename)}>
            下载
          </Button>,
          <Button key="close" onClick={() => setPreviewVisible(false)}>
            关闭
          </Button>,
        ]}
        width={800}
        centered
      >
        {previewWork && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
            {previewWork.work_type === 'image' ? (
              <Image
                src={`${previewWork.url}?token=${token}`}
                alt={previewWork.filename}
                style={{ maxWidth: '100%', maxHeight: '70vh', objectFit: 'contain' }}
              />
            ) : (
              <video
                src={`${previewWork.url}?token=${token}`}
                controls
                autoPlay
                style={{ maxWidth: '100%', maxHeight: '70vh', objectFit: 'contain' }}
              />
            )}
          </div>
        )}
      </Modal>

      {/* Reference Image Preview Modal */}
      <Modal
        open={!!previewReference}
        onCancel={() => setPreviewReference(null)}
        footer={[
          <Button key="close" onClick={() => setPreviewReference(null)}>
            关闭
          </Button>,
        ]}
        width={800}
        centered
        title={previewReference?.filename}
      >
        {previewReference && (
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 300 }}>
            <Image
              src={`${previewReference.url}?token=${token}`}
              alt={previewReference.filename}
              style={{ maxWidth: '100%', maxHeight: '70vh', objectFit: 'contain' }}
            />
          </div>
        )}
      </Modal>

      {/* Change Password Modal */}
      <Modal
        open={changePasswordVisible}
        onCancel={() => setChangePasswordVisible(false)}
        title="修改密码"
        footer={null}
        width={400}
      >
        <Form
          layout="vertical"
          onFinish={handleChangePassword}
        >
          <Form.Item
            name="old_password"
            label="原密码"
            rules={[{ required: true, message: '请输入原密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请输入原密码" />
          </Form.Item>
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少6个字符' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请输入新密码" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label="确认新密码"
            rules={[{ required: true, message: '请确认新密码' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="请再次输入新密码" />
          </Form.Item>
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setChangePasswordVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={changePasswordLoading}>
                确认修改
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </Layout>
  )
}

export default Dashboard
