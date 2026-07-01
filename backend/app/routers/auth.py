from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import random
import string

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserLogin, UserResponse, Token, MessageResponse, EmailVerifyRequest, ChangePasswordRequest
from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# 简单的内存存储验证码（生产环境应使用 Redis）
email_verification_codes = {}

# 验证码有效期（分钟）
CODE_EXPIRE_MINUTES = 10


def generate_verification_code() -> str:
    """生成6位数字+字母随机组合验证码"""
    characters = string.ascii_uppercase + string.digits
    # 排除容易混淆的字符
    characters = characters.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    return ''.join(random.choices(characters, k=6))


@router.post("/send-verify-code", response_model=MessageResponse)
async def send_verify_code(
    email_data: EmailVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """发送验证码"""
    email = email_data.email

    # 检查邮箱是否已注册
    result = await db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )

    # 生成验证码
    code = generate_verification_code()

    # 存储验证码（带过期时间）
    email_verification_codes[email] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=CODE_EXPIRE_MINUTES)
    }

    # 打印日志用于调试
    print(f"[验证码] 邮箱: {email}, 验证码: {code}")

    return MessageResponse(message=f"验证码: {code}，有效期为{CODE_EXPIRE_MINUTES}分钟", success=True)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(email_data: EmailVerifyRequest):
    """验证邮箱验证码"""
    code = email_data.code
    email = email_data.email

    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请输入验证码"
        )

    # 检查验证码是否存在
    stored = email_verification_codes.get(email)
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先获取验证码"
        )

    # 检查是否过期
    if datetime.utcnow() > stored["expires_at"]:
        del email_verification_codes[email]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码已过期，请重新获取"
        )

    # 验证码是否正确（不区分大小写）
    if stored["code"].upper() != code.upper():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="验证码错误"
        )

    return MessageResponse(message="邮箱验证成功", success=True)


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已被使用"
        )

    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该邮箱已被注册"
        )

    # Create user
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password)
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Create token
    access_token = create_access_token(data={"sub": user.username})

    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """Login and get access token"""
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Reset quota if needed (daily reset)
    if user.quota_reset_date and user.quota_reset_date < datetime.utcnow() - timedelta(days=1):
        user.used_image_quota = 0
        user.used_video_quota = 0
        user.quota_reset_date = datetime.utcnow()
        await db.commit()

    access_token = create_access_token(data={"sub": user.username})

    return Token(
        access_token=access_token,
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user info"""
    return UserResponse.model_validate(current_user)


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    username: str = None,
    email: str = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user info"""
    if username:
        result = await db.execute(
            select(User).where(User.username == username, User.id != current_user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        current_user.username = username

    if email:
        result = await db.execute(
            select(User).where(User.email == email, User.id != current_user.id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already taken"
            )
        current_user.email = email

    await db.commit()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改密码"""
    # 验证旧密码
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="原密码错误"
        )

    # 更新密码
    current_user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()

    return MessageResponse(message="密码修改成功", success=True)
