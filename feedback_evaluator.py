import re
from dataclasses import dataclass
from typing import Dict, Any, List, Tuple, Optional, Callable

@dataclass
class FeedbackRecord:
    feedback: str
    source: Optional[str]
    iteration: Optional[int]
    score: float
    confidence: float
    category: str
    improvements: List[Dict[str, Any]]

class FeedbackEvaluator:
    """Enhanced evaluator for both critic and user feedback"""
    # Precompiled patterns
    _NUMBERED_RE = re.compile(r'\b\d+\.\s*(.+?)(?=(?:\n\d+\.|\Z))', re.DOTALL)
    _BULLET_RE = re.compile(r'^[\-\*•]\s+(.+)', re.MULTILINE)
    _INLINE_SEMICOLON_RE = re.compile(r'(?:^|[\n])([^;\n]{4,}?);(?!;)')
    _MULTI_STEP_RE = re.compile(r'\b(first|second|third|fourth|lastly|finally|next)\b[:,]?\s+(.*?)(?=(?:\bfirst|\bsecond|\bthird|\bfourth|\blastly|\bfinally|\bnext)\b|$)', re.IGNORECASE | re.DOTALL)

    def __init__(
        self,
        improvement_keywords: Optional[Dict[str, List[str]]] = None,
        max_history: Optional[int] = 250,
        scoring_fn: Optional[Callable[[str], float]] = None
    ):
        self.feedback_history: List[FeedbackRecord] = []
        self.max_history = max_history
        self.scoring_fn = scoring_fn
        self.improvement_keywords = improvement_keywords or {
            "style": ["professional", "clean", "modern", "style", "appearance"],
            "colors": ["color", "contrast", "palette", "scheme", "visibility"],
            "annotations": ["label", "annotation", "mark", "highlight", "text"],
            "indicators": ["moving average", "ma", "technical", "indicator"],
            "volume": ["volume", "trading volume", "bar chart"],
            "trends": ["trend", "trendline", "direction", "pattern"],
            "peaks": ["peak", "valley", "high", "low", "maximum", "minimum"],
            "comparison": ["benchmark", "compare", "s&p", "index", "relative"],
            "risk": ["risk", "volatility", "standard deviation", "variance"],
            "layout": ["layout", "spacing", "size", "arrangement", "subplot"]
        }
        # Emphasis / priority weights
        self._priority_tokens = {
            "high": ["must", "required", "critical"],
            "medium": ["should", "important", "need"],
        }

    def _preprocess_feedback(self, feedback: str) -> str:
        return feedback.strip()

    def _normalize_suggestion(self, text: str) -> str:
        return re.sub(r'\s+', ' ', re.sub(r'[^\w\s%\-:,.]', '', text.lower())).strip()

    def is_approved(self, feedback: str) -> bool:
        """Check if critic/user approved the output"""
        approval_terms = ["approved", "excellent", "perfect", "great job", "well done", "looks good"]
        f = feedback.lower()
        return any(t in f for t in approval_terms)

    def _detect_categories(self, feedback_lower: str) -> List[Dict[str, Any]]:
        improvements = []
        for category, keywords in self.improvement_keywords.items():
            hits = [kw for kw in keywords if kw in feedback_lower]
            if hits:
                improvements.append({
                    "category": category,
                    "detected_keywords": hits,
                    "priority": self._calculate_priority(feedback_lower, category)
                })
        return improvements

    def _extract_list_items(self, feedback: str) -> List[str]:
        items = []
        items += self._NUMBERED_RE.findall(feedback)
        items += self._BULLET_RE.findall(feedback)
        for m in self._MULTI_STEP_RE.finditer(feedback):
            seg = m.group(2).strip()
            if seg:
                items.append(seg)
        # Split on semicolons for dense inline lists
        for m in self._INLINE_SEMICOLON_RE.finditer(feedback):
            part = m.group(1).strip()
            if part and len(part.split()) > 2:
                items.append(part)
        # Light dedupe
        norm_seen = set()
        deduped = []
        for raw in items:
            norm = self._normalize_suggestion(raw)
            if norm and norm not in norm_seen:
                norm_seen.add(norm)
                deduped.append(raw.strip())
        return deduped

    def extract_improvements(self, feedback: str) -> List[Dict[str, Any]]:
        """Extract structured improvements from feedback (categories + explicit suggestions)."""
        improvements: List[Dict[str, Any]] = []
        clean = self._preprocess_feedback(feedback)
        lower = clean.lower()

        improvements.extend(self._detect_categories(lower))

        for suggestion in self._extract_list_items(clean):
            improvements.append({
                "category": "specific",
                "suggestion": suggestion,
                "priority": "medium"
            })
        return improvements

    def _calculate_priority(self, feedback_lower: str, category: str) -> str:
        """Calculate priority based on feedback emphasis"""
        if any(t in feedback_lower for t in self._priority_tokens["high"]):
            return "high"
        if any(t in feedback_lower for t in self._priority_tokens["medium"]):
            return "medium"
        return "low"

    # Scoring decomposition
    def _score_sentiment(self, feedback_lower: str) -> Tuple[float, int]:
        positive = {
            "excellent": 3, "perfect": 3, "great": 2, "professional": 2,
            "good": 1, "clear": 1, "accurate": 1, "well": 1
        }
        negative = {
            "error": 3, "wrong": 3, "missing": 2, "bad": 2,
            "poor": 2, "unclear": 2, "confusing": 2,
            "fix": 1, "improve": 1, "needs": 1, "add": 1, "should": 1
        }
        score_raw = 0
        matched = 0
        for k, w in positive.items():
            if k in feedback_lower:
                score_raw += w
                matched += 1
        for k, w in negative.items():
            if k in feedback_lower:
                score_raw -= w
                matched += 1
        # Normalize to 0..1 (range approx -10..+10 mapped)
        norm = (score_raw + 10) / 20
        return max(0.0, min(1.0, norm)), matched

    def _score_action_penalty(self, feedback_lower: str) -> float:
        action_terms = ["improve", "needs", "should", "add", "consider", "enhance", "fix"]
        hits = sum(1 for t in action_terms if t in feedback_lower)
        if hits == 0:
            return 0.0
        return min(0.25, 0.05 * hits)  # cap penalty

    def _apply_approval_adjustments(self, base: float, feedback_lower: str) -> float:
        if "approved" in feedback_lower and "not" not in feedback_lower:
            base = max(base, 0.7)
        if any(p in feedback_lower for p in ["not approved", "rejected", "needs work"]):
            base = min(base, 0.4)
        return base

    def score_quality(self, feedback: str) -> float:
        """Composite score 0..1 using sentiment minus action penalty + approval adjustment."""
        if self.scoring_fn:
            return max(0.0, min(1.0, self.scoring_fn(feedback)))
        lower = feedback.lower()
        sentiment, _ = self._score_sentiment(lower)
        penalty = self._score_action_penalty(lower)
        score = sentiment - penalty
        score = self._apply_approval_adjustments(score, lower)
        return max(0.0, min(1.0, score))

    def _confidence(self, feedback: str) -> float:
        lower = feedback.lower()
        tokens = re.findall(r'\b\w+\b', lower)
        if not tokens:
            return 0.3
        sentiment, matched = self._score_sentiment(lower)
        return max(0.1, min(1.0, (matched / len(tokens)) + 0.1 * (0.5 - abs(sentiment - 0.5))))

    def categorize_feedback(self, feedback: str) -> str:
        """Categorize feedback type"""
        lower = feedback.lower()
        if self.is_approved(feedback):
            return "approval"
        if any(w in lower for w in ["error", "bug", "crash", "fail"]):
            return "error"
        if any(w in lower for w in ["improve", "enhance", "add", "include"]):
            return "enhancement"
        if any(w in lower for w in ["change", "modify", "adjust", "update"]):
            return "modification"
        return "general"

    def analyze(self, feedback: str, source: Optional[str] = None, iteration: Optional[int] = None, mutate: bool = False) -> Dict[str, Any]:
        """Analyze feedback; mutate history only if mutate=True."""
        score = self.score_quality(feedback)
        conf = self._confidence(feedback)
        improvements = self.extract_improvements(feedback)
        category = self.categorize_feedback(feedback)
        record = {
            "feedback": feedback,
            "source": source,
            "iteration": iteration,
            "score": score,
            "confidence": conf,
            "category": category,
            "improvements": improvements
        }
        if mutate:
            self.store_feedback(feedback, source or "unknown", iteration if iteration is not None else -1, precomputed=record)
        return record

    def generate_improvement_plan(self, feedback_list: List[str]) -> Dict[str, List[str]]:
        """Aggregate + weight improvements."""
        buckets = {"high_priority": {}, "medium_priority": {}, "low_priority": {}}
        for fb in feedback_list:
            for imp in self.extract_improvements(fb):
                priority = imp.get("priority", "medium")
                key = imp.get("suggestion") or f"Improve {imp['category']}"
                norm = self._normalize_suggestion(key)
                store_key = f"{priority}_priority"
                buckets[store_key][norm] = key  # last wins (original casing)
        # Convert to lists
        return {k: list(v.values()) for k, v in buckets.items()}

    def store_feedback(self, feedback: str, source: str, iteration: int, precomputed: Optional[Dict[str, Any]] = None):
        data = precomputed or self.analyze(feedback, source, iteration, mutate=False)
        rec = FeedbackRecord(
            feedback=data["feedback"],
            source=source,
            iteration=iteration,
            score=data["score"],
            confidence=data["confidence"],
            category=data["category"],
            improvements=data["improvements"]
        )
        self.feedback_history.append(rec)
        if self.max_history and len(self.feedback_history) > self.max_history:
            self.feedback_history = self.feedback_history[-self.max_history:]

    def get_feedback_trends(self) -> Dict[str, Any]:
        """Analyze feedback trends over iterations"""
        if not self.feedback_history:
            return {}
        scores = [r.score for r in self.feedback_history]
        categories = [r.category for r in self.feedback_history]
        improving = "improving" if len(scores) > 1 and scores[-1] > scores[0] else ("declining" if len(scores) > 1 and scores[-1] < scores[0] else "stable")
        return {
            "average_score": sum(scores) / len(scores),
            "score_trend": improving,
            "most_common_category": max(set(categories), key=categories.count),
            "total_feedback": len(self.feedback_history)
        }

    def get_detailed_trends(self) -> Dict[str, Any]:
        """Get detailed trends including category-specific averages."""
        if not self.feedback_history:
            return {}
        per_cat: Dict[str, List[float]] = {}
        for r in self.feedback_history:
            per_cat.setdefault(r.category, []).append(r.score)
        cat_avg = {k: sum(v) / len(v) for k, v in per_cat.items()}
        last5 = self.feedback_history[-5:]
        last5_avg = sum(r.score for r in last5) / len(last5)
        overall = sum(r.score for r in self.feedback_history) / len(self.feedback_history)
        delta_recent = last5_avg - overall
        return {
            "category_averages": cat_avg,
            "recent_avg_vs_overall_delta": delta_recent,
            "history_length": len(self.feedback_history)
        }

    def export_config(self) -> Dict[str, Any]:
        return {
            "improvement_keywords": self.improvement_keywords,
            "max_history": self.max_history,
            "custom_scoring_fn": self.scoring_fn is not None
        }
