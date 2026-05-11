"""
text_extractor.py

Extracts targeted sections from a research paper PDF using pdfplumber.
Target sections: Abstract, Introduction, Conclusion, Discussion, Limitations, Future Work.

Does NOT extract: Related Work, Methodology, Experiments, Results tables.
Total output is capped at 8000 chars to stay within context limits.
"""
import io
import re
import logging

import pdfplumber

logger = logging.getLogger(__name__)

TARGET_SECTIONS = [
    "abstract",
    "introduction",
    "conclusion",
    "conclusions",
    "discussion",
    "limitations",
    "limitation",
    "future work",
    "future directions",
    "broader impact",
]

STOP_SECTIONS = [
    "related work",
    "background",
    "method",
    "methods",
    "approach",
    "methodology",
    "experiments",
    "experimental",
    "evaluation",
    "results",
    "ablation",
    "appendix",
    "references",
    "acknowledgements",
    "acknowledgments",
]

SECTION_CHAR_CAP = 2500
TOTAL_CHAR_CAP   = 8000


def _is_section_heading(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or len(stripped) > 80 or stripped.endswith("."):
        return None

    # Remove leading section numbers: "1.", "2.1", "I.", "A."
    cleaned = re.sub(r"^[\dIVXA-Z]+[.\s]+", "", stripped).strip().lower()

    for section in TARGET_SECTIONS + STOP_SECTIONS:
        if cleaned == section or cleaned.startswith(section + " "):
            return section

    return None


def extract_sections(pdf_bytes: bytes) -> dict[str, str]:
    """
    Extracts target sections from a PDF.
    Returns only sections that were found — missing sections are absent, never empty strings.
    Never raises — returns {} on any failure.
    """
    sections: dict[str, str] = {}
    current_section = None
    current_text: list[str] = []
    total_chars = 0

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text(layout=True) or ""
                lines = text.split("\n")

                for line in lines:
                    heading = _is_section_heading(line)

                    if heading is not None:
                        if current_section and current_text:
                            section_text = " ".join(current_text).strip()[:SECTION_CHAR_CAP]
                            sections[current_section] = section_text
                            total_chars += len(section_text)
                            current_text = []

                        if total_chars >= TOTAL_CHAR_CAP:
                            logger.info("[TextExtractor] Total char cap reached — stopping")
                            break

                        if heading in TARGET_SECTIONS:
                            current_section = heading
                        elif heading in STOP_SECTIONS:
                            current_section = None

                    elif current_section:
                        if re.match(r"^\s*\d+\s*$", line):
                            continue
                        current_text.append(line.strip())

                if total_chars >= TOTAL_CHAR_CAP:
                    break

            if current_section and current_text:
                section_text = " ".join(current_text).strip()[:SECTION_CHAR_CAP]
                sections[current_section] = section_text

    except Exception as e:
        logger.error(f"[TextExtractor] Section extraction failed: {e}")

    found = list(sections.keys())
    total = sum(len(v) for v in sections.values())
    logger.info(f"[TextExtractor] Extracted sections: {found} ({total} chars)")
    return sections


def build_context_text(abstract: str, sections: dict[str, str]) -> str:
    """
    Assembles extracted sections into a single context string for LLM prompts.
    Priority: abstract → introduction → conclusion/discussion → limitations/future work.
    """
    parts = []

    if abstract:
        parts.append(f"=== ABSTRACT ===\n{abstract.strip()}")

    priority_order = [
        "introduction",
        "conclusion", "conclusions", "discussion",
        "limitations", "limitation",
        "future work", "future directions", "broader impact",
    ]

    seen: set[str] = set()
    for key in priority_order:
        if key in sections and key not in seen:
            label = key.upper().replace(" ", "_")
            parts.append(f"=== {label} ===\n{sections[key]}")
            seen.add(key)

    return "\n\n".join(parts)[:TOTAL_CHAR_CAP]
