# Supermarket Product Visual Search Engine — Project Brief

This document is a complete snapshot of the project for handoff to an AI assistant or for presentation prep. It reflects the actual current code, not just the original plan.

## 1. What This Project Is

A web app that lets a user upload a photo of a supermarket shelf/checkout, and the system:
1. Detects every product in the image (bounding boxes).
2. Crops each detected product.
3. Identifies *which specific product* it is by comparing it against a known catalog using visual similarity search.
4. Returns the product name, price, and confidence score, overlaid on the image.

Think: "point your phone at a shelf, get back what's there and what it costs."

## 2. Architecture / Pipeline

```
User uploads image (browser, Flask UI)
        │
        ▼
[Stage 1] YOLO object detection  (Ultralytics YOLOv8, app/app.py)
        │   → bounding boxes for each product-like object
        │   → SKU-110K-pretrained single-class "product" detector
        │     (pretrainedsku-110k.pt), falls back to stock yolov8n.pt
        │     if that weight file is missing
        ▼
[Stage 2] Crop + jitter  (app/app.py: _jitter_crops)
        │   → for each box, generate [original, expanded, tightened] crops
        │     to make the match more robust to imprecise boxes
        ▼
[Stage 3] CLIP embedding  (models/search_engine.py, ImageSearchEngine)
        │   → OpenAI CLIP ViT-B/32 (open_clip), 512-d L2-normalized vector
        │   → embeddings averaged across the 3 jittered crops
        ▼
[Stage 4] FAISS similarity search (cosine via inner product, IndexFlatIP)
        │   → compares against a pre-built catalog index
        │     (data/embeddings/faiss_index_clip.bin + metadata_clip.pkl)
        │   → re-ranked by a color-histogram similarity term (HSV hist,
        │     weighted 30% by default) to disambiguate visually similar
        │     packaging
        │   → score passed through a sigmoid calibration so raw cosine
        │     similarity becomes an intuitive 0–100% match score
        ▼
[Stage 5] Response
        │   → deduplicated top-3 matches per detected box
        │   → annotated image + JSON of detections returned to the browser
        ▼
Flask templates (app/templates/index_v2.html) render results
```

Key design detail: if YOLO finds **no** boxes at all, the app falls back to running the whole image through the same CLIP+FAISS search directly ("direct_match" fallback), so a single-product photo still works without needing strong detections.

## 3. Core Technologies

| Layer | Technology | Notes |
|---|---|---|
| Backend/UI | Flask | `app/app.py`, server-rendered templates |
| Object detection | Ultralytics YOLOv8 | custom-trained on SKU-110K-style single-class data |
| Embeddings | OpenAI CLIP ViT-B/32 (`open_clip`) | replaced an earlier ResNet50 approach |
| Vector search | FAISS (`IndexFlatIP`, cosine sim) | flat index, exact search, no ANN needed at current scale |
| Re-ranking | HSV color histograms | catches cases where CLIP alone confuses similar packaging |
| Rate limiting | flask-limiter (optional) | 15 requests/min on `/upload` |
| Config | `.env` via python-dotenv | thresholds, admin key |

## 4. Important Files

| File | Purpose |
|---|---|
| `app/app.py` | Flask app: routes, YOLO inference, threading over detected boxes, response assembly |
| `models/search_engine.py` | `ImageSearchEngine` class: CLIP feature extraction, FAISS index build/search/add/delete, color rerank, calibration |
| `app/templates/index_v2.html` | Main upload/search UI |
| `app/templates/admin.html` | Admin UI to add/view/delete catalog items |
| `bulk_upload.py` | CLI to bulk-index a folder of product images (optionally with a CSV of name/price) |
| `audit_dataset.py` | Sanity-checks a YOLO-format label dataset (box counts, class balance, tiny-object %) |
| `data/data_prep.py` | Converts COCO-format annotations (e.g. RPC dataset) into YOLO label format |
| `data/create_subset.py` | Samples a % subset of a full YOLO dataset for fast iteration |
| `models/train.py`, `train_subset.py` | YOLO training entry points |
| `models/evaluate*.py` | YOLO evaluation entry points |
| `scripts/build_faiss_index.py`, `index_catalog.py` | Build/rebuild the FAISS catalog index from images |
| `scripts/fill_prices.py`, `generate_csv_template.py` | Catalog metadata helpers |
| `scripts/download_*` | Helpers to pull category-specific training images |
| `pretrainedsku-110k.pt` | Trained YOLO weights (single "product" class) |
| `data/embeddings/faiss_index_clip.bin` / `metadata_clip.pkl` | The live catalog vector index + product metadata |
| `requirements.txt` | Python deps |

## 5. Key Endpoints (Flask)

- `GET /` — main search UI
- `POST /upload` — image in, JSON detections out (rate-limited 15/min)
- `GET /admin`, `POST /admin` — add new catalog product (name, price, 1+ images), protected by optional `ADMIN_KEY` header
- `GET /admin/catalog` — list catalog items
- `POST /admin/delete` — remove a catalog item by id
- `GET /health` — model/index status + current thresholds

## 6. Tunable Parameters (via `.env`)

- `YOLO_CONF_THRESHOLD` (default 0.30) — min detection confidence to keep a box
- `SIMILARITY_THRESHOLD` (default 0.40) — min CLIP similarity to count as a confident match (with an automatic relaxed-threshold retry if nothing passes)
- `MIN_CROP_SHARPNESS` (default 50.0) — Laplacian-variance blur filter; rejects blurry crops before search
- `MAX_IMAGE_DIMENSION` (default 2000) — uploaded images are downscaled to this on the longest side
- `COLOR_WEIGHT` (default 0.30) — how much the HSV color histogram re-rank contributes vs. raw CLIP similarity
- `ADMIN_KEY` — optional shared secret for `/admin*` routes

## 7. Training History (YOLO detector) — the interesting story for a presentation

1. **Started with RPC (Retail Product Checkout) dataset**: ~83,000 images, 421k boxes, 200 specific checkout-item classes (Kaggle, 26GB).
2. **Trained YOLOv8m on RunPod (RTX 4090)** with `workers=8, batch=24, imgsz=800`.
3. **Hit a "domain gap" problem**: training images were clean isolated products on white backgrounds; validation images were cluttered real-world checkout scenes.
   - Disabling mosaic/mixup augmentation collapsed mAP to ~0.029 — the model never learned to handle clutter.
   - Keeping default augmentations let the model memorize the training set (loss dropped) but validation mAP plateaued around 0.09 — it wasn't generalizing.
4. **Pivoted strategy** (the key architectural decision): stop asking YOLO to classify 200 specific brands. Instead:
   - Train YOLO as a **generic single-class detector** ("is this a product, yes/no") — the industry-standard "facings detection" approach used in real shelf-monitoring systems, trained on SKU-110K-style dense shelf data.
   - Push the actual **brand/product identification** downstream to a CLIP + FAISS visual search step, which can be updated by just adding catalog images — no retraining needed.
5. This is why the system today is two clearly separated stages: YOLO (where is a product?) → CLIP/FAISS (which product is it?).

## 8. Notable Engineering Details Worth Mentioning

- **Multi-crop jitter + averaging**: each detection is searched as 3 slightly different crops (tight/expanded/original) and embeddings are averaged — reduces sensitivity to imprecise YOLO boxes.
- **Two-tier confidence fallback**: if no catalog match clears the main similarity threshold, the system retries the same crops at a relaxed threshold and flags the result as `is_trial` so the UI can show it as a lower-confidence guess rather than silently failing.
- **Whole-image fallback**: if YOLO detects nothing at all, the app still attempts a direct CLIP/FAISS search on the full image.
- **Color histogram re-ranking**: CLIP embeddings alone can confuse similarly-shaped packaging (e.g. two cereal boxes); blending in HSV color similarity helps disambiguate.
- **Sigmoid calibration**: raw cosine similarity scores are not intuitive (e.g. 0.55 "feels low" but might be a great match) — they're passed through a tuned sigmoid so the displayed percentage matches human intuition of "how confident is this."
- **Threaded box processing**: each detected box is searched concurrently (`ThreadPoolExecutor`), and Flask's `url_for` (which needs app context) is deliberately resolved *after* the threads finish rather than inside them.
- **Live catalog growth without retraining**: admin can add a new product (with 1+ photos) at runtime via `/admin`; this only updates the FAISS index, not the YOLO model — so the catalog can grow independently of the detector.

## 9. Current Limitations / Possible "Next Steps" Talking Points

- YOLO detector is generic (no brand awareness) — all brand identification relies on the FAISS catalog, so an unstocked product will never be correctly named (falls back to "No confident match found").
- FAISS uses a flat (exact, brute-force) index — fine at current catalog size, would need an ANN index (e.g. IVF/HNSW) if the catalog grew to tens of thousands of items.
- Documented future idea (from earlier project notes): optionally query Google Cloud Vision for logo/text OCR when local FAISS confidence is low, instead of relying purely on embeddings.

## 10. Suggested Presentation Structure

1. **Problem**: identifying products from a photo of a shelf/checkout is hard because there are thousands of similar-looking SKUs.
2. **Naive approach considered**: train one big classifier to recognize every specific product → why it failed (domain gap, 200-class RPC experiment, mAP collapse).
3. **Pivot**: two-stage detect-then-retrieve architecture (industry standard) — explain WHY this is better (catalog updates don't need retraining, generalizes to unseen layouts).
4. **System walkthrough**: live demo of upload → YOLO boxes → crops → CLIP/FAISS matches → price.
5. **Engineering details that show depth**: jittered multi-crop averaging, color rerank, confidence calibration, fallback tiers.
6. **Results / limitations / future work**.
