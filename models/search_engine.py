import os
import logging
import torch
import numpy as np
import faiss
import pickle
import cv2
from PIL import Image

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

_DEFAULT_INDEX = os.path.join(_PROJECT_ROOT, 'data', 'embeddings', 'faiss_index_clip.bin')
_DEFAULT_META  = os.path.join(_PROJECT_ROOT, 'data', 'embeddings', 'metadata_clip.pkl')

_EMBED_DIM = 512

# Configurable via .env
COLOR_WEIGHT = float(os.getenv('COLOR_WEIGHT', '0.30'))

try:
    import open_clip as _open_clip
    _CLIP_AVAILABLE = True
except ImportError:
    _CLIP_AVAILABLE = False


class ImageSearchEngine:
    def __init__(self, index_path=_DEFAULT_INDEX, metadata_path=_DEFAULT_META):
        self.index_path    = index_path
        self.metadata_path = metadata_path
        self.device        = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.embedding_dim = _EMBED_DIM

        self._init_clip()

        self.index        = None
        self.metadata     = []
        self._vectors     = None   # np.ndarray (N, D) — stored for fast delete/rebuild
        self._color_cache = {}

        self._load_index()

    # ------------------------------------------------------------------
    # Model initialisation
    # ------------------------------------------------------------------

    def _init_clip(self):
        if not _CLIP_AVAILABLE:
            raise ImportError(
                "open-clip-torch is not installed.\n"
                "  pip install open-clip-torch"
            )
        self.model, _, self._clip_preprocess = _open_clip.create_model_and_transforms(
            'ViT-B-32-quickgelu', pretrained='openai'
        )
        self.model = self.model.to(self.device)
        self.model.eval()
        logging.getLogger(__name__).info("CLIP ViT-B/32 loaded (512-d).")

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def extract_features(self, img, use_tta=False):
        """Return an L2-normalised 512-d CLIP feature vector from a PIL image.

        use_tta averages brightness variants for lighting robustness;
        horizontal flips excluded because product text is asymmetric.
        """
        if img.mode != 'RGB':
            img = img.convert('RGB')
        views = self._tta_views(img) if use_tta else [img]
        all_feats = []
        for view in views:
            t = self._clip_preprocess(view).unsqueeze(0).to(self.device)
            with torch.no_grad():
                f = self.model.encode_image(t).squeeze(0).cpu().float().numpy()
            all_feats.append(f)
        features = np.mean(all_feats, axis=0)
        features /= np.linalg.norm(features)
        return np.expand_dims(features, axis=0).astype(np.float32)

    @staticmethod
    def _tta_views(img):
        from PIL import ImageEnhance
        return [img,
                ImageEnhance.Brightness(img).enhance(1.3),
                ImageEnhance.Brightness(img).enhance(0.7)]

    # ------------------------------------------------------------------
    # Color histogram helpers
    # ------------------------------------------------------------------

    def _extract_color_histogram(self, img, h_bins=50, s_bins=60):
        if img.mode != 'RGB':
            img = img.convert('RGB')
        hsv    = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2HSV)
        h_hist = np.histogram(hsv[:, :, 0], bins=h_bins, range=(0, 180))[0].astype(np.float32)
        s_hist = np.histogram(hsv[:, :, 1], bins=s_bins, range=(0, 256))[0].astype(np.float32)
        hist   = np.concatenate([h_hist, s_hist])
        norm   = np.linalg.norm(hist)
        if norm > 0:
            hist /= norm
        return hist

    def _get_cached_histogram(self, image_path):
        if image_path not in self._color_cache:
            try:
                self._color_cache[image_path] = self._extract_color_histogram(
                    Image.open(image_path).convert('RGB')
                )
            except Exception:
                self._color_cache[image_path] = None
        return self._color_cache[image_path]

    @staticmethod
    def _histogram_similarity(hist1, hist2):
        return float(np.dot(hist1, hist2))

    # ------------------------------------------------------------------
    # Augmentation helpers (index-time)
    # ------------------------------------------------------------------

    @staticmethod
    def _augment_views(img):
        """±10° rotations for geometric coverage without extra source images."""
        gray = (128, 128, 128)
        return [
            img.rotate(10,  expand=False, fillcolor=gray),
            img.rotate(-10, expand=False, fillcolor=gray),
        ]

    # ------------------------------------------------------------------
    # Confidence calibration
    # ------------------------------------------------------------------

    @staticmethod
    def _sigmoid_calibrate(score, k=12.0, offset=0.55):
        """Map raw cosine similarity to an intuitive display percentage."""
        return float(1.0 / (1.0 + np.exp(-k * (score - offset))))

    # ------------------------------------------------------------------
    # Post-processing pipeline (color → OCR → threshold → calibrate)
    # ------------------------------------------------------------------

    def _rerank_and_calibrate(self, results, query_img,
                              rerank_with_color, calibrate, threshold=0.0):
        if rerank_with_color and results and query_img is not None:
            try:
                query_hist = self._extract_color_histogram(query_img)
                for r in results:
                    cat_hist = self._get_cached_histogram(r['image_path'])
                    if cat_hist is not None:
                        color_sim = self._histogram_similarity(query_hist, cat_hist)
                        r['similarity_score'] = (
                            (1 - COLOR_WEIGHT) * r['similarity_score'] + COLOR_WEIGHT * color_sim
                        )
                        r['color_similarity'] = round(color_sim, 4)
                results.sort(key=lambda r: r['similarity_score'], reverse=True)
            except Exception:
                pass

        if threshold > 0:
            results = [r for r in results if r['similarity_score'] >= threshold]

        if calibrate:
            for r in results:
                r['similarity_score'] = self._sigmoid_calibrate(r['similarity_score'])

        return results

    # ------------------------------------------------------------------
    # Index build
    # ------------------------------------------------------------------

    def build_index(self, image_paths, metadata_list=None, augment=False):
        """Build FAISS index.  augment=True adds ±10° rotation entries per image."""
        print(f"[CLIP] Building index for {len(image_paths)} images"
              f"{' + rotation augmentation (3x entries)' if augment else ''}...")
        self.index    = faiss.IndexFlatIP(self.embedding_dim)
        self.metadata = []
        all_features  = []

        for i, path in enumerate(image_paths):
            if i % 100 == 0:
                print(f"  {i}/{len(image_paths)} images  ({len(all_features)} entries so far)")
            try:
                img  = Image.open(path).convert('RGB')
                meta = (metadata_list[i] if metadata_list and i < len(metadata_list)
                        else {"path": os.path.abspath(path), "name": "", "price": "N/A"})

                all_features.append(self.extract_features(img, use_tta=True))
                self.metadata.append(meta)

                if augment:
                    for aug_img in self._augment_views(img):
                        all_features.append(self.extract_features(aug_img, use_tta=False))
                        self.metadata.append(meta)
            except Exception as e:
                print(f"  Skipping {path}: {e}")

        if all_features:
            features_matrix = np.vstack(all_features)
            self.index.add(features_matrix)
            self._vectors = features_matrix
            self._save_index()
            print(f"  Done: {self.index.ntotal} entries from {len(image_paths)} source images.")
        else:
            print("  No features extracted — index not saved.")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query_img, top_k=5, threshold=0.0,
               rerank_with_color=True, calibrate=True):
        if self.index is None or self.index.ntotal == 0:
            return []
        query_features     = self.extract_features(query_img, use_tta=True)
        distances, indices = self.index.search(query_features, top_k)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            meta = self.metadata[idx]
            if isinstance(meta, dict):
                results.append({
                    "image_path":       meta.get("path", ""),
                    "product_name":     meta.get("name", ""),
                    "price":            meta.get("price", "N/A"),
                    "similarity_score": float(dist),
                })
            else:
                results.append({"image_path": meta, "similarity_score": float(dist)})
        return self._rerank_and_calibrate(results, query_img, rerank_with_color, calibrate, threshold)

    def search_multi_crop(self, crops, top_k=5, threshold=0.0,
                          rerank_with_color=True, calibrate=True):
        """Average embeddings across jittered crops before FAISS search."""
        if self.index is None or self.index.ntotal == 0:
            return []
        if not crops:
            return []

        all_feats = []
        for i, crop in enumerate(crops):
            try:
                all_feats.append(self.extract_features(crop, use_tta=(i == 0))[0])
            except Exception:
                continue
        if not all_feats:
            return []

        avg_feat = np.mean(all_feats, axis=0)
        norm = np.linalg.norm(avg_feat)
        if norm > 0:
            avg_feat /= norm
        query_features = np.expand_dims(avg_feat, axis=0).astype(np.float32)

        distances, indices = self.index.search(query_features, top_k)
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue
            meta = self.metadata[idx]
            if isinstance(meta, dict):
                results.append({
                    "image_path":       meta.get("path", ""),
                    "product_name":     meta.get("name", ""),
                    "price":            meta.get("price", "N/A"),
                    "similarity_score": float(dist),
                })
            else:
                results.append({"image_path": meta, "similarity_score": float(dist)})
        return self._rerank_and_calibrate(results, crops[0], rerank_with_color, calibrate, threshold)

    # ------------------------------------------------------------------
    # Index mutation
    # ------------------------------------------------------------------

    def add_single_item(self, image_path, product_name, price):
        img      = Image.open(image_path).convert('RGB')
        features = self.extract_features(img, use_tta=True)
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.embedding_dim)
        self.index.add(features)
        self.metadata.append({"path": image_path, "name": product_name, "price": price})
        self._vectors = (
            np.vstack([self._vectors, features]) if self._vectors is not None else features.copy()
        )
        self._get_cached_histogram(image_path)
        self._save_index()
        print(f"Added '{product_name}'. Index now has {self.index.ntotal} items.")

    def add_product_multi_images(self, image_paths, product_name, price):
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.embedding_dim)
        new_vecs = []
        added    = 0
        for path in image_paths:
            try:
                img      = Image.open(path).convert('RGB')
                features = self.extract_features(img, use_tta=True)
                self.index.add(features)
                abs_path = os.path.abspath(path)
                self.metadata.append({"path": abs_path, "name": product_name, "price": price})
                new_vecs.append(features[0])
                self._get_cached_histogram(abs_path)
                added += 1
            except Exception as e:
                print(f"Skipping {path}: {e}")
        if added > 0:
            new_arr       = np.array(new_vecs, dtype=np.float32)
            self._vectors = (
                np.vstack([self._vectors, new_arr]) if self._vectors is not None else new_arr
            )
            self._save_index()
        print(f"Added {added}/{len(image_paths)} images for '{product_name}'. "
              f"Index now has {self.index.ntotal} items.")
        return added

    def delete_item(self, faiss_idx):
        n = self.index.ntotal if self.index else 0
        if faiss_idx < 0 or faiss_idx >= n:
            raise IndexError(f"Index {faiss_idx} out of range (0–{n - 1})")
        self.metadata.pop(faiss_idx)
        if self._vectors is None or len(self._vectors) != n:
            all_vecs = np.zeros((n, self.embedding_dim), dtype=np.float32)
            self.index.reconstruct_n(0, n, all_vecs)
            self._vectors = all_vecs
        self._vectors = np.delete(self._vectors, faiss_idx, axis=0)
        self.index    = faiss.IndexFlatIP(self.embedding_dim)
        if len(self._vectors) > 0:
            self.index.add(self._vectors)
        self._save_index()

    def get_catalog(self):
        catalog = []
        for i, meta in enumerate(self.metadata):
            if isinstance(meta, dict):
                catalog.append({
                    "id":           i,
                    "product_name": meta.get("name", ""),
                    "price":        meta.get("price", "N/A"),
                    "image_path":   meta.get("path", ""),
                })
            else:
                catalog.append({"id": i, "product_name": "", "price": "N/A", "image_path": meta})
        return catalog

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save_index(self):
        os.makedirs(os.path.dirname(self.index_path), exist_ok=True)
        faiss.write_index(self.index, self.index_path)
        with open(self.metadata_path, 'wb') as f:
            pickle.dump({"metadata": self.metadata, "vectors": self._vectors}, f)

    def _load_index(self):
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.index_path)
                if self.index.d != self.embedding_dim:
                    print(f"Warning: index dimension {self.index.d} != {self.embedding_dim}. "
                          "Starting empty — rebuild with scripts/build_faiss_index.py.")
                    self.index    = None
                    self.metadata = []
                    self._vectors = None
                    return
                with open(self.metadata_path, 'rb') as f:
                    raw = pickle.load(f)
                if isinstance(raw, dict):
                    self.metadata = raw.get("metadata", [])
                    self._vectors = raw.get("vectors", None)
                else:
                    self.metadata = raw
                    self._vectors = None
                print(f"[CLIP ViT-B/32] Loaded index: {self.index.ntotal} items.")
            except Exception as e:
                print(f"Warning: failed to load index ({e}). Starting empty.")
                self.index    = None
                self.metadata = []
                self._vectors = None
