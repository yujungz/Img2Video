import httpx
import json
from typing import Optional, List, Dict, Any
from app.config import settings


class AIService:
    def __init__(self):
        self.base_url = settings.ANTHROPIC_BASE_URL.rstrip("/")
        self.auth_token = settings.ANTHROPIC_AUTH_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }

    async def _make_request(
        self,
        endpoint: str,
        data: Dict[str, Any],
        timeout: float = 120.0
    ) -> Dict[str, Any]:
        """Make an API request"""
        url = f"{self.base_url}{endpoint}"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=self.headers, json=data)
            response.raise_for_status()
            return response.json()

    async def optimize_prompt(
        self,
        user_prompt: str,
        reference_style: Optional[str] = None
    ) -> str:
        """Use text model to optimize the user's prompt for image generation"""
        system_prompt = """你是一个专业的AI图像生成提示词优化专家。
你的任务是将用户简单的描述转换为详细的、结构化的图像生成提示词。

输出要求：
1. 保持用户的原始意图
2. 添加必要的艺术风格描述
3. 包含画质、光影、构图等专业描述
4. 输出格式为JSON: {"optimized_prompt": "...", "style_keywords": [...], "quality_keywords": [...]}"""

        user_message = f"用户原始提示词: {user_prompt}"
        if reference_style:
            user_message += f"\n\n参考风格特征: {reference_style}"

        data = {
            "model": settings.TEXT_MODEL,
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": user_message}
            ],
            "system": system_prompt
        }

        try:
            result = await self._make_request("/v1/messages", data)
            content = result.get("content", [{}])[0].get("text", "{}")
            parsed = json.loads(content)
            return parsed.get("optimized_prompt", user_prompt)
        except Exception as e:
            print(f"Prompt optimization failed: {e}")
            return user_prompt

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        reference_images: Optional[List[str]] = None,
        width: int = 1024,
        height: int = 1024
    ) -> Dict[str, Any]:
        """Generate image using gpt-image-1 model"""
        data = {
            "model": settings.IMAGE_MODEL,
            "prompt": prompt,
            "size": f"{width}x{height}",
            "n": 1,
            "response_format": "b64_json"
        }

        if negative_prompt:
            data["negative_prompt"] = negative_prompt

        if reference_images:
            data["reference_images"] = reference_images

        result = await self._make_request("/v1/images/generations", data, timeout=300.0)
        return result

    async def extract_style_features(
        self,
        image_base64: str
    ) -> Dict[str, Any]:
        """Extract style features from reference image using vision model"""
        system_prompt = """分析这张图片的艺术风格特征。请识别并描述：
1. 色彩风格（主色调、配色方案、色彩饱和度）
2. 线条特征（粗细、风格、流畅度）
3. 笔触质感（是否明显、风格、方向性）
4. 整体艺术风格（如水彩、油画、卡通、素描等）
5. 角色特征（如果有角色，描述其特征）

输出JSON格式，包含所有识别到的风格特征。"""

        data = {
            "model": settings.TEXT_MODEL,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64
                            }
                        },
                        {
                            "type": "text",
                            "text": "请分析这张图片的艺术风格特征。"
                        }
                    ]
                }
            ],
            "system": system_prompt
        }

        result = await self._make_request("/v1/messages", data)
        return result

    async def generate_video(
        self,
        image_base64: str,
        prompt: str,
        duration: float = 4.0,
        region: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Generate video from static image using sora-2 model"""
        data = {
            "model": settings.VIDEO_MODEL,
            "image": image_base64,
            "prompt": prompt,
            "duration": duration,
            "resolution": "1080p"
        }

        if region:
            data["region"] = region

        result = await self._make_request("/v1/videos/generations", data, timeout=600.0)
        return result

    async def check_video_status(self, task_id: str) -> Dict[str, Any]:
        """Check video generation status"""
        data = {"task_id": task_id}
        result = await self._make_request("/v1/videos/status", data)
        return result


ai_service = AIService()
