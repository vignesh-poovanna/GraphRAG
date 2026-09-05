"""
Neo4j database manager for GraphRAG
"""

import logging
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

logger = logging.getLogger(__name__)

class Neo4jManager:
    """Manager for Neo4j document graph operations"""
    
    def __init__(self, config):
        """Initialize Neo4j manager with configuration"""
        self.config = config
        self.uri = config.get('neo4j.uri', 'bolt://localhost:7687')
        self.username = config.get('neo4j.username', 'neo4j')
        self.password = config.get('neo4j.password', 'password')
        self.database = config.get('neo4j.database', 'neo4j')
        self.driver = None
        
    def connect(self):
        """Connect to Neo4j database"""
        try:
            logger.info(f"Connecting to Neo4j at {self.uri}")
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
            # Test connection
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS test")
                test_value = result.single()["test"]
                if test_value != 1:
                    raise Exception("Connection test failed")
            logger.info("Successfully connected to Neo4j")
            return True
        except AuthError as e:
            logger.error(f"Neo4j authentication error: {str(e)}")
            raise
        except ServiceUnavailable as e:
            logger.error(f"Neo4j service unavailable: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {str(e)}")
            raise
            
    def close(self):
        """Close the Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
            
    def setup_schema(self):
        """Set up the document graph schema with constraints"""
        logger.info("Setting up Neo4j schema with constraints")
        
        # Queries to create constraints
        constraints = [
            # Document uniqueness constraint
            """
            CREATE CONSTRAINT document_id IF NOT EXISTS
            FOR (d:Document) REQUIRE d.id IS UNIQUE
            """,
            # Chunk uniqueness constraint
            """
            CREATE CONSTRAINT chunk_id IF NOT EXISTS
            FOR (c:Chunk) REQUIRE c.id IS UNIQUE
            """
        ]
        
        try:
            with self.driver.session(database=self.database) as session:
                for constraint in constraints:
                    session.run(constraint)
                logger.info("Neo4j schema constraints created successfully")
            return True
        except Exception as e:
            logger.error(f"Error setting up Neo4j schema: {str(e)}")
            raise
            
    def clear_database(self):
        """Clear all nodes and relationships from the database"""
        logger.warning("Clearing all data from Neo4j database")
        
        try:
            with self.driver.session(database=self.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
            logger.info("Neo4j database cleared successfully")
            return True
        except Exception as e:
            logger.error(f"Error clearing Neo4j database: {str(e)}")
            raise
            
    def import_documents(self, documents, chunks):
        """Import documents and chunks into Neo4j"""
        logger.info(f"Importing {len(documents)} documents with {len(chunks)} chunks to Neo4j")
        
        doc_batch_size = 50
        chunk_batch_size = 200
        
        try:
            with self.driver.session(database=self.database) as session:
                for i in range(0, len(documents), doc_batch_size):
                    batch = documents[i:i+doc_batch_size]
                    self._create_documents_batch(session, batch)
                    logger.debug(f"Imported document batch {i//doc_batch_size + 1}")
                
                for i in range(0, len(chunks), chunk_batch_size):
                    batch = chunks[i:i+chunk_batch_size]
                    self._create_chunks_batch(session, batch)
                    logger.debug(f"Imported chunk batch {i//chunk_batch_size + 1}")
                
                # Category-based relationships — tagged via='shared_category' (D3)
                session.run("""
                MATCH (d1:Document), (d2:Document)
                WHERE d1.category = d2.category AND d1.id <> d2.id
                  AND d1.category IS NOT NULL AND d1.category <> ''
                  AND d1.category <> 'uncategorized'
                MERGE (d1)-[r:RELATED_TO {via: 'shared_category'}]->(d2)
                SET r.weight = 0.5
                """)

                # Manual related: frontmatter edges — tagged via='manual' (D3)
                # Build a path→id lookup so we can resolve related filenames to doc IDs
                path_to_id = {doc.get('path', ''): doc['id'] for doc in documents}
                for doc in documents:
                    related_raw = doc.get('related', [])
                    if not related_raw:
                        continue
                    if isinstance(related_raw, str):
                        related_raw = [related_raw]
                    for rel_path in related_raw:
                        target_id = path_to_id.get(str(rel_path))
                        if target_id and target_id != doc['id']:
                            session.run(
                                """
                                MATCH (d1:Document {id: $src})
                                MATCH (d2:Document {id: $tgt})
                                MERGE (d1)-[r:RELATED_TO {via: 'manual'}]->(d2)
                                SET r.weight = 1.0
                                """,
                                src=doc['id'], tgt=target_id,
                            )

            logger.info("Documents and chunks successfully imported to Neo4j")
            return True
        except Exception as e:
            logger.error(f"Error importing documents to Neo4j: {str(e)}")
            raise
            
    def _create_documents_batch(self, session, documents):
        """Create document nodes in batch"""
        # Prepare parameters for batch creation
        params = {'documents': []}
        
        for doc in documents:
            # Prepare document properties
            doc_data = {
                'id': doc['id'],
                'title': doc.get('title', ''),
                'category': doc.get('category', ''),
                'path': doc.get('path', '')
            }
            
            # Add optional properties if they exist
            for key in ['author', 'date', 'tags', 'description']:
                if key in doc:
                    doc_data[key] = doc[key]
                    
            params['documents'].append(doc_data)
        
        # Execute batch creation
        session.run("""
        UNWIND $documents AS doc
        MERGE (d:Document {id: doc.id})
        SET d += doc
        """, params)
        
    def _create_chunks_batch(self, session, chunks):
        """Create chunk nodes and relationships in batch"""
        # Prepare parameters for batch creation
        params = {'chunks': []}
        
        for chunk in chunks:
            # Prepare chunk properties
            chunk_data = {
                'id': chunk['id'],
                'text': chunk['text'],
                'doc_id': chunk['doc_id'],
                'position': chunk['position']
            }
            
            params['chunks'].append(chunk_data)
        
        # Execute batch creation with relationships
        session.run("""                    
        UNWIND $chunks AS chunk
        MERGE (c:Chunk {id: chunk.id})
        SET c.text = chunk.text,
            c.position = chunk.position,
            c.doc_id = chunk.doc_id
        WITH c, chunk
        MERGE (d:Document {id: chunk.doc_id})
        MERGE (d)-[:HAS_CHUNK]->(c)
        WITH c, chunk
        MATCH (prev:Chunk {doc_id: chunk.doc_id, position: chunk.position - 1})
        MERGE (prev)-[:NEXT]->(c)
        """, params)
    def get_document_by_id(self, doc_id):
        """Get a document by ID"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document {id: $id})
                RETURN d
                """, {'id': doc_id})
                
                record = result.single()
                if record:
                    return dict(record['d'])
                return None
        except Exception as e:
            logger.error(f"Error getting document by ID: {str(e)}")
            return None
            
    def get_document_chunks(self, doc_id):
        """Get all chunks for a document ordered by position"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document {id: $id})-[:HAS_CHUNK]->(c:Chunk)
                RETURN c
                ORDER BY c.position
                """, {'id': doc_id})
                
                return [dict(record['c']) for record in result]
        except Exception as e:
            logger.error(f"Error getting document chunks: {str(e)}")
            return []
            
    def get_related_documents(self, doc_id, limit=5):
        """Get related documents ordered by relationship confidence (via priority).
        manual > shared_concepts > embedding_similarity > shared_category
        """
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document {id: $id})-[r:RELATED_TO]->(related:Document)
                WITH related, r,
                     CASE r.via
                       WHEN 'manual'               THEN 4
                       WHEN 'shared_concepts'       THEN 3
                       WHEN 'embedding_similarity'  THEN 2
                       WHEN 'shared_category'       THEN 1
                       ELSE 0
                     END AS via_rank
                RETURN related, r.via AS via, r.weight AS weight
                ORDER BY via_rank DESC, weight DESC
                LIMIT $limit
                """, {'id': doc_id, 'limit': limit})
                return [
                    {**dict(record['related']), 'via': record['via'], 'rel_weight': record['weight']}
                    for record in result
                ]
        except Exception as e:
            logger.error(f"Error getting related documents: {str(e)}")
            return []
            
    def get_document_by_chunk_id(self, chunk_id):
        """Get the parent document of a chunk"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk {id: $id})
                RETURN d
                """, {'id': chunk_id})
                
                record = result.single()
                if record:
                    return dict(record['d'])
                return None
        except Exception as e:
            logger.error(f"Error getting document by chunk ID: {str(e)}")
            return None
            
    def get_chunk_context(self, chunk_id, context_size=1):
        """Get surrounding chunks for context"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (c:Chunk {id: $id})
                OPTIONAL MATCH (c)<-[:NEXT*1..2]-(prev:Chunk)
                OPTIONAL MATCH (c)-[:NEXT*1..2]->(next:Chunk)
                WITH c, collect(prev) as prevs, collect(next) as nexts
                RETURN c as center, prevs, nexts
                """, {'id': chunk_id, 'context_size': context_size})
                record = result.single()
                if record:
                    return {
                        'center': dict(record['center']),
                        'previous': [dict(chunk) for chunk in record['prevs']],
                        'next': [dict(chunk) for chunk in record['nexts']]
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting chunk context: {str(e)}")
            return None
            
    def search_by_category(self, category, limit=10):
        """Search for documents by category"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document)
                WHERE d.category = $category
                RETURN d
                LIMIT $limit
                """, {'category': category, 'limit': limit})
                
                return [dict(record['d']) for record in result]
        except Exception as e:
            logger.error(f"Error searching by category: {str(e)}")
            return []
            
    def get_all_categories(self):
        """Get all document categories"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (d:Document)
                RETURN DISTINCT d.category AS category
                """)
                
                return [record['category'] for record in result]
        except Exception as e:
            logger.error(f"Error getting all categories: {str(e)}")
            return []
            
    def get_statistics(self):
        """Get database statistics"""
        try:
            with self.driver.session(database=self.database) as session:
                doc_count = session.run("MATCH (d:Document) RETURN count(d) AS count").single()['count']
                chunk_count = session.run("MATCH (c:Chunk) RETURN count(c) AS count").single()['count']
                category_count = session.run("MATCH (d:Document) RETURN count(DISTINCT d.category) AS count").single()['count']
                
                return {
                    'document_count': doc_count,
                    'chunk_count': chunk_count,
                    'category_count': category_count
                }
        except Exception as e:
            logger.error(f"Error getting database statistics: {str(e)}")
            return {}

    # ------------------------------------------------------------------
    # Concept-graph traversal for query engine (Part B3)
    # ------------------------------------------------------------------

    def get_entities_for_chunks(self, chunk_ids):
        """
        Return Entity names mentioned by the given chunk IDs.
        Uses Chunk label (HAS_CHUNK schema from import_docs.py).
        """
        if not chunk_ids:
            return []
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
                WHERE c.id IN $ids
                RETURN DISTINCT e.name AS name, e.entity_type AS entity_type
                """, {'ids': list(chunk_ids)})
                return [dict(r) for r in result]
        except Exception as e:
            logger.error(f"Error getting entities for chunks: {str(e)}")
            return []

    def get_documents_for_entities(self, entity_names, exclude_doc_ids=None, limit=10):
        """
        Find documents that mention any of the given entities.
        Uses Chunk/HAS_CHUNK schema (from import_docs.py).
        """
        if not entity_names:
            return []
        exclude = list(exclude_doc_ids or [])
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (e:Entity)<-[:MENTIONS]-(c:Chunk)<-[:HAS_CHUNK]-(d:Document)
                WHERE e.name IN $names
                  AND NOT d.id IN $exclude
                WITH d, c, count(DISTINCT e) AS entity_overlap
                ORDER BY entity_overlap DESC
                WITH d, head(collect(c)) AS rep_chunk, max(entity_overlap) AS overlap
                RETURN d.id AS doc_id,
                       d.title AS doc_title,
                       d.category AS doc_category,
                       rep_chunk.id AS chunk_id,
                       rep_chunk.text AS chunk_text,
                       overlap
                LIMIT $limit
                """, {'names': list(entity_names), 'exclude': exclude, 'limit': limit})
                return [dict(r) for r in result]
        except Exception as e:
            logger.error(f"Error getting documents for entities: {str(e)}")
            return []