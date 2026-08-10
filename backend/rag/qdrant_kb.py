import re
import time
import uuid
import asyncio
import logging
from typing import Dict, Any, List, Optional
from backend.config import settings
from backend.rag.seed_kb import SEED_KB_ARTICLES
from backend.storage.mongo_db import mongo_store

logger = logging.getLogger("voxassist.qdrant")

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False

try:
    from fastembed import TextEmbedding
    HAS_FASTEMBED = True
except ImportError:
    HAS_FASTEMBED = False

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


def _article_point_id(article_id: str) -> str:
    """Qdrant point IDs must be an unsigned int or UUID — derive a stable UUID from the article's string id."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, article_id))


def _article_embedding_text(article: Dict[str, Any]) -> str:
    return f"{article['title']}. Category: {article['category']}. Keywords: {', '.join(article['keywords'])}. Steps: {' '.join(article['steps'])}"


class QdrantKBManager:
    """
    Handles Qdrant vector database indexing and semantic retrieval using local
    FastEmbed ONNX embeddings (dim=384, BAAI/bge-small-en-v1.5), with ultra-fast
    in-memory cosine search acceleration (< 1ms) and Qdrant Cloud fallback.
    """
    def __init__(self):
        self.client: Optional[Any] = None
        self.embed_model: Optional[Any] = None
        self.use_qdrant: bool = False
        self.collection_name = "kb_vectors"
        self._local_articles: List[Dict[str, Any]] = []
        self._local_matrix: Optional[Any] = None
        self._local_matrix_norm: Optional[Any] = None

    async def init_db(self):
        # Save seed articles into Mongo / local store first
        mongo_store.save_kb_articles(SEED_KB_ARTICLES)

        if HAS_FASTEMBED:
            try:
                logger.info(f"Initializing local FastEmbed model ({EMBEDDING_MODEL})...")
                self.embed_model = await asyncio.to_thread(TextEmbedding, model_name=EMBEDDING_MODEL)
                logger.info("Local FastEmbed ONNX embedding engine ready.")
            except Exception as e:
                logger.error(f"FastEmbed initialization error: {e}")
                self.embed_model = None

        if self.embed_model:
            await self._seed_local_memory_vectors()

        if HAS_QDRANT and settings.QDRANT_URL and self.embed_model:
            try:
                self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None, timeout=5)
                self.client.get_collections()
                self.use_qdrant = True
                self._create_collection_if_needed()
                await self._seed_qdrant_vectors()
                if self.use_qdrant:
                    logger.info("Qdrant Vector DB connected and seeded with FastEmbed ONNX (local) embeddings (dim=384).")
                return
            except Exception as e:
                logger.warning(f"Qdrant connection unavailable ({e}). Using in-memory & keyword search fallback.")
                self.use_qdrant = False
        else:
            logger.warning("Qdrant client unavailable. Using in-memory & keyword search fallback.")
            self.use_qdrant = False

    async def _seed_local_memory_vectors(self):
        try:
            import numpy as np
            self._local_articles = SEED_KB_ARTICLES
            texts = [_article_embedding_text(a) for a in self._local_articles]
            embeddings = await self._embed_texts(texts)
            if embeddings:
                matrix = np.array(embeddings, dtype=np.float32)
                norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                self._local_matrix = matrix
                self._local_matrix_norm = matrix / norms
                logger.info(f"In-memory vector index initialized with {len(self._local_articles)} KB articles (dim={EMBEDDING_DIM}).")
        except Exception as e:
            logger.error(f"Error seeding in-memory vector index: {e}")

    def _create_collection_if_needed(self):
        if not self.use_qdrant or not self.client:
            return
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name in collections:
                # Check vector size dimension
                col_info = self.client.get_collection(self.collection_name)
                current_size = getattr(col_info.config.params.vectors, 'size', None)
                if current_size != EMBEDDING_DIM:
                    logger.warning(f"Recreating Qdrant collection '{self.collection_name}' (dimension mismatch {current_size} != {EMBEDDING_DIM}).")
                    self.client.delete_collection(self.collection_name)
                    collections.remove(self.collection_name)

            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
                )
        except Exception as e:
            logger.error(f"Error creating Qdrant collection: {e}")

    async def _embed_texts(self, texts: List[str]) -> Optional[List[List[float]]]:
        if not self.embed_model:
            return None
        try:
            embeddings_generator = await asyncio.to_thread(lambda: list(self.embed_model.embed(texts)))
            return [emb.tolist() for emb in embeddings_generator]
        except Exception as e:
            logger.error(f"FastEmbed embedding error: {e}")
            return None

    async def _seed_qdrant_vectors(self):
        if not self.use_qdrant or not self.client:
            return
        try:
            texts = [_article_embedding_text(a) for a in SEED_KB_ARTICLES]
            embeddings = await self._embed_texts(texts)
            if not embeddings:
                self.use_qdrant = False
                return
            points = [
                PointStruct(id=_article_point_id(article["id"]), vector=emb, payload={"kb_id": article["id"]})
                for article, emb in zip(SEED_KB_ARTICLES, embeddings)
            ]
            self.client.upsert(collection_name=self.collection_name, points=points)
        except Exception as e:
            logger.error(f"Error seeding Qdrant vectors: {e}")
            self.use_qdrant = False

    async def embed_query(self, query: str) -> Optional[List[float]]:
        """
        Embeds a single query string using local FastEmbed ONNX engine.
        """
        if not self.embed_model or not query.strip():
            return None
        embeddings = await self._embed_texts([query])
        return embeddings[0] if embeddings else None

    async def search_kb_by_embedding(self, query: str, embedding: List[float], limit: int = 2) -> List[Dict[str, Any]]:
        """
        Vector search using an already-computed query embedding:
        1. Fast in-memory NumPy matrix cosine search (< 1ms)
        2. Qdrant Cloud fallback if in-memory index is not present
        """
        if self._local_matrix_norm is not None and embedding:
            try:
                import numpy as np
                q_vec = np.array(embedding, dtype=np.float32)
                q_norm = np.linalg.norm(q_vec)
                if q_norm > 0:
                    q_unit = q_vec / q_norm
                    scores = np.dot(self._local_matrix_norm, q_unit)
                    top_indices = np.argsort(scores)[::-1][:limit]
                    results = []
                    for idx in top_indices:
                        art = self._local_articles[idx]
                        item = dict(art)
                        item.pop("_id", None)
                        results.append(item)
                    if results:
                        return results
            except Exception as e:
                logger.error(f"In-memory vector search error: {e}")

        if self.use_qdrant and self.client and embedding:
            try:
                response = await asyncio.to_thread(
                    self.client.query_points,
                    collection_name=self.collection_name,
                    query=embedding,
                    limit=limit
                )
                results = []
                for hit in response.points:
                    kb_id = hit.payload.get("kb_id") if hit.payload else None
                    article = mongo_store.get_kb_article(kb_id) if kb_id else None
                    if article:
                        item = dict(article)
                        item.pop("_id", None)
                        results.append(item)
                if results:
                    return results
            except Exception as e:
                logger.error(f"Qdrant search error, falling back to keyword search: {e}")

        return self._keyword_search_kb(query, limit)

    async def search_kb(self, query: str, limit: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieves relevant KB documents via real Qdrant vector search when
        available, falling back to keyword/topic matching otherwise.
        """
        if self.use_qdrant and self.client and query.strip():
            t0 = time.monotonic()
            embedding = await self.embed_query(query)
            t1 = time.monotonic()
            if embedding:
                result = await self.search_kb_by_embedding(query, embedding, limit)
                t2 = time.monotonic()
                logger.info(
                    f"[latency] KB search: embed={((t1 - t0) * 1000):.0f}ms "
                    f"qdrant={((t2 - t1) * 1000):.0f}ms"
                )
                return result

        return self._keyword_search_kb(query, limit)

    def _keyword_search_kb(self, query: str, limit: int = 2) -> List[Dict[str, Any]]:
        """
        High-precision keyword/topic search — used when Qdrant/embeddings are
        unavailable, and as a safety net if vector search returns nothing.
        """
        query_text = query.lower().strip()
        query_tokens = set(re.findall(r'\w+', query_text))

        # Explicit topic-to-article routing table
        TOPIC_MAP = {
            "wifi": "kb_wifi_01",
            "wireless": "kb_wifi_01",
            "vpn": "kb_vpn_01",
            "tunnel": "kb_vpn_01",
            "password": "kb_pwd_01",
            "passcode": "kb_pwd_01",
            "mfa": "kb_mfa_01",
            "2fa": "kb_mfa_01",
            "authenticator": "kb_mfa_01",
            "keyboard": "kb_kbd_01",
            "keys": "kb_kbd_01",
            "typing": "kb_kbd_01",
            "printer": "kb_print_01",
            "print": "kb_print_01",
            "disk": "kb_disk_01",
            "storage": "kb_disk_01",
            "outlook": "kb_outlook_01",
            "email": "kb_outlook_01",
            "teams": "kb_teams_01",
            "vdi": "kb_vdi_01",
            "citrix": "kb_vdi_01",
            "rdp": "kb_vdi_01",
            "slow": "kb_perf_01",
            "lag": "kb_perf_01",
            "performance": "kb_perf_01"
        }

        if not query_text:
            clean_results = []
            for art in SEED_KB_ARTICLES[:limit]:
                item = dict(art)
                item.pop("_id", None)
                clean_results.append(item)
            return clean_results

        target_topic_id = None
        for tok in query_tokens:
            if tok in TOPIC_MAP:
                target_topic_id = TOPIC_MAP[tok]
                break

        matched_articles = []
        for article in SEED_KB_ARTICLES:
            score = 0
            art_id = article["id"]

            # Massive score boost for explicit topic match
            if target_topic_id and art_id == target_topic_id:
                score += 50

            art_keywords = set(article["keywords"])

            # Exact token intersection
            exact_matches = query_tokens.intersection(art_keywords)
            score += len(exact_matches) * 10

            # Category match
            if article["category"].lower() in query_tokens:
                score += 5

            if score > 0:
                matched_articles.append((score, article))

        matched_articles.sort(key=lambda x: x[0], reverse=True)
        results = [art for score, art in matched_articles[:limit]]

        if not results:
            return []

        clean_results = []
        for art in results:
            item = dict(art)
            item.pop("_id", None)
            clean_results.append(item)

        return clean_results

qdrant_manager = QdrantKBManager()
