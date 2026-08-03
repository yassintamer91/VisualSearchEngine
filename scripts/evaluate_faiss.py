"""
Evaluate FAISS search-engine accuracy using leave-one-out on products
that have >=2 reference images in the index.

Metrics:
  - Top-1 / Top-3 / Top-5 accuracy
  - MRR (Mean Reciprocal Rank)
  - Per-product recall breakdown (best / worst)
  - Catalog coverage stats

Run from the project root:
    python scripts/evaluate_faiss.py
"""

import os
import sys
import pickle
from collections import defaultdict

import numpy as np
import faiss

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
INDEX_PATH   = os.path.join(PROJECT_ROOT, 'data', 'embeddings', 'faiss_index_clip.bin')
META_PATH    = os.path.join(PROJECT_ROOT, 'data', 'embeddings', 'metadata_clip.pkl')

TOP_K = 10   # evaluate at ranks 1, 3, 5 (must be <= TOP_K)


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_index_and_meta():
    if not os.path.exists(INDEX_PATH):
        sys.exit(f"Error: index not found at {INDEX_PATH}\nRun scripts/build_faiss_index.py first.")
    if not os.path.exists(META_PATH):
        sys.exit(f"Error: metadata not found at {META_PATH}")

    index = faiss.read_index(INDEX_PATH)
    with open(META_PATH, 'rb') as f:
        raw = pickle.load(f)

    metadata = raw.get('metadata', []) if isinstance(raw, dict) else raw
    vectors  = raw.get('vectors', None) if isinstance(raw, dict) else None

    if vectors is None or len(vectors) != index.ntotal:
        print("Reconstructing stored vectors from FAISS index (one-time cost)...")
        n   = index.ntotal
        dim = index.d
        vectors = np.zeros((n, dim), dtype=np.float32)
        index.reconstruct_n(0, n, vectors)

    return index, metadata, vectors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_name(meta):
    if isinstance(meta, dict):
        return (meta.get('name') or '').strip()
    return str(meta).strip()


def _skip_generic(name):
    return not name or name.lower().startswith('unlabeled') or name.lower() == 'unknown product'


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(index, metadata, vectors, top_k=TOP_K):
    n = index.ntotal
    print(f"\nIndex contains {n} entries.\n")

    # --- Catalog summary -------------------------------------------------
    name_to_indices = defaultdict(list)
    for i, meta in enumerate(metadata):
        name = _get_name(meta)
        if not _skip_generic(name):
            name_to_indices[name].append(i)

    total_products    = len(name_to_indices)
    evaluable         = {nm: idxs for nm, idxs in name_to_indices.items() if len(idxs) >= 2}
    single_image      = total_products - len(evaluable)
    evaluable_images  = sum(len(v) for v in evaluable.values())

    print("=== Catalog Coverage ===")
    print(f"  Total unique product names   : {total_products}")
    print(f"  Products with >=2 images     : {len(evaluable)}  ({len(evaluable)/max(total_products,1)*100:.1f}%)")
    print(f"  Products with only 1 image   : {single_image}  ({single_image/max(total_products,1)*100:.1f}%)")
    print(f"  Total evaluable images       : {evaluable_images}")
    print()

    if not evaluable:
        print("No products have >=2 images — cannot perform leave-one-out evaluation.")
        print("Recommendation: add multiple reference images per product.")
        return

    # --- Leave-one-out search --------------------------------------------
    k_fetch   = top_k + 1   # +1 because query itself will appear at rank 1

    hits          = {1: 0, 3: 0, 5: 0}
    reciprocal_rs = []
    total_q       = 0
    per_product   = {}   # name -> (correct_top1, total)

    print(f"Running leave-one-out evaluation on {evaluable_images} queries...\n")

    for name, idxs in evaluable.items():
        p_correct = 0
        for query_idx in idxs:
            qvec = vectors[query_idx : query_idx + 1]           # (1, 2048)
            dists, nbrs = index.search(qvec, k_fetch)

            # Remove self, keep top_k
            filtered = [
                (d, nb)
                for d, nb in zip(dists[0], nbrs[0])
                if nb != query_idx and nb >= 0
            ][:top_k]

            total_q  += 1
            hit_rank  = None
            for rank, (_, nb) in enumerate(filtered, start=1):
                if _get_name(metadata[nb]) == name:
                    hit_rank = rank
                    break

            if hit_rank is not None:
                for k in (1, 3, 5):
                    if hit_rank <= k:
                        hits[k] += 1
                reciprocal_rs.append(1.0 / hit_rank)
                if hit_rank == 1:
                    p_correct += 1
            else:
                reciprocal_rs.append(0.0)

        per_product[name] = (p_correct, len(idxs))

    # --- Results ---------------------------------------------------------
    print("=" * 55)
    print(f"  FAISS Search Engine — Accuracy Report [CLIP]")
    print("=" * 55)
    print(f"  Queries evaluated : {total_q}")
    print(f"  Top-1  accuracy   : {hits[1]/total_q*100:6.2f}%  ({hits[1]}/{total_q})")
    print(f"  Top-3  accuracy   : {hits[3]/total_q*100:6.2f}%  ({hits[3]}/{total_q})")
    print(f"  Top-5  accuracy   : {hits[5]/total_q*100:6.2f}%  ({hits[5]}/{total_q})")
    print(f"  MRR               : {np.mean(reciprocal_rs):.4f}")
    print()

    # --- Per-product breakdown -------------------------------------------
    recalls = {nm: c / t for nm, (c, t) in per_product.items()}

    worst = sorted(recalls.items(), key=lambda x: x[1])[:10]
    best  = sorted(recalls.items(), key=lambda x: x[1], reverse=True)[:10]

    print("--- 10 hardest products (lowest top-1 per-product recall) ---")
    for nm, r in worst:
        c, t = per_product[nm]
        print(f"  [{r*100:5.1f}%]  {nm[:55]:<55}  ({t} imgs)")

    print()
    print("--- 10 easiest products (highest top-1 per-product recall) ---")
    for nm, r in best:
        c, t = per_product[nm]
        print(f"  [{r*100:5.1f}%]  {nm[:55]:<55}  ({t} imgs)")

    print()
    print("--- Image-count distribution for evaluable products ---")
    from collections import Counter
    count_dist = Counter(len(idxs) for idxs in evaluable.values())
    for cnt in sorted(count_dist):
        print(f"  {cnt} images/product : {count_dist[cnt]} products")

    # --- Single-image products can never be matched ----------------------
    print()
    print(f"Note: {single_image} products have only 1 image and cannot be evaluated.")
    print("      Adding a second reference image per product would enable matching.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    print("Loading FAISS index and metadata...")
    idx, meta, vecs = load_index_and_meta()
    evaluate(idx, meta, vecs)
