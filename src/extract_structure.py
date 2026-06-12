"""Extracts the structure of Python files in a specified directory and exports it to a CSV file."""

import ast
import csv
import os


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
                # Check for methods inside the class
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


def generate_csv(
    output_csv: str = "code_structure.csv", package_path: str = "."
) -> None:
    """Generate a CSV file with the structure of Python files in the specified directory.

    Args:
        output_csv: Name of the output CSV file (default: 'code_structure.csv').
        package_path: Path to the package directory to scan (default: '.' - current directory).
    """
    all_data = []
    for root, _, files in os.walk(package_path):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                extracted_rows = extract_file_structure(file_path)
                for row in extracted_rows:
                    row["file_path"] = file_path
                    all_data.append(row)

    # Write to CSV
    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["file_path", "type", "name", "parent"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_data)
    print(f"Successfully exported structure to {output_csv}")


if __name__ == "__main__":
    from pathlib import Path

    # Package path
    package_path = Path(__file__).parent / "pywandahydra"
    generate_csv(package_path=str(package_path))
