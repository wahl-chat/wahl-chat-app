'''
Scrape the corpus, format it coherently, access already existing local snapshots. This script should contain everything that is needed in order to access a snapshot in a notebook.

I set up the script in order to allow for maximum flexibility. Therefore:
- any DB can be retrieved, even though the main one is likely to be the one to be interested in, hence set as default in various different methods
- different versions of the same DB can be stored at once, if one is ever interested in having a comparison. As of 19-09-26, the `prod` database contains ~300.000 vectors + metadata, that translate to roughly 5.5GB of local files, and that's not likely to diminish in the future. Therefore, keeping only one copy at a time is suggested.

Concerning how the files are organized: I tried to make the code as self-contained as possible. Ideally, one should be able to access the files by just calling the method `last_export()`, and the whole logic imposes some discipline in the handling of the hierarchical structure. 

The rule is pretty simple: don't touch anything inside the `qdrant` folder, except the actual folders of the version you're using. Those are, the deepest folders in the hierarchy. Inside of those, you're free to add other files, possibly numpy snapshots, or specific values that are dataset-specific and can therefore being recycled. A classical example: computing the mean over the whole corpus can be pretty expensive, so one can also decide to store it.

```python
corpus = last_export(COLLECTION_NAME)

try:
    mean = np.load(corpus.path / "mean.npy")
except:
    mean = corpus.vectors.mean()
    np.save(corpus.path / "mean.npy", mean)
```

The hierarchy logic is as follows: 
qdrant
├── name-collection-1
│   ├── 20260923T224500_<snapshot-hash>
│   │   ├── vectors.npy
│   │   ├── ids.npy
│   │   ├── payloads.parquet
│   │   └── manifest.json
│   └── 20260924T091200_<snapshot-hash>
└── name-collection-2

Version folders are named after the UTC export time followed by the snapshot hash. The time comes first and is fixed width on purpose: sorting the folder names alphabetically is what `last_export()` uses to find the most recent snapshot. `manifest.json` is written last, and its presence is what marks a folder as a complete snapshot rather than an interrupted download.

The `qdrant` folder can be placed anywhere in your laptop, given a variable that shall be added to your .env file. However this might also be skipped, since the code automatically fallbacks to the repository root, which is the most logical place in which such data shall live, that being `<project_root>/local/qdrant`. Ideally, other shared files that are external to the repository could live inside `<project_root>/local`. This procedure also makes some checks less buggy, I'll work on the implementation for more freedom in the next commits.

If you're using `git worktree`, I please you to add a symlink and behave as the files were inside the worktree you're performing analysis on. This is for consistency with other that might use a different setup. Future commits will also add support to handle such automatically.
'''

from __future__ import annotations

import os
import hashlib

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException
import httpx

import shutil
import json
import subprocess
import warnings

from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, UTC
from typing import Any, Iterable, Literal

import numpy as np
import pandas as pd
from tqdm.auto import tqdm

from src.ingestion.setup_collection import (
    read_fingerprint,
    FINGERPRINT_POINT_ID,
    FINGERPRINT_SOURCE_TYPE,
)

DEFAULT_PROD_DATABASE = "wahlchat_chunks_prod"
VECTORS, PAYLOADS, IDS, MANIFEST = "vectors.npy", "payloads.parquet", "ids.npy", "manifest.json"

# Version of the on-disk layout, NOT of the data: it lets a future reader refuse
# a snapshot written with a different file organisation instead of silently
# misreading gigabytes. Bump it whenever a change breaks `_load_corpus()`.
SCHEMA_VERSION = 1

# The fingerprint point is infrastructure (see `setup_collection.write_fingerprint`),
# not a corpus chunk: its vector is a synthetic [1, 0, 0, ...]. It has to be
# excluded identically from the export and from the remote hash, otherwise the
# two describe different point sets and can never be compared.
WITHOUT_FINGERPRINT = models.Filter(
    must_not=[
        models.FieldCondition(
            key="source_type",
            match=models.MatchValue(value=FINGERPRINT_SOURCE_TYPE),
        )
    ]
)

@dataclass
class Manifest:
    '''
    Dataclass that handles the format of the .json file containing metadata and general information about the snapshot.
    '''
    schema_version: int     # layout of the files on disk, see SCHEMA_VERSION
    collection: str
    exported_at: str
    snapshot_hash: str
    point_count: int        # points the server reported, fingerprint excluded
    embedding: dict         # provider/model/dim, i.e. which vector space these live in
    n_rows: int             # rows actually written to disk; < point_count means a truncated export
    n_dims: int
    payload_columns: list
##

# IMPORTANT
# Methods are kept outside of the `Corpus` declaration
# in order not to allow users to use the `.save()` module
# on corpus objects screwing up the logic of the code
# 
# These two should always be updated in pair, changes in one
# has a structural change on the other one

def _save_corpus(
    corpus: "Corpus",
    dest: Path,
    staging: Path | None = None
) -> Path:
    '''
    When `staging` is given, the vectors were already streamed into it by `_fetch_export()` and are not written a second time: only ids, payloads and the manifest are added before the rename.
    '''
    if staging is None:
        staging = dest.with_suffix(".partial")
        staging.mkdir(parents=True, exist_ok=True)
        np.save(staging / VECTORS, corpus.vectors)   # vectors

    np.save(staging / IDS, corpus.ids)           # ids
    corpus.meta.to_parquet(staging / PAYLOADS)   # payloads od data

    (staging / MANIFEST).write_text(json.dumps(asdict(corpus.manifest)))  # last
    os.replace(staging, dest)                  # renaming once versioning is finished
    return dest
##

def save_corpus(
    corpus: "Corpus",
    dest: Path,
    staging: Path | None = None
) -> Path:
    return _save_corpus(corpus, dest, staging)

def _load_corpus(
    cls, 
    path: Path
) -> "Corpus":

    manifest = Manifest(**json.loads((path / MANIFEST).read_text()))
    if manifest.schema_version != SCHEMA_VERSION:
        raise ValueError(
            f"snapshot at {path} was written with layout version {manifest.schema_version}, "
            f"this reader speaks version {SCHEMA_VERSION}"
        )

    # `np.load(..., mmap_mode="r")` parses the .npy header and then maps the
    # buffer lazily; plain `np.memmap` would read those header bytes as data.
    # Pages are pulled in on access, so opening a snapshot costs nothing.
    vectors = np.load(path / VECTORS, mmap_mode="r")
    ids = np.load(path / IDS, mmap_mode="r")
    meta = pd.read_parquet(path / PAYLOADS)

    return cls(
        meta=meta,
        vectors=vectors,
        ids=ids,
        manifest=manifest,
        path=path
    )
##

def load_corpus(path: Path):
    return _load_corpus(Corpus, path)

@dataclass
class Corpus:
    '''
    Main object retrieved by querying Qdrant. Contains full vector representation

    Attributes
    ----------
    - meta: pd.Dataframe containing the metadata associated within each sample, i.e. the Qdrant payloads
    - vectors: the actual embeddings, `float32` array of shape `(n_rows, n_dims)`, memory-mapped read-only
    - ids: the Qdrant point ids, as strings
    - manifest: `Manifest` describing the snapshot (collection, export time, snapshot hash, counts, embedding space)
    - path: folder of the snapshot on disk

    Usage
    -----
    The array and the dataframe are organised such that they share indexes by position. Therefore one can filter the embeddings of documents by masking on the `meta` Dataframe, then translate, as shown in the following snippet.

    ```python
    mask = Corpus.meta['region'] == 'DE'
    corrisponding_vectors = Corpus.vectors[mask]
    ```

    '''

    meta: pd.DataFrame
    vectors: np.ndarray
    ids: np.ndarray
    manifest: Manifest
    path: Path

    def __post_init__(self):
        '''
        Cheap, purely local invariants, checked on every construction — including when a snapshot is re-opened from disk.

        Everything that needs an open Qdrant client, or a full pass over the vectors, lives in `_validate_export()` instead: opening a local snapshot in a notebook must not depend on the cloud being reachable. These checks are free even under memmap, since `len()` and `.shape` read the .npy header rather than the data.
        '''
        if not (len(self.meta) == len(self.vectors) == len(self.ids)):
            raise ValueError(
                f"disalignment: {len(self.meta)} meta rows, {len(self.vectors)} vectors, {len(self.ids)} ids"
            )
        if self.vectors.ndim != 2 or self.vectors.shape[1] != self.manifest.n_dims:
            raise ValueError(
                f"vector shape {self.vectors.shape} contradicts the manifest ({self.manifest.n_dims} dims)"
            )
    ##

    @classmethod
    def load(cls, path: Path) -> "Corpus":
        '''
        Opens a committed snapshot folder. Vectors and ids are read-only memory maps, so nothing is read until accessed; raises `ValueError` if the snapshot was written with a different `SCHEMA_VERSION`.
        '''
        return _load_corpus(Corpus, path)
    ##


    # TODO: effectively implement in the future. Understand if this can be effectively useful.
    def subset(self, mask: np.ndarray) -> "Corpus":
        '''
        Returns another `Corpus` object by slicing the original set.
        '''
        raise NotImplementedError
    ##
    
    def cached(self, name:str):
        raise NotImplementedError('To implement in future commits: ease cache objects obtained from the corpus if they require heavy computation.')
    ##
##

class FetchingError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
##

def _validate_export(corpus: "Corpus") -> None:
    '''
    Acceptance tests on a freshly downloaded `Corpus`, run once by `_fetch_export()` right before saving.

    These are questions about the *download*, not about the object: whether the scroll reached the end, whether pagination handed back the same point twice, whether the vectors are usable numbers. They belong here rather than in `__post_init__` because they are expensive (a full pass over ~5.5GB) and because their reference point is the cloud, which by design is confined to the fetching path.
    '''
    if corpus.manifest.n_rows != corpus.manifest.point_count:
        raise FetchingError(
            f"incomplete export of '{corpus.manifest.collection}': the collection holds "
            f"{corpus.manifest.point_count} points, {corpus.manifest.n_rows} were downloaded"
        )
    # Offset pagination can re-serve a point if the collection is written to
    # mid-scroll; lengths alone would not notice, since a duplicate lands in
    # `meta` and `vectors` alike.
    if len(np.unique(corpus.ids)) != len(corpus.ids):
        raise FetchingError("duplicated point ids: the scroll returned the same point more than once")
    if FINGERPRINT_POINT_ID in set(corpus.ids.tolist()):
        raise FetchingError("the fingerprint sentinel leaked into the corpus: its synthetic vector is not a chunk")
    if not (np.isfinite(corpus.vectors.min()) and np.isfinite(corpus.vectors.max())):
        raise FetchingError("non-finite values among the downloaded vectors")
##

class Datetime(datetime):
    '''
    Standard `datetime` functionalities with easier representation strings
    
    UTC is enforced when constructing instances explicitly. This class does not attempt to enforce the invariant across every inherited datetime operation and shall not be used when trying to do so.
    ''' 
    def __new__(cls, *args, **kwargs):
        if len(args) == 8:  # if timezone is already passed as args
            kwargs.pop('tzinfo', None)
        return super().__new__(cls, *args, **kwargs)

    def __repr__(self) -> str:
        return f"{self.year:04d}{self.month:02d}{self.day:02d}T{self.hour:02d}{self.minute:02d}{self.second:02d}"
    def __str__(self):
        return self.__repr__()

    @classmethod
    def now(cls, tz=None):
        return super().now(UTC)
##


def project_root() -> Path:
    '''
    Needed to understand what kind of repository we're navigating through. Supposes that the folder uses `git`, which seems a really mild hypothesis to me. The root is asked directly to `git` as the parent of the common git directory, shared by every worktree.

    In a plain clone this is the parent of `.git`, i.e. the repository root. In a `git bare` + worktree setup it is the parent of the bare repository (e.g. `.bare`), i.e. the folder holding every worktree.
    '''
    path = Path(__file__).resolve()
    PATH = subprocess.check_output(
        ['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'],
        cwd=path.parent,
    ).decode("utf-8").split("\n")[0]
    if PATH:
        return Path(PATH).parent
    raise FileNotFoundError('Impossible to retrieve the project origin, neither .git or .bare anchors were found')
##

def worktree_root():
    '''
    Same as above, but retrieves the worktree. The two are identical if the repository was cloned without `--bare`.
    '''
    path = Path(__file__).resolve()

    for cand in path.parents:
        if Path(cand / '.git').exists():
            return cand
    raise FileNotFoundError('Impossible to retrieve the project origin, neither .git or .bare anchors were found')
##

def _is_setup_worktree():
    return project_root() != worktree_root()
##

def qdrant_root(redirect_to_default: bool = True) -> Path: 
    '''
    Retrieves the local folder in which the dataset is meant to be stored. `redirect_to_default` is used as a commodity, sets up a top level `local/qdrant` folder inside the project root, that is where I would personally store the files.

    Since this method is inherently called by all the scrapers below, the environment is also set up via mkdir. Symlinks are not handled yet, see `_add_symlink_to_local()`.

    Attributes
    ----------
    *redirect_to_default*: `bool`, *default* = `True`, if the .env files misses the `WAHLCHAT_CORPUS_DIR` var, then pivots to default, otherwise raises `EnvironmentError`.
    '''

    env = os.getenv("WAHLCHAT_CORPUS_DIR")
    if env:
        PATH = Path(env).expanduser()   # this does not check the existence though -> might be interesting 
        # return Path(env).resolve()
    elif redirect_to_default:
        # default is set to be a top directory, see method above
        PATH = project_root() / 'local' / 'qdrant'
    else:
        raise EnvironmentError('Unable to retrieve the .env variable. Ensure to set it up, or enable `redirect_to_default=True`')

    if not PATH.exists():
        PATH.mkdir(parents=True)
    return PATH
##

def _add_symlink_to_local():
    '''
    Utils method: adds a symlink inside the current worktree for setups that use `git worktree` + `.bare` combination. That way a worktree can see the `local` folder. This shall be done only if you're working with different active worktrees.

    '''
    raise NotImplementedError
##

def snapshot_hash(
    pairs: Iterable[tuple[str, str | None]],
    payload_cols: Iterable[str]
) -> str:
    '''
    SHA-256 executed on id-hash pair of points and on the payload column names, helper for `remote_snapshot_hash()`
    '''
    payload_cols = sorted(payload_cols)         # sorting happens to avoid scroll-dependent discrepancy
    gen = hashlib.sha256()
    for col_name in payload_cols:
        # the separator keeps ["ab", "c"] and ["a", "bc"] from hashing alike
        gen.update(f"{col_name}\n".encode())
    for pid, chash in sorted(pairs):
        gen.update(f"{pid}\x00{chash or ''}\n".encode())
    return gen.hexdigest()
##

def remote_snapshot_hash(
    client: QdrantClient, 
    collection: str
) -> str:
    '''
    SHA-256 executed on a given collection. Scrolls the items in the collection without loading the vectors and by computing hashes
    '''
    pairs, offset = [], None
    cols: set[str] = set()
    while True:
        points, offset = client.scroll(
            collection_name=collection,
            offset=offset,
            limit=10_000,
            scroll_filter=WITHOUT_FINGERPRINT,
            with_vectors=False,               
            with_payload=True, 
        )
        pairs += [(str(p.id), (p.payload or {}).get("content_hash")) for p in points]
        for p in points:
            cols.update((p.payload or {}).keys())   # dict_keys is unhashable, so no set([...keys()])
        if offset is None:
            break
    return snapshot_hash(pairs, cols)
##

def is_stale(
    client: QdrantClient, 
    collection: str, 
    local_manifest: Manifest,
    level: Literal['count', 'exact']="count"
) -> bool | None:
    '''
    Check if a new version of the collection is available on the cloud.

    Returns `True` when the local snapshot is provably out of date, `False` when it is provably current, and `None` when the check cannot tell. The cheap `count` level can only ever answer `True` or `None`: an unchanged number of points says nothing about the content, since a corrected chunk is re-upserted under the same id.
    '''
    try:
        if level == "count":
            remote_count = client.count(collection, count_filter=WITHOUT_FINGERPRINT, exact=True).count
            if remote_count != local_manifest.point_count:
                return True
            return None
        elif level == "exact":
            return remote_snapshot_hash(client, collection) != local_manifest.snapshot_hash
        else:
            raise TypeError("Invalid argument passed for `level`: current version supports values in ['count', 'exact']")
    # handle offline moments: if the user tries to access the corpus while offline it should not be a problem
    except ResponseHandlingException as exc:
        if isinstance(exc.source, httpx.TransportError) and not isinstance(exc.source, (httpx.LocalProtocolError, httpx.UnsupportedProtocol)):
            warnings.warn("Unable to connect with the server, no checks were performed with the ground truth collection.")
            return None
        else:
            raise
##


def _snapshot_versions(collection_dir: Path) -> list[Path]:
    '''
    The committed snapshots of one collection, oldest first.

    A snapshot counts as committed only once it holds a manifest: `_save_corpus()` writes that file last, so an interrupted download leaves behind a `.partial` folder without one. Filtering on it is not cosmetic, since `.partial` sorts *after* the folder it is a staging copy of and would otherwise be picked as the most recent version.
    '''
    return sorted(p for p in collection_dir.iterdir() if p.is_dir() and (p / MANIFEST).exists())
##


def last_export(
        collection: str = DEFAULT_PROD_DATABASE,
        check_for_new_updates: bool = False    # NOT IMPLEMENTED, but default shall be `True`
) -> Corpus:
    '''
    Returns the very last acquired snapshot of the database. It works by retrieving the path corresponding to a given folder representing a snapshot of the DB, then calls load_corpus() for consistency
    '''
    path = qdrant_root() / collection

    if not path.exists(): # -> if we don't have a downloaded version, also execute the downloading 
        path = _fetch_export(
            collection=collection,
            keep_as_only=False,
        )
        return load_corpus(path)
    
    ## TODO: add the routine for the new version check via call
    if check_for_new_updates:
        warnings.warn('Auto-updating is not implemented yet, flag `check_for_new_updates` is ignored.')

    versions = _snapshot_versions(path)
    if not versions:
        # the folder is there but holds nothing committed, e.g. only the leftovers
        # of an interrupted download: treat it as if it did not exist
        return load_corpus(_fetch_export(collection=collection, keep_as_only=False))

    last_version_path = versions[-1]
    return load_corpus(last_version_path)
##

def _fetch_export(
        collection: str = DEFAULT_PROD_DATABASE,
        keep_as_only: bool = False,
        scroll_limit: int = 2000,
) -> Path:
    '''
    Retrieve the full corpus and store it to the selected local folder. Returns the path of the committed snapshot.

    The vectors never live in RAM as a whole: each scrolled page is converted to `float32` and written straight into the final `.npy` file through a memory map, so the peak memory is one page of points rather than the whole corpus.

    Params
    ------
    - collection: str,
    Name of the collection to retrieve from Qdrant.

    - keep_as_only: bool
    Boolean flag, if set to `True`, cancels all the other snapshots after the download has been successfully completed.

    - scroll_limit: int
    Points per scroll page. This is the memory knob, not a throughput one: a page is decoded by the client into Python floats (~96 KB per 3072-dim vector) before it is written, so 2000 points cost ~190 MB transiently and 20000 cost ~1.9 GB.
    '''
    ## LADDER:
    ## check for different folders/snapshots in the repo containing different shards.
    ## store those in an array/tuple/iterable
    ## fetches + saving in a coherent format
    ## cancels the files previously elim

    QDRANT_URL = os.getenv("QDRANT_URL")
    API_KEY = os.getenv("QDRANT_API_KEY")
    client = QdrantClient(
        url=QDRANT_URL,
        api_key=API_KEY,
        cloud_inference=True
    )

    if not client.collection_exists(collection):
        raise FileNotFoundError(f"collection '{collection}' does not exist in the qdrant cloud env provided")

    METADATA: dict | None = read_fingerprint(client, collection)
    if METADATA is None:
        raise FetchingError(
            f"collection '{collection}' carries no embedding-space fingerprint: there would be "
            "no way to record which vector space this snapshot belongs to"
        )

    point_count_begin = client.count(
        collection,
        count_filter=WITHOUT_FINGERPRINT,
        exact=True
    ).count
    if point_count_begin == 0:
        raise FetchingError(f"collection '{collection}' holds no points to export")

    # The final folder is named after the snapshot hash, which is only known once
    # every point has been seen, while the memory map has to exist before the
    # first one arrives. The vectors therefore go into a neutrally named staging
    # folder next to the snapshots (same filesystem, so the final rename stays
    # atomic), which `_snapshot_versions()` ignores since it holds no manifest.
    NOW = Datetime.now()
    staging = qdrant_root() / collection / f".{NOW}.partial"
    staging.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {point_count_begin:,} vectors ({METADATA['embedding_dim']}d) from '{collection}', caching temporary files at {staging}")

    try:
        ids: Any = []
        payloads: Any = []

        # shape must be known now: the count taken above is the file's capacity.
        # memmap is chosen to lower the peak memory usage while fetching
        vectors = np.lib.format.open_memmap(
            staging / VECTORS,
            mode="w+",
            dtype=np.float32,
            shape=(point_count_begin, METADATA["embedding_dim"]),
        )
        n_written = 0
        offset = None

        # One buffer for the whole scroll, reused page after page. Its length is
        # only a capacity: a page can hold fewer points (always the last one), so
        # the rows actually filled are `n_page`, and only `page[:n_page]` is
        # meaningful: the rest is left over from earlier pages or uninitialised.
        page = np.empty(shape=(scroll_limit, METADATA["embedding_dim"]), dtype=np.float32)

        with tqdm(
            total= point_count_begin,
            leave=True,
            desc=collection,
            unit="vec",
            unit_scale=True,
        ) as bar:

            while True:
                points, offset = client.scroll(
                    collection_name=collection,
                    offset=offset,
                    limit=scroll_limit,
                    scroll_filter=WITHOUT_FINGERPRINT,
                    with_vectors=True,
                    with_payload=True
                )
                n_page = len(points)

                for i,point in enumerate(points):
                    if not isinstance(point.vector, dict):
                        raise FetchingError(f"point {point.id} has no named vectors: expected a 'dense' entry")
                    dense = point.vector['dense']

                    # a named vector may also be sparse (indices + values) or a
                    # multivector; only a flat list of floats fits a row of the file
                    if not isinstance(dense, list):
                        raise FetchingError(
                            f"point {point.id}: 'dense' is a {type(dense).__name__}, not a flat vector"
                        )
                    # checked explicitly: a length-1 vector would otherwise broadcast
                    # silently across the whole row instead of failing
                    if len(dense) != METADATA['embedding_dim']:
                        raise FetchingError(
                            f"collection '{collection}' declares {METADATA['embedding_dim']}-dimensional "
                            f"vectors, point {point.id} has {len(dense)}"
                        )
                    
                    ids.append(str(point.id))
                    page[i] = dense
                    # TODO: understand whether retrieving by indexing just `sparse` can lead to bugs
                    payloads.append(point.payload)

                if n_page:
                    if n_written + n_page > point_count_begin:
                        raise FetchingError(
                            f"collection '{collection}' grew during the fetching: it held "
                            f"{point_count_begin} points when the download started"
                        )

                    vectors[n_written:n_written + n_page] = page[:n_page]
                    n_written += n_page

                bar.update(n_page)

                if offset is None:
                    break
            ##
        ##

        point_count_end = client.count(
            collection,
            count_filter=WITHOUT_FINGERPRINT,
            exact=True
        ).count

        if point_count_end != point_count_begin:
            raise FetchingError('The collection was overwritten during the fetching')

        if n_written != point_count_begin:
            raise FetchingError(
                f"incomplete export of '{collection}': the collection holds "
                f"{point_count_begin} points, {n_written} were downloaded"
            )

        # Every dirty page has to reach the file before the manifest declares the
        # snapshot complete; the writable map is then dropped and the file reopened
        # read-only, exactly as a user will later see it.
        print("Creating the corpus object...", end="", flush=True)
        vectors.flush()
        del vectors
        vectors = np.load(staging / VECTORS, mmap_mode="r")

        ids = np.asarray(ids, dtype=str)
        content_hashes = [(payload or {}).get("content_hash", "") for payload in payloads]
        payloads = pd.DataFrame(payloads)

        hashing = snapshot_hash(
            pairs = ((i, hsh) for i, hsh in zip(ids.tolist(), content_hashes)),
            payload_cols=sorted(payloads.columns)
        )
        PATH = qdrant_root() / collection / f"{str(NOW)}_{hashing}"

        manifest = Manifest(
            schema_version=SCHEMA_VERSION,
            collection=collection,
            exported_at=str(NOW),
            snapshot_hash=hashing,
            point_count=point_count_end,
            embedding=METADATA,
            n_rows=len(vectors),
            n_dims=vectors.shape[-1],
            payload_columns=sorted(payloads.columns),
        )

        corpus = Corpus(
            meta=payloads,
            vectors=vectors,
            ids=ids,
            manifest=manifest,
            path = PATH
        )
        print("done!")

        print("Executing sanity checks on the fetched collection...", end="", flush=True)
        _validate_export(corpus)
        print("done!")

        print(f"Saving the snapshot to {PATH}...", end="", flush=True)
        save_corpus(corpus, PATH, staging=staging)
        print("done!")

    except BaseException:
        # a failed download must not leave gigabytes of half-written vectors behind
        print(f"Removing cached files from temporary folder at {staging}...", end="", flush=True)
        shutil.rmtree(staging, ignore_errors=True)
        print("done!")
        raise

    ## FINAL CLEANING of the old folders if asked
    if keep_as_only:
        print(f"Removing older snapshots of '{collection}' from {PATH.parent}...", end="", flush=True)
        for version in _snapshot_versions(PATH.parent)[:-1]:  # committed snapshots only, oldest first
            shutil.rmtree(version)
        print("done!")

    return PATH
##