"""
Interactive graph visualization for PAIS entities and relationships.

Generates a standalone HTML file with an interactive network graph using Pyvis.
Open the generated HTML file in any browser to explore your activity graph.

Usage:
    python visualize_graph.py [options]
    
Options:
    --project PROJECT_NAME    Filter by specific project
    --days DAYS              Show entities from last N days (default: 30)
    --output FILE            Output HTML file (default: graph_visualization.html)
    --layout TYPE            Layout type: physics, hierarchical, or random (default: physics)
    
Examples:
    python visualize_graph.py                    # Show all recent entities
    python visualize_graph.py --project my-app   # Show only my-app project
    python visualize_graph.py --days 7           # Show last 7 days only
    python visualize_graph.py --output my-graph.html
"""

import argparse
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Check if pyvis is installed
try:
    from pyvis.network import Network
except ImportError:
    print("Error: pyvis is not installed.")
    print("\nInstall it with: pip install pyvis")
    print("\nOr add to requirements.txt:")
    print("pyvis>=0.3.1")
    exit(1)


# Color scheme for different entity types
ENTITY_COLORS = {
    "technology": "#4CAF50",  # Green
    "webpage": "#2196F3",     # Blue
    "file": "#FF9800",        # Orange
    "concept": "#9C27B0",     # Purple
    "person": "#F44336",      # Red
    "project": "#FFC107",     # Amber
    "activity": "#607D8B",    # Blue Grey
}

# Shape scheme for different entity types
ENTITY_SHAPES = {
    "technology": "dot",
    "webpage": "square",
    "file": "triangle",
    "concept": "diamond",
    "person": "star",
    "project": "hexagon",
    "activity": "box",
}


def get_db_path() -> str:
    """Get the database path from settings or use default."""
    # Try to import from config
    try:
        from config.settings import get_settings
        settings = get_settings()
        return settings.database.path
    except:
        # Default path
        return "data/activity_system.db"


def get_entities_and_relationships(
    db_path: str,
    project_filter: Optional[str] = None,
    days: int = 30,
) -> Tuple[List[Dict], List[Dict]]:
    """
    Fetch entities and relationships from the database.
    
    Returns:
        Tuple of (entities, relationships)
    """
    if not Path(db_path).exists():
        print(f"Error: Database not found at {db_path}")
        return [], []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Get entities
    if project_filter:
        # Get entities linked to a specific project through activities
        cursor.execute("""
            SELECT DISTINCT e.*
            FROM entities e
            JOIN relationships r ON (
                (r.from_type = 'entity' AND r.from_id = e.id AND r.to_type = 'activity')
                OR (r.to_type = 'entity' AND r.to_id = e.id AND r.from_type = 'activity')
            )
            JOIN activities a ON a.id = 
                CASE 
                    WHEN r.from_type = 'activity' THEN r.from_id
                    ELSE r.to_id
                END
            WHERE a.project_name = ? AND a.timestamp >= ?
            ORDER BY e.mention_count DESC
        """, (project_filter, since))
    else:
        # Get all recent entities
        cursor.execute("""
            SELECT * FROM entities
            WHERE last_seen >= ?
            ORDER BY mention_count DESC
            LIMIT 100
        """, (since,))
    
    entities = [dict(row) for row in cursor.fetchall()]
    entity_ids = {e['id'] for e in entities}
    
    # Get relationships between these entities
    if entities:
        placeholders = ','.join('?' * len(entity_ids))
        cursor.execute(f"""
            SELECT * FROM relationships
            WHERE (from_type = 'entity' AND from_id IN ({placeholders}))
               OR (to_type = 'entity' AND to_id IN ({placeholders}))
            ORDER BY created_at DESC
        """, list(entity_ids) + list(entity_ids))
        
        relationships = [dict(row) for row in cursor.fetchall()]
    else:
        relationships = []
    
    conn.close()
    return entities, relationships


def get_project_nodes(db_path: str, project_filter: Optional[str] = None) -> List[Dict]:
    """Get project nodes to add to the graph."""
    if not Path(db_path).exists():
        return []
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if project_filter:
        cursor.execute("SELECT * FROM projects WHERE name = ?", (project_filter,))
    else:
        cursor.execute("SELECT * FROM projects WHERE active = 1")
    
    projects = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return projects


def create_network_graph(
    entities: List[Dict],
    relationships: List[Dict],
    projects: List[Dict],
    layout: str = "physics",
) -> Network:
    """
    Create a Pyvis network graph from entities and relationships.
    """
    # Create network
    net = Network(
        height="800px",
        width="100%",
        bgcolor="#ffffff",
        font_color="#333333",
    )
    
    # Configure physics for smooth interaction with higher repulsion
    if layout == "physics":
        net.set_options("""
        {
          "physics": {
            "forceAtlas2Based": {
              "gravitationalConstant": -150,
              "centralGravity": 0.005,
              "springLength": 200,
              "springConstant": 0.05
            },
            "maxVelocity": 50,
            "solver": "forceAtlas2Based",
            "timestep": 0.35,
            "adaptiveTimestep": true,
            "stabilization": {
              "enabled": true,
              "iterations": 1000,
              "updateInterval": 25
            }
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 200,
            "hideEdgesOnDrag": true
          },
          "edges": {
            "smooth": {
              "type": "continuous",
              "forceDirection": "none"
            },
            "color": {
              "color": "#cccccc",
              "highlight": "#666666"
            }
          },
          "configure": {
            "enabled": true,
            "filter": ["physics", "nodes", "edges"],
            "showButton": true
          }
        }
        """)
    elif layout == "hierarchical":
        net.set_options("""
        {
          "layout": {
            "hierarchical": {
              "enabled": true,
              "direction": "UD",
              "sortMethod": "directed"
            }
          }
        }
        """)
    
    # Add project nodes
    project_ids = {}
    for project in projects:
        project_id = f"project_{project['id']}"
        project_ids[project['name']] = project_id
        
        # Parse keywords for tooltip
        keywords = project.get('keywords', '')
        if keywords:
            try:
                keywords_list = json.loads(keywords)
                keywords_str = ', '.join(keywords_list)
            except:
                keywords_str = keywords
        else:
            keywords_str = "No keywords"
        
        net.add_node(
            project_id,
            label=project['name'],
            title=f"Project: {project['name']}<br>Keywords: {keywords_str}",
            color=ENTITY_COLORS['project'],
            shape=ENTITY_SHAPES['project'],
            size=8,
            font={'size': 8, 'face': 'arial', 'color': '#333333'},
        )
    
    # Add entity nodes
    entity_id_map = {}
    for entity in entities:
        node_id = f"entity_{entity['id']}"
        entity_id_map[entity['id']] = node_id
        
        entity_type = entity.get('entity_type', 'unknown')
        color = ENTITY_COLORS.get(entity_type, '#999999')
        shape = ENTITY_SHAPES.get(entity_type, 'dot')
        
        # Build tooltip
        metadata = entity.get('metadata', '{}')
        try:
            meta_dict = json.loads(metadata) if metadata else {}
            meta_str = '<br>'.join([f"{k}: {v}" for k, v in meta_dict.items() if v])[:200]
        except:
            meta_str = str(metadata)[:200]
        
        title = f"{entity_type.title()}: {entity.get('display_name', entity['name'])}<br>Mentions: {entity.get('mention_count', 1)}"
        if meta_str:
            title += f"<br><br>Metadata:<br>{meta_str}"
        
        # Size based on mention count (scaled down)
        mentions = entity.get('mention_count', 1)
        size = min(6 + (mentions * 0.8), 12)
        
        net.add_node(
            node_id,
            label=entity.get('display_name', entity['name']),
            title=title,
            color=color,
            shape=shape,
            size=size,
            font={'size': 6, 'face': 'arial'},
        )
    
    # Add relationship edges
    for rel in relationships:
        if rel['from_type'] == 'entity' and rel['to_type'] == 'entity':
            from_id = entity_id_map.get(rel['from_id'])
            to_id = entity_id_map.get(rel['to_id'])
            
            if from_id and to_id:
                net.add_edge(
                    from_id,
                    to_id,
                    title=f"{rel['rel_type']} (confidence: {rel.get('confidence', 1.0)})",
                    label=rel['rel_type'],
                    arrows='to',
                )
    
    # Add edges from activities to entities (link projects to their entities)
    # This requires querying activity-entity relationships
    add_project_entity_edges(net, db_path=get_db_path(), projects=projects, entity_id_map=entity_id_map, project_ids=project_ids)
    
    return net


def add_project_entity_edges(
    net: Network,
    db_path: str,
    projects: List[Dict],
    entity_id_map: Dict[int, str],
    project_ids: Dict[str, str],
):
    """Add edges connecting projects to their frequently used entities."""
    if not Path(db_path).exists():
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    for project in projects:
        project_node_id = project_ids.get(project['name'])
        if not project_node_id:
            continue
        
        # Get top entities for this project
        cursor.execute("""
            SELECT e.id, COUNT(*) as usage_count
            FROM entities e
            JOIN relationships r ON (
                (r.from_type = 'entity' AND r.from_id = e.id AND r.to_type = 'activity')
                OR (r.to_type = 'entity' AND r.to_id = e.id AND r.from_type = 'activity')
            )
            JOIN activities a ON a.id = 
                CASE 
                    WHEN r.from_type = 'activity' THEN r.from_id
                    ELSE r.to_id
                END
            WHERE a.project_name = ?
            GROUP BY e.id
            ORDER BY usage_count DESC
            LIMIT 10
        """, (project['name'],))
        
        for row in cursor.fetchall():
            entity_node_id = entity_id_map.get(row[0])
            if entity_node_id:
                net.add_edge(
                    project_node_id,
                    entity_node_id,
                    title=f"uses ({row[1]} times)",
                    color={'color': '#ff9800', 'opacity': 0.6},
                    dashes=True,
                    arrows='to',
                )
    
    conn.close()


def generate_html_legend() -> str:
    """Generate HTML legend for the graph."""
    legend_items = []
    for entity_type, color in ENTITY_COLORS.items():
        legend_items.append(
            f'<div style="display: inline-block; margin: 5px 10px;">'
            f'<span style="display: inline-block; width: 20px; height: 20px; '
            f'background-color: {color}; border-radius: 50%; vertical-align: middle; '
            f'margin-right: 5px;"></span>'
            f'<span style="vertical-align: middle; text-transform: capitalize;">'
            f'{entity_type}</span></div>'
        )
    
    return (
        '<div style="background: #f5f5f5; padding: 15px; margin: 10px; '
        'border-radius: 5px; font-family: Arial, sans-serif;">'
        '<h3 style="margin-top: 0;">Legend</h3>'
        '<div>' + ''.join(legend_items) + '</div>'
        '<p style="margin-bottom: 0; font-size: 0.9em; color: #666;">'
        '<strong>Controls:</strong> Scroll to zoom • Drag to pan • Click nodes for details • '
        'Drag nodes to rearrange • Double-click to focus</p>'
        '</div>'
    )


def main():
    parser = argparse.ArgumentParser(
        description="Visualize PAIS activity knowledge graph",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python visualize_graph.py                    # Show all recent entities
  python visualize_graph.py --project my-app   # Show only my-app project
  python visualize_graph.py --days 7           # Show last 7 days only
  python visualize_graph.py --output graph.html
        """
    )
    
    parser.add_argument(
        '--project',
        type=str,
        help='Filter by specific project name',
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Show entities from last N days (default: 30)',
    )
    parser.add_argument(
        '--output',
        type=str,
        default='graph_visualization.html',
        help='Output HTML file (default: graph_visualization.html)',
    )
    parser.add_argument(
        '--layout',
        type=str,
        choices=['physics', 'hierarchical', 'random'],
        default='physics',
        help='Layout type (default: physics)',
    )
    
    args = parser.parse_args()
    
    print(f"Loading data from database...")
    db_path = get_db_path()
    print(f"Database: {db_path}")
    
    # Fetch data
    entities, relationships = get_entities_and_relationships(
        db_path=db_path,
        project_filter=args.project,
        days=args.days,
    )
    
    projects = get_project_nodes(db_path, args.project)
    
    if not entities:
        print("\nNo entities found. Try:")
        print("  - Running the system to collect some activities first")
        print(f"  - Checking if database exists at {db_path}")
        print(f"  - Extending the time range with --days")
        return
    
    print(f"Found {len(entities)} entities and {len(relationships)} relationships")
    if projects:
        print(f"Found {len(projects)} projects")
    
    # Create network
    print("\nGenerating interactive graph...")
    net = create_network_graph(entities, relationships, projects, layout=args.layout)
    
    # Add legend to the HTML
    legend_html = generate_html_legend()
    
    # Save the graph
    output_path = Path(args.output)
    net.save_graph(str(output_path))
    
    # Inject legend into the HTML
    html_content = output_path.read_text(encoding='utf-8')
    # Insert legend before the closing </body> tag
    if '</body>' in html_content:
        html_content = html_content.replace('</body>', legend_html + '</body>')
        output_path.write_text(html_content, encoding='utf-8')
    
    print(f"\nGraph saved to: {output_path.absolute()}")
    print(f"\nOpen this file in your browser to explore the graph!")
    print("\nControls:")
    print("  - Scroll to zoom in/out")
    print("  - Drag background to pan")
    print("  - Click nodes to see details")
    print("  - Drag nodes to rearrange")
    print("  - Use the physics toggle to stop/start animation")


if __name__ == "__main__":
    main()
