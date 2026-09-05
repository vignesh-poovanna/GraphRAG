# GraphRAG Visualization Guide: Vector Space & Knowledge Graph

This guide provides everything you need to visualize, explore, and analyze your **Vector Database (Qdrant)** and **Knowledge Graph (Neo4j)** for technical documentation, system understanding, and personal reference.

---

## 1. Quick Access Summary

| Visualization Tool | Access Point | Purpose |
| :--- | :--- | :--- |
| **Interactive GraphRAG Dashboard** | [graphrag_visualizer.html](file:///c:/Users/vigne/OneDrive/Desktop/GraphRAG/visualizations/graphrag_visualizer.html) | All-in-one 2D/3D Vector Space + Interactive Knowledge Graph + Payload Inspector |
| **Neo4j Browser (Native)** | [http://localhost:7474](http://localhost:7474) | Interactive Cypher queries, graph node styling, high-res PNG/SVG graph export |
| **Qdrant Web UI (Native)** | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | Point exploration, payload filtering, vector dimensionality verification |

---

## 2. Interactive GraphRAG Visualizer Dashboard

An automated generator script pulls live data from your running Docker containers and compiles an interactive, dark-mode dashboard.

### How to Open It
Open the generated file in any web browser (e.g., double-click or drag into Chrome/Edge):
```text
c:\Users\vigne\OneDrive\Desktop\GraphRAG\visualizations\graphrag_visualizer.html
```

### How to Regenerate After Ingesting New Docs
Whenever you import new documents via `scripts/import_docs.py` or run `scripts/extract_concepts.py`, regenerate the visualization with:
```powershell
.\venv\Scripts\python.exe scripts/generate_visualizations.py
```

### Dashboard Features

#### 🌌 Tab 1: Vector Space Explorer (Qdrant)
- **2D t-SNE & 3D PCA Projections**: Compresses the 384-dimensional `all-MiniLM-L6-v2` embeddings into human-readable 2D/3D coordinate space using Scikit-Learn.
- **Semantic Clustering**: Document chunks group naturally by subsystem: *ADCS, Communications, Power Subsystem, Fault Handling, Orbit Mechanics, etc.*
- **Interactive Chunk Inspector**: Hover or click on any point in the scatter plot to inspect the exact chunk text, category, position index, and document source.
- **Keyword Filtering**: Type keywords (e.g. `battery`, `antenna`, `safe mode`) to highlight matching points in vector space.
- **Export**: Click the camera icon on the top-right of the plot to export a high-resolution PNG for documentation.

#### 🕸️ Tab 2: Knowledge Graph Explorer (Neo4j)
- **Force-Directed Physics Layout**: Interactive physics simulation using `vis-network`.
- **Node Classification**:
  - 🟡 **Documents (Hexagons)**: 12 root documents.
  - 🔵 **Chunks (Dots)**: Text chunks connected via `HAS_CHUNK` and sequential `NEXT` edges.
  - 🌸 **Entities (Boxes)**: Domain concepts (*CubeSat, Solar Panels, Orbit, ADCS, Battery Chemistry*) connected via `MENTIONS` and `RELATED_TO`.
- **View Filters**:
  - *Complete Graph*: Full structural and conceptual network.
  - *Entity Knowledge Graph (Ontology)*: Clean view showing only domain entities and cross-concept relationships.
  - *Document Hierarchy*: Structural view of documents and chunk chains.
- **Search & Focus**: Search for any entity name to automatically zoom in and isolate its connections.

#### ⚡ Tab 3: Duality Architecture Breakdown
- Technical comparison between **Latent Semantic Search** (Vector Proximity) and **Symbolic Relational Context** (Knowledge Graph Traversal).
- Concrete walkthrough of a multi-hop query (*"What happens if battery voltage drops below threshold in safe mode?"*).

---

## 3. Neo4j Native Browser: Visualizing the Graph

Neo4j includes a browser interface accessible at [http://localhost:7474](http://localhost:7474).

- **URL**: `http://localhost:7474`
- **Username**: `neo4j`
- **Password**: `password`

### Curated Cypher Queries for Graph Inspection

Run these Cypher queries in the top query bar of Neo4j Browser to generate clear graph visualizations:

#### Query 1: Domain Entity Knowledge Graph
Shows the conceptual ontology and relationships between subsystems:
```cypher
MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity)
RETURN e1, r, e2
```

#### Query 2: Document-to-Chunk Hierarchy (Structural Graph)
Shows how documents break down into chunks:
```cypher
MATCH (d:Document)-[r:HAS_CHUNK]->(c:Chunk)
RETURN d, r, c
LIMIT 60
```

#### Query 3: Sequential Reading Chain (`NEXT` edges)
Shows how chunks retain narrative continuity across the document:
```cypher
MATCH (c1:Chunk)-[r:NEXT]->(c2:Chunk)
RETURN c1, r, c2
LIMIT 50
```

#### Query 4: Complete Bridge (Documents -> Chunks -> Entities)
Shows the complete bridge from source documents to domain knowledge:
```cypher
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[m:MENTIONS]->(e:Entity)
RETURN d, c, m, e
LIMIT 80
```

#### Query 5: Centrality / Hub Analysis
Finds the most connected entities in your knowledge graph:
```cypher
MATCH (e:Entity)-[r]-()
RETURN e.name AS Entity, count(r) AS Connections
ORDER BY Connections DESC
LIMIT 10
```

### Pro-Tips for Neo4j Visualization
1. **Node Colors & Sizes**: Click any node label pill at the top of the Neo4j visualization (`Document`, `Chunk`, `Entity`) to choose custom colors and size.
2. **Display Meaningful Captions**: Click the `Entity` label pill and set the caption to `name`. Click the `Document` label pill and set the caption to `title`.
3. **Export Image**: Click the **Download** icon on the bottom right of the visualization pane in Neo4j Browser to export a clean PNG or SVG.

---

## 4. Qdrant Native Dashboard: Visualizing the Vector DB

Qdrant provides a web UI accessible at [http://localhost:6333/dashboard](http://localhost:6333/dashboard).

- **URL**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)
- **Collection**: `document_chunks`

### What to Explore in Qdrant Dashboard
1. **Collection Metrics**:
   - Total Points & Vector Dimensions: `384` (Model: `all-MiniLM-L6-v2`)
   - Distance Metric: `Cosine`
2. **Payload Inspection**:
   - Click on the `document_chunks` collection.
   - Click on individual points to view metadata payloads: `title`, `category`, `doc_id`, `position`, and text snippets.
3. **Interactive Filter Search**:
   - Test JSON filter queries such as:
     ```json
     {
       "must": [
         { "key": "category", "match": { "value": "Operations" } }
       ]
     }
     ```

---

## 5. Architecture & Duality Reference

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
   |   candidate chunks       |              | - Traverses NEXT &       |
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
