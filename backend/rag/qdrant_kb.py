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
    from openai import AsyncOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def _article_point_id(article_id: str) -> str:
    """Qdrant point IDs must be an unsigned int or UUID — derive a stable UUID from the article's string id."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, article_id))


def _article_embedding_text(article: Dict[str, Any]) -> str:
    return f"{article['title']}. Category: {article['category']}. Keywords: {', '.join(article['keywords'])}. Steps: {' '.join(article['steps'])}"


class QdrantKBManager:
    """
    Handles Qdrant vector database indexing and semantic retrieval using real
    OpenAI embeddings, falling back to keyword/topic matching when Qdrant or
    the embeddings API is unavailable.
    """
    def __init__(self):
        self.client: Optional[Any] = None
        self.embed_client: Optional[Any] = None
        self.use_qdrant: bool = False
        self.collection_name = "kb_vectors"

    async def init_db(self):
        # Save seed articles into Mongo / local store first
        mongo_store.save_kb_articles(SEED_KB_ARTICLES)

        if HAS_OPENAI and settings.is_openai_live:
            self.embed_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        if HAS_QDRANT and settings.QDRANT_URL and self.embed_client:
            try:
                self.client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None, timeout=5)
                self.client.get_collections()
                self.use_qdrant = True
                self._create_collection_if_needed()
                await self._seed_qdrant_vectors()
                if self.use_qdrant:
                    logger.info("Qdrant Vector DB connected and seeded with real OpenAI embeddings.")
                return
            except Exception as e:
                logger.warning(f"Qdrant connection unavailable ({e}). Using keyword search fallback.")
                self.use_qdrant = False
        else:
            logger.warning("Qdrant client or live OpenAI embeddings unavailable. Using keyword search fallback.")
            self.use_qdrant = False

    def _create_collection_if_needed(self):
        if not self.use_qdrant or not self.client:
            return
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
                )
        except Exception as e:
            logger.error(f"Error creating Qdrant collection: {e}")

    async def _embed_texts(self, texts: List[str]) -> Optional[List[List[float]]]:
        if not self.embed_client:
            return None
        try:
            response = await self.embed_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"OpenAI embeddings error: {e}")
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
        Embeds a single query string for callers that want to reuse the
        embedding themselves (e.g. comparing it against a cached topic
        embedding before deciding whether a fresh Qdrant search is needed).
        Returns None if embeddings are unavailable.
        """
        if not self.use_qdrant or not self.embed_client or not query.strip():
            return None
        embeddings = await self._embed_texts([query])
        return embeddings[0] if embeddings else None

    async def search_kb_by_embedding(self, query: str, embedding: List[float], limit: int = 2) -> List[Dict[str, Any]]:
        """
        Vector search using an already-computed query embedding — skips
        re-embedding for callers that already have one. Falls back to
        keyword/topic matching on failure, same as search_kb.
        """
        if self.use_qdrant and self.client and embedding:
            try:
                # self.client is the sync QdrantClient — query_points() is a
                # blocking network call, so it's offloaded to a worker thread
                # instead of running directly on the asyncio event loop (which
                # would otherwise stall every other concurrent task, including
                # barge-in handling, for the duration of the network round trip).
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
            results = SEED_KB_ARTICLES[:limit]

        clean_results = []
        for art in results:
            item = dict(art)
            item.pop("_id", None)
            clean_results.append(item)

        return clean_results

qdrant_manager = QdrantKBManager()
