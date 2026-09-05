# GraphRAG Visualization Guide: Vector Space and Knowledge Graph

This guide explains how to inspect and explore the vector database (Qdrant) and knowledge graph (Neo4j) for documentation and technical reference.

---

## 1. Quick Access Summary

| Visualization Asset | Access Point | Purpose |
| :--- | :--- | :--- |
| **Knowledge Graph SVG** | `visualizations/knowledge-graph.svg` | Global topology of all Documents, Chunks, and Entities |
| **Entity Bridges SVG** | `visualizations/entity-bridges.svg` | Cross-document conceptual connection paths |
| **Inter-Entity SVG** | `visualizations/inter-entity.svg` | Concept-to-concept relationship network |
| **Neo4j Browser (Native)** | http://localhost:7474 | Interactive Cypher queries, graph node styling, PNG/SVG export |
| **Qdrant Web UI (Native)** | http://localhost:6333/dashboard | Point exploration, payload filtering, vector dimensionality verification |

---

## 2. Pre-Rendered SVG Visualizations

The `visualizations/` folder contains pre-rendered SVG architecture maps of the live database:

1. **`visualizations/knowledge-graph.svg`**:
   - Complete layout of all Document root nodes, sequentially ordered Chunk nodes, and extracted Entity nodes.
2. **`visualizations/entity-bridges.svg`**:
   - Demonstrates how shared conceptual entities bridge distinct source documents together.
3. **`visualizations/inter-entity.svg`**:
   - Pure conceptual ontology view showing direct `:RELATED_TO` edges between domain concepts.

---

## 3. Neo4j Native Browser: Visualizing the Graph

Neo4j includes a local web console accessible at http://localhost:7474.

- **URL**: `http://localhost:7474`
- **Username**: `neo4j`
- **Password**: `password`

### Curated Cypher Queries for Graph Inspection

Execute these Cypher queries in the top query bar of Neo4j Browser:

#### Query 1: Cross-Document Entity Bridges (Recommended)
Shows how specific technical concepts bridge chunks across different source documents:
```cypher
MATCH (d1:Document)-[:HAS_CHUNK]->(c1:Chunk)-[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(c2:Chunk)<-[:HAS_CHUNK]-(d2:Document)
WHERE d1 <> d2
RETURN d1.title, c1, e, c2, d2.title LIMIT 60;
```

#### Query 2: Entity Relationship Graph
Displays direct relationships between extracted concepts:
```cypher
MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
RETURN e1, r, e2 LIMIT 100;
```

#### Query 3: Document-to-Chunk Hierarchy
Visualizes how source documents decompose into sequentially linked chunks:
```cypher
MATCH (d:Document)-[r:HAS_CHUNK]->(c:Chunk)
RETURN d, r, c LIMIT 60;
```

#### Query 4: Sequential Reading Chain (NEXT edges)
Shows how chunks retain sequential narrative continuity across parent documents:
```cypher
MATCH (c1:Chunk)-[r:NEXT]->(c2:Chunk)
RETURN c1, r, c2 LIMIT 50;
```

#### Query 5: Centrality / Hub Analysis
Finds the most connected entities across the knowledge graph:
```cypher
MATCH (e:Entity)-[r]-()
RETURN e.name AS Entity, count(r) AS Connections
ORDER BY Connections DESC
LIMIT 10;
```

### Pro-Tips for Neo4j Visualization
1. **Node Colors and Sizes**: Click any node label pill at the top of the Neo4j visualization (`Document`, `Chunk`, `Entity`) to choose custom colors and sizes.
2. **Display Meaningful Captions**: Click the `Entity` label pill and set the caption to `name`. Click the `Document` label pill and set the caption to `title`.
3. **Export Image**: Click the Download icon on the bottom right of the visualization pane in Neo4j Browser to export a clean PNG or SVG.

---

## 4. Qdrant Native Dashboard: Visualizing the Vector DB

Qdrant provides an administrative web interface at http://localhost:6333/dashboard.

- **URL**: http://localhost:6333/dashboard
- **Collection**: `document_chunks`

### What to Explore in Qdrant Dashboard
1. **Collection Metrics**:
   - Total Points and Vector Dimensions: `384` (Model: `all-MiniLM-L6-v2`)
   - Distance Metric: `Cosine`
2. **Payload Inspection**:
   - Select the `document_chunks` collection.
   - Click individual points to inspect metadata payloads: `title`, `category`, `doc_id`, `position`, and raw text previews.
3. **Interactive Filter Search**:
   - Test JSON payload filtering:
     ```json
     {
       "must": [
         { "key": "category", "match": { "value": "operations" } }
       ]
     }
     ```

---

## 5. Architecture and Duality Reference

```
+-------------------------------------------------------------------------+
|                              USER QUERY                                 |
+------------------------------------+------------------------------------+
                                     |
                +--------------------+--------------------+
                |                                         |
                v                                         v
   +--------------------------+              +--------------------------+
   |   Qdrant Vector DB       |              |   Neo4j Knowledge Graph  |
   |   (Latent Space)         |              |   (Symbolic Topology)    |
   +--------------------------+              +--------------------------+
   | - 384D Embeddings        |              | - Documents              |
   | - Cosine Similarity      |              | - Chunks                 |
   | - Finds semantic seed    |              | - Entities               |
   |   candidate chunks       |              | - Traverses NEXT and     |
   |                          |              |   RELATED_TO multi-hop   |
   +------------+-------------+              +------------+-------------+
                |                                         |
                +--------------------+--------------------+
                                     |
                                     v
                        +--------------------------+
                        |  Hybrid Context Merger   |
                        +--------------------------+
                                     |
                                     v
                        +--------------------------+
                        |     LLM Generation       |
                        |   (Zero Hallucination)   |
                        +--------------------------+
```
