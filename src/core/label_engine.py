# src/core/label_engine.py
"""
LabelEngine — detects product quality seals via keyword matching and INCI inference.

Three detection methods:
  1. Keyword matching: scans text fields for seal keywords from YAML config (word-boundary).
  2. Image element scanning: matches keywords against img alt/title/filename strings.
  3. INCI inference: infers seals by checking ingredient lists against prohibited lists.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Default config paths (relative to project root)
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SEALS_PATH = _PROJECT_ROOT / "config" / "labels" / "seals.yaml"
_DEFAULT_SILICONES_PATH = _PROJECT_ROOT / "config" / "labels" / "silicones.yaml"
_DEFAULT_SURFACTANTS_PATH = _PROJECT_ROOT / "config" / "labels" / "surfactants.yaml"

# Parabens that indicate a product is NOT paraben-free
PARABEN_INDICATORS = [
    "methylparaben",
    "ethylparaben",
    "propylparaben",
    "butylparaben",
    "isobutylparaben",
    "isopropylparaben",
    "benzylparaben",
    "sodium methylparaben",
    "sodium propylparaben",
    "sodium butylparaben",
    "calcium paraben",
    "potassium paraben",
]

# Petrolatum / petroleum derivatives
PETROLATUM_INDICATORS = [
    "petrolatum",
    "paraffinum liquidum",
    "mineral oil",
    "cera microcristallina",
    "microcrystalline wax",
    "ceresin",
    "ozokerite",
    "paraffin",
    "petroleum jelly",
    "vaseline",
]

# Synthetic dye indicators (CI numbers + common dyes)
DYE_INDICATORS = [
    "ci 1", "ci 2", "ci 4", "ci 5", "ci 6", "ci 7",
    "fd&c", "d&c",
    "red no.", "yellow no.", "blue no.", "green no.",
    "red dye", "yellow dye", "blue dye",
    "tartrazine",
    "amaranth",
    "erythrosine",
    "brilliant blue",
]


# ---------------------------------------------------------------------------
# Config loaders
# ---------------------------------------------------------------------------

def load_seal_keywords(path: Path | str) -> dict[str, list[str]]:
    """Load seals.yaml and return dict mapping seal_name -> list of lowercased keywords."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    result: dict[str, list[str]] = {}
    for seal_name, seal_data in data["seals"].items():
        result[seal_name] = [kw.lower() for kw in seal_data["keywords"]]
    return result


def load_prohibited_list(path: Path | str, key: str) -> list[str]:
    """Load a YAML file and return the lowercased list under the given key."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return [item.lower() for item in data[key]]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LabelEvidence:
    """Evidence for a single seal detection or inference."""
    field_name: str           # e.g. "label:sulfate_free"
    extraction_method: str    # "text_keyword", "html_img_element", or "inci_inference"
    raw_source_text: str      # matched text or analysis summary
    evidence_locator: str     # field where evidence was found


@dataclass
class LabelResult:
    """Result of label detection for a single product."""
    detected: list[str]                     # seals found via keyword match
    inferred: list[str]                     # seals inferred from INCI analysis
    confidence: float                       # 0.0-1.0
    sources: list[str]                      # "official_text", "html_img_element", "inci_analysis"
    manually_verified: bool = False         # default False
    manually_overridden: bool = False       # default False
    _evidence: list[LabelEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable dict (excludes internal _evidence)."""
        return {
            "detected": self.detected,
            "inferred": self.inferred,
            "confidence": self.confidence,
            "sources": self.sources,
            "manually_verified": self.manually_verified,
            "manually_overridden": self.manually_overridden,
        }

    def evidence_entries(self) -> list[dict[str, str]]:
        """Return list of evidence dicts for the product_evidence table."""
        return [
            {
                "field_name": e.field_name,
                "extraction_method": e.extraction_method,
                "raw_source_text": e.raw_source_text,
                "evidence_locator": e.evidence_locator,
            }
            for e in self._evidence
        ]


# ---------------------------------------------------------------------------
# LabelEngine
# ---------------------------------------------------------------------------

class LabelEngine:
    """Detects quality seals via keyword matching, image scanning, and INCI inference."""

    def __init__(
        self,
        seals_path: Path | str | None = None,
        silicones_path: Path | str | None = None,
        surfactants_path: Path | str | None = None,
    ) -> None:
        seals_path = seals_path or _DEFAULT_SEALS_PATH
        silicones_path = silicones_path or _DEFAULT_SILICONES_PATH
        surfactants_path = surfactants_path or _DEFAULT_SURFACTANTS_PATH

        self.seal_keywords: dict[str, list[str]] = load_seal_keywords(seals_path)
        self.silicones: list[str] = load_prohibited_list(silicones_path, "silicones")
        self.low_poo_prohibited: list[str] = load_prohibited_list(
            surfactants_path, "low_poo_prohibited"
        )
        self.no_poo_prohibited: list[str] = load_prohibited_list(
            surfactants_path, "no_poo_prohibited"
        )

        # Pre-compile regex patterns for each keyword (word-boundary matching)
        self._seal_patterns: dict[str, list[tuple[str, re.Pattern]]] = {}
        for seal_name, keywords in self.seal_keywords.items():
            patterns = []
            for kw in keywords:
                pattern = re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE)
                patterns.append((kw, pattern))
            self._seal_patterns[seal_name] = patterns

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        description: str | None = None,
        product_name: str | None = None,
        benefits_claims: list[str] | None = None,
        usage_instructions: str | None = None,
        inci_ingredients: list[str] | None = None,
        image_texts: list[str] | None = None,
    ) -> LabelResult:
        """Run keyword detection + image scanning + INCI inference and return a LabelResult."""
        detected: list[str] = []
        inferred: list[str] = []
        sources: list[str] = []
        evidence: list[LabelEvidence] = []

        # --- Method 1: Keyword matching (text fields) ---
        text_fields = self._build_text_fields(
            description=description,
            product_name=product_name,
            benefits_claims=benefits_claims,
            usage_instructions=usage_instructions,
        )

        for seal_name, patterns in self._seal_patterns.items():
            matched = False
            for field_name, text in text_fields:
                for kw, pattern in patterns:
                    if pattern.search(text):
                        detected.append(seal_name)
                        if "official_text" not in sources:
                            sources.append("official_text")
                        evidence.append(
                            LabelEvidence(
                                field_name=f"label:{seal_name}",
                                extraction_method="text_keyword",
                                raw_source_text=kw,
                                evidence_locator=field_name,
                            )
                        )
                        matched = True
                        break  # first match per seal
                if matched:
                    break  # don't scan more fields for this seal

        # --- Method 2: Image element scanning ---
        if image_texts:
            for seal_name, patterns in self._seal_patterns.items():
                if seal_name in detected:
                    continue  # already detected via text
                for img_text in image_texts:
                    found = False
                    for kw, pattern in patterns:
                        if pattern.search(img_text):
                            detected.append(seal_name)
                            if "html_img_element" not in sources:
                                sources.append("html_img_element")
                            evidence.append(
                                LabelEvidence(
                                    field_name=f"label:{seal_name}",
                                    extraction_method="html_img_element",
                                    raw_source_text=f"{kw} (in: {img_text[:100]})",
                                    evidence_locator="img_alt_title_filename",
                                )
                            )
                            found = True
                            break
                    if found:
                        break

        # --- Method 3: INCI inference ---
        if inci_ingredients is not None:
            inci_lower = [ing.lower() for ing in inci_ingredients]

            has_silicone = self._has_prohibited(inci_lower, self.silicones)
            has_low_poo_prohibited = self._has_prohibited(
                inci_lower, self.low_poo_prohibited
            )
            has_no_poo_prohibited = self._has_prohibited(
                inci_lower, self.no_poo_prohibited
            )
            has_paraben = self._has_prohibited(inci_lower, PARABEN_INDICATORS)
            has_petrolatum = self._has_prohibited(inci_lower, PETROLATUM_INDICATORS)
            has_dye = self._has_dye(inci_lower)

            # Infer silicone_free
            if not has_silicone and "silicone_free" not in detected:
                inferred.append("silicone_free")
                evidence.append(
                    LabelEvidence(
                        field_name="label:silicone_free",
                        extraction_method="inci_inference",
                        raw_source_text="no silicone found in INCI list",
                        evidence_locator="inci_ingredients",
                    )
                )

            # Infer sulfate_free from INCI
            if not has_low_poo_prohibited and "sulfate_free" not in detected:
                inferred.append("sulfate_free")
                evidence.append(
                    LabelEvidence(
                        field_name="label:sulfate_free",
                        extraction_method="inci_inference",
                        raw_source_text="no harsh sulfates found in INCI list",
                        evidence_locator="inci_ingredients",
                    )
                )

            # Infer paraben_free from INCI
            if not has_paraben and "paraben_free" not in detected:
                inferred.append("paraben_free")
                evidence.append(
                    LabelEvidence(
                        field_name="label:paraben_free",
                        extraction_method="inci_inference",
                        raw_source_text="no parabens found in INCI list",
                        evidence_locator="inci_ingredients",
                    )
                )

            # Infer petrolatum_free from INCI
            if not has_petrolatum and "petrolatum_free" not in detected:
                inferred.append("petrolatum_free")
                evidence.append(
                    LabelEvidence(
                        field_name="label:petrolatum_free",
                        extraction_method="inci_inference",
                        raw_source_text="no petrolatum/petroleum derivatives found in INCI list",
                        evidence_locator="inci_ingredients",
                    )
                )

            # Infer dye_free from INCI
            if not has_dye and "dye_free" not in detected:
                inferred.append("dye_free")
                evidence.append(
                    LabelEvidence(
                        field_name="label:dye_free",
                        extraction_method="inci_inference",
                        raw_source_text="no synthetic dyes/colorants found in INCI list",
                        evidence_locator="inci_ingredients",
                    )
                )

            # Infer low_poo
            if not has_low_poo_prohibited and "low_poo" not in detected:
                inferred.append("low_poo")
                evidence.append(
                    LabelEvidence(
                        field_name="label:low_poo",
                        extraction_method="inci_inference",
                        raw_source_text="no harsh sulfates found in INCI list",
                        evidence_locator="inci_ingredients",
                    )
                )

            # Infer no_poo: no prohibited surfactants AND no silicones
            if (
                not has_no_poo_prohibited
                and not has_silicone
                and "no_poo" not in detected
            ):
                inferred.append("no_poo")
                evidence.append(
                    LabelEvidence(
                        field_name="label:no_poo",
                        extraction_method="inci_inference",
                        raw_source_text="no prohibited surfactants or silicones in INCI list",
                        evidence_locator="inci_ingredients",
                    )
                )

            if inferred and "inci_analysis" not in sources:
                sources.append("inci_analysis")

        # --- Confidence scoring ---
        confidence = self._compute_confidence(detected, inferred)

        return LabelResult(
            detected=detected,
            inferred=inferred,
            confidence=confidence,
            sources=sources,
            manually_verified=False,
            manually_overridden=False,
            _evidence=evidence,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_text_fields(
        description: str | None,
        product_name: str | None,
        benefits_claims: list[str] | None,
        usage_instructions: str | None,
    ) -> list[tuple[str, str]]:
        """Build list of (field_name, text) for keyword scanning."""
        fields: list[tuple[str, str]] = []
        if description is not None:
            fields.append(("description", description))
        if product_name is not None:
            fields.append(("product_name", product_name))
        if benefits_claims is not None:
            fields.append(("benefits_claims", " ".join(benefits_claims)))
        if usage_instructions is not None:
            fields.append(("usage_instructions", usage_instructions))
        return fields

    @staticmethod
    def _has_prohibited(inci_lower: list[str], prohibited: list[str]) -> bool:
        """Check if any prohibited name appears as substring in any ingredient."""
        for ingredient in inci_lower:
            for name in prohibited:
                if name in ingredient:
                    return True
        return False

    @staticmethod
    def _has_dye(inci_lower: list[str]) -> bool:
        """Check if any CI (colour index) number or known dye is in the INCI list."""
        for ingredient in inci_lower:
            for indicator in DYE_INDICATORS:
                if indicator in ingredient:
                    return True
            # Also check for CI + digits pattern (e.g. "ci 19140", "ci 77891")
            if re.search(r'\bci\s*\d{4,5}\b', ingredient):
                return True
        return False

    @staticmethod
    def _compute_confidence(detected: list[str], inferred: list[str]) -> float:
        """
        Confidence scoring:
            0.0 — no seals found
            0.5 — only inferred (no text confirmation)
            0.8 — only detected (text keywords)
            0.9 — both detected AND inferred have seals
            1.0 — manually_verified = true (not set by engine)
        """
        has_detected = len(detected) > 0
        has_inferred = len(inferred) > 0

        if has_detected and has_inferred:
            return 0.9
        elif has_detected:
            return 0.8
        elif has_inferred:
            return 0.5
        else:
            return 0.0


# ---------------------------------------------------------------------------
# HTML image seal text extractor (used during scrape, not label detection)
# ---------------------------------------------------------------------------

def extract_seal_image_texts(html: str) -> list[str]:
    """Extract text from <img> alt, title, and filename that may indicate quality seals.

    Returns a list of strings suitable for passing to LabelEngine.detect(image_texts=...).
    Only returns texts that look potentially seal-related (short, descriptive).
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    soup = BeautifulSoup(html, "lxml")
    texts: list[str] = []
    seen: set[str] = set()

    for img in soup.find_all("img"):
        # Collect alt text
        alt = (img.get("alt") or "").strip()
        if alt and len(alt) < 200 and alt.lower() not in seen:
            seen.add(alt.lower())
            texts.append(alt)

        # Collect title text
        title = (img.get("title") or "").strip()
        if title and len(title) < 200 and title.lower() not in seen:
            seen.add(title.lower())
            texts.append(title)

        # Extract filename from src/data-src
        src = img.get("src") or img.get("data-src") or ""
        if src:
            # Get filename without extension
            filename = src.rsplit("/", 1)[-1].rsplit(".", 1)[0] if "/" in src else src
            # Clean common patterns: replace hyphens/underscores with spaces
            filename_clean = filename.replace("-", " ").replace("_", " ").strip()
            if filename_clean and len(filename_clean) < 200 and filename_clean.lower() not in seen:
                seen.add(filename_clean.lower())
                texts.append(filename_clean)

    return texts
