from flask import Flask, request, jsonify, Response, send_file
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import os
import tempfile
import yt_dlp
import uuid

app = Flask(__name__)

DOWNLOAD_DIR = tempfile.gettempdir()

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

@app.route("/download", methods=["GET"])
def download_video():
    video_url = request.args.get("url", "")
    quality = request.args.get("quality", "best")
    
    if not video_url:
        return jsonify({"success": False, "error": "URL de vidéo requise. Utilisez ?url=VIDEO_URL"}), 400
    
    unique_id = str(uuid.uuid4())[:8]
    output_template = os.path.join(DOWNLOAD_DIR, f'video_{unique_id}.%(ext)s')
    
    if quality == "low":
        format_option = 'worst[ext=mp4]/worstvideo[ext=mp4]+worstaudio/worst'
    elif quality == "medium":
        format_option = 'best[height<=480][ext=mp4]/best[height<=480]/best[ext=mp4]/best'
    else:
        format_option = 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
    
    ydl_opts = {
        'format': format_option,
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'noplaylist': True,
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            
            title = info.get('title', 'video')
            safe_title = re.sub(r'[^\w\s-]', '', title)[:50]
            
            downloaded_file = None
            for ext in ['mp4', 'webm', 'mkv', 'mp3', 'm4a']:
                potential_file = os.path.join(DOWNLOAD_DIR, f'video_{unique_id}.{ext}')
                if os.path.exists(potential_file):
                    downloaded_file = potential_file
                    break
            
            if not downloaded_file:
                for f in os.listdir(DOWNLOAD_DIR):
                    if f.startswith(f'video_{unique_id}'):
                        downloaded_file = os.path.join(DOWNLOAD_DIR, f)
                        break
            
            if downloaded_file and os.path.exists(downloaded_file):
                ext = os.path.splitext(downloaded_file)[1]
                download_name = f"{safe_title}{ext}"
                
                return send_file(
                    downloaded_file,
                    as_attachment=True,
                    download_name=download_name,
                    mimetype='video/mp4'
                )
            else:
                return jsonify({
                    "success": False, 
                    "error": "Fichier téléchargé introuvable"
                }), 500
                
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/info", methods=["GET"])
def video_info():
    video_url = request.args.get("url", "")
    
    if not video_url:
        return jsonify({"success": False, "error": "URL de vidéo requise"}), 400
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            return jsonify({
                "success": True,
                "titre": info.get('title'),
                "duree": info.get('duration'),
                "thumbnail": info.get('thumbnail'),
                "channel": info.get('channel') or info.get('uploader'),
                "view_count": info.get('view_count'),
                "upload_date": info.get('upload_date'),
                "description": info.get('description', '')[:500] if info.get('description') else None,
                "formats_disponibles": [
                    {
                        "format_id": f.get('format_id'),
                        "ext": f.get('ext'),
                        "resolution": f.get('resolution') or f"{f.get('width', '?')}x{f.get('height', '?')}",
                        "filesize": f.get('filesize') or f.get('filesize_approx')
                    }
                    for f in info.get('formats', [])[:10]
                ]
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

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
        "message": "API Google Video Search & Downloader",
        "endpoints": {
            "/recherche": "GET - Scrape et parse les résultats vidéo Google",
            "/download": "GET - Télécharger une vidéo YouTube/Dailymotion",
            "/info": "GET - Obtenir les infos d'une vidéo",
            "/html": "GET - Récupère le HTML brut de Google"
        },
        "usage": {
            "recherche": "/recherche?video=film malagasy complet",
            "download": "/download?url=https://youtube.com/watch?v=XXX&quality=best",
            "info": "/info?url=https://youtube.com/watch?v=XXX",
            "html": "/html?video=film malagasy complet"
        },
        "qualites": ["best", "medium", "low"]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
