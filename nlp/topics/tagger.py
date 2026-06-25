import yaml
import re
from typing import Dict, List, Set, Tuple


class TopicTagger:
    """Rule-based keyword topic tagger (Phase 0 — unchanged)."""

    def __init__(self, taxonomy_path: str = 'config/taxonomy.yaml'):
        with open(taxonomy_path, 'r') as f:
            self.taxonomy = yaml.safe_load(f).get('categories', [])
            
        # Pre-compile regex for performance
        self._compiled_rules = {}
        for category in self.taxonomy:
            topic_id = category['id']
            keywords = category.get('keywords', [])
            # Create a regex that matches any of the keywords as whole words
            if keywords:
                # Escape keywords and join with OR, bounded by word boundaries
                pattern = r'\b(?:' + '|'.join(map(re.escape, keywords)) + r')\b'
                self._compiled_rules[topic_id] = re.compile(pattern, re.IGNORECASE)

    def extract_topics(self, text: str) -> list:
        """
        Scans text for keywords defined in the taxonomy.
        Returns a list of dicts: [{'topic_id': 'search_discovery', 'confidence': 0.8, 'method': 'rule'}]
        """
        found_topics = []
        if not text:
            return found_topics
            
        for topic_id, regex in self._compiled_rules.items():
            matches = regex.findall(text)
            if matches:
                # Basic confidence heuristic: more matches = higher confidence, capped at 1.0
                confidence = min(1.0, 0.4 + (len(matches) * 0.15))
                found_topics.append({
                    "topic_id": topic_id,
                    "confidence": round(confidence, 4),
                    "method": "rule"
                })
                
        return found_topics


# ==========================================================================
# Phase 2: Hierarchical Topic Tagger
# ==========================================================================

class HierarchicalTopicTagger:
    """
    Phase 2: Validates and normalises LLM-extracted topics/sub-topics
    against the taxonomy defined in config/taxonomy.yaml.

    Builds two lookup structures at init:
      - topic_id_to_label:  {topic_id: label}           e.g. 'ads_experience' -> 'Ads Experience'
      - label_to_topic_id:  {label_lower: topic_id}     e.g. 'ads experience' -> 'ads_experience'
      - subtopic_to_parent: {sub_lower: topic_id}       e.g. 'ad frequency' -> 'ads_experience'
    """

    def __init__(self, taxonomy_path: str = 'config/taxonomy.yaml'):
        with open(taxonomy_path, 'r') as f:
            categories = yaml.safe_load(f).get('categories', [])

        self.topic_id_to_label: Dict[str, str] = {}
        self.label_to_topic_id: Dict[str, str] = {}
        self.subtopic_to_parent: Dict[str, str] = {}  # subtopic_lower -> topic_id
        self.topic_subtopics: Dict[str, List[str]] = {}  # topic_id -> [subtopics]

        for cat in categories:
            topic_id = cat['id']
            label = cat['label']
            self.topic_id_to_label[topic_id] = label
            # Map both the label and the id for flexible LLM matching
            self.label_to_topic_id[label.lower()] = topic_id
            self.label_to_topic_id[topic_id] = topic_id  # also accept raw id

            subs = cat.get('subtopics', [])
            self.topic_subtopics[topic_id] = subs
            for sub in subs:
                self.subtopic_to_parent[sub.lower()] = topic_id

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_topic_id(self, raw_topic: str) -> str | None:
        """
        Resolve an LLM-returned topic string to a canonical topic_id.
        Accepts the display label ('Ads Experience'), the raw id ('ads_experience'),
        or minor variations (case-insensitive).
        """
        if not raw_topic:
            return None
        key = raw_topic.strip().lower()
        return self.label_to_topic_id.get(key)

    def validate_subtopic(self, subtopic: str, parent_topic_id: str) -> str | None:
        """
        Returns the canonical subtopic string if it belongs to the given
        parent topic, else None.
        """
        if not subtopic or not parent_topic_id:
            return None
        key = subtopic.strip().lower()
        if self.subtopic_to_parent.get(key) == parent_topic_id:
            # Return the canonical-cased version from taxonomy
            for canonical in self.topic_subtopics.get(parent_topic_id, []):
                if canonical.lower() == key:
                    return canonical
        return None

    def map_llm_extraction(self, llm_output: dict) -> dict:
        """
        Takes the raw dict from Phase 1's extract_issues_and_topics()
        and returns a validated/normalised copy with resolved topic_ids.

        Input keys:  topics, sub_topics, issues, user_intent, severity, product_area
        Output keys: topic_ids (list of str), sub_topics (validated list),
                     issues, user_intent, severity, product_area
        """
        raw_topics = llm_output.get('topics', [])
        raw_subs = llm_output.get('sub_topics', [])

        # Step 1: Resolve parent topic ids
        resolved_ids: List[str] = []
        for t in raw_topics:
            tid = self.resolve_topic_id(t)
            if tid and tid not in resolved_ids:
                resolved_ids.append(tid)

        # Step 2: Validate sub-topics against resolved parents
        validated_subs: List[str] = []
        for sub in raw_subs:
            for parent_id in resolved_ids:
                canonical = self.validate_subtopic(sub, parent_id)
                if canonical and canonical not in validated_subs:
                    validated_subs.append(canonical)
                    break  # matched to one parent, move on

        return {
            "topic_ids": resolved_ids,
            "sub_topics": validated_subs,
            "issues": llm_output.get('issues', []),
            "user_intent": llm_output.get('user_intent'),
            "severity": llm_output.get('severity'),
            "product_area": llm_output.get('product_area'),
        }

    def get_subtopics_for(self, topic_id: str) -> List[str]:
        """Returns the defined subtopics for a given topic_id."""
        return self.topic_subtopics.get(topic_id, [])
