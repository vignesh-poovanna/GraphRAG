"""
Neo4j utility functions.
"""

from neo4j import GraphDatabase
import json
from src.config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class Neo4jHelper:
    """Helper class for Neo4j operations."""
    
    def __init__(self, uri=NEO4J_URI, user=NEO4J_USER, password=NEO4J_PASSWORD):
        """Initialize the Neo4j connection."""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        """Close the Neo4j connection."""
        self.driver.close()
    
    def verify_connection(self):
        """Verify the Neo4j connection is working."""
        try:
            with self.driver.session() as session:
                result = session.run("RETURN 'Connection successful' AS message")
                return result.single()["message"]
        except Exception as e:
            return f"Connection failed: {str(e)}"
    
    def setup_schema(self):
        """Set up the Neo4j schema for the GraphRAG project."""
        schema_queries = [
            # Node constraints
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Content) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            
            # Indexes for faster lookups
            "CREATE INDEX IF NOT EXISTS FOR (c:Content) ON (c.text)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.title)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.category)",
            "CREATE INDEX IF NOT EXISTS FOR (d:Document) ON (d.path)",
            "CREATE INDEX IF NOT EXISTS FOR (t:Topic) ON (t.name)"
        ]
        
        with self.driver.session() as session:
            for query in schema_queries:
                session.run(query)
    
    def create_document(self, doc_id, title, path):
        """Create a document node in Neo4j."""
        query = """
        MERGE (d:Document {id: $id})
        SET d.title = $title,
            d.path = $path,
            d.created_at = datetime()
        RETURN d
        """
        with self.driver.session() as session:
            result = session.run(query, id=doc_id, title=title, path=path)
            return result.single()
    
    def create_document_with_metadata(self, doc_id, title, path, category='', updated='', metadata=None):
        """
        Create a document node with metadata from frontmatter.
        
        Args:
            doc_id: Unique document ID
            title: Document title
            path: Document file path
            category: Document category
            updated: Last updated date
            metadata: Additional metadata from frontmatter
        """
        if metadata is None:
            metadata = {}
        
        # Convert metadata to JSON string for storage
        metadata_json = json.dumps(metadata)
        
        query = """
        MERGE (d:Document {id: $id})
        SET d.title = $title,
            d.path = $path,
            d.category = $category,
            d.updated = $updated,
            d.metadata = $metadata,
            d.created_at = datetime()
        RETURN d
        """
        with self.driver.session() as session:
            result = session.run(
                query, 
                id=doc_id, 
                title=title, 
                path=path, 
                category=category,
                updated=updated,
                metadata=metadata_json
            )
            return result.single()
    
    def create_content_chunk(self, chunk_id, text, doc_id, sequence=0):
        """Create a content chunk node and link it to a document."""
        query = """
        MATCH (d:Document {id: $doc_id})
        MERGE (c:Content {id: $id})
        SET c.text = $text,
            c.sequence = $sequence,
            c.created_at = datetime()
        MERGE (d)-[:CONTAINS]->(c)
        RETURN c
        """
        with self.driver.session() as session:
            result = session.run(
                query, 
                id=chunk_id, 
                text=text, 
                doc_id=doc_id, 
                sequence=sequence
            )
            return result.single()
    
    def link_content_chunks(self, from_id, to_id):
        """Create a NEXT relationship between content chunks."""
        query = """
        MATCH (c1:Content {id: $from_id})
        MATCH (c2:Content {id: $to_id})
        MERGE (c1)-[:NEXT]->(c2)
        """
        with self.driver.session() as session:
            session.run(query, from_id=from_id, to_id=to_id)
    
    def create_topic_and_relationship(self, doc_id, topic_name):
        """
        Create a Topic node and link it to a Document.
        
        Args:
            doc_id: Document ID
            topic_name: Topic name
        """
        query = """
        MATCH (d:Document {id: $doc_id})
        MERGE (t:Topic {name: $topic_name})
        MERGE (d)-[:HAS_TOPIC]->(t)
        RETURN t
        """
        with self.driver.session() as session:
            result = session.run(query, doc_id=doc_id, topic_name=topic_name)
            return result.single()
    
    def link_documents(self, source_doc_id, target_doc_id, rel_type="RELATED_TO", via="manual", weight=1.0):
        """
        Create a relationship between two Document nodes.
        via: provenance tag — "manual" | "shared_category" | "shared_concepts" | "embedding_similarity"
        """
        query = f"""
        MATCH (d1:Document {{id: $source_id}})
        MATCH (d2:Document {{id: $target_id}})
        MERGE (d1)-[r:{rel_type}]->(d2)
        SET r.via = $via, r.weight = $weight
        """
        with self.driver.session() as session:
            session.run(query, source_id=source_doc_id, target_id=target_doc_id, via=via, weight=weight)
    
    def get_document_chunks(self, doc_id):
        """Get all content chunks for a document."""
        query = """
        MATCH (d:Document {id: $doc_id})-[:CONTAINS]->(c:Content)
        RETURN c.id AS id, c.text AS text, c.sequence AS sequence
        ORDER BY c.sequence
        """
        with self.driver.session() as session:
            result = session.run(query, doc_id=doc_id)
            return [dict(record) for record in result]
            
    def get_document_by_path(self, path):
        """
        Get a document node by its file path.
        
        Args:
            path: Document file path
            
        Returns:
            Document record or None
        """
        query = """
        MATCH (d:Document {path: $path})
        RETURN d.id AS id, d.title AS title
        """
        with self.driver.session() as session:
            result = session.run(query, path=path)
            record = result.single()
            return dict(record) if record else None
            
    def get_related_documents(self, doc_id, rel_type="RELATED_TO"):
        """
        Get documents related to the specified document.
        
        Args:
            doc_id: Document ID
            rel_type: Relationship type (default: RELATED_TO)
            
        Returns:
            List of related document records
        """
        query = f"""
        MATCH (d:Document {{id: $doc_id}})-[:{rel_type}]->(related:Document)
        RETURN related.id AS id, related.title AS title, related.category AS category
        """
        with self.driver.session() as session:
            result = session.run(query, doc_id=doc_id)
            return [dict(record) for record in result]
            
    def get_document_topics(self, doc_id):
        """
        Get topics associated with a document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            List of topic names
        """
        query = """
        MATCH (d:Document {id: $doc_id})-[:HAS_TOPIC]->(t:Topic)
        RETURN t.name AS name
        """
        with self.driver.session() as session:
            result = session.run(query, doc_id=doc_id)
            return [record["name"] for record in result]
            
    def get_documents_by_topic(self, topic_name):
        """
        Get documents associated with a specific topic.
        
        Args:
            topic_name: Topic name
            
        Returns:
            List of document records
        """
        query = """
        MATCH (t:Topic {name: $topic_name})<-[:HAS_TOPIC]-(d:Document)
        RETURN d.id AS id, d.title AS title, d.category AS category
        """
        with self.driver.session() as session:
            result = session.run(query, topic_name=topic_name)
            return [dict(record) for record in result]
    
    def clear_database(self):
        """Clear all data in the Neo4j database."""
        query = """
        MATCH (n)
        DETACH DELETE n
        """
        with self.driver.session() as session:
            session.run(query)
        return "Database cleared successfully."
    
    def test_connection(self):
        """Test the Neo4j connection."""
        try:
            result = self.verify_connection()
            return "Connection successful" in result
        except Exception:
            return False
            
    def get_database_stats(self):
        """Get database statistics."""
        stats = {}
        with self.driver.session() as session:
            # Get document count
            result = session.run("MATCH (d:Document) RETURN count(d) as count")
            stats['document_count'] = result.single()["count"]
            
            # Get chunk count
            result = session.run("MATCH (c:Chunk) RETURN count(c) as count")
            stats['chunk_count'] = result.single()["count"]
            
            # Get relationship count
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            stats['relationship_count'] = result.single()["count"]
            
        return stats

    # ------------------------------------------------------------------
    # Entity / concept graph (Part B1) — pure additions, no existing
    # method signatures changed.
    # ------------------------------------------------------------------

    def create_entity(self, name, entity_type=None):
        """MERGE an Entity node by name. entity_type is optional metadata."""
        query = """
        MERGE (e:Entity {name: $name})
        SET e.entity_type = $entity_type
        RETURN e
        """
        with self.driver.session() as session:
            return session.run(query, name=name, entity_type=entity_type or "").single()

    def link_chunk_to_entity(self, chunk_id, entity_name):
        """Create (:Content)-[:MENTIONS]->(:Entity). Idempotent via MERGE."""
        query = """
        MATCH (c:Content {id: $chunk_id})
        MERGE (e:Entity {name: $entity_name})
        MERGE (c)-[:MENTIONS]->(e)
        """
        with self.driver.session() as session:
            session.run(query, chunk_id=chunk_id, entity_name=entity_name)

    def link_entities(self, entity_a, entity_b, rel_type="RELATED_TO", weight=1.0):
        """Create a weighted (:Entity)-[:RELATED_TO]->(:Entity) edge. Idempotent."""
        # rel_type validated against allowlist to prevent Cypher injection
        allowed = {"RELATED_TO", "PART_OF"}
        if rel_type not in allowed:
            rel_type = "RELATED_TO"
        query = (
            "MERGE (a:Entity {name: $a}) "
            "MERGE (b:Entity {name: $b}) "
            "MERGE (a)-[r:" + rel_type + "]->(b) "
            "SET r.weight = $weight "
            "RETURN r"
        )
        with self.driver.session() as session:
            return session.run(query, a=entity_a, b=entity_b, weight=weight).single()

    def get_related_entities(self, entity_name, depth=1):
        """Traverse RELATED_TO up to `depth` hops from an entity."""
        query = """
        MATCH (e:Entity {name: $name})-[:RELATED_TO*1..$depth]-(related:Entity)
        RETURN DISTINCT related.name AS name, related.entity_type AS entity_type
        """
        with self.driver.session() as session:
            result = session.run(query, name=entity_name, depth=depth)
            return [dict(r) for r in result]

    def get_documents_for_entity(self, entity_name):
        """Find all documents that have chunks mentioning the given entity."""
        query = """
        MATCH (d:Document)-[:CONTAINS]->(c:Content)-[:MENTIONS]->(e:Entity {name: $name})
        RETURN DISTINCT d.id AS id, d.title AS title, d.category AS category
        """
        with self.driver.session() as session:
            result = session.run(query, name=entity_name)
            return [dict(r) for r in result]

    def auto_link_related_documents(
        self, min_shared_concepts=2, threshold=0.75, doc_embeddings=None
    ):
        """
        Auto-discover and link related documents via two mechanisms (D2):

        1. Concept-overlap: pairs sharing >= min_shared_concepts entities get a
           RELATED_TO edge tagged via="shared_concepts".
        2. Embedding-similarity: if doc_embeddings {doc_id: np.array} is provided,
           pairs with cosine similarity >= threshold get a RELATED_TO edge tagged
           via="embedding_similarity".

        Both checks are idempotent (MERGE). Manually-authored edges (via="manual")
        are untouched — they carry higher implicit confidence.
        """
        linked = {"shared_concepts": 0, "embedding_similarity": 0}

        # --- 1. Concept-overlap ---
        cypher = """
        MATCH (d1:Document)-[:HAS_CHUNK]->(c1:Chunk)-[:MENTIONS]->(e:Entity)
              <-[:MENTIONS]-(c2:Chunk)<-[:HAS_CHUNK]-(d2:Document)
        WHERE d1.id < d2.id
        WITH d1, d2, count(DISTINCT e) AS shared
        WHERE shared >= $min_shared
        MERGE (d1)-[r:RELATED_TO {via: "shared_concepts"}]->(d2)
        SET r.weight = shared
        RETURN count(r) AS n
        """
        with self.driver.session() as session:
            row = session.run(cypher, min_shared=min_shared_concepts).single()
            linked["shared_concepts"] = row["n"] if row else 0

        # --- 2. Embedding-similarity ---
        if doc_embeddings and len(doc_embeddings) > 1:
            try:
                import numpy as np  # already a core dep

                ids = list(doc_embeddings.keys())
                vecs = np.array([doc_embeddings[i] for i in ids], dtype=float)
                # L2-normalise for cosine similarity via dot product
                norms = np.linalg.norm(vecs, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                vecs = vecs / norms

                with self.driver.session() as session:
                    for i in range(len(ids)):
                        for j in range(i + 1, len(ids)):
                            sim = float(np.dot(vecs[i], vecs[j]))
                            if sim >= threshold:
                                session.run(
                                    """
                                    MATCH (d1:Document {id: $a})
                                    MATCH (d2:Document {id: $b})
                                    MERGE (d1)-[r:RELATED_TO {via: "embedding_similarity"}]->(d2)
                                    SET r.weight = $sim
                                    """,
                                    a=ids[i], b=ids[j], sim=sim,
                                )
                                linked["embedding_similarity"] += 1
            except Exception as exc:
                logger.warning("Embedding-similarity linking failed: %s", exc)

        logger.info(
            "auto_link_related_documents: shared_concepts=%d  embedding_similarity=%d",
            linked["shared_concepts"], linked["embedding_similarity"],
        )
        return linked

    def update_document_category(self, doc_id, category):
        """Update a document's category if it is currently 'uncategorized'."""
        with self.driver.session() as session:
            session.run(
                """
                MATCH (d:Document {id: $id})
                WHERE d.category = 'uncategorized' OR d.category IS NULL OR d.category = ''
                SET d.category = $category
                """,
                id=doc_id, category=category,
            )