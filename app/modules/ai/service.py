from typing import Dict, Any, List
from app.config import settings
import requests
import json
import re


# Words that indicate wrong language (simple heuristic)
ENGLISH_DOMINANT = re.compile(r"\b(the|and|is|are|was|were|have|has|had|for|with|this|that|you|your|will|can)\b", re.I)
SPANISH_DOMINANT = re.compile(r"\b(el|la|los|las|un|una|de|que|en|es|por|con|para|al|lo|como|más|pero|sus|le|ya|o|fue|este|sí|porque|esta|entre|cuando|muy|sin|sobre|también|me|hasta|hay|donde|han|quien|desde|todo|nos|durante|estados|todos|uno|les|ni|contra|otros|ese|eso|ante|ellos|e|esto|mí|antes|algunos|qué|unos|yo|otro|otras|otra|él|tanto|esa|estos|mucho|quienes|nada|ser|muchos|cuál|sea|poco|ella|están|estas|algunas|algo|nosotros)\b", re.I)


def validate_content_language(content: str, expected_language: str) -> None:
    """Raise ValueError if content appears to be in the wrong language."""
    if not content or not content.strip():
        return
    content_lower = content.lower()
    if expected_language == "es":
        en_count = len(ENGLISH_DOMINANT.findall(content_lower))
        if en_count >= 3:  # dominant English
            raise ValueError("Content appears to be in English; campaign language is Spanish (ES).")
    elif expected_language == "en":
        es_count = len(SPANISH_DOMINANT.findall(content_lower))
        if es_count >= 3:  # dominant Spanish
            raise ValueError("Content appears to be in Spanish; campaign language is English (EN).")


class AIService:
    """AI service for generating campaign plans and posts."""

    @staticmethod
    def generate_monthly_plan_posts(
        campaign_name: str,
        description: str,
        language: str,
    ) -> List[Dict[str, Any]]:
        """
        Generate structured plan for 4 weeks; each week 2-3 posts.
        Each post: title, platform (linkedin|instagram), content.
        Respects language; uses AI_PROVIDER env or mock if no key.
        """
        if settings.AI_API_KEY and settings.AI_PROVIDER:
            return AIService._generate_via_api(campaign_name, description, language)
        return AIService._generate_mock(campaign_name, description, language)

    @staticmethod
    def _generate_mock(
        campaign_name: str,
        description: str,
        language: str,
    ) -> List[Dict[str, Any]]:
        """Mock: 4 weeks, 2-3 posts per week, title/platform/content in correct language."""
        posts = []
        themes_es = [
            "Introducción a la campaña",
            "Beneficios clave",
            "Casos de éxito",
            "Consejos prácticos",
            "Llamada a la acción",
            "Testimonios",
            "Tendencias del sector",
            "Recursos útiles",
            "Próximos pasos",
            "Resumen de la semana",
        ]
        themes_en = [
            "Campaign introduction",
            "Key benefits",
            "Success stories",
            "Practical tips",
            "Call to action",
            "Testimonials",
            "Industry trends",
            "Useful resources",
            "Next steps",
            "Week summary",
        ]
        themes = themes_es if language == "es" else themes_en
        platforms = ["linkedin", "instagram"]
        for week in range(1, 5):
            n = 2 + (week % 2)  # 2 or 3 posts per week
            for i in range(n):
                idx = (week - 1) * 3 + i
                theme = themes[idx % len(themes)]
                platform = platforms[i % 2]
                if language == "es":
                    content = (
                        f"🎯 {theme}\n\n"
                        f"Este contenido forma parte de la campaña «{campaign_name}». "
                        f"{description or 'Contenido de valor para nuestra audiencia.'}\n\n"
                        "#MarketingDigital #SocialMedia"
                    )
                else:
                    content = (
                        f"🎯 {theme}\n\n"
                        f"This content is part of the «{campaign_name}» campaign. "
                        f"{description or 'Valuable content for our audience.'}\n\n"
                        "#DigitalMarketing #SocialMedia"
                    )
                posts.append({
                    "week_number": week,
                    "title": theme,
                    "platform": platform,
                    "content": content,
                })
        return posts

    @staticmethod
    def _generate_via_api(
        campaign_name: str,
        description: str,
        language: str,
    ) -> List[Dict[str, Any]]:
        """Call OpenAI-style API to generate 4 weeks of posts."""
        lang_instruction = "Spanish (es)" if language == "es" else "English (en)"
        system = (
            f"You are a social media content planner. Generate a monthly plan: 4 weeks, "
            f"2-3 posts per week. Each post must have: title (short), platform (linkedin or instagram), "
            f"content (post body, 2-4 sentences). All content must be strictly in {lang_instruction}."
        )
        user = (
            f"Campaign: {campaign_name}\nDescription: {description or 'N/A'}\n"
            f"Respond with a JSON array of objects with keys: week_number (1-4), title, platform, content."
        )
        url = f"{settings.AI_API_URL.rstrip('/')}/chat/completions"
        payload = {
            "model": "gpt-4" if "openai" in (settings.AI_PROVIDER or "").lower() else "gpt-4",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {settings.AI_API_KEY}"},
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return AIService._generate_mock(campaign_name, description, language)
            text = choices[0].get("message", {}).get("content", "[]")
            # Extract JSON array from markdown code block if present
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            posts = json.loads(text)
            for p in posts:
                validate_content_language(p.get("content", ""), language)
            return posts
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            return AIService._generate_mock(campaign_name, description, language)

    @staticmethod
    def generate_campaign_plan(
        campaign_name: str,
        description: str = None,
        language: str = "es",
    ) -> Dict[str, Any]:
        """Legacy: returns a mock plan structure."""
        plan = {
            "theme": campaign_name,
            "description": description or "",
            "language": language,
            "posts_count": 5,
            "posting_schedule": "daily",
            "content_themes": [
                f"Introduction to {campaign_name}",
                f"Benefits of {campaign_name}",
                f"Success stories related to {campaign_name}",
                f"Tips and best practices for {campaign_name}",
                f"Call to action for {campaign_name}",
            ],
            "target_audience": "General audience",
            "tone": "Professional and engaging",
        }
        return plan

    @staticmethod
    def generate_posts(
        campaign_plan: Dict[str, Any],
        language: str = "es",
    ) -> List[Dict[str, Any]]:
        """Legacy: returns mock posts from plan."""
        posts = []
        content_themes = campaign_plan.get("content_themes", [])
        posts_count = campaign_plan.get("posts_count", 5)
        for i, theme in enumerate(content_themes[:posts_count]):
            platform = "linkedin" if i % 2 == 0 else "instagram"
            if language == "es":
                content = (
                    f"🎯 {theme}\n\n"
                    "Este es un post de ejemplo generado para la campaña. "
                    f"Contenido relevante que se adapta al tema: {theme}.\n\n"
                    "#MarketingDigital #SocialMedia"
                )
            else:
                content = (
                    f"🎯 {theme}\n\n"
                    "This is an example post generated for the campaign. "
                    f"Relevant content that adapts to the theme: {theme}.\n\n"
                    "#DigitalMarketing #SocialMedia"
                )
            posts.append({
                "content": content,
                "platform": platform,
                "metadata": {"theme": theme, "order": i + 1},
            })
        return posts
