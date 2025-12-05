from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

def scrape_films():
    url = "https://sehatra.com/film/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    
    films = []
    seen_urls = set()
    
    containers = soup.find_all("div", class_="image-container")
    
    for container in containers:
        titre = ""
        image_url = ""
        url_video = ""
        
        img_elem = container.find("img")
        if img_elem:
            titre = img_elem.get("alt", "")
            image_url = img_elem.get("src", "")
        
        link_elem = container.find("a", class_="gen-button")
        if link_elem:
            href = link_elem.get("href", "")
            if href:
                if href.startswith("/"):
                    url_video = "https://sehatra.com" + href
                else:
                    url_video = href
        
        if titre and image_url and url_video not in seen_urls:
            seen_urls.add(url_video)
            films.append({
                "titre": titre,
                "image_url": image_url,
                "url_video": url_video
            })
    
    return films

@app.route("/recherche", methods=["GET"])
def recherche():
    video_query = request.args.get("video", "").lower()
    
    films = scrape_films()
    
    if video_query:
        resultats = [
            film for film in films 
            if video_query in film["titre"].lower()
        ]
    else:
        resultats = films
    
    return jsonify(resultats)

@app.route("/")
def index():
    return jsonify({
        "message": "API Sehatra Films",
        "usage": "/recherche?video=nom_du_film"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
