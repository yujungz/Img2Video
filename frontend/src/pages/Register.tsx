import React from 'react'
import { Form, Input, Button, Card, Typography, message } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined, SafetyOutlined, ReloadOutlined } from '@ant-design/icons'
import { useNavigate, Link } from 'react-router-dom'
import { authApi } from '@/api'
import { useAuthStore } from '@/stores/authStore'

const { Title, Text } = Typography

interface RegisterForm {
  username: string
  email: string
  password: string
  confirmPassword: string
  captcha: string
}

// 生成随机验证码（排除易混淆字符）
const generateRandomCode = (length: number = 6): string => {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789' // 排除 I, O, 0, 1
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

const Register: React.FC = () => {
  const [form] = Form.useForm()
  const navigate = useNavigate()
  const [loading, setLoading] = React.useState(false)
  const captchaCodeRef = React.useRef('')
  const captchaCanvasRef = React.useRef<HTMLCanvasElement>(null)
  const setAuth = useAuthStore((state) => state.setAuth)

  // 生成并绘制验证码
  const drawCaptcha = React.useCallback(() => {
    const code = generateRandomCode(6)
    captchaCodeRef.current = code
    console.log('[验证码] 生成:', code)

    const canvas = captchaCanvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.width
    const height = canvas.height

    // 清空画布
    ctx.fillStyle = '#f0f0f0'
    ctx.fillRect(0, 0, width, height)

    // 绘制干扰线
    for (let i = 0; i < 4; i++) {
      ctx.strokeStyle = `rgba(${Math.random() * 255},${Math.random() * 255},${Math.random() * 255},0.5)`
      ctx.beginPath()
      ctx.moveTo(Math.random() * width, Math.random() * height)
      ctx.lineTo(Math.random() * width, Math.random() * height)
      ctx.stroke()
    }

    // 绘制验证码文字
    ctx.font = 'bold 24px Arial'
    ctx.textBaseline = 'middle'

    for (let i = 0; i < code.length; i++) {
      const x = 12 + i * 23
      const y = height / 2 + (Math.random() * 10 - 5)
      const rotation = (Math.random() - 0.5) * 0.4

      ctx.save()
      ctx.translate(x, y)
      ctx.rotate(rotation)
      ctx.fillStyle = `rgb(${50 + Math.random() * 100},${50 + Math.random() * 100},${50 + Math.random() * 100})`
      ctx.fillText(code[i], 0, 0)
      ctx.restore()
    }

    // 绘制干扰点
    for (let i = 0; i < 30; i++) {
      ctx.fillStyle = `rgba(${Math.random() * 255},${Math.random() * 255},${Math.random() * 255},0.5)`
      ctx.beginPath()
      ctx.arc(Math.random() * width, Math.random() * height, 1, 0, 2 * Math.PI)
      ctx.fill()
    }
  }, [])

  // 初始化验证码
  React.useEffect(() => {
    // 延迟一帧确保 canvas 已挂载
    requestAnimationFrame(() => {
      drawCaptcha()
    })
  }, [drawCaptcha])

  const handleSubmit = async (values: RegisterForm) => {
    const userInput = (values.captcha || '').trim().toUpperCase()
    const correctCode = captchaCodeRef.current.toUpperCase()

    console.log('[验证码] 用户输入:', userInput, '正确值:', correctCode)

    // 验证验证码（不区分大小写）
    if (!userInput || userInput !== correctCode) {
      message.error('验证码错误')
      drawCaptcha() // 刷新验证码
      return
    }

    setLoading(true)
    try {
      const response = await authApi.register({
        username: values.username,
        email: values.email,
        password: values.password,
      })
      setAuth(response.data.access_token, response.data.user)
      message.success('注册成功')
      navigate('/')
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } }
      message.error(err.response?.data?.detail || '注册失败')
      drawCaptcha() // 注册失败也刷新验证码
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
    }}>
      <Card style={{ width: 400, boxShadow: '0 4px 12px rgba(0,0,0,0.15)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Title level={2} style={{ margin: 0 }}>Img2Video</Title>
          <Text type="secondary">生成式插画与动画平台</Text>
        </div>

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          autoComplete="off"
        >
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" size="large" />
          </Form.Item>

          <Form.Item
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="邮箱" size="large" />
          </Form.Item>

          <Form.Item
            name="captcha"
            rules={[
              { required: true, message: '请输入验证码' },
            ]}
          >
            <div style={{ display: 'flex', gap: 8 }}>
              <Input
                prefix={<SafetyOutlined />}
                placeholder="验证码"
                size="large"
                style={{ flex: 1 }}
              />
              <div
                style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                onClick={drawCaptcha}
                title="点击刷新验证码"
              >
                <canvas
                  ref={captchaCanvasRef}
                  width={150}
                  height={40}
                  style={{ borderRadius: 4, border: '1px solid #d9d9d9' }}
                />
                <ReloadOutlined style={{ marginLeft: 4, color: '#1890ff' }} />
              </div>
            </div>
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" size="large" />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="确认密码" size="large" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              注册
            </Button>
          </Form.Item>

          <div style={{ textAlign: 'center' }}>
            <Text type="secondary">
              已有账号？ <Link to="/login">立即登录</Link>
            </Text>
          </div>
        </Form>
      </Card>
    </div>
  )
}

export default Register
