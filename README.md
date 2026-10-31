# Student community detector

Finds groups of students with similar interests. Students are the vertices of a graph, an edge links two students whose interests overlap enough, and **BFS** and **DFS** find the connected groups (communities). A Flask API serves the results to an interactive web page where you can watch both searches run.

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The app starts with 48 sample students, so there is nothing to set up.

Run the tests with `python -m unittest discover -s tests -v`.

## How it works

1. **Similarity.** Each student has a set of interests. Two students are compared with Jaccard similarity: shared interests divided by all interests either has. Two students with `{python, chess}` and `{python, music}` score 1/3.
2. **Graph.** Students connect when their similarity reaches the threshold (the slider). Raising it makes the graph sparser and splits big groups; lowering it merges them.
3. **Communities.** A community is a connected component. BFS or DFS starts at an unvisited student, collects everyone reachable, and repeats until all students are placed. Both give the same groups; they visit students in a different order.
4. **Bridge students.** Tarjan's low-link algorithm (a DFS) finds students whose removal would split their community, and links whose removal would do the same.
5. **Quality.** Newman modularity scores how cleanly the groups separate (above 0.4 is a strong structure).
6. **Suggestions.** For a selected student, the app ranks students they are not yet connected to by shared interests and mutual connections, and uses BFS to report how many hops away each one is.

| Part | Algorithm | Time |
|---|---|---|
| Build graph | Pairwise Jaccard | O(n² · k) for k interests |
| Traversal, communities | BFS (queue), DFS (stack) | O(V + E) |
| Shortest path | BFS with parent links | O(V + E) |
| Bridge students and links | Tarjan low-link DFS | O(V + E) |
| Modularity | Edge count per group | O(V + E) |

## The web page

- **Threshold slider** re-detects communities live.
- **BFS / DFS switch**, then **Walk from selected student** animates the search. BFS spreads in rings of hops; DFS follows one chain and backs up. Visit order is numbered on each student. Double-clicking a student also starts a walk.
- **Shortest path** between the selected student and another (shift-click a student to choose the destination).
- **Communities list** shows each group's label, hub, average similarity and top interests. Click one to focus it.
- **Add, delete, import and export** students. Drag students to rearrange, scroll to zoom, drag the background to pan. Escape clears highlights.

## API

| Method and path | Purpose |
|---|---|
| `GET /api/graph?threshold=0.3&method=bfs` | Nodes, edges, communities and summary stats |
| `GET /api/traverse?start=1&algo=dfs&threshold=0.3` | Step-by-step visit order for animation |
| `GET /api/path?src=1&dst=9&threshold=0.3` | Fewest-hops path between two students |
| `GET /api/recommend/<id>?threshold=0.3` | Suggested connections for a student |
| `GET /api/interests` | Interests ranked by popularity |
| `POST /api/students` | Add a student: `{name, department, year, interests}` |
| `DELETE /api/students/<id>` | Remove a student |
| `GET /api/export.csv`, `POST /api/import` | CSV round trip (replaces all students on import) |
| `POST /api/reset` | Restore the sample data |

CSV columns: `name, department, year, interests`. Separate interests with semicolons, for example `python;chess;running`.

## Files

```
app.py            Flask routes and validation
graph_engine.py   Graph, BFS, DFS, components, shortest path, Tarjan, modularity
data.py           Seeded sample students
templates/        Page markup
static/           app.js (force layout, drawing, interaction) and style.css
tests/            Algorithm and API tests
```

## Notes

- Data lives in memory and resets when the server restarts. To keep it, export a CSV first.
- `app.py` runs Flask in debug mode for development. Turn `debug` off before sharing it on a network.
- Ideas to extend it: weight interests by rarity (TF-IDF) before comparing, add Louvain community detection for large dense graphs, or store students in SQLite.
