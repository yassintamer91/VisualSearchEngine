import codecs

new_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Supermarket Visual Search Engine</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Playfair+Display:wght@600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #272727;
            --bg-image: url('{{ url_for("static", filename="darkmode_background.jpg") }}');
            --bg-overlay: rgba(0, 0, 0, 0.5);
            --text-main: #ffffff;
            --text-muted: #a0a0a0;
            --text-subtitle: #cccccc;
            --box-bg: #333333;
            --box-border: #444444;
            --card-bg: rgba(43, 43, 43, 0.85);
            --item-bg: #222222;
            --accent: #61bcf7;
            --glass-bg: rgba(40, 40, 40, 0.5);
            --glass-border: rgba(255, 255, 255, 0.2);
            --drop-text: #e0e0e0;
            --btn-bg: #3498db;
            --btn-hover: #2980b9;
            --btn-icon: #ffffff;
        }

        [data-theme="light"] {
            --bg-main: #f4f6f9;
            --bg-image: url('{{ url_for("static", filename="lightmode_background.jpg") }}');
            --bg-overlay: rgba(255, 255, 255, 0.35);
            --text-main: #1e1e1e;
            --text-muted: #555555;
            --text-subtitle: #333333;
            --box-bg: #ffffff;
            --box-border: #dddddd;
            --card-bg: rgba(249, 249, 249, 0.85);
            --item-bg: #ffffff;
            --accent: #0078d7;
            --glass-bg: rgba(255, 255, 255, 0.45);
            --glass-border: rgba(0, 0, 0, 0.15);
            --drop-text: #333333;
            --btn-bg: #0078d7;
            --btn-hover: #005a9e;
            --btn-icon: #ffffff;
        }

        body { 
            font-family: 'DM Sans', 'Segoe UI', Tahoma, sans-serif; 
            background-color: var(--bg-main); 
            color: var(--text-main);
            margin: 0; 
            padding: 40px 20px; 
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
            position: relative;
            transition: background-color 0.3s, color 0.3s;
        }

        body::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image: var(--bg-image);
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            z-index: -2;
            transition: background-image 0.3s;
        }

        body::after {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background-color: var(--bg-overlay);
            z-index: -1;
            transition: background-color 0.3s;
        }

        .theme-toggle {
            position: absolute;
            top: 20px;
            right: 20px;
            background: transparent;
            border: none;
            color: var(--text-main);
            padding: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: opacity 0.3s, transform 0.3s, color 0.3s;
            opacity: 0.8;
            z-index: 10;
        }

        .theme-toggle:hover {
            opacity: 1;
            transform: scale(1.1);
        }
        
        .theme-toggle span { display: none; }
        
        .theme-toggle svg {
            width: 28px;
            height: 28px;
        }

        .hero-section {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 25px;
            width: 100%;
            max-width: 800px;
            margin-bottom: 40px;
            text-align: center;
            animation: fadeIn 0.6s ease-out;
            z-index: 1;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .logo-container img {
            width: 100%;
            max-width: 180px;
            object-fit: contain;
            border-radius: 12px;
            filter: drop-shadow(0 4px 10px rgba(0,0,0,0.3));
            background: transparent;
        }

        .main-title {
            font-family: 'Playfair Display', serif;
            font-size: 3rem;
            margin: 0;
            line-height: 1.2;
            color: var(--text-main);
            text-shadow: 0 2px 6px rgba(0,0,0,0.3);
        }
        
        .subtitle {
            font-size: 1.15rem;
            margin: 10px 0 0 0;
            color: var(--text-subtitle);
            font-weight: 500;
        }

        .search-area {
            display: flex;
            width: 100%;
            max-width: 700px;
            height: 70px;
            border-radius: 16px;
            border: 2px dashed var(--glass-border);
            background: var(--glass-bg);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            overflow: hidden;
            transition: all 0.3s ease;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            margin-top: 15px;
        }

        .search-area:hover, .search-area.dragover {
            border-color: var(--accent);
            transform: translateY(-2px);
            box-shadow: 0 12px 36px rgba(0,0,0,0.25);
            background: var(--card-bg);
        }

        .drop-zone {
            flex-grow: 1;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            padding-left: 25px;
            cursor: pointer;
        }

        .drop-zone-text {
            color: var(--drop-text);
            font-size: 18px;
            font-weight: 500;
            pointer-events: none;
            display: flex;
            align-items: center;
            gap: 12px;
            transition: color 0.3s;
        }

        .drop-zone-text svg {
            width: 26px;
            height: 26px;
            fill: var(--drop-text);
            transition: transform 0.3s ease;
        }

        .search-area:hover .drop-zone-text svg {
            transform: translateY(-3px) scale(1.05);
            fill: var(--accent);
        }

        .drop-zone input[type="file"] {
            position: absolute;
            left: 0; top: 0; width: 100%; height: 100%;
            opacity: 0;
            cursor: pointer;
        }

        .search-btn {
            width: 90px;
            background-color: var(--btn-bg);
            border: none;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        }

        .search-btn:hover {
            background-color: var(--btn-hover);
        }

        .search-btn svg {
            width: 32px;
            height: 32px;
            fill: var(--btn-icon);
            transition: transform 0.3s ease;
        }

        .search-btn:hover svg {
            transform: scale(1.15) rotate(-5deg);
        }

        .content-container {
            width: 100%;
            max-width: 1000px;
            margin-top: 30px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            z-index: 1;
        }

        .image-preview-container {
            display: none;
            background: var(--box-bg);
            padding: 20px;
            text-align: center;
            box-shadow: 0 8px 24px rgba(0,0,0,0.15);
            border-radius: 12px;
            border: 1px solid var(--box-border);
        }

        #preview, #annotatedPreview {
            max-width: 100%;
            border-radius: 8px;
        }

        .results-panel {
            background: var(--box-bg);
            padding: 25px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.15);
            border-radius: 12px;
            min-height: 200px;
            border: 1px solid var(--box-border);
        }

        .detection-card { 
            border: 1px solid var(--box-border); 
            padding: 20px; 
            margin-bottom: 20px; 
            background: var(--card-bg); 
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: transform 0.2s;
        }
        .detection-card:hover { transform: translateY(-2px); }
        
        .detection-card h3 { margin-top: 0; color: var(--accent); font-family: 'DM Sans', sans-serif; font-size: 1.4rem; }
        
        .similarity-list { list-style: none; padding: 0; display: flex; gap: 15px; overflow-x: auto; padding-bottom: 10px;}
        .similarity-item { background: var(--item-bg); border: 1px solid var(--box-border); padding: 12px; text-align: center; min-width: 130px; border-radius: 8px; }
        .similarity-item img { max-width: 110px; height: 110px; object-fit: cover; border-radius: 6px; box-shadow: 0 2px 6px rgba(0,0,0,0.1);}
        
        .loading { display: none; text-align: center; padding: 30px; font-weight: bold; color: var(--accent); font-size: 20px; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    </style>
</head>
<body>

    <!-- Theme Toggle -->
    <button class="theme-toggle" id="themeToggle" title="Toggle Light/Dark Mode">
        <svg id="themeIcon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="28" height="28" fill="currentColor">
            <path d="M12 7c-2.76 0-5 2.24-5 5s2.24 5 5 5 5-2.24 5-5-2.24-5-5-5zM2 13h2c.55 0 1-.45 1-1s-.45-1-1-1H2c-.55 0-1 .45-1 1s.45 1 1 1zm18 0h2c.55 0 1-.45 1-1s-.45-1-1-1h-2c-.55 0-1 .45-1 1s.45 1 1 1zM11 2v2c0 .55.45 1 1 1s1-.45 1-1V2c0-.55-.45-1-1-1s-1 .45-1 1zm0 18v2c0 .55.45 1 1 1s1-.45 1-1v-2c0-.55-.45-1-1-1s-1 .45-1 1zM5.99 4.58c-.39-.39-1.03-.39-1.41 0-.39.39-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0 .39-.39.39-1.03 0-1.41L5.99 4.58zm12.37 12.37c-.39-.39-1.03-.39-1.41 0-.39.39-.39 1.03 0 1.41l1.06 1.06c.39.39 1.03.39 1.41 0 .39-.39.39-1.03 0-1.41l-1.06-1.06zm1.06-10.96c.39-.39.39-1.03 0-1.41-.39-.39-1.03-.39-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41.39.39 1.03.39 1.41 0l1.06-1.06zM7.05 18.36c.39-.39.39-1.03 0-1.41-.39-.39-1.03-.39-1.41 0l-1.06 1.06c-.39.39-.39 1.03 0 1.41.39.39 1.03.39 1.41 0l1.06-1.06z"/>
        </svg>
        <span id="themeToggleText">Toggle Light Mode</span>
    </button>

    <!-- Center Flexbox Hero: Logo, Titles, Search -->
    <div class="hero-section">
        <div class="logo-container">
            <img src="{{ url_for('static', filename='logo.jpg') }}" alt="Supermarket Logo">
        </div>
        
        <div>
            <h1 class="main-title">Visual Supermarket Search</h1>
            <p class="subtitle">Snap a product, find it instantly.</p>
        </div>

        <form id="uploadForm" class="search-area" enctype="multipart/form-data">
            <div class="drop-zone" id="dropZone">
                <span class="drop-zone-text" id="dropZoneText">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM14 13v4h-4v-4H7l5-5 5 5h-3z"/></svg>
                    Drag and drop or click to add photos
                </span>
                <input type="file" id="imageInput" accept="image/*" required>
            </div>
            <button type="submit" class="search-btn" aria-label="Search">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
                    <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
                </svg>
            </button>
        </form>
    </div>

    <!-- Results Section -->
    <div class="content-container">
        
        <div id="loading" class="loading">?? Analyzing shelf and searching database...</div>
        
        <div class="image-preview-container" id="previewContainer">
            <h3 style="margin-top: 0; color: var(--text-muted);">Original Upload</h3>
            <img id="preview" alt="Image preview">
            <h3 style="margin-top: 30px; color: var(--text-muted); display: none;" id="annotatedTitle">Detection Results</h3>
            <img id="annotatedPreview" alt="Annotated Output" style="display: none;">
        </div>

        <div class="results-panel" id="resultsPanel" style="display: none;">
            <h2 style="margin-top: 0; font-family: 'Playfair Display', serif; color: var(--text-main);">Extracted Products & Matches</h2>
            <div id="resultsContainer"></div>
        </div>
    </div>

"""

js_part = codecs.open('script_extract.txt', 'r', 'utf-8').read()

with codecs.open('C:\\Users\\ytame\\Desktop\\New folder\\app\\templates\\index.html', 'w', 'utf-8') as f:
    f.write(new_html + js_part)

print("Done!")
