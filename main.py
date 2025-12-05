from flask import Flask, request, jsonify, Response
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

app = Flask(__name__)

def clean_title(raw_title):
    if not raw_title:
        return ""
    
    clean = re.sub(r'^\d{1,2}:\d{2}(:\d{2})?', '', raw_title)
    
    clean = re.sub(r'YouTube.*$', '', clean)
    clean = re.sub(r'Dailymotion.*$', '', clean)
    
    clean = clean.strip()
    return clean

def scrape_google_videos(query="film malagasy complet"):
    encoded_query = urllib.parse.quote(query)
    url = f"https://www.google.com/search?q={encoded_query}&udm=7&hl=fr"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = 'utf-8'
        html_content = response.text
        
        soup = BeautifulSoup(html_content, "html.parser")
        
        videos = []
        seen_urls = set()
        
        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "")
            
            if "youtube.com/watch" in href or "youtu.be" in href or "dailymotion.com" in href:
                video_url = None
                
                if href.startswith("/url?"):
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    if "q" in parsed:
                        video_url = parsed["q"][0]
                    elif "url" in parsed:
                        video_url = parsed["url"][0]
                else:
                    video_url = href
                
                if not video_url or video_url in seen_urls:
                    continue
                
                seen_urls.add(video_url)
                video_data = {"url_video": video_url}
                
                parent = a_tag
                for _ in range(5):
                    parent = parent.parent
                    if parent is None:
                        break
                
                if parent:
                    h3 = parent.find("h3")
                    if h3:
                        video_data["titre"] = clean_title(h3.get_text(strip=True))
                    else:
                        divs = parent.find_all("div")
                        for div in divs:
                            text = div.get_text(strip=True)
                            if len(text) > 20 and len(text) < 200:
                                video_data["titre"] = clean_title(text)
                                break
                    
                    img = parent.find("img")
                    if img:
                        src = img.get("src", "") or img.get("data-src", "")
                        if src and not src.startswith("data:"):
                            video_data["image_url"] = src
                    
                    spans = parent.find_all("span")
                    for span in spans:
                        text = span.get_text(strip=True)
                        if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', text):
                            video_data["duree"] = text
                        elif "YouTube" in text:
                            video_data["source"] = "YouTube"
                        elif "Dailymotion" in text:
                            video_data["source"] = "Dailymotion"
                
                if "titre" not in video_data or not video_data["titre"]:
                    title_text = a_tag.get_text(strip=True)
                    if title_text and len(title_text) > 5:
                        video_data["titre"] = clean_title(title_text)
                
                if "titre" in video_data and video_data["titre"]:
                    videos.append(video_data)
        
        return {
            "success": True,
            "query": query,
            "total": len(videos),
            "videos": videos
        }
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e),
            "query": query,
            "videos": []
        }

@app.route("/recherche", methods=["GET"])
def recherche():
    video_query = request.args.get("video", "film malagasy complet")
    
    result = scrape_google_videos(video_query)
    
    return jsonify(result)

@app.route("/html", methods=["GET"])
def get_raw_html():
    video_query = request.args.get("video", "film malagasy complet")
    encoded_query = urllib.parse.quote(video_query)
    url = f"https://www.google.com/search?q={encoded_query}&udm=7&hl=fr"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        return Response(response.text, mimetype='text/html; charset=utf-8')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return jsonify({
        "message": "API Google Video Search Scraper",
        "endpoints": {
            "/recherche": "GET - Scrape et parse les résultats vidéo Google",
            "/html": "GET - Récupère le HTML brut de Google"
        },
        "usage": {
            "recherche": "/recherche?video=film malagasy complet",
            "html": "/html?video=film malagasy complet"
        }
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
