"""
Expert Validation Service - Generate validation rules from expert email corpus

Analyzes the star index to extract patterns from Otero's corrections,
building experience-based validation rules that supplement hardcoded ones.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

KB_DATA_DIR = Path('/var/www/astrogen/kb_data')
EXPERT_RULES_PATH = KB_DATA_DIR / 'expert_rules.json'


def build_expert_rules() -> Dict:
    """
    Analyze star index to build experience-based validation rules.

    Groups expert corrections by variable type to find common patterns.
    Returns structured rules that can supplement hardcoded validation.
    """
    from agata.kb.services.star_index import load_star_index

    index = load_star_index()
    if not index:
        logger.warning("Star index empty, cannot build expert rules")
        return {}

    # Collect corrections grouped by variable type
    corrections_by_type = defaultdict(list)
    all_corrections = []
    type_stats = defaultdict(lambda: {'stars': 0, 'expert_reviews': 0, 'corrections': 0})

    for star_id, entry in index.items():
        types = entry.get('variable_types_discussed', [])
        corrections = entry.get('corrections', [])
        expert_corrections = [c for c in corrections if c.get('is_expert')]

        for vtype in types:
            type_stats[vtype]['stars'] += 1
            if entry.get('expert_emails'):
                type_stats[vtype]['expert_reviews'] += 1
            for c in expert_corrections:
                corrections_by_type[vtype].append({
                    'text': c['text'],
                    'star_id': star_id,
                    'date': c.get('date', ''),
                })
                type_stats[vtype]['corrections'] += 1

        all_corrections.extend(expert_corrections)

    # Build rules per type
    rules = {
        'generated_at': None,
        'total_stars': len(index),
        'total_expert_corrections': len(all_corrections),
        'type_rules': {},
        'common_warnings': [],
    }

    from datetime import datetime
    rules['generated_at'] = datetime.now().isoformat()

    # Extract common warnings from correction text patterns
    common_patterns = _find_common_patterns(all_corrections)
    rules['common_warnings'] = common_patterns

    # Per-type rules
    for vtype, corrections in corrections_by_type.items():
        stats = type_stats[vtype]
        type_rule = {
            'type': vtype,
            'total_stars_analyzed': stats['stars'],
            'expert_reviews': stats['expert_reviews'],
            'total_corrections': stats['corrections'],
            'common_issues': _summarize_corrections(corrections),
            'example_corrections': [
                {'text': c['text'], 'star': c['star_id']}
                for c in corrections[:5]
            ],
        }
        rules['type_rules'][vtype] = type_rule

    # Save to disk
    with open(EXPERT_RULES_PATH, 'w', encoding='utf-8') as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)

    logger.info(f"Expert rules built: {len(rules['type_rules'])} types, "
                f"{len(all_corrections)} corrections analyzed")
    print(f"Expert rules saved to: {EXPERT_RULES_PATH}")
    print(f"  Types covered: {len(rules['type_rules'])}")
    print(f"  Total corrections analyzed: {len(all_corrections)}")

    return rules


def _find_common_patterns(corrections: List[Dict]) -> List[Dict]:
    """Find frequently occurring correction themes"""
    import re

    themes = {
        'reference_errors': {
            'pattern': r'reference|referenc|citation|bibcode',
            'count': 0,
            'warning': 'Verifica accuratamente i riferimenti bibliografici (bibcode, URL). Errori frequenti nelle reference.',
            'severity': 'medium',
        },
        'period_doubling': {
            'pattern': r'half|double|doppio|metà|twice|raddoppia',
            'count': 0,
            'warning': 'Il periodo potrebbe essere il doppio o la meta di quello reale. Verifica con il phase plot.',
            'severity': 'high',
        },
        'classification_uncertainty': {
            'pattern': r'uncertain|incert|might be wrong|classificat|check.*box|dubbio',
            'count': 0,
            'warning': 'La classificazione del tipo variabile potrebbe essere incerta. Considera di selezionare il flag di incertezza.',
            'severity': 'medium',
        },
        'spectral_type_source': {
            'pattern': r'spectral type|classe spettrale|skiff|original reference',
            'count': 0,
            'warning': 'Per il tipo spettrale, citare sempre la referenza originale, non compilazioni secondarie (es. Skiff).',
            'severity': 'medium',
        },
        'naming_convention': {
            'pattern': r'name should|designation|naming|nome|TIC\s|AAVSO\s*ID',
            'count': 0,
            'warning': 'Verifica la naming convention: usare TIC ID come nome primario quando disponibile.',
            'severity': 'low',
        },
        'contamination': {
            'pattern': r'contaminat|blend|neighbor|vicin|TPF',
            'count': 0,
            'warning': 'Verifica contaminazione da stelle vicine (check TPF/target pixel file).',
            'severity': 'high',
        },
        'amplitude_measurement': {
            'pattern': r'amplitude|ampiezza|magnitud.*wrong|magnitud.*correct',
            'count': 0,
            'warning': 'Ricontrolla la misurazione dell\'ampiezza: deve essere peak-to-peak nella banda corretta.',
            'severity': 'medium',
        },
    }

    for c in corrections:
        text = c.get('text', '').lower()
        for theme_key, theme in themes.items():
            if re.search(theme['pattern'], text, re.IGNORECASE):
                theme['count'] += 1

    # Return themes with at least 2 occurrences, sorted by count
    result = []
    for theme_key, theme in sorted(themes.items(), key=lambda x: -x[1]['count']):
        if theme['count'] >= 2:
            result.append({
                'theme': theme_key,
                'occurrences': theme['count'],
                'warning': theme['warning'],
                'severity': theme['severity'],
            })

    return result


def _summarize_corrections(corrections: List[Dict]) -> List[str]:
    """Extract unique correction themes for a variable type"""
    seen = set()
    summaries = []
    for c in corrections:
        text = c['text'].strip()
        # Deduplicate similar corrections
        key = text[:50].lower()
        if key not in seen:
            seen.add(key)
            summaries.append(text)
    return summaries[:10]


def load_expert_rules() -> Dict:
    """Load expert rules from disk. Returns empty dict if not found."""
    if EXPERT_RULES_PATH.exists():
        with open(EXPERT_RULES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def get_expert_warnings(variable_type: str, star_id: Optional[str] = None) -> List[Dict]:
    """
    Get expert-derived warnings for a variable type and optional specific star.

    Args:
        variable_type: Variable star type (e.g., 'EA', 'DSCT', 'RR Lyrae')
        star_id: Optional specific star ID (e.g., 'GrAGVar049')

    Returns:
        List of warning dicts with 'text', 'severity', 'source' keys
    """
    rules = load_expert_rules()
    if not rules:
        return []

    warnings = []

    # Common warnings (apply to all types)
    for w in rules.get('common_warnings', []):
        if w.get('occurrences', 0) >= 3:  # Only show if frequent enough
            warnings.append({
                'text': w['warning'],
                'severity': w['severity'],
                'source': 'expert_pattern',
                'occurrences': w['occurrences'],
            })

    # Type-specific warnings
    type_rule = rules.get('type_rules', {}).get(variable_type, {})
    if type_rule:
        for issue in type_rule.get('common_issues', [])[:5]:
            warnings.append({
                'text': issue,
                'severity': 'medium',
                'source': 'expert_type_correction',
                'type': variable_type,
            })

    # Star-specific warnings (from star index directly)
    if star_id:
        from agata.kb.services.star_index import get_star_context
        context = get_star_context(star_id)
        if context:
            expert_corrections = [c for c in context.get('corrections', []) if c.get('is_expert')]
            for c in expert_corrections[:5]:
                warnings.append({
                    'text': c['text'],
                    'severity': 'high',
                    'source': 'expert_star_specific',
                    'from': c.get('from', ''),
                    'date': c.get('date', ''),
                })

    return warnings
