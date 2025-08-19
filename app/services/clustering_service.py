import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

import numpy as np
from sklearn.cluster import KMeans, AgglomerativeClustering
from sklearn.preprocessing import normalize
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)


class ClusteringService:
    """
    A service to perform clustering on image embeddings.
    """

    def _select_k(self, embeddings: np.ndarray, max_k: int = 10) -> int:
        """Heuristic to choose number of clusters via silhouette score."""
        n_samples = embeddings.shape[0]
        # At least 2 samples required for clustering
        if n_samples < 2:
            return 1
        max_k = min(max_k, n_samples - 1)
        best_k = None
        best_score = -1.0
        for k in range(2, max_k + 1):
            try:
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = km.fit_predict(embeddings)
                # silhouette_score requires more than 1 label and fewer labels than samples
                if len(set(labels)) <= 1 or len(set(labels)) >= n_samples:
                    continue
                score = silhouette_score(embeddings, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
            except Exception:
                continue
        # Fallbacks
        if best_k is None:
            return min(3, n_samples)  # default sensible value
        return best_k

    def _cluster(
        self,
        embeddings: np.ndarray,
        image_ids: List[str],
        algorithm: str,
        n_clusters: Optional[int] = None,
    ) -> Tuple[Dict[int, List[str]], List[str]]:
        """
        Performs clustering on a set of embeddings using a specified algorithm.

        Returns:
            A tuple containing:
            - A dictionary mapping cluster_id to a list of image_ids.
            - A list of image_ids that were not clustered (noise points).
        """
        # Guard against invalid n_clusters values (0 or negative) coming from the request
        if n_clusters is not None and n_clusters < 1:
            logger.warning("Received invalid n_clusters=%s; falling back to automatic selection.", n_clusters)
            n_clusters = None

        if embeddings.shape[0] < 2:
            logger.warning(
                "Not enough images to perform clustering. Returning all as unclustered."
            )
            return {}, image_ids

        # Normalize embeddings for better performance with distance-based algorithms
        embeddings = normalize(embeddings)

        # If n_clusters is None, choose automatically
        if n_clusters is None:
            # limit search to a reasonable number to avoid long compute
            chosen_k = self._select_k(embeddings, max_k=10)
            logger.info(f"Auto-selected n_clusters={chosen_k} via silhouette heuristic.")
            n_clusters = chosen_k

        model = None
        if algorithm == "kmeans":
            if embeddings.shape[0] < n_clusters:
                logger.warning(
                    f"Number of images ({embeddings.shape[0]}) is less than n_clusters ({n_clusters}). Adjusting n_clusters."
                )
                n_clusters = embeddings.shape[0]
            model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)

        elif algorithm == "hierarchical":
            if embeddings.shape[0] < n_clusters:
                logger.warning(
                    f"Number of images ({embeddings.shape[0]}) is less than n_clusters ({n_clusters}). Adjusting n_clusters."
                )
                n_clusters = embeddings.shape[0]
            model = AgglomerativeClustering(n_clusters=n_clusters)

        else:
            raise ValueError(f"Unknown clustering algorithm: {algorithm}")

        logger.info(f"Running {algorithm} clustering on {len(image_ids)} images with k={n_clusters}...")
        labels = model.fit_predict(embeddings)
        logger.info(f"Clustering complete. Found labels: {np.unique(labels)}")

        clusters: Dict[int, List[str]] = {}
        noise_points: List[str] = []

        for image_id, label in zip(image_ids, labels):
            if label == -1:  # DBSCAN noise points are labeled -1 (not used here but kept)
                noise_points.append(image_id)
            else:
                clusters.setdefault(int(label), []).append(image_id)

        return clusters, noise_points

    def cluster_images(
        self, image_records: List[Dict[str, Any]], algorithm: str, n_clusters: Optional[int] = None
    ) -> Tuple[Dict[int, List[str]], List[str]]:
        """Extracts embeddings and clusters images."""
        # If caller passed an invalid n_clusters (e.g. 0 or negative), treat it as auto-select
        if n_clusters is not None and n_clusters < 1:
            logger.warning("cluster_images received invalid n_clusters=%s; using automatic selection.", n_clusters)
            n_clusters = None

        records_with_embeddings = [r for r in image_records if r.get("embedding")]
        if not records_with_embeddings:
            logger.warning("No images with embeddings found for clustering.")
            return {}, [r["image_id"] for r in image_records]

        image_ids = [record["image_id"] for record in records_with_embeddings]
        embeddings = np.array([record["embedding"] for record in records_with_embeddings])

        return self._cluster(embeddings, image_ids, algorithm, n_clusters)
