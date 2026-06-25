"""
aggregation/clustering.py

Phase 6: Issue Clustering.
Groups similar issues using keyword-overlap (Jaccard similarity)
to identify systemic problem clusters. Pure-Python, no sklearn needed.
"""

from collections import Counter, defaultdict
from typing import List, Dict, Any, Set
import re


# Common English stop words to exclude from similarity comparison
_STOP_WORDS = frozenset(
    "the and a of to is in it i this my app for with on are but so have not too they "
    "that was had been its an or at as from by be his her their you your we our "
    "can will just don should now very also more most".split()
)


def _tokenize(text: str) -> Set[str]:
    """Tokenize issue text into a set of meaningful keywords."""
    tokens = set(re.findall(r'\b[a-z]{3,}\b', text.lower()))
    return tokens - _STOP_WORDS


def _jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0


class IssueClusterer:
    """
    Phase 6: Groups similar issues into clusters using keyword overlap.
    Uses a simple agglomerative approach: start with each unique issue as its
    own cluster, then merge clusters whose representative keywords overlap
    above a similarity threshold.
    """

    def __init__(self, similarity_threshold: float = 0.25, min_cluster_size: int = 2):
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size

    def cluster_issues(self, reviews: List[Dict]) -> Dict[str, Any]:
        """
        Cluster similar issues from review data to identify systemic problems.

        Args:
            reviews: List of review dicts, each with an 'issues' key and optionally 'sentiment'.

        Returns:
            {
                "clusters": [
                    {
                        "cluster_id": 0,
                        "issues": ["premium popups", "excessive ads", "ad frequency"],
                        "volume": 120,
                        "representative_issue": "excessive ads",
                        "sentiment_distribution": {"NEGATIVE": 90, "NEUTRAL": 20, "POSITIVE": 10}
                    },
                    ...
                ],
                "total_issues_clustered": 500,
                "noise_issues": 15
            }
        """
        # Step 1: Collect all issue texts with their review metadata
        issue_entries = []  # (issue_text, sentiment)
        for review in reviews:
            issues = review.get('issues') or []
            if isinstance(issues, str):
                issues = [issues]
            sentiment = (review.get('sentiment') or 'NEUTRAL').upper()
            for issue_text in issues:
                text = issue_text.strip()
                if text:
                    issue_entries.append((text.lower(), sentiment))

        if len(issue_entries) < 5:
            return {"clusters": [], "total_issues_clustered": 0, "noise_issues": 0}

        # Step 2: Count occurrences and tokenize each unique issue
        issue_counts = Counter(text for text, _ in issue_entries)
        unique_issues = list(issue_counts.keys())
        issue_tokens = {issue: _tokenize(issue) for issue in unique_issues}

        # Step 3: Build sentiment distribution per issue
        issue_sentiment = defaultdict(lambda: Counter())
        for text, sentiment in issue_entries:
            issue_sentiment[text][sentiment] += 1

        # Step 4: Agglomerative clustering — merge similar issues
        # Start: each unique issue is its own cluster
        clusters = [[issue] for issue in unique_issues]

        merged = True
        while merged:
            merged = False
            i = 0
            while i < len(clusters):
                j = i + 1
                while j < len(clusters):
                    # Compute similarity between cluster representatives
                    # Use the most common issue in each cluster as representative
                    rep_a = max(clusters[i], key=lambda x: issue_counts[x])
                    rep_b = max(clusters[j], key=lambda x: issue_counts[x])
                    sim = _jaccard_similarity(issue_tokens[rep_a], issue_tokens[rep_b])

                    if sim >= self.similarity_threshold:
                        # Merge cluster j into cluster i
                        clusters[i].extend(clusters[j])
                        clusters.pop(j)
                        merged = True
                    else:
                        j += 1
                i += 1

        # Step 5: Build cluster output, filter by min size
        result_clusters = []
        noise_count = 0
        cluster_id = 0

        for cluster_issues_list in clusters:
            # Total volume for this cluster
            volume = sum(issue_counts[iss] for iss in cluster_issues_list)

            if len(cluster_issues_list) < self.min_cluster_size and volume < 3:
                noise_count += len(cluster_issues_list)
                continue

            # Representative issue = most frequently mentioned
            representative = max(cluster_issues_list, key=lambda x: issue_counts[x])

            # Sentiment distribution across all reviews mentioning issues in this cluster
            sent_dist = Counter()
            for iss in cluster_issues_list:
                sent_dist.update(issue_sentiment[iss])

            result_clusters.append({
                "cluster_id": cluster_id,
                "issues": sorted(cluster_issues_list, key=lambda x: issue_counts[x], reverse=True),
                "volume": volume,
                "representative_issue": representative,
                "sentiment_distribution": dict(sent_dist),
            })
            cluster_id += 1

        # Sort by volume descending
        result_clusters.sort(key=lambda c: c['volume'], reverse=True)
        # Re-assign cluster_ids after sorting
        for idx, cluster in enumerate(result_clusters):
            cluster['cluster_id'] = idx

        total_clustered = sum(c['volume'] for c in result_clusters)
        return {
            "clusters": result_clusters,
            "total_issues_clustered": total_clustered,
            "noise_issues": noise_count,
        }
