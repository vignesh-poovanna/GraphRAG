#!/usr/bin/env python3
"""
GraphRAG Visualization Generator
Extracts vector embeddings from Qdrant and knowledge graph topology from Neo4j,
computes 2D/3D dimensionality reductions, and generates a self-contained,
interactive visualizer dashboard (HTML) for documentation and reference.
"""

import os
import sys
import json
import numpy as np
from pathlib import Path
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA

# Connection defaults
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "document_chunks")

OUTPUT_DIR = Path("visualizations")
OUTPUT_HTML = OUTPUT_DIR / "graphrag_visualizer.html"


def fetch_qdrant_data():
    """Fetch all vectors and payloads from Qdrant."""
    print("[1/4] Fetching vector embeddings from Qdrant...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    
    # Scroll up to 2000 points
    points, _ = client.scroll(
        collection_name=QDRANT_COLLECTION,
        limit=2000,
        with_vectors=True,
        with_payload=True
    )
    
    print(f"      Retrieved {len(points)} vector records from collection '{QDRANT_COLLECTION}'.")
    
    records = []
    vectors = []
    
    for p in points:
        payload = p.payload or {}
        vec = p.vector
        if vec is not None:
            vectors.append(vec)
            records.append({
                "id": str(p.id),
                "title": payload.get("title", "Untitled"),
                "category": payload.get("category", "General"),
                "doc_id": payload.get("doc_id", "Unknown"),
                "chunk_type": payload.get("chunk_type", "text"),
                "position": payload.get("position", 0),
                "text": payload.get("text", "")[:400],  # preview
                "full_text_length": len(payload.get("text", ""))
            })
            
    vectors = np.array(vectors, dtype=np.float32)
    return records, vectors


def compute_projections(vectors):
    """Compute 2D t-SNE and 3D PCA coordinates."""
    print("[2/4] Computing 2D t-SNE and 3D PCA projections...")
    
    # 2D t-SNE
    perplexity = min(30, max(5, len(vectors) // 10))
    tsne = TSNE(n_components=2, perplexity=perplexity, random_state=42, max_iter=1000)
    coords_2d = tsne.fit_transform(vectors)
    
    # 3D PCA
    pca = PCA(n_components=3, random_state=42)
    coords_3d = pca.fit_transform(vectors)
    var_exp = [float(v) for v in pca.explained_variance_ratio_]
    
    print(f"      2D t-SNE complete. 3D PCA explained variance: {[round(x, 3) for x in var_exp]}")
    
    return coords_2d.tolist(), coords_3d.tolist(), var_exp


def fetch_neo4j_graph():
    """Fetch nodes and relationships from Neo4j."""
    print("[3/4] Fetching Knowledge Graph topology from Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    nodes = []
    edges = []
    node_id_map = {}
    
    with driver.session() as session:
        # 1. Fetch Document nodes
        docs = session.run("MATCH (d:Document) RETURN id(d) as nid, d.id as doc_id, d.title as title, d.category as category").data()
        for d in docs:
            nid = f"doc_{d['nid']}"
            node_id_map[d['nid']] = nid
            nodes.append({
                "id": nid,
                "label": d.get("title") or d.get("doc_id") or "Document",
                "group": "Document",
                "doc_id": d.get("doc_id"),
                "title": d.get("title"),
                "category": d.get("category", "General"),
                "size": 28
            })
            
        # 2. Fetch Chunk nodes
        chunks = session.run("""
            MATCH (c:Chunk) 
            RETURN id(c) as nid, c.id as chunk_id, c.position as position, 
                   substring(c.text, 0, 150) as preview, c.category as category
        """).data()
        for c in chunks:
            nid = f"chk_{c['nid']}"
            node_id_map[c['nid']] = nid
            nodes.append({
                "id": nid,
                "label": f"Chunk #{c.get('position', 0)}",
                "group": "Chunk",
                "chunk_id": c.get("chunk_id"),
                "position": c.get("position"),
                "preview": c.get("preview", ""),
                "category": c.get("category", "General"),
                "size": 12
            })
            
        # 3. Fetch Entity nodes
        entities = session.run("MATCH (e:Entity) RETURN id(e) as nid, e.name as name").data()
        for e in entities:
            nid = f"ent_{e['nid']}"
            node_id_map[e['nid']] = nid
            nodes.append({
                "id": nid,
                "label": e.get("name") or "Entity",
                "group": "Entity",
                "name": e.get("name"),
                "size": 18
            })
            
        # 4. Fetch Relationships
        rels = session.run("""
            MATCH (a)-[r]->(b)
            RETURN id(a) as from_id, id(b) as to_id, type(r) as rel_type
        """).data()
        
        for r in rels:
            from_nid = node_id_map.get(r["from_id"])
            to_nid = node_id_map.get(r["to_id"])
            if from_nid and to_nid:
                edges.append({
                    "from": from_nid,
                    "to": to_nid,
                    "label": r["rel_type"],
                    "type": r["rel_type"]
                })
                
    driver.close()
    print(f"      Retrieved {len(nodes)} nodes (Docs: {len(docs)}, Chunks: {len(chunks)}, Entities: {len(entities)}) and {len(edges)} relationships.")
    return nodes, edges


def generate_html(records, coords_2d, coords_3d, var_exp, graph_nodes, graph_edges):
    """Generate self-contained interactive visualizer."""
    print("[4/4] Assembling interactive HTML dashboard...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Merge vector data
    vector_points = []
    categories = set()
    docs = set()
    
    for i, r in enumerate(records):
        categories.add(r["category"])
        docs.add(r["title"])
        vector_points.append({
            "id": r["id"],
            "title": r["title"],
            "category": r["category"],
            "doc_id": r["doc_id"],
            "chunk_type": r["chunk_type"],
            "position": r["position"],
            "text": r["text"],
            "x2d": coords_2d[i][0],
            "y2d": coords_2d[i][1],
            "x3d": coords_3d[i][0],
            "y3d": coords_3d[i][1],
            "z3d": coords_3d[i][2],
        })
        
    dataset_json = json.dumps({
        "vector_points": vector_points,
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "stats": {
            "total_vectors": len(vector_points),
            "total_documents": sum(1 for n in graph_nodes if n["group"] == "Document"),
            "total_chunks": sum(1 for n in graph_nodes if n["group"] == "Chunk"),
            "total_entities": sum(1 for n in graph_nodes if n["group"] == "Entity"),
            "total_relations": len(graph_edges),
            "pca_variance": var_exp
        }
    })
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GraphRAG Visualizer | Vector Space & Knowledge Graph</title>
  <!-- Google Fonts & CDN Libraries -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    :root {{
      --bg-dark: #090d16;
      --bg-card: rgba(18, 24, 38, 0.75);
      --bg-card-border: rgba(255, 255, 255, 0.08);
      --accent-cyan: #00f2fe;
      --accent-blue: #4facfe;
      --accent-purple: #9d4edd;
      --accent-gold: #f59e0b;
      --accent-emerald: #10b981;
      --accent-rose: #f43f5e;
      --text-main: #f1f5f9;
      --text-muted: #94a3b8;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(circle at 10% 20%, rgba(79, 172, 254, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 90% 80%, rgba(157, 78, 221, 0.08) 0%, transparent 40%);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      overflow-x: hidden;
    }}

    /* Header */
    header {{
      background: rgba(10, 15, 29, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--bg-card-border);
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }}

    .brand {{
      display: flex;
      align-items: center;
      gap: 0.85rem;
    }}

    .logo-badge {{
      width: 40px;
      height: 40px;
      border-radius: 10px;
      background: linear-gradient(135deg, var(--accent-cyan), var(--accent-purple));
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 1.1rem;
      color: #fff;
      box-shadow: 0 4px 14px rgba(0, 242, 254, 0.3);
    }}

    .brand-title h1 {{
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      background: linear-gradient(90deg, #ffffff, #cbd5e1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .brand-title p {{
      font-size: 0.78rem;
      color: var(--text-muted);
    }}

    /* Quick stats header chips */
    .stat-pills {{
      display: flex;
      gap: 0.75rem;
      align-items: center;
    }}

    .pill {{
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--bg-card-border);
      padding: 0.35rem 0.75rem;
      border-radius: 9999px;
      font-size: 0.78rem;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-muted);
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }}

    .pill-val {{
      color: #fff;
      font-weight: 600;
    }}

    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }}
    .dot-cyan {{ background: var(--accent-cyan); box-shadow: 0 0 8px var(--accent-cyan); }}
    .dot-purple {{ background: var(--accent-purple); box-shadow: 0 0 8px var(--accent-purple); }}
    .dot-gold {{ background: var(--accent-gold); box-shadow: 0 0 8px var(--accent-gold); }}

    /* Navigation Tabs */
    .tab-bar {{
      display: flex;
      gap: 0.5rem;
      padding: 0.75rem 2rem 0;
      background: rgba(13, 19, 33, 0.5);
      border-bottom: 1px solid var(--bg-card-border);
    }}

    .tab-btn {{
      padding: 0.65rem 1.25rem;
      border: none;
      background: transparent;
      color: var(--text-muted);
      font-family: 'Outfit', sans-serif;
      font-size: 0.92rem;
      font-weight: 500;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}

    .tab-btn:hover {{
      color: #fff;
    }}

    .tab-btn.active {{
      color: var(--accent-cyan);
      border-bottom: 2px solid var(--accent-cyan);
      font-weight: 600;
    }}

    /* Main Content Container */
    main {{
      flex: 1;
      padding: 1.5rem 2rem;
      display: flex;
      flex-direction: column;
      gap: 1.5rem;
    }}

    .tab-panel {{
      display: none;
      flex-direction: column;
      gap: 1.25rem;
      height: 100%;
    }}

    .tab-panel.active {{
      display: flex;
    }}

    /* Controls Toolbar */
    .toolbar {{
      background: var(--bg-card);
      border: 1px solid var(--bg-card-border);
      border-radius: 12px;
      padding: 0.75rem 1.25rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 1rem;
    }}

    .toolbar-group {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
    }}

    .control-label {{
      font-size: 0.82rem;
      color: var(--text-muted);
      font-weight: 500;
    }}

    .btn {{
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid var(--bg-card-border);
      color: var(--text-main);
      padding: 0.45rem 0.9rem;
      border-radius: 8px;
      font-size: 0.82rem;
      font-family: inherit;
      cursor: pointer;
      transition: all 0.2s;
    }}

    .btn:hover {{
      background: rgba(255, 255, 255, 0.12);
      border-color: rgba(255, 255, 255, 0.2);
    }}

    .btn.active {{
      background: linear-gradient(135deg, rgba(0, 242, 254, 0.2), rgba(79, 172, 254, 0.2));
      border-color: var(--accent-cyan);
      color: var(--accent-cyan);
      font-weight: 600;
    }}

    select, input[type="text"] {{
      background: rgba(10, 15, 29, 0.8);
      border: 1px solid var(--bg-card-border);
      color: var(--text-main);
      padding: 0.45rem 0.85rem;
      border-radius: 8px;
      font-size: 0.82rem;
      font-family: inherit;
      outline: none;
    }}

    select:focus, input[type="text"]:focus {{
      border-color: var(--accent-cyan);
    }}

    /* Viewer Stage & Drawer Layout */
    .stage-container {{
      display: grid;
      grid-template-columns: 1fr 340px;
      gap: 1.25rem;
      height: 720px;
    }}

    .viewport-card {{
      background: var(--bg-card);
      border: 1px solid var(--bg-card-border);
      border-radius: 16px;
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
    }}

    #vector-plot, #graph-canvas {{
      width: 100%;
      height: 100%;
      flex: 1;
    }}

    /* Detail Drawer */
    .detail-drawer {{
      background: var(--bg-card);
      border: 1px solid var(--bg-card-border);
      border-radius: 16px;
      padding: 1.25rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
      overflow-y: auto;
    }}

    .detail-drawer h3 {{
      font-size: 1.05rem;
      font-weight: 600;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}

    .drawer-empty {{
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      height: 100%;
      color: var(--text-muted);
      font-size: 0.85rem;
      gap: 0.75rem;
    }}

    .detail-item {{
      display: flex;
      flex-direction: column;
      gap: 0.3rem;
      padding-bottom: 0.75rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }}

    .detail-item .key {{
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      font-family: 'JetBrains Mono', monospace;
    }}

    .detail-item .val {{
      font-size: 0.88rem;
      color: #e2e8f0;
      word-break: break-word;
    }}

    .text-box {{
      background: rgba(0, 0, 0, 0.35);
      border: 1px solid var(--bg-card-border);
      border-radius: 8px;
      padding: 0.85rem;
      font-size: 0.82rem;
      line-height: 1.5;
      color: #cbd5e1;
      max-height: 250px;
      overflow-y: auto;
      font-family: 'Outfit', sans-serif;
    }}

    /* Architecture / Duality Tab */
    .duality-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1.5rem;
    }}

    .duality-card {{
      background: var(--bg-card);
      border: 1px solid var(--bg-card-border);
      border-radius: 16px;
      padding: 1.5rem;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }}

    .duality-card.vector-side {{
      border-top: 4px solid var(--accent-cyan);
    }}

    .duality-card.graph-side {{
      border-top: 4px solid var(--accent-purple);
    }}

    .card-badge {{
      display: inline-block;
      align-self: flex-start;
      padding: 0.3rem 0.7rem;
      border-radius: 6px;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .badge-vector {{
      background: rgba(0, 242, 254, 0.15);
      color: var(--accent-cyan);
    }}

    .badge-graph {{
      background: rgba(157, 78, 221, 0.15);
      color: var(--accent-purple);
    }}

    .feature-list {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 0.75rem;
      font-size: 0.9rem;
      color: #cbd5e1;
    }}

    .feature-list li {{
      display: flex;
      align-items: flex-start;
      gap: 0.6rem;
    }}

    .feature-list li::before {{
      content: "✦";
      color: var(--accent-cyan);
    }}
    .graph-side .feature-list li::before {{
      color: var(--accent-purple);
    }}

    /* Legend */
    .legend-box {{
      position: absolute;
      bottom: 1rem;
      left: 1rem;
      background: rgba(10, 15, 29, 0.85);
      backdrop-filter: blur(8px);
      border: 1px solid var(--bg-card-border);
      border-radius: 10px;
      padding: 0.6rem 0.9rem;
      display: flex;
      gap: 1rem;
      font-size: 0.75rem;
      z-index: 10;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 0.4rem;
    }}
    .legend-circle {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}

    /* Scrollbar Styling */
    ::-webkit-scrollbar {{
      width: 6px;
      height: 6px;
    }}
    ::-webkit-scrollbar-track {{
      background: rgba(0, 0, 0, 0.2);
    }}
    ::-webkit-scrollbar-thumb {{
      background: rgba(255, 255, 255, 0.15);
      border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
      background: rgba(255, 255, 255, 0.3);
    }}
  </style>
</head>
<body>

  <!-- Header -->
  <header>
    <div class="brand">
      <div class="logo-badge">GR</div>
      <div class="brand-title">
        <h1>GraphRAG Hybrid Visualizer</h1>
        <p>Qdrant Vector Database + Neo4j Knowledge Graph (CubeSat Knowledge Base)</p>
      </div>
    </div>
    
    <div class="stat-pills">
      <div class="pill">
        <span class="dot dot-cyan"></span>
        Vectors: <span class="pill-val">{len(vector_points)}</span>
      </div>
      <div class="pill">
        <span class="dot dot-gold"></span>
        Documents: <span class="pill-val">{sum(1 for n in graph_nodes if n["group"] == "Document")}</span>
      </div>
      <div class="pill">
        <span class="dot dot-purple"></span>
        Entities: <span class="pill-val">{sum(1 for n in graph_nodes if n["group"] == "Entity")}</span>
      </div>
      <div class="pill">
        Relations: <span class="pill-val">{len(graph_edges)}</span>
      </div>
    </div>
  </header>

  <!-- Navigation Tabs -->
  <div class="tab-bar">
    <button class="tab-btn active" onclick="switchTab('vector')">
      <span>🌌</span> Vector Space (Qdrant)
    </button>
    <button class="tab-btn" onclick="switchTab('graph')">
      <span>🕸️</span> Knowledge Graph (Neo4j)
    </button>
    <button class="tab-btn" onclick="switchTab('duality')">
      <span>⚡</span> GraphRAG Duality Explained
    </button>
    <button class="tab-btn" onclick="switchTab('portals')">
      <span>🔌</span> Database Portals & Cypher Queries
    </button>
  </div>

  <!-- Main Viewports -->
  <main>

    <!-- 1. VECTOR SPACE TAB -->
    <section id="tab-vector" class="tab-panel active">
      <div class="toolbar">
        <div class="toolbar-group">
          <span class="control-label">Projection Mode:</span>
          <button id="btn-2d" class="btn active" onclick="setVectorDim('2d')">2D t-SNE (Non-linear)</button>
          <button id="btn-3d" class="btn" onclick="setVectorDim('3d')">3D PCA (Variance Maximized)</button>
        </div>

        <div class="toolbar-group">
          <span class="control-label">Color By:</span>
          <select id="vector-color-select" onchange="updateVectorPlot()">
            <option value="title">Document Source</option>
            <option value="category">Category</option>
          </select>
        </div>

        <div class="toolbar-group">
          <input type="text" id="vector-search" placeholder="Filter by keyword..." oninput="filterVectorPoints(this.value)" />
          <button class="btn" onclick="resetVectorView()">Reset Zoom</button>
        </div>
      </div>

      <div class="stage-container">
        <div class="viewport-card">
          <div id="vector-plot"></div>
        </div>

        <div class="detail-drawer" id="vector-drawer">
          <h3><span>📍</span> Chunk Inspector</h3>
          <div id="vector-drawer-content" class="drawer-empty">
            <p>Hover or click any point in the scatter plot to inspect its semantic payload.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 2. KNOWLEDGE GRAPH TAB -->
    <section id="tab-graph" class="tab-panel">
      <div class="toolbar">
        <div class="toolbar-group">
          <span class="control-label">Filter View:</span>
          <button class="btn active" id="filter-all" onclick="filterGraph('all')">Complete Graph</button>
          <button class="btn" id="filter-entities" onclick="filterGraph('entities')">Entity Knowledge Graph (Ontology)</button>
          <button class="btn" id="filter-docs" onclick="filterGraph('docs')">Document Hierarchy</button>
        </div>

        <div class="toolbar-group">
          <span class="control-label">Physics:</span>
          <button id="btn-physics" class="btn active" onclick="togglePhysics()">Stabilize</button>
          <button class="btn" onclick="fitGraph()">Fit Graph</button>
        </div>

        <div class="toolbar-group">
          <input type="text" id="graph-search" placeholder="Search entity/doc..." oninput="searchGraph(this.value)" />
        </div>
      </div>

      <div class="stage-container">
        <div class="viewport-card">
          <div id="graph-canvas"></div>
          <div class="legend-box">
            <div class="legend-item"><span class="legend-circle" style="background:#f59e0b"></span> Document (12)</div>
            <div class="legend-item"><span class="legend-circle" style="background:#00f2fe"></span> Chunk (371)</div>
            <div class="legend-item"><span class="legend-circle" style="background:#ec4899"></span> Entity (48)</div>
          </div>
        </div>

        <div class="detail-drawer" id="graph-drawer">
          <h3><span>🔍</span> Node Inspector</h3>
          <div id="graph-drawer-content" class="drawer-empty">
            <p>Click on any node or edge in the network to inspect properties and relationships.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 3. DUALITY EXPLAINED TAB -->
    <section id="tab-duality" class="tab-panel">
      <div class="duality-grid">
        <div class="duality-card vector-side">
          <span class="card-badge badge-vector">Vector Database (Qdrant)</span>
          <h2>Latent Semantic Search</h2>
          <p style="color: var(--text-muted); font-size: 0.95rem;">
            Vector embeddings capture fuzzy conceptual similarity across 384 dimensions using cosine distance.
          </p>
          <ul class="feature-list">
            <li><strong>Strength:</strong> Finds relevant passages even when phrasing, synonyms, or vocabulary differ completely.</li>
            <li><strong>CubeSat Example:</strong> Querying <em>"power loss during eclipse"</em> retrieves battery discharge specs even if the word "blackout" was never indexed.</li>
            <li><strong>Blind Spot:</strong> Disconnected from structure—cannot traverse sequential chunks (what happened next) or find 2-hop entity relationships.</li>
          </ul>
        </div>

        <div class="duality-card graph-side">
          <span class="card-badge badge-graph">Knowledge Graph (Neo4j)</span>
          <h2>Symbolic Relational Context</h2>
          <p style="color: var(--text-muted); font-size: 0.95rem;">
            Explicit graph nodes connected by typed edges (<code>HAS_CHUNK</code>, <code>NEXT</code>, <code>MENTIONS</code>, <code>RELATED_TO</code>).
          </p>
          <ul class="feature-list">
            <li><strong>Strength:</strong> Multi-hop reasoning, strict chronological reading via <code>NEXT</code> edges, and domain ontology.</li>
            <li><strong>CubeSat Example:</strong> Knowing that <em>Solar Panels</em> are related to <em>Power Subsystem</em>, which connects to <em>Battery Chemistry</em>.</li>
            <li><strong>Synergy:</strong> Qdrant retrieves the seed entry point; Neo4j expands the surrounding neighborhood for hallucination-free generation!</li>
          </ul>
        </div>
      </div>

      <div class="duality-card" style="background: rgba(18, 24, 38, 0.5);">
        <h2>Retriever Synergy Pipeline</h2>
        <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: #a5f3fc; line-height: 1.8; background: rgba(0,0,0,0.3); padding: 1.25rem; border-radius: 10px;">
          1. User Query: "What happens if battery voltage drops below threshold in safe mode?"<br/>
          2. Qdrant Vector Search -> Returns top 3 candidate Chunks [chk_12, chk_45, chk_88] via Cosine Proximity.<br/>
          3. Neo4j Graph Traversal -> Expands [chk_12] -[:NEXT]-> [chk_13] (continuation paragraph) and -[:MENTIONS]-> (Entity: Safe Mode) -[:RELATED_TO]-> (Entity: ADCS).<br/>
          4. LLM Synthesis -> Synthesizes exact procedure with both semantic nuance AND complete chronological context.
        </div>
      </div>
    </section>

    <!-- 4. DATABASE PORTALS & QUERIES TAB -->
    <section id="tab-portals" class="tab-panel">
      <div class="duality-grid">
        <div class="duality-card">
          <h2>Neo4j Browser & Cypher Queries</h2>
          <p style="color: var(--text-muted); font-size: 0.88rem;">
            Access the native Neo4j Browser UI at <a href="http://localhost:7474" target="_blank" style="color:var(--accent-cyan);">http://localhost:7474</a> (Auth: <code>neo4j</code> / <code>password</code>).
          </p>
          <div style="display:flex; flex-direction:column; gap: 0.75rem;">
            <div style="background:rgba(0,0,0,0.35); padding:0.85rem; border-radius:8px; border:1px solid var(--bg-card-border);">
              <span style="font-size:0.75rem; color:var(--accent-purple); font-weight:600;">Entity Ontology Graph</span>
              <div style="font-family:'JetBrains Mono'; font-size:0.78rem; color:#cbd5e1; margin-top:0.3rem;">
                MATCH (e1:Entity)-[r:RELATED_TO]->(e2:Entity) RETURN e1, r, e2;
              </div>
            </div>
            <div style="background:rgba(0,0,0,0.35); padding:0.85rem; border-radius:8px; border:1px solid var(--bg-card-border);">
              <span style="font-size:0.75rem; color:var(--accent-gold); font-weight:600;">Document Hierarchy</span>
              <div style="font-family:'JetBrains Mono'; font-size:0.78rem; color:#cbd5e1; margin-top:0.3rem;">
                MATCH (d:Document)-[r:HAS_CHUNK]->(c:Chunk) RETURN d, r, c LIMIT 50;
              </div>
            </div>
            <div style="background:rgba(0,0,0,0.35); padding:0.85rem; border-radius:8px; border:1px solid var(--bg-card-border);">
              <span style="font-size:0.75rem; color:var(--accent-cyan); font-weight:600;">Sequential Chunk Reading Chain</span>
              <div style="font-family:'JetBrains Mono'; font-size:0.78rem; color:#cbd5e1; margin-top:0.3rem;">
                MATCH (c1:Chunk)-[r:NEXT]->(c2:Chunk) RETURN c1, r, c2 LIMIT 50;
              </div>
            </div>
          </div>
        </div>

        <div class="duality-card">
          <h2>Qdrant Web UI & Metrics</h2>
          <p style="color: var(--text-muted); font-size: 0.88rem;">
            Access the native Qdrant Dashboard at <a href="http://localhost:6333/dashboard" target="_blank" style="color:var(--accent-cyan);">http://localhost:6333/dashboard</a>.
          </p>
          <div style="display:flex; flex-direction:column; gap: 0.75rem;">
            <div style="background:rgba(0,0,0,0.35); padding:0.85rem; border-radius:8px; border:1px solid var(--bg-card-border);">
              <span style="font-size:0.75rem; color:var(--accent-cyan); font-weight:600;">Collection: document_chunks</span>
              <p style="font-size:0.8rem; color:var(--text-muted); margin-top:0.3rem;">
                Points: <code>371</code> | Dimensions: <code>384</code> (Model: <code>all-MiniLM-L6-v2</code>) | Metric: <code>Cosine</code>
              </p>
            </div>
            <div style="background:rgba(0,0,0,0.35); padding:0.85rem; border-radius:8px; border:1px solid var(--bg-card-border);">
              <span style="font-size:0.75rem; color:#10b981; font-weight:600;">Metadata Payload Fields</span>
              <p style="font-size:0.8rem; color:var(--text-muted); margin-top:0.3rem;">
                <code>title</code>, <code>category</code>, <code>doc_id</code>, <code>chunk_type</code>, <code>position</code>, <code>text</code>
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>

  </main>

  <script>
    // Embedded Data
    const DATA = {dataset_json};

    let currentDim = '2d';
    let network = null;
    let graphData = null;

    // --- TAB SWITCHING ---
    function switchTab(tabId) {{
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
      
      const targetBtn = event ? event.currentTarget : document.querySelector(`.tab-btn[onclick*="${{tabId}}"]`);
      if (targetBtn) targetBtn.classList.add('active');
      
      const panel = document.getElementById(`tab-${{tabId}}`);
      if (panel) panel.classList.add('active');

      if (tabId === 'vector') {{
        setTimeout(() => Plotly.Plots.resize('vector-plot'), 50);
      }} else if (tabId === 'graph') {{
        if (!network) initGraph();
        setTimeout(() => network.fit(), 50);
      }}
    }}

    // --- VECTOR PLOT (PLOTLY) ---
    function initVectorPlot() {{
      updateVectorPlot();
    }}

    function setVectorDim(dim) {{
      currentDim = dim;
      document.getElementById('btn-2d').classList.toggle('active', dim === '2d');
      document.getElementById('btn-3d').classList.toggle('active', dim === '3d');
      updateVectorPlot();
    }}

    function updateVectorPlot() {{
      const colorField = document.getElementById('vector-color-select').value;
      const pts = DATA.vector_points;

      // Group points by colorField
      const groups = {{}};
      pts.forEach(p => {{
        const key = p[colorField] || 'Other';
        if (!groups[key]) groups[key] = [];
        groups[key].push(p);
      }});

      const traces = [];
      const colors = [
        '#00f2fe', '#4facfe', '#9d4edd', '#f59e0b', '#10b981', 
        '#f43f5e', '#ec4899', '#8b5cf6', '#3b82f6', '#14b8a6', 
        '#eab308', '#f97316'
      ];
      let colIdx = 0;

      for (const [groupName, groupPts] of Object.entries(groups)) {{
        const color = colors[colIdx % colors.length];
        colIdx++;

        if (currentDim === '2d') {{
          traces.push({{
            name: groupName,
            x: groupPts.map(p => p.x2d),
            y: groupPts.map(p => p.y2d),
            mode: 'markers',
            type: 'scatter',
            customdata: groupPts,
            marker: {{
              size: 9,
              color: color,
              opacity: 0.82,
              line: {{ color: '#ffffff', width: 0.5 }}
            }},
            hovertemplate: '<b>%{{customdata.title}}</b><br>Chunk #%{{customdata.position}}<br><i>%{{customdata.category}}</i><extra></extra>'
          }});
        }} else {{
          traces.push({{
            name: groupName,
            x: groupPts.map(p => p.x3d),
            y: groupPts.map(p => p.y3d),
            z: groupPts.map(p => p.z3d),
            mode: 'markers',
            type: 'scatter3d',
            customdata: groupPts,
            marker: {{
              size: 5,
              color: color,
              opacity: 0.85
            }},
            hovertemplate: '<b>%{{customdata.title}}</b><br>Chunk #%{{customdata.position}}<extra></extra>'
          }});
        }}
      }}

      const layout = {{
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: {{ family: 'Outfit, sans-serif', color: '#94a3b8' }},
        margin: {{ l: 40, r: 20, t: 30, b: 40 }},
        legend: {{
          orientation: 'h',
          y: -0.15,
          font: {{ size: 10, color: '#cbd5e1' }}
        }},
        hoverlabel: {{
          bgcolor: '#1e293b',
          bordercolor: '#334155',
          font: {{ family: 'Outfit', color: '#f8fafc' }}
        }}
      }};

      if (currentDim === '2d') {{
        layout.xaxis = {{ gridcolor: 'rgba(255,255,255,0.06)', zerolinecolor: 'rgba(255,255,255,0.1)' }};
        layout.yaxis = {{ gridcolor: 'rgba(255,255,255,0.06)', zerolinecolor: 'rgba(255,255,255,0.1)' }};
      }} else {{
        layout.scene = {{
          xaxis: {{ gridcolor: 'rgba(255,255,255,0.08)', backgroundcolor: 'rgba(0,0,0,0)' }},
          yaxis: {{ gridcolor: 'rgba(255,255,255,0.08)', backgroundcolor: 'rgba(0,0,0,0)' }},
          zaxis: {{ gridcolor: 'rgba(255,255,255,0.08)', backgroundcolor: 'rgba(0,0,0,0)' }}
        }};
      }}

      const config = {{
        responsive: true,
        displayModeBar: true,
        displaylogo: false,
        toImageButtonOptions: {{
          format: 'png',
          filename: 'graphrag_vector_space',
          height: 900,
          width: 1400,
          scale: 2
        }}
      }};

      Plotly.react('vector-plot', traces, layout, config);

      const plotEl = document.getElementById('vector-plot');
      plotEl.on('plotly_hover', function(data) {{
        if (data.points.length > 0) {{
          showChunkDetail(data.points[0].customdata);
        }}
      }});

      plotEl.on('plotly_click', function(data) {{
        if (data.points.length > 0) {{
          showChunkDetail(data.points[0].customdata);
        }}
      }});
    }}

    function showChunkDetail(item) {{
      const drawer = document.getElementById('vector-drawer-content');
      drawer.className = '';
      drawer.innerHTML = `
        <div class="detail-item">
          <span class="key">Document Title</span>
          <span class="val" style="font-weight:600; color:var(--accent-cyan);">${{item.title}}</span>
        </div>
        <div class="detail-item">
          <span class="key">Category</span>
          <span class="val">${{item.category}}</span>
        </div>
        <div class="detail-item">
          <span class="key">Chunk Index</span>
          <span class="val">Position #${{item.position}}</span>
        </div>
        <div class="detail-item">
          <span class="key">Vector ID</span>
          <span class="val" style="font-family:'JetBrains Mono'; font-size:0.75rem;">${{item.id}}</span>
        </div>
        <div class="detail-item">
          <span class="key">Text Content Preview</span>
          <div class="text-box">${{item.text}}...</div>
        </div>
      `;
    }}

    function resetVectorView() {{
      updateVectorPlot();
    }}

    function filterVectorPoints(term) {{
      const termLower = term.toLowerCase();
      // Plotly restyle opacity
      const plotEl = document.getElementById('vector-plot');
      if (!plotEl || !plotEl.data) return;

      plotEl.data.forEach((trace, traceIdx) => {{
        const opacities = trace.customdata.map(p => {{
          const match = p.title.toLowerCase().includes(termLower) ||
                        p.text.toLowerCase().includes(termLower) ||
                        p.category.toLowerCase().includes(termLower);
          return match ? 0.9 : 0.1;
        }});
        Plotly.restyle('vector-plot', {{ 'marker.opacity': [opacities] }}, [traceIdx]);
      }});
    }}

    // --- KNOWLEDGE GRAPH (VIS-NETWORK) ---
    function initGraph() {{
      const container = document.getElementById('graph-canvas');

      const visNodes = DATA.graph_nodes.map(n => {{
        let color = '#00f2fe';
        if (n.group === 'Document') color = '#f59e0b';
        if (n.group === 'Entity') color = '#ec4899';

        return {{
          id: n.id,
          label: n.label,
          group: n.group,
          value: n.size,
          shape: n.group === 'Document' ? 'hexagon' : (n.group === 'Entity' ? 'box' : 'dot'),
          color: {{
            background: color,
            border: '#ffffff',
            highlight: {{ background: '#ffffff', border: color }}
          }},
          font: {{
            color: '#f8fafc',
            face: 'Outfit',
            size: n.group === 'Document' ? 14 : (n.group === 'Entity' ? 12 : 9)
          }},
          raw: n
        }};
      }});

      const edgeColors = {{
        'HAS_CHUNK': 'rgba(245, 158, 11, 0.4)',
        'NEXT': 'rgba(0, 242, 254, 0.35)',
        'MENTIONS': 'rgba(236, 72, 153, 0.5)',
        'RELATED_TO': 'rgba(157, 78, 221, 0.6)'
      }};

      const visEdges = DATA.graph_edges.map(e => ({{
        from: e.from,
        to: e.to,
        label: e.type,
        color: {{
          color: edgeColors[e.type] || 'rgba(255,255,255,0.2)',
          highlight: '#ffffff'
        }},
        arrows: 'to',
        font: {{ size: 8, color: '#94a3b8', strokeWidth: 0, align: 'middle' }},
        raw: e
      }}));

      graphData = {{
        nodes: new vis.DataSet(visNodes),
        edges: new vis.DataSet(visEdges)
      }};

      const options = {{
        nodes: {{
          scaling: {{ min: 10, max: 30 }}
        }},
        edges: {{
          smooth: {{ type: 'continuous' }},
          width: 1
        }},
        physics: {{
          barnesHut: {{
            gravitationalConstant: -2800,
            centralGravity: 0.25,
            springLength: 95,
            springConstant: 0.04
          }},
          stabilization: {{ iterations: 120 }}
        }},
        interaction: {{
          hover: true,
          tooltipDelay: 100
        }}
      }};

      network = new vis.Network(container, graphData, options);

      network.on('click', function(params) {{
        if (params.nodes.length > 0) {{
          const nid = params.nodes[0];
          const node = graphData.nodes.get(nid);
          showGraphNodeDetail(node.raw);
        }}
      }});
    }}

    function showGraphNodeDetail(item) {{
      const drawer = document.getElementById('graph-drawer-content');
      drawer.className = '';
      drawer.innerHTML = `
        <div class="detail-item">
          <span class="key">Node Type</span>
          <span class="val" style="font-weight:700; color:var(--accent-purple);">${{item.group}}</span>
        </div>
        <div class="detail-item">
          <span class="key">Label / Name</span>
          <span class="val" style="font-weight:600;">${{item.label || item.name}}</span>
        </div>
        ${{item.category ? `
        <div class="detail-item">
          <span class="key">Category</span>
          <span class="val">${{item.category}}</span>
        </div>` : ''}}
        ${{item.position !== undefined ? `
        <div class="detail-item">
          <span class="key">Chunk Index</span>
          <span class="val">#${{item.position}}</span>
        </div>` : ''}}
        ${{item.preview ? `
        <div class="detail-item">
          <span class="key">Content Preview</span>
          <div class="text-box">${{item.preview}}...</div>
        </div>` : ''}}
      `;
    }}

    function filterGraph(mode) {{
      document.getElementById('filter-all').classList.toggle('active', mode === 'all');
      document.getElementById('filter-entities').classList.toggle('active', mode === 'entities');
      document.getElementById('filter-docs').classList.toggle('active', mode === 'docs');

      if (!network || !graphData) return;

      if (mode === 'all') {{
        DATA.graph_nodes.forEach(n => {{
          graphData.nodes.update({{ id: n.id, hidden: false }});
        }});
        DATA.graph_edges.forEach(e => {{
          graphData.edges.update({{ from: e.from, to: e.to, hidden: false }});
        }});
      }} else if (mode === 'entities') {{
        DATA.graph_nodes.forEach(n => {{
          const isEntityOrDoc = n.group === 'Entity' || n.group === 'Document';
          graphData.nodes.update({{ id: n.id, hidden: !isEntityOrDoc }});
        }});
      }} else if (mode === 'docs') {{
        DATA.graph_nodes.forEach(n => {{
          const isDocOrChunk = n.group === 'Document' || n.group === 'Chunk';
          graphData.nodes.update({{ id: n.id, hidden: !isDocOrChunk }});
        }});
      }}
      network.fit();
    }}

    let physicsEnabled = true;
    function togglePhysics() {{
      physicsEnabled = !physicsEnabled;
      network.setOptions({{ physics: {{ enabled: physicsEnabled }} }});
      document.getElementById('btn-physics').classList.toggle('active', physicsEnabled);
      document.getElementById('btn-physics').innerText = physicsEnabled ? 'Stabilize' : 'Enable Physics';
    }}

    function fitGraph() {{
      if (network) network.fit();
    }}

    function searchGraph(val) {{
      if (!network || !graphData) return;
      const lower = val.toLowerCase();
      if (!val) {{
        DATA.graph_nodes.forEach(n => graphData.nodes.update({{ id: n.id, opacity: 1 }}));
        return;
      }}
      const foundIds = [];
      DATA.graph_nodes.forEach(n => {{
        const match = (n.label && n.label.toLowerCase().includes(lower)) ||
                      (n.name && n.name.toLowerCase().includes(lower));
        graphData.nodes.update({{ id: n.id, opacity: match ? 1 : 0.15 }});
        if (match) foundIds.push(n.id);
      }});
      if (foundIds.length === 1) {{
        network.focus(foundIds[0], {{ scale: 1.2, animation: true }});
      }}
    }}

    // Init
    window.addEventListener('DOMContentLoaded', () => {{
      initVectorPlot();
    }});
  </script>
</body>
</html>
"""

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"      [SUCCESS] Generated visualizer at: {OUTPUT_HTML.resolve()}")
    return OUTPUT_HTML


def main():
    print("=" * 60)
    print("GraphRAG Visualization Pipeline")
    print("=" * 60)
    try:
        records, vectors = fetch_qdrant_data()
        coords_2d, coords_3d, var_exp = compute_projections(vectors)
        nodes, edges = fetch_neo4j_graph()
        output_file = generate_html(records, coords_2d, coords_3d, var_exp, nodes, edges)
        print("=" * 60)
        print(f"DONE! Visualizer ready: {output_file}")
        print("=" * 60)
    except Exception as e:
        print(f"[ERROR] Visualization pipeline failed: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
