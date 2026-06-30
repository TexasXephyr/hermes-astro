"""
Pluggable chart synthesis engine.
Rules-based (default) and LLM-based providers.
Stdlib only.
"""
import json
import os
import urllib.request
import urllib.error

# ------------------------------------------------------------------
# Sign names for display

SIGN_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]

# ------------------------------------------------------------------
# Abstract base

class SynthesisProvider:
    """Abstract base for chart interpretation generators."""
    def generate(self, chart_analysis: dict) -> str:
        raise NotImplementedError


# ------------------------------------------------------------------
# Rules-based provider

class RulesProvider(SynthesisProvider):
    """
    Default cookbook astrology from structured data.
    No external calls. Factual, not mystical.
    """

    def generate(self, chart_analysis: dict) -> str:
        parts = []
        parts.append(self._overview(chart_analysis))
        parts.append(self._dignities(chart_analysis.get("dignities", [])))
        parts.append(self._patterns(chart_analysis.get("patterns", [])))
        parts.append(self._houses(chart_analysis.get("house_emphasis", {})))
        parts.append(self._balance(chart_analysis))
        return "\n\n".join(p for p in parts if p)

    def _overview(self, analysis: dict) -> str:
        dignities = analysis.get("dignities", [])
        bodies = [d["body"] for d in dignities]
        return f"This chart contains {len(bodies)} planetary bodies. The following sections summarize essential dignity, geometric patterns, house concentration, and elemental balance."

    def _dignities(self, dignities: list) -> str:
        if not dignities:
            return ""
        lines = ["Dignities and Strengths:"]
        strong = []
        weak = []
        neutral = []
        for d in dignities:
            body = d["body"]
            sign = SIGN_NAMES[d.get("sign", 0)] if "sign" in d else ""
            if not sign:
                # try to recover from chart_analysis if available; not critical
                sign = ""
            parts = []
            if d.get("domicile"):
                parts.append("is in its domicile (very strong)")
            elif d.get("exaltation"):
                parts.append("is exalted (strong)")
            elif d.get("detriment"):
                parts.append("is in detriment (weakened)")
            elif d.get("fall"):
                parts.append("is in fall (weakened)")
            else:
                parts.append("has no essential dignity or debility")

            if d.get("retrograde"):
                parts.append("and is retrograde")
            else:
                parts.append("and is direct")

            accidental = d.get("accidental", "weak")
            parts.append(f"in an {accidental} house")

            line = f"  • {body} {', '.join(parts)}. Score: {d.get('score', 0)}."
            score = d.get("score", 0)
            if score >= 5:
                strong.append(line)
            elif score <= -3:
                weak.append(line)
            else:
                neutral.append(line)

        for label, group in [("Strong", strong), ("Weakened", weak), ("Moderate", neutral)]:
            if group:
                lines.append(f"  {label}:")
                lines.extend(group)
        return "\n".join(lines)

    def _patterns(self, patterns: list) -> str:
        if not patterns:
            return "No major geometric patterns (grand trine, T-square, stellium, etc.) were detected."
        lines = ["Detected Patterns:"]
        for p in patterns:
            ptype = p.get("type", "Pattern")
            bodies = ", ".join(p.get("bodies", []))
            extra = ""
            if ptype == "Stellium":
                basis = p.get("basis", "")
                if basis == "house":
                    extra = f" concentrated in house {p.get('house')}"
                elif basis == "sign":
                    extra = f" concentrated in {SIGN_NAMES[p.get('sign', 0)]}"
            elif ptype in ("T-Square", "Yod"):
                extra = f" with apex {p.get('apex', '')}"
            elif ptype == "Kite":
                extra = f" with apex {p.get('apex', '')}"
            elif ptype == "Grand Trine":
                extra = f" in {p.get('element', '')}"
            lines.append(f"  • {ptype}: {bodies}{extra}.")
        return "\n".join(lines)

    def _houses(self, house_emphasis: dict) -> str:
        if not house_emphasis:
            return ""
        lines = ["House Emphasis:"]
        sorted_houses = sorted(house_emphasis.items(), key=lambda kv: -kv[1])
        for house, count in sorted_houses:
            if count >= 3:
                lines.append(f"  • House {house} contains {count} bodies — a strong concentration.")
            elif count == 2:
                lines.append(f"  • House {house} contains {count} bodies — notable focus.")
            else:
                lines.append(f"  • House {house} contains {count} body(s).")
        return "\n".join(lines)

    def _balance(self, analysis: dict) -> str:
        eb = analysis.get("element_balance", {})
        mb = analysis.get("modality_balance", {})
        lines = ["Elemental and Modality Balance:"]
        if eb:
            total = sum(eb.values())
            elems = []
            for el, count in sorted(eb.items(), key=lambda kv: -kv[1]):
                pct = round(count / total * 100) if total else 0
                elems.append(f"{el}: {count} ({pct}%)")
            lines.append("  Elements — " + ", ".join(elems) + ".")
            dominant = max(eb, key=eb.get)
            lines.append(f"  The dominant element is {dominant}, indicating a corresponding psychological emphasis.")
        if mb:
            total = sum(mb.values())
            mods = []
            for mod, count in sorted(mb.items(), key=lambda kv: -kv[1]):
                pct = round(count / total * 100) if total else 0
                mods.append(f"{mod}: {count} ({pct}%)")
            lines.append("  Modalities — " + ", ".join(mods) + ".")
            dominant = max(mb, key=mb.get)
            lines.append(f"  The dominant modality is {dominant}, suggesting a corresponding mode of action.")
        return "\n".join(lines)


# ------------------------------------------------------------------
# LLM-based provider

class LLMProvider(SynthesisProvider):
    """
    Optional provider that sends structured chart analysis to an
    OpenAI-compatible endpoint (default Ollama on localhost).
    Falls back to rules-based message if the endpoint is unreachable.
    """

    SYSTEM_PROMPT = (
        "You are an astrology synthesis assistant. "
        "You receive structured chart analysis data (dignities, patterns, house emphasis, element balance). "
        "Write a concise, factual natal chart interpretation. Avoid mystical language; describe what the data means."
    )

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        base = self.config.get("endpoint", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        if base.endswith("/v1"):
            self.endpoint = base + "/chat/completions"
        else:
            self.endpoint = base + "/v1/chat/completions"
        self.model = self.config.get("model", "llama3.1")
        self.api_key = self.config.get("api_key", os.getenv("OLLAMA_API_KEY", "").strip('"'))
        self.temperature = self.config.get("temperature", 0.7)
        self.timeout = self.config.get("timeout", 15)

    def generate(self, chart_analysis: dict) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(chart_analysis, indent=2)},
            ],
            "temperature": self.temperature,
        }
        req_body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            self.endpoint,
            data=req_body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content", "")
                # Some APIs return content directly in choices[0]
                if choices and "content" in choices[0]:
                    return choices[0]["content"]
                return "LLM returned an unexpected format. Use rules-based interpretation."
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ConnectionError) as e:
            return f"LLM unavailable ({type(e).__name__}). Use rules-based interpretation."
        except Exception as e:
            return f"LLM unavailable ({type(e).__name__}). Use rules-based interpretation."


# ------------------------------------------------------------------
# Factory

def get_provider(config: dict) -> SynthesisProvider:
    """Return a SynthesisProvider based on config dict."""
    if config.get("provider") == "llm":
        return LLMProvider(config.get("llm_config", {}))
    return RulesProvider()
