from flask import Flask, request, jsonify, render_template, send_file
import requests
from bs4 import BeautifulSoup
import pandas as pd
import os
import uuid

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_page_data(url):
    headers = {"User-Agent": "Mozilla/5.0 (SEO Meta Analyzer Bot)"}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Meta Title
    meta_title = soup.title.string.strip() if soup.title else ""

    # Meta Description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    meta_description = meta_desc["content"].strip() if meta_desc else ""

    # OG Title
    og_title_tag = soup.find("meta", property="og:title")
    og_title = og_title_tag["content"].strip() if og_title_tag else ""

    # OG Description
    og_desc_tag = soup.find("meta", property="og:description")
    og_description = og_desc_tag["content"].strip() if og_desc_tag else ""

    # Page Title (H1)
    h1 = soup.find("h1")
    page_title = h1.get_text(strip=True) if h1 else ""

    # Page Description (first meaningful paragraph)
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


@app.route("/")
def home():
    return render_template("index.html")

# 🔹 Single URL
@app.route("/analyze", methods=["GET"])
def analyze():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "URL required"}), 400

    try:
        data = extract_page_data(url)
        data["url"] = url
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 🔹 Bulk Excel Upload
@app.route("/bulk", methods=["POST"])
def bulk_analyze():
    if "file" not in request.files:
        return jsonify({"error": "Excel file required"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    # Save uploaded file
    upload_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}.xlsx")
    file.save(upload_path)

    try:
        df = pd.read_excel(upload_path)
    except Exception:
        return jsonify({"error": "Invalid Excel file"}), 400

    if "url" not in df.columns:
        return jsonify({"error": "Excel must contain a 'url' column"}), 400

    # Drop empty URLs
    df = df.dropna(subset=["url"])

    # Optional safety limit
    if len(df) > 100:
        return jsonify({"error": "Maximum 100 URLs allowed per upload"}), 400

    results = []

    for raw_url in df["url"]:
        try:
            url = str(raw_url).strip()

            # Auto-fix missing scheme
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

    # Save result file
    result_df = pd.DataFrame(results)
    output_path = os.path.join(
        UPLOAD_FOLDER, f"results_{uuid.uuid4()}.xlsx"
    )
    result_df.to_excel(output_path, index=False)

    # Clean up uploaded file
    os.remove(upload_path)

    return send_file(output_path, as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
