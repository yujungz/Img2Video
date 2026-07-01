from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
import json

from app.database import get_db
from app.models import User, Task, TaskStatus, TaskType, GeneratedWork, SystemConfig
from app.services.storage import storage_service
from app.schemas import (
    UserResponse,
    UserUpdate,
    TaskResponse,
    DashboardStats,
    SystemConfigUpdate,
    SystemConfigResponse,
    MessageResponse
)
from app.auth import get_current_admin_user, get_password_hash

router = APIRouter(prefix="/api/admin", tags=["Admin"])

# 超级用户ID
SUPER_USER_ID = 1


class AdminChangePasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=100)


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics"""
    # User stats
    total_users = await db.scalar(select(func.count(User.id)))
    active_users = await db.scalar(
        select(func.count(User.id)).where(User.is_active == True)
    )

    # Task stats
    total_tasks = await db.scalar(select(func.count(Task.id)))
    pending_tasks = await db.scalar(
        select(func.count(Task.id)).where(Task.status == TaskStatus.PENDING)
    )
    completed_tasks = await db.scalar(
        select(func.count(Task.id)).where(Task.status == TaskStatus.COMPLETED)
    )
    failed_tasks = await db.scalar(
        select(func.count(Task.id)).where(Task.status == TaskStatus.FAILED)
    )

    # Work stats
    total_images = await db.scalar(
        select(func.count(GeneratedWork.id)).where(GeneratedWork.work_type == "image")
    )
    total_videos = await db.scalar(
        select(func.count(GeneratedWork.id)).where(GeneratedWork.work_type == "video")
    )

    return DashboardStats(
        total_users=total_users or 0,
        active_users=active_users or 0,
        total_tasks=total_tasks or 0,
        pending_tasks=pending_tasks or 0,
        completed_tasks=completed_tasks or 0,
        failed_tasks=failed_tasks or 0,
        total_images=total_images or 0,
        total_videos=total_videos or 0
    )


# User Management
@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    is_active: bool = None,
    is_admin: bool = None,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all users with pagination"""
    query = select(User)

    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if is_admin is not None:
        query = query.where(User.is_admin == is_admin)

    query = query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()
    return [UserResponse.model_validate(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user details"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    update_data: UserUpdate,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user details"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_dict = update_data.model_dump(exclude_unset=True)

    # 超级用户保护：不能修改 is_active 和 is_admin
    if user.id == SUPER_USER_ID:
        if 'is_active' in update_dict:
            del update_dict['is_active']
        if 'is_admin' in update_dict:
            del update_dict['is_admin']

    # 只有超级用户可以修改邮箱
    if 'email' in update_dict:
        if admin.id != SUPER_USER_ID:
            del update_dict['email']
        else:
            # 检查邮箱是否已被其他用户使用
            existing = await db.execute(
                select(User).where(User.email == update_dict['email'], User.id != user_id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="该邮箱已被其他用户使用")

    for key, value in update_dict.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user from database"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 超级用户不能被删除
    if user.id == SUPER_USER_ID:
        raise HTTPException(status_code=400, detail="超级用户不能被删除")

    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己")

    await db.delete(user)
    await db.commit()
    return MessageResponse(message="用户已删除")


@router.post("/users/{user_id}/change-password", response_model=MessageResponse)
async def admin_change_user_password(
    user_id: int,
    password_data: AdminChangePasswordRequest,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """管理员修改用户密码"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = get_password_hash(password_data.new_password)
    await db.commit()
    return MessageResponse(message="密码修改成功")


# Task Management
@router.get("/tasks", response_model=List[TaskResponse])
async def list_all_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    task_type: TaskType = None,
    status: TaskStatus = None,
    user_id: int = None,
    username: str = None,  # 用户名模糊查询
    prompt: str = None,    # 提示词模糊查询
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all tasks with filters"""
    from sqlalchemy import or_, cast, String
    from sqlalchemy.dialects.postgresql import JSONB

    query = select(Task).join(User, Task.user_id == User.id)

    if task_type:
        query = query.where(Task.task_type == task_type)
    if status:
        query = query.where(Task.status == status)
    if user_id:
        query = query.where(Task.user_id == user_id)
    if username:
        query = query.where(User.username.ilike(f"%{username}%"))
    if prompt:
        # input_data 是 JSON 字符串，转换为 JSONB 后搜索
        query = query.where(
            cast(Task.input_data, JSONB)['prompt'].as_string().ilike(f"%{prompt}%")
        )

    query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()

    # 获取用户名
    task_responses = []
    for task in tasks:
        user_result = await db.execute(select(User).where(User.id == task.user_id))
        user = user_result.scalar_one_or_none()
        task_dict = TaskResponse.model_validate(task).model_dump()
        task_dict['username'] = user.username if user else None
        task_responses.append(TaskResponse(**task_dict))

    return task_responses


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_details(
    task_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get task details"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.delete("/tasks/{task_id}", response_model=MessageResponse)
async def delete_task(
    task_id: int,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a task"""
    # 只有超级用户可以删除任务
    if admin.id != SUPER_USER_ID:
        raise HTTPException(status_code=403, detail="只有超级用户可以删除任务")

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    await db.delete(task)
    await db.commit()
    return MessageResponse(message="任务已删除")


@router.delete("/tasks", response_model=MessageResponse)
async def clear_all_tasks(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Clear all tasks"""
    # 只有超级用户可以清空任务
    if admin.id != SUPER_USER_ID:
        raise HTTPException(status_code=403, detail="只有超级用户可以清空任务")

    await db.execute(Task.__table__.delete())
    await db.commit()
    return MessageResponse(message="所有任务已清空")


# System Configuration
@router.get("/config", response_model=List[SystemConfigResponse])
async def list_configs(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all system configurations"""
    result = await db.execute(select(SystemConfig))
    configs = result.scalars().all()
    return [SystemConfigResponse.model_validate(c) for c in configs]


@router.put("/config", response_model=SystemConfigResponse)
async def update_config(
    config_data: SystemConfigUpdate,
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update system configuration"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == config_data.key)
    )
    config = result.scalar_one_or_none()

    if not config:
        config = SystemConfig(key=config_data.key, value=config_data.value)
        db.add(config)
    else:
        config.value = config_data.value

    await db.commit()
    await db.refresh(config)
    return SystemConfigResponse.model_validate(config)


@router.post("/config/init", response_model=MessageResponse)
async def init_default_configs(
    admin: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Initialize default system configurations"""
    default_configs = [
        ("max_file_size", "10485760", "Maximum file upload size in bytes"),
        ("daily_image_quota_default", "50", "Default daily image generation quota"),
        ("daily_video_quota_default", "10", "Default daily video generation quota"),
        ("max_reference_images", "3", "Maximum reference images per generation"),
        ("supported_image_formats", "jpg,jpeg,png", "Supported image formats"),
        ("max_video_duration", "10", "Maximum video duration in seconds"),
    ]

    for key, value, description in default_configs:
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        if not result.scalar_one_or_none():
            config = SystemConfig(key=key, value=value, description=description)
            db.add(config)

    await db.commit()
    return MessageResponse(message="Default configurations initialized")


@router.get("/tasks/{task_id}/preview")
async def get_task_preview(
    task_id: int,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Get preview for task result (image or video) - token required for auth"""
    from jose import jwt, JWTError
    from app.config import settings

    # Verify token
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get user
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    # Check if user is admin
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Task not completed")

    # Get result_data
    result_data = json.loads(task.result_data) if task.result_data else {}
    work_id = result_data.get("work_id")

    # Get generated work - try by work_id first, then by task_id
    work = None
    if work_id:
        work_result = await db.execute(select(GeneratedWork).where(GeneratedWork.id == work_id))
        work = work_result.scalar_one_or_none()

    if not work:
        # Fallback: find by task_id
        work_result = await db.execute(select(GeneratedWork).where(GeneratedWork.task_id == task_id))
        work = work_result.scalar_one_or_none()

    if not work:
        raise HTTPException(status_code=404, detail="Generated work not found")

    # Fetch content from storage
    content = await storage_service.get_file(work.file_path)
    return Response(
        content=content,
        media_type=work.mime_type or "application/octet-stream"
    )
