import datetime
import logging
from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from backend.config import settings

logger = logging.getLogger("voxassist.mongo")

class MongoStore:
    """
    MongoDB storage layer for KB articles, escalation tickets, and archived logs.
    Includes in-memory fallback if MongoDB connection is unavailable.
    """
    def __init__(self):
        self.client: Optional[MongoClient] = None
        self.db = None
        self.use_mongo: bool = False
        
        self._local_kb: List[Dict[str, Any]] = []
        self._local_tickets: List[Dict[str, Any]] = []
        self._local_logs: List[Dict[str, Any]] = []

    def connect(self):
        try:
            self.client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=1000)
            self.client.admin.command('ping')
            self.db = self.client[settings.MONGODB_DB_NAME]
            self.use_mongo = True
            logger.info("Connected to MongoDB successfully.")
        except Exception as e:
            logger.warning(f"MongoDB connection unavailable ({e}). Using in-memory Mongo store fallback.")
            self.use_mongo = False

    def save_kb_articles(self, articles: List[Dict[str, Any]]):
        self._local_kb = articles
        if self.use_mongo and self.db is not None:
            try:
                import copy
                doc_copies = [copy.deepcopy(a) for a in articles]
                self.db.kb_articles.delete_many({})
                self.db.kb_articles.insert_many(doc_copies)
                return
            except Exception as e:
                logger.error(f"MongoDB save KB error: {e}")

    def get_kb_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        if self.use_mongo and self.db is not None:
            try:
                return self.db.kb_articles.find_one({"id": article_id}, {"_id": 0})
            except Exception as e:
                logger.error(f"MongoDB get KB error: {e}")
        
        for art in self._local_kb:
            if art.get("id") == article_id:
                return art
        return None

    def create_ticket(self, session_id: str, issue_summary: str, steps_tried: List[str], transcript_summary: str) -> Dict[str, Any]:
        ticket = {
            "ticket_id": f"TICK-{int(datetime.datetime.now().timestamp())}",
            "session_id": session_id,
            "issue_summary": issue_summary,
            "steps_tried": steps_tried,
            "status": "escalated",
            "transcript_summary": transcript_summary,
            "created_at": datetime.datetime.now().isoformat()
        }
        
        if self.use_mongo and self.db is not None:
            try:
                self.db.tickets.insert_one(ticket)
            except Exception as e:
                logger.error(f"MongoDB ticket creation error: {e}")
        
        self._local_tickets.append(ticket)
        logger.info(f"Created escalation ticket: {ticket['ticket_id']}")
        return ticket

    def list_tickets(self) -> List[Dict[str, Any]]:
        if self.use_mongo and self.db is not None:
            try:
                return list(self.db.tickets.find({}, {"_id": 0}))
            except Exception as e:
                logger.error(f"MongoDB list tickets error: {e}")
        
        return self._local_tickets

mongo_store = MongoStore()
