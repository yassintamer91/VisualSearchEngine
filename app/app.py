import os
import sys
import time
import uuid
import logging
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
from werkzeug.utils import secure_filename
import cv2
from PIL import Image
from ultralytics import YOLO

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _limiter_available = True
except ImportError:
    _limiter_available = False
    logging.warning("flask-limiter not installed — rate limiting disabled. Run: pip install flask-limiter")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.search_engine import ImageSearchEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

app = Flask(__name__)

# Rate limiter (gracefully disabled if package not installed)
if _limiter_available:
    limiter = Limiter(get_remote_address, app=app, default_limits=[], storage_uri="memory://")
else:
    class _NoopLimiter:
        def limit(self, *a, **kw):
            return lambda f: f
    limiter = _NoopLimiter()

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Tunable thresholds — override via .env without touching source code
YOLO_CONF_THRESHOLD  = float(os.getenv('YOLO_CONF_THRESHOLD', '0.30'))
SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', '0.40'))
MIN_CROP_SHARPNESS   = float(os.getenv('MIN_CROP_SHARPNESS', '50.0'))
MAX_IMAGE_DIMENSION  = int(os.getenv('MAX_IMAGE_DIMENSION', '2000'))
ADMIN_KEY            = os.getenv('ADMIN_KEY', '')

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp', 'bmp', 'tiff', 'tif'}

# Cleanup throttle — scan the uploads directory every N requests, not every request
_upload_counter   = 0
_CLEANUP_INTERVAL = 20

# Load YOLO model
sku_model_path = os.path.join(ROOT_DIR, 'pretrainedsku-110k.pt')
if os.path.exists(sku_model_path):
    log.info("Loading SKU-110K YOLO model from %s", sku_model_path)
    yolo_model = YOLO(sku_model_path)
else:
    log.warning("pretrainedsku-110k.pt not found — falling back to yolov8n")
    yolo_model = YOLO("yolov8n.pt")

search_engine = ImageSearchEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _resize_if_needed(pil_img):
    """Downscale to MAX_IMAGE_DIMENSION on the longest side; no-op if already small enough."""
    w, h = pil_img.size
    if max(w, h) <= MAX_IMAGE_DIMENSION:
        return pil_img
    scale = MAX_IMAGE_DIMENSION / max(w, h)
    return pil_img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def _cleanup_old_uploads(max_age_seconds=1800):
    """Delete upload files older than max_age_seconds."""
    upload_dir = app.config['UPLOAD_FOLDER']
    now = time.time()
    for fname in os.listdir(upload_dir):
        fpath = os.path.join(upload_dir, fname)
        try:
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath)) > max_age_seconds:
                os.remove(fpath)
        except OSError:
            pass


def _image_sharpness(pil_img):
    gray = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _build_image_url(path):
    p = os.path.normpath(path).replace('\\', '/')
    if 'imgss' in p:
        return url_for('serve_imgss', filename=os.path.basename(p))
    if 'static/' in p:
        return url_for('static', filename=p.split('static/')[1])
    if 'catalog/' in p:
        parts = p.split('catalog/')
        if len(parts) > 1:
            return url_for('serve_catalog_image', filename=parts[1])
    return path


def _deduplicate(results):
    """Keep only the highest-scoring result per product name.

    When product_name is empty, image_path is used as the dedup key so that
    unnamed items are not incorrectly collapsed into a single result.
    """
    seen = {}
    for r in results:
        name = (r.get('product_name') or '').strip()
        key  = name if name else r.get('image_path', '')
        if key not in seen or r.get('similarity_score', 0) > seen[key].get('similarity_score', 0):
            seen[key] = r
    return sorted(seen.values(), key=lambda x: x.get('similarity_score', 0), reverse=True)


_GENERIC_FOLDERS = {'imgss', 'catalog', 'static', 'uploads', 'images', 'data'}

def _name_from_path(path):
    parts  = path.replace('\\', '/').split('/')
    parent = parts[-2] if len(parts) >= 2 else ''
    if not parent or parent.lower() in _GENERIC_FOLDERS:
        return os.path.splitext(os.path.basename(path))[0]
    return parent.replace("white background", "").strip()


def _jitter_crops(pil_img, x1, y1, x2, y2, jitter=0.05):
    """Return [original, expanded, tightened] crops around a YOLO bounding box."""
    W, H  = pil_img.size
    bw, bh = x2 - x1, y2 - y1
    dx, dy = max(1, int(bw * jitter)), max(1, int(bh * jitter))

    crops = [pil_img.crop((x1, y1, x2, y2))]
    crops.append(pil_img.crop((max(0, x1 - dx), max(0, y1 - dy),
                                min(W, x2 + dx), min(H, y2 + dy))))
    nx1, ny1, nx2, ny2 = x1 + dx, y1 + dy, x2 - dx, y2 - dy
    if nx2 > nx1 and ny2 > ny1:
        crops.append(pil_img.crop((nx1, ny1, nx2, ny2)))
    return crops


def _process_box(args):
    """Process a single YOLO detection box: crop → jitter → FAISS search.

    Designed to run inside a ThreadPoolExecutor.  url_for is intentionally
    NOT called here — URL resolution happens in the route after threads finish.
    Returns a result dict (without crop_image URL) or None if skipped.
    """
    i, box, pil_img, upload_dir, filename = args
    try:
        conf = float(box.conf[0].cpu().numpy())
        if conf < YOLO_CONF_THRESHOLD:
            return None

        x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
        cls_name = yolo_model.names[int(box.cls[0].cpu().numpy())]

        product_crop = pil_img.crop((x1, y1, x2, y2))
        if _image_sharpness(product_crop) < MIN_CROP_SHARPNESS:
            return None

        crop_filename = f"crop_{i}_{filename}"
        product_crop.save(os.path.join(upload_dir, crop_filename))

        crops      = _jitter_crops(pil_img, x1, y1, x2, y2)
        raw_results = search_engine.search_multi_crop(
            crops, top_k=6, threshold=SIMILARITY_THRESHOLD
        )
        similarity_results = _deduplicate(raw_results)[:3]
        is_trial = False

        # Per-crop fallback: no confident match → retry with relaxed threshold
        if not similarity_results:
            trial_threshold = max(0.15, SIMILARITY_THRESHOLD - 0.15)
            trial_raw       = search_engine.search_multi_crop(
                crops, top_k=6, threshold=trial_threshold
            )
            similarity_results = _deduplicate(trial_raw)[:3]
            if similarity_results:
                is_trial = True

        if similarity_results:
            top               = similarity_results[0]
            predicted_product = top.get('product_name') or _name_from_path(top.get('image_path', ''))
            product_price     = top.get('price', 'N/A')
            match_confidence  = top.get('similarity_score', 0)
        else:
            predicted_product = "No confident match found"
            product_price     = "N/A"
            match_confidence  = 0

        return {
            "detection_type":  "trial_match" if is_trial else cls_name,
            "class":           predicted_product,
            "price":           product_price,
            "confidence":      round(conf * 100, 2),
            "match_score":     round(match_confidence * 100, 2),
            "bbox":            [x1, y1, x2, y2],
            "crop_filename":   crop_filename,      # resolved to URL by caller
            "similar_items":   similarity_results, # image_url added by caller
            "is_trial":        is_trial,
        }
    except Exception as e:
        log.error("Error processing detection %d: %s", i, e)
        return None


# ---------------------------------------------------------------------------
# Routes — image serving
# ---------------------------------------------------------------------------

@app.route('/imgss/<path:filename>')
def serve_imgss(filename):
    return send_from_directory(os.path.join(ROOT_DIR, 'imgss'), filename)


@app.route('/catalog_images/<path:filename>')
def serve_catalog_image(filename):
    return send_from_directory(os.path.join(ROOT_DIR, 'catalog'), filename)


# ---------------------------------------------------------------------------
# Routes — pages & API
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index_v2.html')


@app.route('/health')
def health():
    try:
        index_size = search_engine.index.ntotal if search_engine.index is not None else 0
    except Exception:
        index_size = -1
    model_name = os.path.basename(sku_model_path) if os.path.exists(sku_model_path) else 'yolov8n'
    return jsonify({
        "status":          "ok",
        "yolo_model":      model_name,
        "faiss_index_size": index_size,
        "thresholds": {
            "yolo_confidence": YOLO_CONF_THRESHOLD,
            "similarity":      SIMILARITY_THRESHOLD,
            "min_sharpness":   MIN_CROP_SHARPNESS,
        },
    })


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        if ADMIN_KEY and request.headers.get('X-Admin-Key') != ADMIN_KEY:
            return jsonify({"error": "Unauthorized — invalid admin key"}), 401

        product_name = request.form.get('product_name', '').strip()
        price        = request.form.get('price', '').strip()

        if not product_name:
            return jsonify({"error": "Product name is required"}), 400
        if not price:
            return jsonify({"error": "Price is required"}), 400

        files = request.files.getlist('file')
        valid_files = [f for f in files if f and f.filename and _allowed_file(f.filename)]
        if not valid_files:
            return jsonify({"error": "No valid image file uploaded. Supported: JPG, PNG, WebP."}), 400

        catalog_path = os.path.join(app.root_path, 'static', 'catalog')
        os.makedirs(catalog_path, exist_ok=True)

        saved_paths = []
        for f in valid_files:
            filepath = os.path.join(catalog_path, f"{uuid.uuid4().hex}_{secure_filename(f.filename)}")
            f.save(filepath)
            saved_paths.append(filepath)

        try:
            if len(saved_paths) == 1:
                search_engine.add_single_item(saved_paths[0], product_name, price)
            else:
                search_engine.add_product_multi_images(saved_paths, product_name, price)
            return jsonify({
                "message": (
                    f"Successfully added '{product_name}' ({price} EGP) — "
                    f"{len(saved_paths)} image(s) indexed."
                )
            })
        except Exception as e:
            return jsonify({"error": f"Failed to add to index: {e}"}), 500

    return render_template('admin.html')


@app.route('/admin/catalog')
def admin_catalog():
    if ADMIN_KEY and request.headers.get('X-Admin-Key') != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    catalog = search_engine.get_catalog()
    items = []
    for item in catalog:
        items.append({
            "id":           item['id'],
            "product_name": item['product_name'] or 'Unnamed',
            "price":        item['price'],
            "image_url":    _build_image_url(item.get('image_path', '')),
        })
    return jsonify({"catalog": items, "total": len(items)})


@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    if ADMIN_KEY and request.headers.get('X-Admin-Key') != ADMIN_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json(silent=True)
    if not data or 'id' not in data:
        return jsonify({"error": "Missing 'id' field in JSON body"}), 400

    try:
        idx = int(data['id'])
        search_engine.delete_item(idx)
        remaining = search_engine.index.ntotal if search_engine.index else 0
        return jsonify({"message": f"Item {idx} deleted. Index now has {remaining} items."})
    except IndexError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        log.error("Delete failed: %s", e)
        return jsonify({"error": f"Delete failed: {e}"}), 500


@app.route('/upload', methods=['POST'])
@limiter.limit("15 per minute")
def upload():
    global _upload_counter
    _upload_counter += 1
    if _upload_counter % _CLEANUP_INTERVAL == 0:
        _cleanup_old_uploads()

    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not _allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type. Please upload a JPG, PNG, or WebP image."}), 400

    filename = f"{uuid.uuid4().hex}_{secure_filename(file.filename)}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        img = cv2.imread(filepath)
        if img is None:
            return jsonify({"error": "Could not read image — unsupported format or corrupt file"}), 400

        img_rgb  = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img  = Image.fromarray(img_rgb)
        pil_img  = _resize_if_needed(pil_img)
        # Save resized version back so annotated image stays consistent
        pil_img.save(filepath)

        # 1. Detect products with YOLO
        results = yolo_model(pil_img)
        res     = results[0]

        annotated_img      = res.plot()
        annotated_filename = "annotated_" + filename
        cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], annotated_filename), annotated_img)

        # 2. Pre-filter boxes and run search in parallel
        upload_dir  = app.config['UPLOAD_FOLDER']
        valid_boxes = [
            (i, box) for i, box in enumerate(res.boxes)
            if float(box.conf[0].cpu().numpy()) >= YOLO_CONF_THRESHOLD
        ]

        box_results = {}
        if valid_boxes:
            args_list = [(i, box, pil_img, upload_dir, filename) for i, box in valid_boxes]
            with ThreadPoolExecutor(max_workers=min(4, len(valid_boxes))) as executor:
                futures = {executor.submit(_process_box, args): args[0] for args in args_list}
                for future in as_completed(futures):
                    i = futures[future]
                    try:
                        result = future.result()
                        if result is not None:
                            box_results[i] = result
                    except Exception as e:
                        log.error("Future for box %d failed: %s", i, e)

        # 3. Assign IDs and resolve URLs in order (url_for requires app context — done here)
        detections = []
        for i in sorted(box_results.keys()):
            det = box_results[i]
            det['id']         = len(detections) + 1
            det['crop_image'] = url_for('static', filename=f'uploads/{det.pop("crop_filename")}')
            for sim in det['similar_items']:
                sim['image_url'] = _build_image_url(sim.get('image_path', ''))
            detections.append(det)

        # 4. Fallback: no YOLO detections — run whole-image search
        if not detections:
            log.info("No YOLO detections — running whole-image fallback search")
            try:
                fallback_threshold = max(0.25, SIMILARITY_THRESHOLD - 0.10)
                raw_results        = search_engine.search(pil_img, top_k=6, threshold=fallback_threshold)
                similarity_results = _deduplicate(raw_results)[:3]

                for sim in similarity_results:
                    sim['image_url'] = _build_image_url(sim.get('image_path', ''))

                if similarity_results:
                    top               = similarity_results[0]
                    predicted_product = top.get('product_name') or _name_from_path(top.get('image_path', ''))
                    product_price     = top.get('price', 'N/A')
                    match_confidence  = top.get('similarity_score', 0)

                    detections.append({
                        "id":             1,
                        "detection_type": "direct_match",
                        "class":          predicted_product,
                        "price":          product_price,
                        "confidence":     0.0,   # YOLO did not fire — not a real confidence score
                        "match_score":    round(match_confidence * 100, 2),
                        "bbox":           [0, 0, pil_img.width, pil_img.height],
                        "crop_image":     url_for('static', filename=f'uploads/{filename}'),
                        "similar_items":  similarity_results,
                    })
            except Exception as e:
                log.error("Whole-image fallback search failed: %s", e)

    except Exception as e:
        return jsonify({"error": f"Processing failed: {e}"}), 500

    return jsonify({
        "message":         "Detection and search complete!",
        "original_image":  url_for('static', filename=f'uploads/{filename}'),
        "annotated_image": url_for('static', filename=f'uploads/{annotated_filename}'),
        "detections":      detections,
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
