"""Extract package structure and optional dependency graph visualizations."""

import argparse
import ast
import csv
import json
from pathlib import Path


def extract_file_structure(file_path: str) -> list[dict[str, str | None]]:
    """Extract classes and functions from a Python file.

    Args:
        file_path: Path to the Python file to analyze.

    Returns:
        A list of dictionaries with keys: 'type' (Class/Function/Method), 'name',
          and 'parent' (for methods).
    """
    rows = []
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                rows.append({"type": "Class", "name": node.name, "parent": None})
                for sub_node in node.body:
                    if isinstance(sub_node, ast.FunctionDef):
                        rows.append(
                            {
                                "type": "Method",
                                "name": sub_node.name,
                                "parent": node.name,
                            }
                        )
            elif isinstance(node, ast.FunctionDef):
                rows.append({"type": "Function", "name": node.name, "parent": "Global"})
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    return rows


def iter_python_files(package_path: str) -> list[Path]:
    """Return all Python files under package_path."""
    base = Path(package_path)
    return [path for path in base.rglob("*.py") if path.is_file()]


def module_name_from_path(file_path: Path, package_root: Path) -> str:
    """Convert a file path to a Python module name rooted at package_root."""
    relative = file_path.relative_to(package_root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    base = package_root.name
    if not parts:
        return base
    return ".".join([base] + parts)


def resolve_relative_module(current_module: str, level: int, module: str | None) -> str:
    """Resolve import-from statements to an absolute-ish module name."""
    parts = current_module.split(".")
    package_parts = parts[:-1]

    up = max(level - 1, 0)
    if up > len(package_parts):
        base_parts: list[str] = []
    elif up == 0:
        base_parts = package_parts
    else:
        base_parts = package_parts[:-up]

    if module:
        base_parts = base_parts + module.split(".")

    return ".".join(base_parts)


def best_known_module(candidate: str, known_modules: set[str]) -> str | None:
    """Return the best matching known module for candidate."""
    if candidate in known_modules:
        return candidate

    prefix = f"{candidate}."
    matches = [module for module in known_modules if module.startswith(prefix)]
    if matches:
        return sorted(matches, key=len)[0]

    return None


def extract_internal_import_edges(
    package_path: str,
) -> tuple[list[str], list[tuple[str, str]]]:
    """Extract module-to-module dependency edges for internal package imports."""
    package_root = Path(package_path).resolve()
    py_files = iter_python_files(package_path)

    modules_by_file = {
        path: module_name_from_path(path.resolve(), package_root) for path in py_files
    }
    known_modules = set(modules_by_file.values())

    edges: set[tuple[str, str]] = set()

    for file_path, source_module in modules_by_file.items():
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        except Exception as e:
            print(f"Error parsing imports from {file_path}: {e}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = best_known_module(alias.name, known_modules)
                    if target and target != source_module:
                        edges.add((source_module, target))
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    base = node.module or ""
                else:
                    base = resolve_relative_module(source_module, node.level, node.module)

                target = best_known_module(base, known_modules) if base else None
                if target and target != source_module:
                    edges.add((source_module, target))

                for alias in node.names:
                    if base:
                        submodule_candidate = f"{base}.{alias.name}"
                    else:
                        submodule_candidate = alias.name
                    submodule_target = best_known_module(submodule_candidate, known_modules)
                    if submodule_target and submodule_target != source_module:
                        edges.add((source_module, submodule_target))

    modules = sorted(known_modules)
    sorted_edges = sorted(edges)
    return modules, sorted_edges


def generate_csv(output_csv: str = "code_structure.csv", package_path: str = ".") -> None:
    """Generate a CSV file with the structure of Python files in package_path."""
    all_data = []
    for file_path in iter_python_files(package_path):
        extracted_rows = extract_file_structure(str(file_path))
        for row in extracted_rows:
            row["file_path"] = str(file_path)
            all_data.append(row)

    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["file_path", "type", "name", "parent"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_data)
    print(f"Successfully exported structure to {output_csv}")


def generate_dependency_html(output_html: str, package_path: str) -> None:
    """Generate a draggable, zoomable HTML dependency graph."""
    modules, edges = extract_internal_import_edges(package_path)
    package_name = Path(package_path).resolve().name

    nodes_data = [
        {
            "id": module,
            "label": module.removeprefix(f"{package_name}."),
            "group": (
                module.removeprefix(f"{package_name}.").split(".")[0]
                if "." in module.removeprefix(f"{package_name}.")
                else module.removeprefix(f"{package_name}.")
            ),
        }
        for module in modules
    ]
    links_data = [{"source": source, "target": target} for source, target in edges]

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Package Dependency Graph</title>
  <style>
    :root {{
      --bg: #f2efe8;
      --fg: #1f2933;
      --muted: #52606d;
      --panel: rgba(255, 255, 255, 0.85);
      --link: #9aa5b1;
    }}
    html, body {{ height: 100%; margin: 0; }}
    body {{
      font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
      background: radial-gradient(circle at 20% 20%, #f8f5ee 0%, var(--bg) 70%);
      color: var(--fg);
      overflow: hidden;
    }}
    #toolbar {{
      position: fixed;
      top: 14px;
      left: 14px;
      z-index: 10;
      background: var(--panel);
      border: 1px solid #d2d6dc;
      border-radius: 12px;
      padding: 10px 12px;
      box-shadow: 0 6px 20px rgba(15, 23, 42, 0.14);
      backdrop-filter: blur(4px);
      max-width: 580px;
    }}
    #toolbar h1 {{
      font-size: 14px;
      margin: 0 0 6px 0;
      letter-spacing: 0.02em;
    }}
    #toolbar p {{
      margin: 0;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }}
    #graph {{ width: 100vw; height: 100vh; }}
    .link {{ stroke: var(--link); stroke-opacity: 0.55; stroke-width: 1.2px; }}
    .node circle {{ stroke: #ffffff; stroke-width: 1.2px; }}
    .node text {{
      font-size: 11px;
      fill: #102a43;
      pointer-events: none;
      text-shadow: 0 1px 1px rgba(255,255,255,0.8);
    }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
</head>
<body>
  <div id="toolbar">
    <h1>Package Dependency Graph</h1>
        <p>Drag nodes to rearrange. Scroll to zoom. Drag empty space to pan.</p>
        <p>Arrows indicate import direction (information flow): importer -> imported.</p>
    <p>Nodes: {len(nodes_data)} | Links: {len(links_data)}</p>
  </div>
  <svg id="graph"></svg>
  <script>
    const nodes = {json.dumps(nodes_data)};
    const links = {json.dumps(links_data)};
    const width = window.innerWidth;
    const height = window.innerHeight;

    const svg = d3.select("#graph");
    const root = svg.append("g");
        svg.call(
            d3.zoom()
                .scaleExtent([0.2, 5])
                .on("zoom", (event) => root.attr("transform", event.transform))
        );

        const defs = svg.append("defs");
        defs.append("marker")
            .attr("id", "arrowhead")
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 16)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("fill", "#9aa5b1");

    const color = d3.scaleOrdinal(d3.schemeTableau10);

        const levelById = new Map(nodes.map((n) => [n.id, 0]));
        for (let i = 0; i < 12; i += 1) {{
            links.forEach((edge) => {{
                const sourceId = edge.source.id ? edge.source.id : edge.source;
                const targetId = edge.target.id ? edge.target.id : edge.target;
                const sourceLevel = levelById.get(sourceId) ?? 0;
                const targetLevel = levelById.get(targetId) ?? 0;
                if (targetLevel < sourceLevel + 1) {{
                    levelById.set(targetId, sourceLevel + 1);
                }}
            }});
        }}

        const maxLevel = Math.max(1, ...levelById.values());
        const leftPadding = 120;
        const rightPadding = 120;
        const levelToX = (level) =>
            leftPadding + ((width - leftPadding - rightPadding) * level) / maxLevel;

        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(95).strength(0.25))
      .force("charge", d3.forceManyBody().strength(-220))
      .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide(24))
            .force("x", d3.forceX(d => levelToX(levelById.get(d.id) ?? 0)).strength(0.18))
            .force("y", d3.forceY(height / 2).strength(0.04));

    const link = root.append("g")
      .attr("stroke-linecap", "round")
      .selectAll("line")
      .data(links)
      .join("line")
            .attr("class", "link")
            .attr("marker-end", "url(#arrowhead)");

    const node = root.append("g")
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", "node")
      .call(d3.drag()
        .on("start", dragstarted)
        .on("drag", dragged)
        .on("end", dragended));

    node.append("circle")
      .attr("r", 8)
      .attr("fill", d => color(d.group));

    node.append("text")
      .attr("x", 11)
      .attr("y", 4)
            .text(d => d.label);

    simulation.on("tick", () => {{
      link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

      node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
    }});

    function dragstarted(event, d) {{
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }}

    function dragged(event, d) {{
      d.fx = event.x;
      d.fy = event.y;
    }}

    function dragended(event, d) {{
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }}
  </script>
</body>
</html>
"""

    Path(output_html).write_text(html, encoding="utf-8")
    print(f"Successfully exported dependency graph to {output_html}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract package structure and generate optional dependency graph HTML."
    )
    parser.add_argument(
        "package_path",
        nargs="?",
        default=".",
        help="Path to the package directory to scan (for example: src/pywandahydra)",
    )
    parser.add_argument(
        "--output-csv",
        default="code_structure.csv",
        help="Output CSV path for classes/functions inventory",
    )
    parser.add_argument(
        "--output-html",
        default=None,
        help="Optional output HTML path for interactive dependency graph",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    generate_csv(output_csv=args.output_csv, package_path=args.package_path)
    if args.output_html:
        generate_dependency_html(output_html=args.output_html, package_path=args.package_path)
