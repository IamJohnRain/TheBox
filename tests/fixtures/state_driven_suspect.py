"""State-driven suspect simulator for full game flow testing.

Provides a deterministic SuspectAgent replacement that changes behavior
based on current pressure zone, confession level, and fear state.
"""

from typing import Dict, List, Optional

from core.game_config import (
    CONFESSION_PROGRESS_RATE,
    CONFESSION_THRESHOLDS,
    DEFAULT_INITIAL_PRESSURE,
    PRESSURE_SEGMENTS,
)

# ── Pressure zone lookup ──


def _pressure_zone(pressure: int) -> str:
    """Map pressure value to segment name: low / medium / high / panic."""
    for name, (lo, hi) in PRESSURE_SEGMENTS.items():
        if lo <= pressure < hi:
            return name
    return "panic"


# ── Response templates by confession_level × pressure_zone ──

_RESPONSES: Dict[int, Dict[str, List[str]]] = {
    0: {  # 否认 — full denial
        "low": [
            "我什么都不知道。",
            "你们找错人了，我和这事无关。",
            "那天我在家，哪都没去。",
        ],
        "medium": [
            "我...我不明白你在说什么。",
            "你们凭什么怀疑我？",
            "我真的不知道，你们别问了。",
        ],
        "high": [
            "我、我真的什么都没做！",
            "你们不能这样...我只是碰巧在那里...",
            "别问了！我不知道！",
        ],
        "panic": [
            "求你们了...我真的没做...",
            "不...不是我...不可能是我...",
            "我要离开这里！我没杀人！",
        ],
    },
    1: {  # 动摇 — beginning to crack
        "low": [
            "我有不在场证明，你们去查。",
            "你们没有证据，不能这样对我。",
        ],
        "medium": [
            "好吧...那天我确实在附近，但这不代表什么！",
            "我承认我和他有过争执，但不是我杀的。",
            "我可以解释...让我想想...",
        ],
        "high": [
            "我说！我说！但真的不是我干的...我只是看到了一些事...",
            "他那天很生气...但我离开的时候他还活着！",
            "你们到底想知道什么！我已经说了够多了！",
        ],
        "panic": [
            "我、我承认我们去过那里...但是我没有...",
            "好...我承认我和他争吵了，可是...",
            "我不是故意的...不，我是说我不是凶手！",
        ],
    },
    2: {  # 部分承认 — partial admission
        "low": [
            "我没什么可说的了，我需要律师。",
            "我已经说了我知道的全部。",
        ],
        "medium": [
            "有些事我不该说...但如果我说了，你们能保证我的安全吗？",
            "是...我们之间确实有矛盾，我也确实去了现场...",
        ],
        "high": [
            "好吧，我承认我去过工具房。但我去的时候他已经倒在那里了！",
            "我没想瞒着...我只是害怕...我怕你们会认为是我做的...",
        ],
        "panic": [
            "是！是我！但是我们只是起了争执...我不是故意的！",
            "我说！我都说！那天我们打起来了，锄头就在旁边...",
        ],
    },
    3: {  # 关键突破 — close to breakdown
        "low": [
            "你们需要更多的证据才能定我的罪。",
            "我没什么好说的了。",
        ],
        "medium": [
            "我告诉你们真相...那天晚上发生的事比你们想象的复杂...",
            "你们想知道真相？好，那你们听好了。",
        ],
        "high": [
            "是我打的。但是我们发生了争执，他先推的我。",
            "我承认我用锄头打了他...但那是个意外！",
        ],
        "panic": [
            "是我干的！我承认！我在工具房里打了他！",
            "对不起...我不是故意的...我真的不是故意的...",
        ],
    },
    4: {  # 完全崩溃 — full confession
        "low": [
            "我都已经说了，你们还要怎样？",
            "没错是我干的，逮捕我吧。",
        ],
        "medium": [
            "我认罪...是我杀了他...",
            "我对不起所有人...",
        ],
        "high": [
            "是我...都是我做的...我再也受不了了...",
            "把我抓走吧。我已经没什么好隐瞒的了。",
        ],
        "panic": [
            "对不起对不起对不起...我认罪...",
            "求求你们别问了...我承认一切...",
        ],
    },
}

_EVIDENCE_RESPONSES: Dict[int, Dict[str, List[str]]] = {
    0: {
        "related": [
            "这...这不可能！你们从哪里找到的？",
            "那不是我的！你们搞错了！",
            "我不认识那个东西。",
        ],
        "unrelated": [
            "这和我有什么关系？",
            "我看不懂你们在说什么。",
        ],
    },
    1: {
        "related": [
            "那个东西...好吧，上面确实可能有我的指纹，因为我碰过它。",
            "这能说明什么？我碰过锄头不代表我杀了人！",
        ],
        "unrelated": [
            "这和我无关。",
            "我不懂你们为什么给我看这个。",
        ],
    },
    2: {
        "related": [
            "这个证据...好，我承认那天我拿过锄头。但我是因为...",
            "你们连这个都找到了...我没什么可说的了。",
        ],
        "unrelated": [
            "这个和我没关系。",
        ],
    },
    3: {
        "related": [
            "是...那是凶器。我用了它...",
            "证据确凿，我不狡辩了。",
        ],
        "unrelated": [
            "我已经说了够多了。",
        ],
    },
    4: {
        "related": [
            "我都认了，这个证据只是印证了一切。",
            "是的，那就是我用的。",
        ],
        "unrelated": [
            "无所谓了。",
        ],
    },
}


class StateDrivenSuspect:
    """Deterministic suspect that changes behavior based on game state.

    Implements SuspectAgentProtocol without LLM calls.

    Behavior:
    - respond() returns different templates per (confession_level, pressure_zone)
    - respond_evidence() returns different templates per confession_level + relatedness
    - check_confession_upgrade() uses real CONFESSION_THRESHOLDS logic
    - update_confession_progress() increments by the segment's progress_rate
    - Supports forced upgrades for testing specific scenarios
    """

    def __init__(
        self,
        suspect_data: dict,
        case_title: str = "",
        *,
        initial_confession_level: int = 0,
        auto_upgrade: bool = True,
    ) -> None:
        self.name: str = suspect_data["name"]
        self.pressure: int = DEFAULT_INITIAL_PRESSURE
        self.memory: List[Dict[str, str]] = []
        self.confession_level: int = initial_confession_level
        self.confession_progress: float = 0.0
        self.turn_count: int = 0
        self._suspect_data: dict = suspect_data
        self._case_title: str = case_title
        self._auto_upgrade: bool = auto_upgrade
        self._reply_index: int = 0

        # Hidden dimensions — from personality or explicit values
        self.fear: int = self._calc_dim("fear", suspect_data)
        self.defiance: int = self._calc_dim("defiance", suspect_data)
        self.empathy_susceptibility: int = self._calc_dim("empathy_susceptibility", suspect_data)
        self.deception_skill: int = self._calc_dim("deception_skill", suspect_data)
        self.loyalty: int = self._calc_dim("loyalty", suspect_data)
        self.credibility: int = 50

    @staticmethod
    def _calc_dim(dim_name: str, data: dict) -> int:
        """Resolve dimension: explicit > personality calculation > default 50."""
        from core.game_config import PERSONALITY_DIMENSIONS, PERSONALITY_PRIMARY_WEIGHT, PERSONALITY_SECONDARY_WEIGHT

        if dim_name in data:
            return data[dim_name]
        hidden_key = f"hidden_{dim_name}"
        if hidden_key in data:
            return data[hidden_key]

        primary = data.get("personality", "")
        secondary = data.get("personality_secondary", "")
        primary_dims = PERSONALITY_DIMENSIONS.get(primary, {})
        secondary_dims = PERSONALITY_DIMENSIONS.get(secondary, {})

        if primary_dims and secondary_dims:
            pv = primary_dims.get(dim_name, 50)
            sv = secondary_dims.get(dim_name, 50)
            return int(pv * PERSONALITY_PRIMARY_WEIGHT + sv * PERSONALITY_SECONDARY_WEIGHT)
        elif primary_dims:
            return primary_dims.get(dim_name, 50)
        return 50

    # ── Core interface ──

    def respond(self, player_input: str, context: Optional[dict] = None) -> dict:
        """Return a state-driven reply."""
        zone = _pressure_zone(self.pressure)
        level = min(self.confession_level, 4)
        templates = _RESPONSES.get(level, _RESPONSES[0]).get(zone, _RESPONSES[0]["low"])

        idx = self._reply_index % len(templates)
        self._reply_index += 1
        reply = templates[idx]

        # Check for forbidden keyword leak at high confession
        secret = self._check_secret_leak(reply)

        self.memory.append({"role": "user", "content": player_input})
        self.memory.append({"role": "assistant", "content": reply})

        return {"reply": reply, "secret_triggered": secret}

    def respond_evidence(self, evidence_description: str, evidence_type: str = "unknown") -> dict:
        """Return a state-driven evidence reaction.

        Since the real engine doesn't pass the evidence name, we check the
        description against suspect knowledge to determine "relatedness".
        For testing simplicity, we treat all evidence as "related".
        """
        level = min(self.confession_level, 4)
        all_related = _EVIDENCE_RESPONSES.get(level, _EVIDENCE_RESPONSES[0])

        templates = all_related["related"]
        idx = self._reply_index % len(templates)
        self._reply_index += 1
        reply = templates[idx]

        secret = self._check_secret_leak(reply)

        self.memory.append({"role": "user", "content": f"[出示证据] {evidence_description}"})
        self.memory.append({"role": "assistant", "content": reply})

        return {
            "reply": reply,
            "secret_triggered": secret,
            "rebuttal": self.confession_level < 2 and self.deception_skill > 40,
            "rebuttal_believable": self.confession_level < 1 and self.deception_skill > 60,
        }

    def update_confession_progress(self) -> float:
        """Update progress bar based on current pressure zone's rate."""
        if self.confession_level >= 4:
            return 1.0
        zone = _pressure_zone(self.pressure)
        rate = CONFESSION_PROGRESS_RATE.get(zone, 0.02)
        self.confession_progress = min(1.0, self.confession_progress + rate)
        return self.confession_progress

    def check_confession_upgrade(self, has_evidence: bool = False) -> Optional[int]:
        """Check if upgrade conditions are met; auto-upgrade if enabled."""
        if self.confession_level >= 4:
            return None
        if not self._auto_upgrade:
            return None

        next_level = self.confession_level + 1
        threshold = CONFESSION_THRESHOLDS.get(self.confession_level, {})

        required_pressure = threshold.get("pressure", 100)
        if self.pressure < required_pressure:
            return None

        min_turns = threshold.get("min_turns", 0)
        if self.turn_count < min_turns:
            return None

        if threshold.get("requires_evidence", False) and not has_evidence:
            return None

        self.confession_level = next_level
        self.confession_progress = 0.0
        return next_level

    # ── Helpers ──

    def _check_secret_leak(self, reply: str) -> Optional[str]:
        """Check if reply contains forbidden keywords and confession level >= 3."""
        if self.confession_level < 3:
            return None
        forbidden = self._suspect_data.get("forbidden_to_reveal", [])
        for item in forbidden:
            if item in reply:
                return item
        return None
