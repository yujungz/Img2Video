import base64
import json
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database import get_db
from app.models import User, ReferenceImage, Task, TaskType, TaskStatus
from app.schemas import (
    ReferenceImageResponse,
    ImageGenerationRequest,
    VideoGenerationRequest,
    TaskResponse,
    GeneratedWorkResponse,
    MessageResponse
)
from app.auth import get_current_user
from app.services.storage import storage_service
from app.services.ai_service import ai_service
from app.services.tasks import process_image_generation, process_video_generation
from app.config import settings
from jose import jwt

router = APIRouter(prefix="/api/images", tags=["Images"])


@router.post("/upload", response_model=ReferenceImageResponse)
async def upload_reference_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload a reference image for style extraction"""
    # Validate file
    if not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        raise HTTPException(
            status_code=400,
            detail="Only JPG and PNG files are allowed"
        )

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File size must be less than 10MB"
        )

    # Upload to storage
    file_path = await storage_service.upload_bytes(
        content,
        file.filename,
        file.content_type or "image/jpeg",
        prefix=f"users/{current_user.id}/reference"
    )

    # Extract style features asynchronously (could be a task)
    try:
        image_base64 = base64.b64encode(content).decode()
        style_result = await ai_service.extract_style_features(image_base64)
        style_features = style_result.get("content", [{}])[0].get("text", "{}")
    except Exception as e:
        style_features = "{}"
        print(f"Style extraction failed: {e}")

    # Save to database
    ref_image = ReferenceImage(
        user_id=current_user.id,
        filename=file_path.split("/")[-1],
        original_filename=file.filename,
        file_path=file_path,
        file_size=len(content),
        mime_type=file.content_type,
        style_features=style_features
    )
    db.add(ref_image)
    await db.commit()
    await db.refresh(ref_image)

    return ReferenceImageResponse.model_validate(ref_image)


@router.get("/reference", response_model=List[ReferenceImageResponse])
async def list_reference_images(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's reference images"""
    result = await db.execute(
        select(ReferenceImage)
        .where(ReferenceImage.user_id == current_user.id)
        .order_by(ReferenceImage.created_at.desc())
    )
    images = result.scalars().all()
    # Return with proxy URLs
    response = []
    for img in images:
        img_dict = {
            'id': img.id,
            'filename': img.filename,
            'original_filename': img.original_filename,
            'file_size': img.file_size,
            'created_at': img.created_at,
            'url': f'/api/images/reference/{img.id}/preview'
        }
        response.append(ReferenceImageResponse(**img_dict))
    return response


@router.get("/reference/{image_id}/preview")
async def get_reference_image_preview(
    image_id: int,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Get preview for reference image (token required for auth)"""
    from fastapi.responses import Response
    from jose import jwt, JWTError

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

    # Get image
    result = await db.execute(
        select(ReferenceImage)
        .where(ReferenceImage.id == image_id, ReferenceImage.user_id == user.id)
    )
    img = result.scalar_one_or_none()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")

    # Fetch image content and return directly
    image_bytes = await storage_service.get_file(img.file_path)
    return Response(
        content=image_bytes,
        media_type=img.mime_type or "image/png"
    )


@router.delete("/reference/{image_id}", response_model=MessageResponse)
async def delete_reference_image(
    image_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a reference image"""
    result = await db.execute(
        select(ReferenceImage)
        .where(ReferenceImage.id == image_id, ReferenceImage.user_id == current_user.id)
    )
    image = result.scalar_one_or_none()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    await storage_service.delete_file(image.file_path)
    await db.delete(image)
    await db.commit()

    return MessageResponse(message="Image deleted successfully")


@router.post("/generate", response_model=TaskResponse)
async def generate_image(
    request: ImageGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate an image with style cloning"""
    # Check quota
    if current_user.used_image_quota >= current_user.daily_image_quota:
        raise HTTPException(
            status_code=429,
            detail="Daily image generation quota exceeded"
        )

    # Validate reference images
    for ref_id in request.reference_image_ids:
        result = await db.execute(
            select(ReferenceImage)
            .where(ReferenceImage.id == ref_id, ReferenceImage.user_id == current_user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Reference image {ref_id} not found"
            )

    # Create task
    task = Task(
        user_id=current_user.id,
        task_type=TaskType.IMAGE_GENERATION,
        input_data=json.dumps(request.model_dump())
    )
    db.add(task)

    # Update quota
    current_user.used_image_quota += 1
    await db.commit()
    await db.refresh(task)

    # Queue task
    process_image_generation.delay(task.id)

    return TaskResponse.model_validate(task)


@router.post("/generate-video", response_model=TaskResponse)
async def generate_video(
    request: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate a video from a static image"""
    # Check quota
    if current_user.used_video_quota >= current_user.daily_video_quota:
        raise HTTPException(
            status_code=429,
            detail="Daily video generation quota exceeded"
        )

    # Validate source image
    from app.models import GeneratedWork
    result = await db.execute(
        select(GeneratedWork)
        .where(GeneratedWork.id == request.image_id, GeneratedWork.user_id == current_user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Source image not found"
        )

    # Create task
    task = Task(
        user_id=current_user.id,
        task_type=TaskType.VIDEO_GENERATION,
        input_data=json.dumps(request.model_dump())
    )
    db.add(task)

    await db.commit()
    await db.refresh(task)

    # Queue task
    process_video_generation.delay(task.id)

    return TaskResponse.model_validate(task)


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    task_type: TaskType = None,
    status: TaskStatus = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's tasks"""
    query = select(Task).where(Task.user_id == current_user.id)

    if task_type:
        query = query.where(Task.task_type == task_type)
    if status:
        query = query.where(Task.status == status)

    query = query.order_by(Task.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    tasks = result.scalars().all()
    return [TaskResponse.model_validate(t) for t in tasks]


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get task details"""
    result = await db.execute(
        select(Task)
        .where(Task.id == task_id, Task.user_id == current_user.id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse.model_validate(task)


@router.get("/works", response_model=List[GeneratedWorkResponse])
async def list_generated_works(
    work_type: str = None,
    limit: int = 20,
    offset: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List user's generated works"""
    from app.models import GeneratedWork

    query = select(GeneratedWork).where(GeneratedWork.user_id == current_user.id)

    if work_type:
        query = query.where(GeneratedWork.work_type == work_type)

    query = query.order_by(GeneratedWork.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    works = result.scalars().all()

    # Build response with preview URLs
    response = []
    for w in works:
        w_dict = {
            'id': w.id,
            'work_type': w.work_type,
            'filename': w.filename,
            'prompt': w.prompt,
            'created_at': w.created_at,
            'file_size': w.file_size,
            'url': f'/api/images/works/{w.id}/preview'
        }
        response.append(GeneratedWorkResponse(**w_dict))
    return response


@router.get("/works/{work_id}/download")
async def download_work(
    work_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download a generated work"""
    from fastapi.responses import Response
    from app.models import GeneratedWork

    result = await db.execute(
        select(GeneratedWork)
        .where(GeneratedWork.id == work_id, GeneratedWork.user_id == current_user.id)
    )
    work = result.scalar_one_or_none()

    if not work:
        raise HTTPException(status_code=404, detail="Work not found")

    # Fetch file content
    content = await storage_service.get_file(work.file_path)

    # Return with download headers
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type=work.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{work.filename}"'
        }
    )


@router.get("/works/{work_id}/preview")
async def preview_work(
    work_id: int,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """Get preview for generated work (token required for auth)"""
    from fastapi.responses import Response
    from jose import JWTError
    from app.models import GeneratedWork

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

    # Get work
    result = await db.execute(
        select(GeneratedWork)
        .where(GeneratedWork.id == work_id, GeneratedWork.user_id == user.id)
    )
    work = result.scalar_one_or_none()
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")

    # Fetch content and return directly
    content = await storage_service.get_file(work.file_path)
    return Response(
        content=content,
        media_type=work.mime_type or "image/png"
    )


@router.get("/works/{work_id}/public")
async def get_public_work(
    work_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get generated work publicly (no auth required, for external API access)"""
    from fastapi.responses import Response
    from app.models import GeneratedWork

    # Get work
    result = await db.execute(select(GeneratedWork).where(GeneratedWork.id == work_id))
    work = result.scalar_one_or_none()
    if not work:
        raise HTTPException(status_code=404, detail="Work not found")

    # Only allow image type for public access
    if work.work_type != "image":
        raise HTTPException(status_code=400, detail="Only images can be accessed publicly")

    # Fetch content and return directly
    content = await storage_service.get_file(work.file_path)
    return Response(
        content=content,
        media_type=work.mime_type or "image/png"
    )


@router.delete("/works/{work_id}", response_model=MessageResponse)
async def delete_work(
    work_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a generated work"""
    from app.models import GeneratedWork

    result = await db.execute(
        select(GeneratedWork)
        .where(GeneratedWork.id == work_id, GeneratedWork.user_id == current_user.id)
    )
    work = result.scalar_one_or_none()

    if not work:
        raise HTTPException(status_code=404, detail="Work not found")

    # Delete file from storage
    await storage_service.delete_file(work.file_path)

    # Delete from database
    await db.delete(work)
    await db.commit()

    return MessageResponse(message="Work deleted successfully")
