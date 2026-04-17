"""
Star Knowledge Extractor - Extract structured astronomical data from emails/messages

Extracts star IDs, variable types, period values, amplitude values,
corrections, and topic classification using deterministic regex patterns.
"""
import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional


# Variable star type keywords and their canonical forms
VARIABLE_TYPE_PATTERNS = {
    # Eclipsing
    'EA': r'\bEA\b',
    'EB': r'\bEB\b',
    'EW': r'\bEW\b',
    'ELL': r'\bELL\b',
    # Pulsating
    'DSCT': r'\bDSCT\b|\bdelta\s*scuti\b|\bDelta\s*Sct\b|\bHADS\b',
    'RRAB': r'\bRRAB\b',
    'RRC': r'\bRRC\b',
    'RR Lyrae': r'\bRR\s*Lyr(?:ae)?\b',
    'DCEP': r'\bDCEP\b|\bCepheid\b',
    'GDOR': r'\bGDOR\b|\bgamma\s*Dor\b',
    'Mira': r'\bMira\b',
    'SR': r'\bSR[A-D]?\b(?![\w])',  # SR, SRA, SRB, SRC, SRD but not SRS followed by word chars
    'SRS': r'\bSRS\b',
    'LPV': r'\bLPV\b',
    'BCEP': r'\bBCEP\b|\bbeta\s*Cep\b',
    'SPB': r'\bSPB\b',
    # Rotating
    'ACV': r'\bACV\b|\balpha2?\s*CVn\b',
    'BY': r'\bBY\s*Dra?\b|\bBY\b',
    'RS': r'\bRS\s*CVn?\b|\bRS\b(?!\s*[\d])',
    'ROT': r'\bROT\b',
    # Eruptive
    'UV': r'\bUV\s*Cet?\b',
    'GCAS': r'\bGCAS\b',
    # Other
    'SB1': r'\bSB1\b',
    'SB2': r'\bSB2\b',
    'ORG': r'\bORG\b',
}

# Patterns indicating corrections/recommendations from expert
CORRECTION_INDICATORS = [
    r'should\s+be\b',
    r'change\s+(?:to|it)\b',
    r'wrong\b',
    r'instead\b',
    r'correct(?:ed|ion)?\b',
    r'mistake\b',
    r'messed\s+up\b',
    r'keep\s+\w+\s+but\b',
    r'add\s+(?:a\s+)?remark\b',
    r'check\s+the\b',
    r'should\s+not\b',
    r'shouldn\'t\b',
    r'is\s+not\s+(?:a|typical)\b',
    r'classification\s+(?:might|is)\s+(?:be\s+)?wrong\b',
    r'period\s+(?:is|should)\b',
    r'use\s+(?:the|this)\b',
    r'remove\b',
    r'(?:do|does)\s+not\s+(?:have|show|need)\b',
    r'uncertainty\s+box\b',
    r'not\s+typical\b',
]

# Expert email domains
EXPERT_DOMAINS = ['aavso.org']


@dataclass
class StarKnowledge:
    """Structured knowledge extracted from a single email/message"""
    star_ids: List[str] = field(default_factory=list)
    variable_types: List[str] = field(default_factory=list)
    period_values: List[float] = field(default_factory=list)
    amplitude_values: List[float] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)
    is_expert: bool = False
    topic: str = 'general'

    def to_dict(self) -> dict:
        return asdict(self)


def extract_star_ids(text: str) -> List[str]:
    """Extract GrAGVar star identifiers from text"""
    matches = re.findall(r'GrAGVar\d+', text, re.IGNORECASE)
    # Normalize to GrAGVar format
    normalized = set()
    for m in matches:
        # Fix case: GrAGVAr005 -> GrAGVar005
        num = re.search(r'\d+', m).group()
        normalized.add(f'GrAGVar{num}')
    return sorted(normalized)


def extract_variable_types(text: str) -> List[str]:
    """Extract variable star type classifications mentioned in text"""
    found = []
    for vtype, pattern in VARIABLE_TYPE_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            found.append(vtype)
    return found


def extract_period_values(text: str) -> List[float]:
    """Extract period values from text (in days)"""
    patterns = [
        # P = 0.567 d, P= 1.234 days, P=0.567d
        r'[Pp]\s*=\s*(\d+\.?\d*)\s*(?:d(?:ays?)?\.?|\b)',
        # period 0.567 d, period of 1.234 days
        r'[Pp]eriod(?:\s+(?:of|is|was))?\s+(\d+\.?\d*)\s*(?:d(?:ays?)?\.?|\b)',
        # periodo 0.567 giorni/d
        r'[Pp]eriodo\s+(?:di\s+)?(\d+\.?\d*)\s*(?:d|giorni)',
        # "con periodo (circa 12.8 d)"
        r'periodo\s*\(?\s*(?:circa\s+)?(\d+\.?\d*)\s*d',
    ]
    values = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            try:
                val = float(match.group(1))
                if 0.001 < val < 10000:  # Reasonable period range
                    values.add(val)
            except ValueError:
                pass
    return sorted(values)


def extract_amplitude_values(text: str) -> List[float]:
    """Extract amplitude values from text (in magnitudes)"""
    patterns = [
        # amplitude 0.5 mag, amplitude of 1.2 magnitudes
        r'[Aa]mplitud[eo]\s+(?:of\s+|di\s+)?(\d+\.?\d*)\s*(?:mag|magnitud)',
        # A = 0.5, A= 1.2
        r'\bA\s*=\s*(\d+\.?\d*)\s*(?:mag)?',
        # ampiezza 0.5
        r'[Aa]mpiezza\s+(?:di\s+)?(\d+\.?\d*)',
        # 0.5 mag amplitude
        r'(\d+\.?\d*)\s*mag(?:nitud[ei])?\s+(?:di\s+)?ampli',
    ]
    values = set()
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            try:
                val = float(match.group(1))
                if 0.001 < val < 15:  # Reasonable amplitude range
                    values.add(val)
            except ValueError:
                pass
    return sorted(values)


def extract_corrections(text: str) -> List[str]:
    """Extract sentences containing corrections/recommendations"""
    # Split text into sentences
    sentences = re.split(r'[.!?\n]+', text)
    corrections = []
    combined_pattern = '|'.join(CORRECTION_INDICATORS)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue
        if re.search(combined_pattern, sentence, re.IGNORECASE):
            # Limit sentence length
            if len(sentence) > 300:
                sentence = sentence[:297] + '...'
            corrections.append(sentence)
    return corrections


def classify_topic(text: str, corrections: List[str], variable_types: List[str]) -> str:
    """Classify the main topic of the message"""
    text_lower = text.lower()

    # Check for submission/naming topics
    if any(w in text_lower for w in ['submission', 'submit', 'reference', 'referenc', 'name should',
                                       'naming', 'designation', 'sottoposto', 'invio']):
        return 'submission'

    # Check for period-related discussion
    if any(w in text_lower for w in ['period', 'periodo', 'frequency', 'frequen', 'aliasing',
                                       'lomb-scargle', 'periodogram', 'phase fold']):
        return 'period'

    # Check for classification discussion
    if corrections and variable_types:
        return 'classification'

    if any(w in text_lower for w in ['classif', 'type should', 'tipo', 'variability type',
                                       'spectral type', 'classe spettrale']):
        return 'classification'

    # Check for amplitude discussion
    if any(w in text_lower for w in ['amplitude', 'ampiezza', 'magnitud']):
        return 'amplitude'

    # Check for data/catalog discussion
    if any(w in text_lower for w in ['tess', 'ztf', 'asas', 'gaia', 'catalog', 'catalogo',
                                       'data source', 'survey']):
        return 'data_sources'

    return 'general'


def is_expert_email(from_email: Optional[str] = None, from_name: Optional[str] = None) -> bool:
    """Check if sender is a recognized expert"""
    if from_email:
        for domain in EXPERT_DOMAINS:
            if domain in from_email.lower():
                return True
    if from_name:
        if 'otero' in from_name.lower():
            return True
    return False


def extract_knowledge(text: str, subject: str = '',
                      from_email: Optional[str] = None,
                      from_name: Optional[str] = None) -> StarKnowledge:
    """
    Extract all structured knowledge from a text (email body or Teams message).

    Args:
        text: Body text to analyze
        subject: Subject line (also searched for star IDs)
        from_email: Sender email address
        from_name: Sender display name

    Returns:
        StarKnowledge dataclass with extracted data
    """
    full_text = f"{subject}\n{text}" if subject else text

    star_ids = extract_star_ids(full_text)
    variable_types = extract_variable_types(full_text)
    period_values = extract_period_values(text)
    amplitude_values = extract_amplitude_values(text)
    corrections = extract_corrections(text)
    expert = is_expert_email(from_email, from_name)
    topic = classify_topic(text, corrections, variable_types)

    return StarKnowledge(
        star_ids=star_ids,
        variable_types=variable_types,
        period_values=period_values,
        amplitude_values=amplitude_values,
        corrections=corrections,
        is_expert=expert,
        topic=topic,
    )
