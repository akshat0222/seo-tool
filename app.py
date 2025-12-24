from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import uuid

app = Flask(__name__)
CORS(app)  # 🔥 REQUIRED for static frontend → backend communication

# Render-safe temp directory
UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_page_data(url):
    headers = {"User-Agent": "Mozilla/5.0 (SEO Meta Analyzer Bot)"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    meta_title = soup.title.string.strip() if soup.title else ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_desc["content"].strip() if meta_desc else ""

    og_title_tag = soup.find("meta", property="og:title")
    og_title = og_title_tag["content"].strip() if og_title_tag else ""

    og_desc_tag = soup.find("meta", property="og:description")
    og_description = og_desc_tag["content"].strip() if og_desc_tag else ""

    h1 = soup.find("h1")
    page_title = h1.get_text(strip=True) if h1 else ""

    page_description = ""
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) > 50:
            page_description = text
            break

    return {
        "meta_title": meta_title,
        "meta_description": meta_description,
        "og_title": og_title,
        "og_description": og_description,
        "page_title": page_title,
        "page_description": page_description
    }

# 🔹 Health Check (Render friendly)
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "SEO Analyzer API running"}), 200

# 🔹 Single URL API
@app.route("/analyze", methods=["GET"])
def analyze():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "URL is required"}), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        data = extract_page_data(url)
        data["url"] = url
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 🔹 Bulk Excel API
@app.route("/bulk", methods=["POST"])
def bulk_analyze():
    if "file" not in request.files:
        return jsonify({"error": "Excel file required"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    upload_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.xlsx")
    file.save(upload_path)

    try:
        df = pd.read_excel(upload_path)
    except Exception:
        return jsonify({"error": "Invalid Excel file"}), 400

    if "url" not in df.columns:
        return jsonify({"error": "Excel must have 'url' column"}), 400

    df = df.dropna(subset=["url"])

    if len(df) > 100:
        return jsonify({"error": "Maximum 100 URLs allowed"}), 400

    results = []

    for raw_url in df["url"]:
        try:
            url = str(raw_url).strip()
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            data = extract_page_data(url)
            data["url"] = url
            results.append(data)

        except Exception as e:
            results.append({
                "url": raw_url,
                "error": str(e)
            })

    result_df = pd.DataFrame(results)
    output_path = os.path.join(
        UPLOAD_FOLDER, f"results_{uuid.uuid4()}.xlsx"
    )
    result_df.to_excel(output_path, index=False)

    os.remove(upload_path)

    return send_file(output_path, as_attachment=True)
