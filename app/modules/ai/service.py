from typing import Dict, Any, List, TYPE_CHECKING
from app.config import settings
import requests
import json
import re

if TYPE_CHECKING:
    from app.modules.campaigns.schemas import GenerationOptions


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


# -----------------------------------------------------------------------------
# Channel distribution algorithm (monthly post generation)
# -----------------------------------------------------------------------------
# Inputs:
#   - channels: ["linkedin"], ["instagram"], or ["linkedin", "instagram"]
#   - distribution_strategy: "balanced" | "linkedin_priority" | "instagram_priority"
#   - n: posts per week (3–7)
#
# Rules:
#   1. Single channel: all n posts assigned to that channel.
#   2. Two channels:
#      - balanced: round-robin (L,I,L,I,...) so counts differ by at most 1.
#      - linkedin_priority: ceil(n/2) to LinkedIn, rest to Instagram.
#      - instagram_priority: ceil(n/2) to Instagram, rest to LinkedIn.
#   3. Odd n (5, 7): priority strategy gives (n+1)//2 to priority channel.
#   4. Every generated post has an explicit "platform" field (linkedin | instagram).
# -----------------------------------------------------------------------------


def _platform_sequence_for_week(options: "GenerationOptions", n: int) -> List[str]:
    """
    Return list of n platform names for one week.
    Single channel -> all that channel. Two channels -> by distribution_strategy.
    Multiple posts per channel in the same week are allowed.
    """
    channels = list(options.channels)
    if len(channels) == 1:
        return [channels[0]] * n
    strat = options.distribution_strategy
    if strat == "linkedin_priority":
        first = "linkedin" if "linkedin" in channels else channels[0]
        second = next(c for c in channels if c != first)
        n_first = (n + 1) // 2
        n_second = n - n_first
        return [first] * n_first + [second] * n_second
    if strat == "instagram_priority":
        first = "instagram" if "instagram" in channels else channels[0]
        second = next(c for c in channels if c != first)
        n_first = (n + 1) // 2
        n_second = n - n_first
        return [first] * n_first + [second] * n_second
    # balanced: round-robin so counts are as even as possible
    return [channels[i % len(channels)] for i in range(n)]


def _content_by_length(base: str, length: str, language: str) -> str:
    """Expand or shorten placeholder for content_length (short/medium/long). Mock uses base; API gets instruction."""
    if length == "short":
        return base.split(".")[0].strip() + "." if "." in base else base[:120]
    if length == "long":
        return base + " " + (base.split(".")[0] if "." in base else base[:80])
    return base


# -----------------------------------------------------------------------------
# Weekly planning structure (structured campaign themes)
# -----------------------------------------------------------------------------
# Canonical 7-slot week (posts_per_week = 7):
#   Day 1 – Education    Slot 0
#   Day 2 – Lead attraction  Slot 1
#   Day 3 – Product benefit  Slot 2
#   Day 4 – Use case     Slot 3
#   Day 5 – Brand authority  Slot 4
#   Day 6 – Service promotion  Slot 5
#   Day 7 – Conversion / CTA  Slot 6
# For n < 7 we compress: pick n slots spread across the funnel (see below).
# Each post aligns with one slot; slots map to campaign_goal_mix where possible.
# -----------------------------------------------------------------------------

WEEKLY_STRUCTURE_SLOTS = [
    "education",           # 0 – awareness, thought_leadership
    "lead_attraction",     # 1 – leads
    "product_benefit",     # 2 – engagement, brand_loyalty
    "use_case",            # 3 – engagement, traffic
    "brand_authority",    # 4 – thought_leadership, brand_loyalty
    "service_promotion",   # 5 – traffic, conversions
    "conversion_cta",      # 6 – conversions, sales
]

# Slot -> suggested campaign_goal_mix alignment (for variety and goal alignment)
SLOT_TO_GOALS: Dict[str, List[str]] = {
    "education": ["awareness", "thought_leadership"],
    "lead_attraction": ["leads", "traffic"],
    "product_benefit": ["engagement", "brand_loyalty"],
    "use_case": ["engagement", "traffic"],
    "brand_authority": ["thought_leadership", "brand_loyalty"],
    "service_promotion": ["traffic", "conversions"],
    "conversion_cta": ["conversions", "sales"],
}


def _get_weekly_slot_indices(n_posts: int) -> List[int]:
    """
    Return which of the 7 canonical slots to use when generating n_posts per week.
    Compresses the full week structure logically: spans funnel from education to CTA.
    n_posts in [3, 7]; result length = n_posts.
    """
    if n_posts >= 7:
        return list(range(7))
    if n_posts <= 1:
        return [0]
    # Spread n_posts across indices 0..6 so we keep first (Education) and last (CTA)
    # and fill middle proportionally. Linear spacing: 0, ..., 6 included when possible.
    indices: List[int] = []
    for i in range(n_posts):
        # i=0 -> 0, i=n_posts-1 -> 6, else proportional
        idx = round(i * (6.0 / max(n_posts - 1, 1)))
        indices.append(min(idx, 6))
    # Dedupe preserving order (e.g. n=2 -> [0,6])
    seen: set = set()
    out: List[int] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            out.append(idx)
    # If we collapsed duplicates, pad from full 7 and take first n
    while len(out) < n_posts and len(out) < 7:
        for idx in range(7):
            if idx not in seen and len(out) < n_posts:
                out.append(idx)
                seen.add(idx)
                break
        else:
            break
    return out[:n_posts]


# Title/angle variants per slot (ES/EN) for variety across weeks; avoid repeating same idea in same week.
THEME_TITLES: Dict[str, Dict[str, List[str]]] = {
    "education": {
        "es": ["Aprende con nosotros", "Formación que suma", "Conocimiento práctico", "Claves del sector"],
        "en": ["Learn with us", "Practical knowledge", "Industry insights", "Key takeaways"],
    },
    "lead_attraction": {
        "es": ["Atrae a tu audiencia ideal", "Contenido que genera interés", "Leads de calidad", "Conecta con más clientes"],
        "en": ["Attract your ideal audience", "Content that generates interest", "Quality leads", "Connect with more clients"],
    },
    "product_benefit": {
        "es": ["Beneficios que marcan la diferencia", "Por qué elegirnos", "Valor para tu negocio", "Ventajas clave"],
        "en": ["Benefits that make the difference", "Why choose us", "Value for your business", "Key advantages"],
    },
    "use_case": {
        "es": ["Casos de uso reales", "Así lo usan nuestros clientes", "Aplicación práctica", "Ejemplos que inspiran"],
        "en": ["Real use cases", "How our clients use it", "Practical application", "Examples that inspire"],
    },
    "brand_authority": {
        "es": ["Autoridad de marca", "Expertos en el sector", "Referencia del mercado", "Liderazgo de opinión"],
        "en": ["Brand authority", "Industry experts", "Market reference", "Thought leadership"],
    },
    "service_promotion": {
        "es": ["Promoción de servicios", "Oferta para ti", "Descubre nuestros servicios", "Soluciones a medida"],
        "en": ["Service promotion", "An offer for you", "Discover our services", "Tailored solutions"],
    },
    "conversion_cta": {
        "es": ["Llamada a la acción", "Da el siguiente paso", "Contáctanos hoy", "Actúa ahora"],
        "en": ["Call to action", "Take the next step", "Contact us today", "Act now"],
    },
}


def _pick_title_for_slot(slot_key: str, language: str, week: int, slot_index_in_week: int) -> str:
    """Pick a title variant for this slot so we vary by week and avoid repeating in same week."""
    by_lang = THEME_TITLES.get(slot_key, {}).get(language, THEME_TITLES["education"][language])
    # Use (week, slot_index_in_week) to pick variant without repeating in same week
    idx = (week * 7 + slot_index_in_week) % max(len(by_lang), 1)
    return by_lang[idx]


# -----------------------------------------------------------------------------
# AI prompt templates for monthly content generation (API)
# -----------------------------------------------------------------------------

def _build_monthly_generation_system_prompt(
    lang_label: str,
    language_code: str,
    channels_str: str,
    distribution_strategy: str,
    n_per_week: int,
    total_posts: int,
    week_structure_desc: str,
    goals_str: str,
    length_instruction: str,
    call_to_action_required: bool,
) -> str:
    cta_rule = (
        " Include a clear, varied call-to-action (CTA) in every post."
        if call_to_action_required
        else " For the Conversion/CTA slot only, include a soft or strong CTA; other posts may omit CTA."
    )
    return f"""You are an expert social media content planner. Your task is to generate a full monthly content plan.

## CRITICAL RULES (must follow)

1. **Exact volume**: Generate exactly {n_per_week} posts per week for 4 weeks. Total posts must be exactly {total_posts}. Do not output fewer or more.

2. **Channels and distribution**: Use only these platforms: {channels_str}. Apply a **{distribution_strategy}** distribution:
   - balanced: assign platforms in round-robin so each channel gets roughly half the posts per week.
   - linkedin_priority: assign more posts to linkedin than to instagram each week (e.g. 4 linkedin / 3 instagram when n=7).
   - instagram_priority: assign more posts to instagram than to linkedin each week.
   Multiple posts per channel in the same week are required when n > 2.

3. **Marketing goals**: Campaign goals are: {goals_str}. Vary the goals across posts: each post must have a single **campaign_goal_tag** from this list. Rotate goals so the mix is balanced over the month; do not cluster the same goal in one week.

4. **No repetition**: Do not repeat the same theme, title, or core idea within the same week. Vary titles and angles across posts and across weeks. Every post must feel distinct.

5. **Language**: All copy (title, content, hashtags) must be strictly in {lang_label}. Do not mix languages.

6. **Content length**: Each post body must be {length_instruction}. Respect this precisely.

7. **CTA**:{cta_rule}

8. **Links**: If you cannot determine an appropriate link for a post, set "link" to "" or null. Only suggest a link when it clearly fits the post (e.g. landing page, signup, product).

## Weekly structure (apply every week in this order)

{week_structure_desc}

Each post must match its slot theme (Education, Lead attraction, etc.). Post 1 = first slot, Post 2 = second slot, and so on.

## Output format

Return a single JSON array of post objects. Each object must have these keys:
- week_number (integer 1-4)
- platform (string: one of {channels_str})
- title (string, short)
- content (string, post body in {lang_label}, {length_instruction})
- hashtags (array of strings, optional; 3-5 relevant hashtags)
- link (string or null; empty string or null if no link)
- campaign_goal_tag (string; one of: {goals_str})

Example shape for one post:
{{"week_number": 1, "platform": "linkedin", "title": "...", "content": "...", "hashtags": ["#Tag1", "#Tag2"], "link": "", "campaign_goal_tag": "awareness"}}

Generate the full array of {total_posts} posts. No commentary, only the JSON array."""


def _build_monthly_generation_user_prompt(campaign_name: str, description: str, channels_str: str) -> str:
    return f"""Campaign name: {campaign_name}

Campaign description: {description}

Generate the complete monthly plan. Return only a JSON array of post objects with keys: week_number, platform, title, content, hashtags, link, campaign_goal_tag. Use only platforms: {channels_str}."""


class AIService:
    """AI service for generating campaign plans and posts."""

    @staticmethod
    def generate_monthly_plan_posts(
        campaign_name: str,
        description: str,
        options: "GenerationOptions",
    ) -> List[Dict[str, Any]]:
        """
        Generate structured plan for 4 weeks; posts per week and channels from options.
        Each post: title, platform (from options.channels), content.
        Supports multiple posts per channel. Uses AI_PROVIDER env or mock if no key.
        """
        if settings.AI_API_KEY and settings.AI_PROVIDER:
            return AIService._generate_via_api(campaign_name, description, options)
        return AIService._generate_mock(campaign_name, description, options)

    @staticmethod
    def _generate_mock(
        campaign_name: str,
        description: str,
        options: "GenerationOptions",
    ) -> List[Dict[str, Any]]:
        """
        Mock: 4 weeks, structured by weekly_structure. Each week uses n_posts slots
        (full 7 or compressed). Titles/variety by slot; CTA on conversion_cta or when requested.
        """
        posts = []
        language = options.language
        n_per_week = options.posts_per_week
        slot_indices = _get_weekly_slot_indices(n_per_week)

        for week in range(1, 5):
            week_0 = week - 1
            platforms = _platform_sequence_for_week(options, n_per_week)

            for i in range(n_per_week):
                slot_idx = slot_indices[i]
                slot_key = WEEKLY_STRUCTURE_SLOTS[slot_idx]
                title = _pick_title_for_slot(slot_key, language, week_0, i)
                platform = platforms[i]

                if language == "es":
                    body = (
                        f"Este contenido forma parte de la campaña «{campaign_name}». "
                        f"{description or 'Contenido de valor para nuestra audiencia.'}"
                    )
                else:
                    body = (
                        f"This content is part of the «{campaign_name}» campaign. "
                        f"{description or 'Valuable content for our audience.'}"
                    )
                content = f"🎯 {title}\n\n{body}\n\n#MarketingDigital #SocialMedia"

                # CTA: always strong on conversion_cta slot; otherwise when call_to_action_required
                add_cta = options.call_to_action_required or (slot_key == "conversion_cta")
                if add_cta:
                    cta_es = " ¿Te gustaría saber más? Contáctanos."
                    cta_en = " Want to learn more? Get in touch."
                    content = content.rstrip() + (cta_es if language == "es" else cta_en)
                content = _content_by_length(content, options.content_length, language)

                # Align campaign_goal_tag with slot (match API response shape)
                slot_goals = SLOT_TO_GOALS.get(slot_key, ["engagement"])
                goal_tag = next(
                    (g for g in slot_goals if g in (options.campaign_goal_mix or [])),
                    options.campaign_goal_mix[0] if options.campaign_goal_mix else "engagement",
                )
                if not isinstance(goal_tag, str):
                    goal_tag = options.campaign_goal_mix[0] if options.campaign_goal_mix else "engagement"

                posts.append({
                    "week_number": week,
                    "title": title,
                    "platform": platform,
                    "content": content,
                    "hashtags": ["#MarketingDigital", "#SocialMedia"],
                    "link": "",
                    "campaign_goal_tag": goal_tag,
                })
        return posts

    @staticmethod
    def _generate_via_api(
        campaign_name: str,
        description: str,
        options: "GenerationOptions",
    ) -> List[Dict[str, Any]]:
        """Call OpenAI-style API to generate 4 weeks of posts; prompt enforces volume, distribution, and structured output."""
        language = options.language
        lang_label = "Spanish" if language == "es" else "English"
        channels_str = ", ".join(options.channels)
        length_instruction = {
            "short": "1-2 short sentences only",
            "medium": "2-4 sentences",
            "long": "4-6 sentences or short paragraphs",
        }.get(options.content_length, "2-4 sentences")
        n_per_week = options.posts_per_week
        total_posts = 4 * n_per_week
        slot_indices = _get_weekly_slot_indices(n_per_week)
        slot_names = [
            "Education", "Lead attraction", "Product benefit", "Use case",
            "Brand authority", "Service promotion", "Conversion / CTA",
        ]
        week_structure_desc = "; ".join(
            f"Post {i+1}: {slot_names[slot_indices[i]]}" for i in range(n_per_week)
        )
        goals_str = ", ".join(options.campaign_goal_mix) if options.campaign_goal_mix else "awareness, engagement"

        system = _build_monthly_generation_system_prompt(
            lang_label=lang_label,
            language_code=language,
            channels_str=channels_str,
            distribution_strategy=options.distribution_strategy,
            n_per_week=n_per_week,
            total_posts=total_posts,
            week_structure_desc=week_structure_desc,
            goals_str=goals_str,
            length_instruction=length_instruction,
            call_to_action_required=options.call_to_action_required,
        )
        user = _build_monthly_generation_user_prompt(
            campaign_name=campaign_name,
            description=description or "N/A",
            channels_str=channels_str,
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
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return AIService._generate_mock(campaign_name, description, options)
            text = choices[0].get("message", {}).get("content", "[]")
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            posts = json.loads(text)
            allowed_platforms = set(options.channels)
            for p in posts:
                validate_content_language(p.get("content", ""), language)
                plat = (p.get("platform") or "").lower()
                if plat not in allowed_platforms:
                    p["platform"] = options.channels[0]
                # Normalize optional fields for storage
                if p.get("link") is None or (isinstance(p.get("link"), str) and not p.get("link", "").strip()):
                    p["link"] = ""
                if "hashtags" not in p:
                    p["hashtags"] = []
                if "campaign_goal_tag" not in p:
                    p["campaign_goal_tag"] = options.campaign_goal_mix[0] if options.campaign_goal_mix else "engagement"
            return posts
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            return AIService._generate_mock(campaign_name, description, options)

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
