import asyncio
import base64
import json
from datetime import datetime
from celery import Celery
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Task, TaskStatus, TaskType, GeneratedWork, ReferenceImage, User


def debug_log(message: str):
    """Print debug log if ANTHROPIC_DEBUG is enabled"""
    if settings.ANTHROPIC_DEBUG:
        print(message)


def timing_log(message: str):
    """Print timing log (always visible for performance analysis)"""
    print(f"[TIMING] {message}")

# Celery app
celery_app = Celery(
    "img2video_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
)

# Sync database for Celery tasks with connection pooling
sync_engine = create_engine(
    settings.DATABASE_URL.replace("+asyncpg", ""),
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600
)
SyncSessionLocal = sessionmaker(bind=sync_engine)


def run_async(coro):
    """Run async function in sync context"""
    return asyncio.get_event_loop().run_until_complete(coro)


async def get_file_sync(file_path: str) -> bytes:
    """Synchronous wrapper for storage service"""
    from minio import Minio
    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )
    response = client.get_object(settings.MINIO_BUCKET, file_path)
    return response.read()


async def upload_file_sync(data: bytes, filename: str, content_type: str, prefix: str) -> str:
    """Synchronous wrapper for storage service"""
    import io
    import uuid
    from minio import Minio
    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE
    )
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    unique_id = uuid.uuid4().hex
    object_name = f"{prefix}/{unique_id}.{ext}" if prefix else f"{unique_id}.{ext}"
    client.put_object(
        settings.MINIO_BUCKET,
        object_name,
        io.BytesIO(data),
        len(data),
        content_type=content_type
    )
    return object_name


async def call_ai_api(endpoint: str, data: dict, timeout: float = 120.0) -> dict:
    """Make synchronous API call"""
    import httpx
    url = f"{settings.ANTHROPIC_BASE_URL.rstrip('/')}{endpoint}"
    headers = {
        "Authorization": f"Bearer {settings.ANTHROPIC_AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response.json()


async def call_gemini_api(data: dict, timeout: float = 300.0, max_retries: int = 3) -> dict:
    """Call Gemini-style API with combined URL and retry logic"""
    import httpx
    url = f"{settings.ANTHROPIC_BASE_URL.rstrip('/')}{settings.ANTHROPIC_PATH_URL}"
    headers = {
        "Authorization": f"Bearer {settings.ANTHROPIC_AUTH_TOKEN}",
        "Content-Type": "application/json"
    }

    last_error = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            last_error = e
            print(f"API call attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                import asyncio
                await asyncio.sleep(5)  # Wait 5 seconds before retry

    raise last_error


async def optimize_prompt_async(prompt: str, reference_style: str = None) -> str:
    """Optimize prompt using AI - simplified version that returns original prompt"""
    # Skip prompt optimization as the API may not support text generation
    # Just return the original prompt with style info if available
    if reference_style:
        return f"{prompt}\n\n参考风格: {reference_style}"
    return prompt


def process_reference_image(image_bytes: bytes) -> bytes:
    """
    Process reference image to target size 720x1280.

    Rules:
    1. If width < 720 AND height < 1280: Scale up until (width == 720 AND height >= 1280)
       OR (width >= 720 AND height == 1280)
    2. If width > 720 AND height > 1280: Scale down until (width == 720 AND height >= 1280)
       OR (width >= 720 AND height == 1280)
    3. If width == 720 AND height > 1280: Crop top and bottom evenly to make height == 1280
       If width > 720 AND height == 1280: Crop left and right evenly to make width == 720
    """
    import io
    from PIL import Image

    TARGET_WIDTH = 720
    TARGET_HEIGHT = 1280

    img = Image.open(io.BytesIO(image_bytes))
    orig_width, orig_height = img.size

    # Convert to RGB if necessary
    if img.mode in ('RGBA', 'P'):
        img = img.convert('RGB')

    debug_log(f"[DEBUG] Processing reference image: original size {orig_width}x{orig_height}")

    # Case 1: Both dimensions smaller than target - scale up
    if orig_width < TARGET_WIDTH and orig_height < TARGET_HEIGHT:
        # Calculate scale factors to reach target
        scale_by_width = TARGET_WIDTH / orig_width
        scale_by_height = TARGET_HEIGHT / orig_height

        # Use the larger scale factor to ensure at least one dimension meets target
        scale = max(scale_by_width, scale_by_height)
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        debug_log(f"[DEBUG] Scaled up to: {new_width}x{new_height}")

    # Case 2: Both dimensions larger than target - scale down
    elif orig_width > TARGET_WIDTH and orig_height > TARGET_HEIGHT:
        # Calculate scale factors to reach target
        scale_by_width = TARGET_WIDTH / orig_width
        scale_by_height = TARGET_HEIGHT / orig_height

        # Use the larger scale factor (smaller reduction) to ensure one dimension is at target
        scale = max(scale_by_width, scale_by_height)
        new_width = int(orig_width * scale)
        new_height = int(orig_height * scale)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        debug_log(f"[DEBUG] Scaled down to: {new_width}x{new_height}")

    # Get current size after potential scaling
    current_width, current_height = img.size

    # Case 3: Crop to exact target size
    # If width == 720 AND height > 1280: crop top/bottom
    if current_width == TARGET_WIDTH and current_height > TARGET_HEIGHT:
        crop_amount = current_height - TARGET_HEIGHT
        top = crop_amount // 2
        bottom = top + TARGET_HEIGHT
        img = img.crop((0, top, TARGET_WIDTH, bottom))
        debug_log(f"[DEBUG] Cropped height from {current_height} to {TARGET_HEIGHT}")

    # If width > 720 AND height == 1280: crop left/right
    elif current_width > TARGET_WIDTH and current_height == TARGET_HEIGHT:
        crop_amount = current_width - TARGET_WIDTH
        left = crop_amount // 2
        right = left + TARGET_WIDTH
        img = img.crop((left, 0, right, TARGET_HEIGHT))
        debug_log(f"[DEBUG] Cropped width from {current_width} to {TARGET_WIDTH}")

    # Final check: if still not exact size, resize to target
    current_width, current_height = img.size
    if current_width != TARGET_WIDTH or current_height != TARGET_HEIGHT:
        img = img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        debug_log(f"[DEBUG] Final resize to: {TARGET_WIDTH}x{TARGET_HEIGHT}")

    # Convert back to bytes
    output_buffer = io.BytesIO()
    img.save(output_buffer, format='PNG')
    processed_bytes = output_buffer.getvalue()
    debug_log(f"[DEBUG] Processed reference image: {len(processed_bytes)} bytes")

    return processed_bytes


async def generate_image_async(prompt: str, negative_prompt: str = None,
                                reference_images: list = None,
                                width: int = 1024, height: int = 1024) -> dict:
    """Generate image using Gemini-style API with reference images for style cloning"""
    # Build the prompt with negative prompt if provided
    full_prompt = prompt
    if negative_prompt:
        full_prompt = f"{prompt}\n\nNegative prompt: {negative_prompt}"

    # Build parts list - start with text
    parts = [{"text": full_prompt}]

    # Add reference images for style cloning
    debug_log(f"[DEBUG] generate_image_async called with {len(reference_images) if reference_images else 0} reference images")
    if reference_images:
        style_prompt = "\n\n请参考以下图片的艺术风格来生成新图片，保持相同的画风、色彩和笔触特点："
        parts[0]["text"] = style_prompt + "\n\n" + full_prompt

        for i, img_base64 in enumerate(reference_images[:3]):  # Max 3 reference images
            parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": img_base64
                }
            })
            debug_log(f"[DEBUG] Added reference image {i+1} to parts, base64 length: {len(img_base64)}")

    debug_log(f"[DEBUG] Total parts: {len(parts)} (1 text + {len(reference_images) if reference_images else 0} images)")

    # Gemini-style API format
    data = {
        "model": settings.ANTHROPIC_MODEL_NAME,
        "contents": [{
            "role": "user",
            "parts": parts
        }]
    }

    # Print API request parameters
    timing_log(f"Image API Request:")
    timing_log(f"  URL: {settings.ANTHROPIC_BASE_URL.rstrip('/')}{settings.ANTHROPIC_PATH_URL}")
    timing_log(f"  Model: {settings.ANTHROPIC_MODEL_NAME}")
    timing_log(f"  Prompt (first 200 chars): {full_prompt[:200]}...")
    timing_log(f"  Reference images count: {len(reference_images) if reference_images else 0}")
    timing_log(f"  Width: {width}, Height: {height}")

    return await call_gemini_api(data, timeout=300.0)


async def generate_video_async(image_base64: str, prompt: str,
                                duration: float = 4.0, region: dict = None) -> dict:
    """Generate video using AI - DEPRECATED, use video task workflow instead"""
    data = {
        "model": settings.VIDEO_MODEL,
        "image": image_base64,
        "prompt": prompt,
        "duration": duration,
        "resolution": "1080p"
    }
    if region:
        data["region"] = region

    return await call_ai_api("/v1/videos/generations", data, timeout=600.0)


def create_video_task_sync(image_url: str, prompt: str, duration: int = 5) -> str:
    """
    Step 1: Create video generation task using Kling API
    Returns task_id for subsequent polling

    API: POST {base_url}{path_url}
    JSON body: model_name, mode, sound, aspect_ratio, image, prompt, duration
    """
    import httpx
    import time as time_module

    start_time = time_module.time()

    # Build API URL
    base_url = settings.ANTHROPIC_BASE_URL_VIDEO.rstrip('/')
    path_url = settings.ANTHROPIC_PATH_URL_VIDEO
    url = f"{base_url}{path_url}"

    timing_log(f"Video Step 1 - Create task: Calling API...")
    debug_log(f"[VIDEO] Step 1 URL: {url}")
    debug_log(f"[VIDEO] Step 1 Prompt: {prompt}")
    debug_log(f"[VIDEO] Step 1 Duration: {duration}s")
    debug_log(f"[VIDEO] Step 1 Image URL: {image_url}")

    # Prepare headers
    headers = {
        "Authorization": f"Bearer {settings.ANTHROPIC_AUTH_TOKEN_VIDEO}",
        "Content-Type": "application/json"
    }

    # Prepare JSON body for Kling API
    data = {
        "model_name": settings.ANTHROPIC_MODEL_NAME_VIDEO,
        "mode": "pro",
        "sound": "on",
        "aspect_ratio": "9:16",
        "image": image_url,
        "prompt": prompt,
        "duration": str(duration)
    }

    debug_log(f"[VIDEO] Step 1 Request body: {data}")

    with httpx.Client(timeout=settings.ANTHROPIC_TIMEOUT) as client:
        response = client.post(url, headers=headers, json=data)

        debug_log(f"[VIDEO] Step 1 Response Status: {response.status_code}")
        debug_log(f"[VIDEO] Step 1 Response Body: {response.text}")

        if response.status_code != 200:
            raise ValueError(f"Video API error: {response.status_code} - {response.text}")

        result = response.json()

    timing_log(f"Video Step 1 - Create task: {time_module.time() - start_time:.2f}s")

    # Check response
    code = result.get("code")
    if code != 0:
        raise ValueError(f"Video API returned error code: {code}, message: {result.get('message')}")

    data_result = result.get("data", {})
    task_status = data_result.get("task_status")
    if task_status != "submitted":
        raise ValueError(f"Video task not submitted: {task_status}")

    task_id = data_result.get("task_id")
    if not task_id:
        raise ValueError(f"No task_id in response: {result}")

    debug_log(f"[VIDEO] Step 1 Task ID: {task_id}")
    return task_id


def poll_video_status_sync(task_id: str) -> dict:
    """
    Step 2: Poll video status until completed or error/timeout

    API: GET {base_url}{path_url}/{task_id}
    Returns when task_status == "succeed"
    """
    import httpx
    import time as time_module

    start_time = time_module.time()
    base_url = settings.ANTHROPIC_BASE_URL_VIDEO.rstrip('/')
    path_url = settings.ANTHROPIC_PATH_URL_VIDEO
    url = f"{base_url}{path_url}/{task_id}"

    headers = {
        "Authorization": f"Bearer {settings.ANTHROPIC_AUTH_TOKEN_VIDEO}"
    }

    poll_interval = 5  # seconds between polls
    max_wait_time = settings.ANTHROPIC_TIMEOUT_VIDEO

    timing_log(f"Video Step 2 - Poll status: Starting for task {task_id}")
    debug_log(f"[VIDEO] Step 2 URL: {url}")

    with httpx.Client(timeout=settings.ANTHROPIC_TIMEOUT) as client:
        while True:
            elapsed = time_module.time() - start_time

            # Check timeout
            if elapsed > max_wait_time:
                raise TimeoutError(f"Video generation timed out after {max_wait_time} seconds")

            response = client.get(url, headers=headers)
            debug_log(f"[VIDEO] Step 2 Response: {response.status_code} - {response.text}")

            if response.status_code != 200:
                raise ValueError(f"Video status API error: {response.status_code}")

            result = response.json()

            # Check response code
            code = result.get("code")
            if code != 0:
                raise ValueError(f"Video API error: code={code}, message={result.get('message')}")

            data_result = result.get("data", {})
            task_status = data_result.get("task_status")
            task_status_msg = data_result.get("task_status_msg", "")

            debug_log(f"[VIDEO] Step 2 Status: {task_status}, Message: {task_status_msg}, Elapsed: {elapsed:.1f}s")

            # Check for completion
            if task_status == "succeed":
                timing_log(f"Video Step 2 - Poll status: {time_module.time() - start_time:.2f}s")
                return data_result

            # Check for errors
            if task_status in ["failed", "error"]:
                raise ValueError(f"Video generation failed: {task_status_msg}")

            # Wait before next poll
            time_module.sleep(poll_interval)


def download_video_from_url(video_url: str) -> bytes:
    """
    Step 3: Download generated video from URL

    Returns video content as bytes
    """
    import httpx
    import time as time_module

    start_time = time_module.time()

    timing_log(f"Video Step 3 - Download content: Starting from URL")
    debug_log(f"[VIDEO] Step 3 URL: {video_url}")

    with httpx.Client(timeout=settings.ANTHROPIC_TIMEOUT) as client:
        response = client.get(video_url)

        debug_log(f"[VIDEO] Step 3 Response Status: {response.status_code}")
        debug_log(f"[VIDEO] Step 3 Content-Type: {response.headers.get('content-type')}")
        debug_log(f"[VIDEO] Step 3 Content-Length: {len(response.content)} bytes")

        if response.status_code != 200:
            raise ValueError(f"Video download error: {response.status_code}")

        timing_log(f"Video Step 3 - Download content: {time_module.time() - start_time:.2f}s")
        return response.content


@celery_app.task(bind=True)
def process_image_generation(self, task_id: int):
    """Process image generation task"""
    import time as time_module

    total_start = time_module.time()
    timing_log(f"========== Image generation task {task_id} started ==========")
    db = SyncSessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"error": "Task not found"}

        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.utcnow()
        db.commit()

        step_start = time_module.time()
        input_data = json.loads(task.input_data)
        prompt = input_data.get("prompt", "")
        negative_prompt = input_data.get("negative_prompt")
        reference_image_ids = input_data.get("reference_image_ids", [])
        width = input_data.get("width", 1024)
        height = input_data.get("height", 1024)
        timing_log(f"Parse input data: {time_module.time() - step_start:.2f}s")

        # Get reference images
        step_start = time_module.time()
        reference_images = []
        style_features = []
        debug_log(f"[DEBUG] Reference image IDs: {reference_image_ids}")
        for ref_id in reference_image_ids:
            ref_img = db.query(ReferenceImage).filter(ReferenceImage.id == ref_id).first()
            if ref_img:
                debug_log(f"[DEBUG] Found reference image {ref_id}: {ref_img.original_filename}")
                if ref_img.style_features:
                    style_features.append(json.loads(ref_img.style_features))

                # Get file from storage
                file_start = time_module.time()
                image_bytes = run_async(get_file_sync(ref_img.file_path))
                timing_log(f"Get file from storage (ref_id={ref_id}): {time_module.time() - file_start:.2f}s")

                # Process reference image to target size 720x1280
                process_start = time_module.time()
                processed_bytes = process_reference_image(image_bytes)
                timing_log(f"Process reference image (resize/crop): {time_module.time() - process_start:.2f}s")

                img_base64 = base64.b64encode(processed_bytes).decode()
                reference_images.append(img_base64)
                debug_log(f"[DEBUG] Image size: {len(image_bytes)} bytes, processed: {len(processed_bytes)} bytes, base64 length: {len(img_base64)}")

        timing_log(f"Total reference images processing: {time_module.time() - step_start:.2f}s")

        # Optimize prompt with style features
        step_start = time_module.time()
        combined_style = json.dumps(style_features) if style_features else None
        optimized_prompt = run_async(optimize_prompt_async(prompt, combined_style))
        timing_log(f"Optimize prompt: {time_module.time() - step_start:.2f}s")

        # Add pre-prompt if configured
        if settings.ANTHROPIC_IMG_PREPROMPT:
            optimized_prompt = f"{settings.ANTHROPIC_IMG_PREPROMPT}\n{optimized_prompt}"
            debug_log(f"[DEBUG] Added pre-prompt: {settings.ANTHROPIC_IMG_PREPROMPT}")

        # Generate image
        step_start = time_module.time()
        timing_log(f"Starting AI API call...")
        result = run_async(generate_image_async(
            prompt=optimized_prompt,
            negative_prompt=negative_prompt,
            reference_images=reference_images,
            width=width,
            height=height
        ))
        timing_log(f"AI API call (generate image): {time_module.time() - step_start:.2f}s")

        # Parse Gemini-style response
        step_start = time_module.time()
        image_data = None
        if "candidates" in result:
            for candidate in result.get("candidates", []):
                content = candidate.get("content", {})
                for part in content.get("parts", []):
                    if "inlineData" in part:
                        inline_data = part["inlineData"]
                        image_data = base64.b64decode(inline_data["data"])
                        break
                    elif "text" in part:
                        # Check if text contains base64 image data
                        text = part["text"]
                        if text.startswith("data:image"):
                            # Extract base64 from data URL
                            import re
                            match = re.search(r'base64,(.+)', text)
                            if match:
                                image_data = base64.b64decode(match.group(1))
                        else:
                            # Try to parse as JSON with image data
                            try:
                                parsed = json.loads(text)
                                if isinstance(parsed, dict) and "image" in parsed:
                                    image_data = base64.b64decode(parsed["image"])
                            except:
                                pass
        elif "data" in result and result["data"]:
            # Fallback to OpenAI-style response
            image_data = base64.b64decode(result["data"][0]["b64_json"])
        timing_log(f"Parse response: {time_module.time() - step_start:.2f}s")

        # Save generated image
        if image_data:
            step_start = time_module.time()
            filename = f"generated_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
            file_path = run_async(upload_file_sync(
                image_data, filename, "image/png", "generated/images"
            ))
            timing_log(f"Upload generated image: {time_module.time() - step_start:.2f}s")

            # Create generated work record
            work = GeneratedWork(
                user_id=task.user_id,
                task_id=task.id,
                work_type="image",
                filename=filename,
                file_path=file_path,
                file_size=len(image_data),
                mime_type="image/png",
                prompt=prompt,
                negative_prompt=negative_prompt,
                reference_image_ids=json.dumps(reference_image_ids)
            )
            db.add(work)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.result_data = json.dumps({
                "work_id": work.id,
                "file_path": file_path
            })
        else:
            task.status = TaskStatus.FAILED
            task.error_message = "No image data in response"

        db.commit()
        timing_log(f"========== TOTAL TIME: {time_module.time() - total_start:.2f}s ==========")

    except Exception as e:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def process_video_generation(self, task_id: int):
    """Process video generation task using Kling API workflow"""
    import time as time_module

    total_start = time_module.time()
    timing_log(f"========== Video generation task {task_id} started ==========")

    db = SyncSessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return {"error": "Task not found"}

        task.status = TaskStatus.PROCESSING
        task.started_at = datetime.utcnow()
        db.commit()

        input_data = json.loads(task.input_data)
        image_id = input_data.get("image_id")
        prompt = input_data.get("prompt", "")
        duration = input_data.get("duration", 5)

        # Get source image
        step_start = time_module.time()
        work = db.query(GeneratedWork).filter(GeneratedWork.id == image_id).first()
        if not work:
            raise ValueError("Source image not found")

        # Generate public URL for the source image
        # The Kling API requires a publicly accessible image URL
        image_url = f"{settings.PUBLIC_BASE_URL}/api/images/works/{image_id}/public"
        timing_log(f"Get source image URL: {time_module.time() - step_start:.2f}s")
        debug_log(f"[VIDEO] Source image URL: {image_url}")

        # Step 1: Create video generation task
        timing_log(f"Starting video generation API workflow...")
        video_task_id = create_video_task_sync(
            image_url=image_url,
            prompt=prompt,
            duration=int(duration)
        )

        task.result_data = json.dumps({
            "video_task_id": video_task_id,
            "status": "processing"
        })
        db.commit()

        # Step 2: Poll for completion
        status_result = poll_video_status_sync(video_task_id)

        # Step 3: Get video URL from result and download
        task_result = status_result.get("task_result", {})
        videos = task_result.get("videos", [])
        if not videos:
            raise ValueError("No video in result")

        video_url = videos[0].get("url")
        if not video_url:
            raise ValueError("No video URL in result")

        debug_log(f"[VIDEO] Video URL: {video_url}")
        video_data = download_video_from_url(video_url)

        # Save video
        step_start = time_module.time()
        filename = f"generated_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
        file_path = run_async(upload_file_sync(
            video_data, filename, "video/mp4", "generated/videos"
        ))
        timing_log(f"Upload video to storage: {time_module.time() - step_start:.2f}s")

        # Create generated work record
        video_work = GeneratedWork(
            user_id=task.user_id,
            task_id=task.id,
            work_type="video",
            filename=filename,
            file_path=file_path,
            file_size=len(video_data),
            mime_type="video/mp4",
            prompt=prompt
        )
        db.add(video_work)

        # Update user's video quota after successful generation
        user = db.query(User).filter(User.id == task.user_id).first()
        if user:
            user.used_video_quota += 1

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result_data = json.dumps({
            "work_id": video_work.id,
            "file_path": file_path,
            "video_task_id": video_task_id
        })
        db.commit()

        timing_log(f"========== Video TOTAL TIME: {time_module.time() - total_start:.2f}s ==========")

    except Exception as e:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            db.commit()
        raise
    finally:
        db.close()
