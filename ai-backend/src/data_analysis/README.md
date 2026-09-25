# `data_analysis` — local corpus snapshots

This package downloads a Qdrant collection (vectors + payloads) to local disk once, so that exploratory analysis with NumPy and pandas runs against a cached, versioned snapshot instead of querying the cloud on every notebook run. Everything lives in `corpus.py`.

> **Status: draft.** Downloading, versioning, loading and freshness checks work and are covered by offline tests. Several conveniences are declared but not implemented yet (see [Current state](#current-state)). The API may still change before the module is considered stable.

## Setup

The heavy dependencies are kept out of the server image and live in the opt-in `analysis` dependency group (`numpy`, `pandas`, `pyarrow`, `tqdm`, `ipywidgets`). From `ai-backend/`:

```bash
uv sync --group analysis
```

The module is imported as `src.data_analysis.corpus`, so `ai-backend/` must be on `sys.path` — the simplest way is to start the notebook kernel from that folder.

Two environment variables are needed only when a download actually happens: `QDRANT_URL` and `QDRANT_API_KEY` (the cloud cluster, not the `localhost` default of `.env.example`). **The module does not load `.env` by itself**; do it in the notebook before the first call:

```python
from dotenv import load_dotenv
load_dotenv(".env")          # path relative to ai-backend/
```

Opening a snapshot that is already on disk needs neither variable, nor network access.

## Usage

`load_last_export()` is the entry point to use by default; the other functions below are for specific cases.

```python
from src.data_analysis.corpus import load_last_export

corpus = load_last_export()                        # default: "wahlchat_chunks_prod"
corpus = load_last_export("some_other_collection") # any collection on the cluster
```

`load_last_export()` returns the most recent local snapshot of the collection. If there is none — no folder yet, or only the leftovers of an interrupted download — it downloads one first and then returns it. When a snapshot already exists, it **does not contact the cloud at all**: it will happily hand you an old snapshot. Checking for newer versions is your job for now (see [Freshness](#freshness)).

A specific snapshot, e.g. an older one kept for comparison, is opened by path:

```python
from src.data_analysis.corpus import Corpus, qdrant_root

corpus = Corpus.load(qdrant_root() / "wahlchat_chunks_prod" / "20260923T224500_<hash>")
```

Forcing a fresh download currently goes through the private function `_fetch_export()`:

```python
from src.data_analysis.corpus import Corpus, _fetch_export

path = _fetch_export("wahlchat_chunks_prod", keep_as_only=True)  # also deletes older snapshots
corpus = Corpus.load(path)
```

`keep_as_only=True` removes every older committed snapshot of that collection after the new one is safely written, **including any files you added inside them**. A production snapshot is roughly 5.5 GB (≈300k vectors as of September 2026), so keeping one copy per collection is recommended.

`scroll_limit` (default 2000) is the number of points per page and is the knob that controls peak memory during the download: the Qdrant client decodes each page into Python floats (~96 KB per 3072-dimensional vector) before it is written to disk, so 2000 points cost ~190 MB transiently and 20000 about 1.9 GB. It does not meaningfully change the download speed.

## The `Corpus` object

| attribute  | type                      | content                                                        |
|------------|---------------------------|----------------------------------------------------------------|
| `vectors`  | `np.ndarray`, `float32`, read-only memory map | one row per point, shape `(n_rows, n_dims)` |
| `ids`      | `np.ndarray` of `str`, read-only memory map   | Qdrant point ids (UUID strings)             |
| `meta`     | `pd.DataFrame`            | the payloads, one row per point                                |
| `manifest` | `Manifest`                | metadata of the snapshot, see below                            |
| `path`     | `Path`                    | the snapshot folder                                            |

The three containers are **aligned by position**: row `i` of `meta`, `vectors` and `ids` describe the same point. Filtering is therefore done on the dataframe and carried over as a mask:

```python
mask = (corpus.meta["source_type"] == "party_manifesto").to_numpy()
subset = corpus.vectors[mask]
```

Payloads are heterogeneous across source types, so a column that a point does not carry is `NaN` in `meta`.

### Memory

Opening a snapshot costs almost nothing: the vectors are memory-mapped and read from disk only when touched. What you do with them decides how much RAM you use:

- **Reductions stream.** `corpus.vectors.mean(axis=0)`, `.min()`, `.max()` walk the file through the operating system's page cache without allocating a copy.
- **Fancy and boolean indexing copy.** `corpus.vectors[mask]` materialises the selected rows in RAM; with the full production corpus that is ~3.7 GB per full copy. Select only what you need, or work in chunks (`corpus.vectors[i:i + 10_000]` is a view, not a copy).
- **Element-wise operations on the whole array copy.** `np.isfinite(corpus.vectors)` or `corpus.vectors * 2` allocate a new full-size array.

The arrays are read-only on purpose: an in-place write would otherwise go straight into the snapshot file. Use `np.array(corpus.vectors[...])` to get a writable copy.

## Storage layout

```
<qdrant root>
├── wahlchat_chunks_prod
│   ├── 20260923T224500_<snapshot-hash>
│   │   ├── vectors.npy
│   │   ├── ids.npy
│   │   ├── payloads.parquet
│   │   └── manifest.json
│   └── 20260924T091200_<snapshot-hash>
└── another_collection
```

The root is resolved by `qdrant_root()`:

- if `WAHLCHAT_CORPUS_DIR` is set, it **is** the root, i.e. the folder that directly contains one sub-folder per collection (see `.env.example`);
- otherwise it is `<project root>/local/qdrant`, where the project root is the repository root, or the folder holding `.bare` in a bare-repository + worktree setup. In that setup every worktree therefore already resolves to the same shared folder. `/local/` is git-ignored.

Version folders are named `<UTC export time>_<snapshot hash>`. The time comes first and has a fixed width, so **alphabetical order is chronological order**: that is how `load_last_export()` finds the newest snapshot. Do not rename these folders.

A download is written into a hidden staging folder `.<timestamp>.partial` inside the collection folder and renamed to its final name only at the end; `manifest.json` is written last and its presence is what marks a folder as a complete snapshot. Folders without a manifest are ignored when looking for versions.

### The manifest

| field             | meaning                                                                          |
|-------------------|----------------------------------------------------------------------------------|
| `schema_version`  | version of the on-disk layout (not of the data); a mismatch refuses to load     |
| `collection`      | source collection name                                                           |
| `exported_at`     | UTC timestamp of the download, same format as the folder name                    |
| `snapshot_hash`   | content identity of the snapshot, see below                                      |
| `point_count`     | points reported by the server, fingerprint sentinel excluded                     |
| `n_rows`, `n_dims`| shape of the vectors actually written                                            |
| `embedding`       | the collection's embedding-space fingerprint (provider, model, dimension)        |
| `payload_columns` | sorted payload keys found across the corpus                                      |

## Versioning and freshness

### What the snapshot hash identifies

The snapshot hash is a SHA-256 over the sorted pairs `(point id, content_hash)` plus the sorted payload column names. `content_hash` is the payload field the ingestion mappers compute from the source text **before** embedding; points without one contribute an empty string. Consequences worth knowing:

- the hash does not depend on the order in which Qdrant returns points;
- it changes when a chunk is added, removed, or its source content changes, and when the set of payload fields changes;
- it is **not** computed from the vectors, so re-embedding the same content with a different model leaves it unchanged. The embedding space is recorded separately, in `manifest.embedding`.

The fingerprint sentinel point that the ingestion pipeline stores in each collection (`setup_collection.write_fingerprint`) is infrastructure, not a chunk: it is excluded from the download, from every count and from the hash.

### Freshness

```python
from qdrant_client import QdrantClient
from src.data_analysis.corpus import is_stale

client = QdrantClient(url=..., api_key=...)
is_stale(client, "wahlchat_chunks_prod", corpus.manifest)                 # level="count"
is_stale(client, "wahlchat_chunks_prod", corpus.manifest, level="exact")
```

- `level="count"` is one cheap request. It returns `True` if the number of points changed and `None` otherwise: an unchanged count proves nothing, since a corrected chunk is re-upserted under the same id.
- `level="exact"` recomputes the hash remotely by scrolling every payload (no vectors). It returns `True` or `False`, but costs a full pass over the collection's payloads.

## Validation and failure modes

A download is checked before it is committed, and raises `FetchingError` (after deleting the staging folder) when:

- the collection has no embedding-space fingerprint, or holds no points;
- a point has no named `"dense"` vector, or one of the wrong type or dimension;
- the collection grew, shrank or was rewritten while it was being downloaded (the point count is taken before and after);
- fewer points were written than the server reports, or the same point id appears twice;
- the fingerprint sentinel leaked into the data, or some vector contains `NaN`/`inf`.

A collection that does not exist raises `FileNotFoundError`. If ingestion is writing to the collection at the same time, the download fails rather than producing a mixed snapshot: wait for ingestion to finish and try again.

## Guidelines

- **Treat everything under the qdrant root as managed by the code**, except the inside of a version folder. Do not rename, move or hand-edit snapshot folders or their four files.
- **Derived artefacts may live next to the snapshot** they were computed from, which keeps expensive results tied to the exact data version:

  ```python
  try:
      mean = np.load(corpus.path / "mean.npy")
  except FileNotFoundError:
      mean = corpus.vectors.mean(axis=0)
      np.save(corpus.path / "mean.npy", mean)
  ```

  Remember that `keep_as_only=True` deletes them together with the old snapshot.
- **Record which snapshot a result came from**, e.g. `corpus.path.name`, so results stay comparable across versions.
- **A leftover `.<timestamp>.partial` folder** can only survive a hard kill (power loss, `kill -9`); failures and Ctrl-C clean up after themselves. It is ignored by the code and safe to delete by hand.
- **Mind the disk**: each production snapshot is several gigabytes.

## Current state

Implemented and tested: download with streaming to disk, atomic commit, timestamped versioning, pruning of old versions, loading as memory maps, count- and hash-based freshness checks, post-download validation.

Declared but not implemented yet:

- `load_last_export(check_for_new_updates=True)` is ignored with a warning; the intended default is to check for and fetch a newer version automatically.
- `Corpus.subset()` and `Corpus.cached()` raise `NotImplementedError`.
- `_add_symlink_to_local()` (linking a worktree to a shared `local/` folder) raises `NotImplementedError`.
- There is no public function to force a new download (use `_fetch_export()`), no retry on a failed scroll request, and an interrupted download restarts from zero.

## Tests

The tests replace Qdrant with an in-memory fake, so they run offline. From `ai-backend/`:

```bash
uv run --group analysis pytest tests/test_data_analysis_corpus.py
```

Without the `analysis` group installed they are skipped, so the regular backend test run is unaffected.
