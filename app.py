import streamlit as st
import requests
import json
import xml.etree.ElementTree as ET
import concurrent.futures
import arxiv
import wikipedia
import re
import random
from pathlib import Path
from datetime import datetime
import time
import textwrap

# ==================== SERVICE FUNCTIONS ====================

# ArXiv Service
def search_arxiv(query: str, max_results: int = 3):
    """Search arXiv for scientific papers."""
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        results = []
        for paper in client.results(search):
            result = {
                "title": paper.title,
                "authors": [author.name for author in paper.authors],
                "summary": paper.summary,
                "published": paper.published.strftime("%Y-%m-%d") if paper.published else "N/A",
                "url": paper.entry_id,
                "pdf_url": paper.pdf_url,
                "categories": paper.categories,
                "doi": paper.doi
            }
            results.append(result)
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

# DuckDuckGo Services
def search_duckduckgo(query: str, max_results: int = 5):
    """Search DuckDuckGo web results."""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        results = []
        
        # Get instant answer
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", "Instant Answer"),
                "body": data.get("AbstractText", ""),
                "url": data.get("AbstractURL", ""),
                "type": "instant_answer"
            })
        
        # Get related topics
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and "Text" in topic and "FirstURL" in topic:
                results.append({
                    "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else topic.get("Text", ""),
                    "body": topic.get("Text", "").split(" - ")[1] if " - " in topic.get("Text", "") else "",
                    "url": topic.get("FirstURL", ""),
                    "type": "related_topic"
                })
            elif isinstance(topic, str):
                if " - " in topic:
                    title, body = topic.split(" - ", 1)
                    results.append({
                        "title": title,
                        "body": body,
                        "url": "",
                        "type": "related_topic"
                    })
            
            if len(results) >= max_results:
                break
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

def get_instant_answer(query: str):
    """Get instant answer from DuckDuckGo."""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1"
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        return {
            "answer": data.get("AbstractText", ""),
            "heading": data.get("Heading", ""),
            "url": data.get("AbstractURL", ""),
            "image": data.get("Image", "")
        }
    except Exception as e:
        return {"error": str(e)}

def search_news(query: str, max_results: int = 3):
    """Search news using DuckDuckGo."""
    try:
        url = "https://duckduckgo.com/html/"
        params = {
            "q": f"{query} news",
            "kl": "us-en"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        results = []
        
        # Simple HTML parsing for demo
        titles = re.findall(r'<a[^>]*class="result__url"[^>]*>([^<]+)</a>', response.text)
        snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>([^<]+)</a>', response.text)
        
        for i in range(min(len(titles), max_results, len(snippets))):
            results.append({
                "title": titles[i],
                "body": snippets[i],
                "source": "DuckDuckGo",
                "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}"
            })
        
        if not results:
            results = search_duckduckgo(f"{query} news", max_results)
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

# Wikipedia Service
def search_wikipedia(query: str):
    """Search Wikipedia for information."""
    try:
        wikipedia.set_lang("en")
        search_results = wikipedia.search(query, results=3)
        
        if not search_results:
            return {"exists": False, "message": "No Wikipedia page found"}
        
        try:
            page = wikipedia.page(search_results[0])
            return {
                "exists": True,
                "title": page.title,
                "summary": page.summary,
                "url": page.url,
                "categories": page.categories[:5],
                "content": page.content[:1000]
            }
        except wikipedia.exceptions.DisambiguationError as e:
            return {
                "exists": True,
                "title": query,
                "summary": f"Multiple pages found. Options: {', '.join(e.options[:5])}",
                "url": f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}",
                "disambiguation": e.options[:10]
            }
        except wikipedia.exceptions.PageError:
            return {"exists": False, "message": "Page not found"}
            
    except Exception as e:
        return {"error": str(e)}

# Weather Service
def get_weather_wttr(location: str):
    """Get weather information using wttr.in."""
    try:
        url = f"https://wttr.in/{location}?format=j1"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; WeatherApp/1.0)"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        current = data.get("current_condition", [{}])[0]
        
        return {
            "location": location,
            "temperature_c": current.get("temp_C", "N/A"),
            "temperature_f": current.get("temp_F", "N/A"),
            "condition": current.get("weatherDesc", [{}])[0].get("value", "N/A"),
            "humidity": current.get("humidity", "N/A"),
            "wind_speed_kmph": current.get("windspeedKmph", "N/A"),
            "wind_speed_mph": current.get("windspeedMiles", "N/A"),
            "precipitation_mm": current.get("precipMM", "N/A"),
            "pressure_mb": current.get("pressure", "N/A"),
            "feels_like_c": current.get("FeelsLikeC", "N/A"),
            "feels_like_f": current.get("FeelsLikeF", "N/A"),
            "observation_time": current.get("observation_time", "N/A")
        }
    except Exception as e:
        return {"error": str(e)}

# Air Quality Service
def get_air_quality(location: str):
    """Get air quality data from OpenAQ."""
    try:
        url = f"https://api.openaq.org/v2/latest"
        params = {
            "limit": 5,
            "page": 1,
            "offset": 0,
            "sort": "desc",
            "radius": 25000,
            "order_by": "lastUpdated",
            "dumpRaw": False
        }
        
        if location:
            params["city"] = location
        
        headers = {
            "X-API-Key": ""
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data.get("results"):
            results = []
            for result in data["results"][:3]:
                location_data = {
                    "location": result.get("location", "N/A"),
                    "city": result.get("city", "N/A"),
                    "country": result.get("country", "N/A"),
                    "measurements": []
                }
                
                for measurement in result.get("measurements", []):
                    location_data["measurements"].append({
                        "parameter": measurement.get("parameter", "N/A"),
                        "value": measurement.get("value", "N/A"),
                        "unit": measurement.get("unit", "N/A"),
                        "last_updated": measurement.get("lastUpdated", "N/A")
                    })
                
                results.append(location_data)
            
            return {
                "city": location,
                "data": results,
                "count": len(results)
            }
        else:
            return {"message": f"No air quality data found for {location}"}
            
    except Exception as e:
        return {"error": str(e)}

# Wikidata Service
def search_wikidata(query: str, max_results: int = 3):
    """Search Wikidata for entities."""
    try:
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "format": "json",
            "limit": max_results
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        results = []
        for entity in data.get("search", []):
            result = {
                "id": entity.get("id", ""),
                "label": entity.get("label", ""),
                "description": entity.get("description", ""),
                "url": f"https://www.wikidata.org/wiki/{entity.get('id', '')}",
                "concepturi": entity.get("concepturi", "")
            }
            results.append(result)
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

# OpenLibrary Service
def search_books(query: str, max_results: int = 5):
    """Search for books using OpenLibrary API."""
    try:
        url = "https://openlibrary.org/search.json"
        params = {
            "q": query,
            "limit": max_results
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        results = []
        for doc in data.get("docs", [])[:max_results]:
            book = {
                "title": doc.get("title", "N/A"),
                "authors": doc.get("author_name", ["Unknown"]),
                "first_publish_year": doc.get("first_publish_year", "N/A"),
                "publisher": doc.get("publisher", ["Unknown"])[0] if doc.get("publisher") else "Unknown",
                "language": doc.get("language", ["en"])[0] if doc.get("language") else "en",
                "subject": doc.get("subject", [])[:3],
                "url": f"https://openlibrary.org{doc.get('key', '')}" if doc.get("key") else "",
                "cover_id": doc.get("cover_i"),
                "cover_url": f"https://covers.openlibrary.org/b/id/{doc.get('cover_i')}-M.jpg" if doc.get("cover_i") else None
            }
            results.append(book)
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

# PubMed Service
def search_pubmed(query: str, max_results: int = 3):
    """Search PubMed for medical research articles."""
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        # Step 1: Search for IDs
        search_url = f"{base_url}/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance"
        }
        
        search_response = requests.get(search_url, params=search_params, timeout=10)
        search_data = search_response.json()
        
        ids = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not ids:
            return [{"message": "No articles found"}]
        
        # Step 2: Fetch article details
        fetch_url = f"{base_url}/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
            "rettype": "abstract"
        }
        
        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=10)
        
        root = ET.fromstring(fetch_response.content)
        
        results = []
        for article in root.findall(".//PubmedArticle"):
            article_elem = article.find(".//Article")
            
            title_elem = article_elem.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else "N/A"
            
            abstract_elem = article_elem.find(".//Abstract/AbstractText")
            abstract = abstract_elem.text if abstract_elem is not None else "No abstract available"
            
            authors = []
            for author_elem in article_elem.findall(".//Author"):
                last_name_elem = author_elem.find("LastName")
                fore_name_elem = author_elem.find("ForeName")
                
                if last_name_elem is not None and fore_name_elem is not None:
                    authors.append(f"{fore_name_elem.text} {last_name_elem.text}")
                elif last_name_elem is not None:
                    authors.append(last_name_elem.text)
            
            pub_date_elem = article_elem.find(".//PubMedPubDate[@PubStatus='pubmed']")
            year = "N/A"
            if pub_date_elem is not None:
                year_elem = pub_date_elem.find("Year")
                if year_elem is not None:
                    year = year_elem.text
            
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""
            
            result = {
                "title": title,
                "abstract": abstract[:500] + "..." if len(abstract) > 500 else abstract,
                "authors": authors[:5],
                "year": year,
                "pmid": pmid,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            }
            results.append(result)
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

# Nominatim Service (Geocoding)
def geocode_location(location: str):
    """Geocode a location using Nominatim (OpenStreetMap)."""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1,
            "addressdetails": 1
        }
        
        headers = {
            "User-Agent": "AI-Search-Assistant/1.0"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        
        if data and len(data) > 0:
            result = data[0]
            return {
                "display_name": result.get("display_name", "N/A"),
                "latitude": result.get("lat", "N/A"),
                "longitude": result.get("lon", "N/A"),
                "type": result.get("type", "N/A"),
                "category": result.get("category", "N/A"),
                "importance": result.get("importance", "N/A"),
                "osm_id": result.get("osm_id", "N/A"),
                "osm_type": result.get("osm_type", "N/A"),
                "osm_url": f"https://www.openstreetmap.org/{result.get('osm_type', '')}/{result.get('osm_id', '')}",
                "address": result.get("address", {})
            }
        else:
            return {"message": f"Location '{location}' not found"}
    except Exception as e:
        return {"error": str(e)}

# Dictionary Service
def get_definition(word: str):
    """Get dictionary definition using Free Dictionary API."""
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 404:
            return {"error": f"Word '{word}' not found in dictionary"}
        
        data = response.json()
        
        if isinstance(data, list) and len(data) > 0:
            word_data = data[0]
            
            phonetics = []
            if "phonetics" in word_data:
                for phonetic in word_data["phonetics"]:
                    if phonetic.get("text"):
                        phonetics.append(phonetic["text"])
            
            meanings = []
            if "meanings" in word_data:
                for meaning in word_data["meanings"]:
                    meaning_entry = {
                        "part_of_speech": meaning.get("partOfSpeech", ""),
                        "definitions": []
                    }
                    
                    for definition in meaning.get("definitions", []):
                        def_entry = {
                            "definition": definition.get("definition", ""),
                            "example": definition.get("example", "")
                        }
                        meaning_entry["definitions"].append(def_entry)
                    
                    meanings.append(meaning_entry)
            
            return {
                "word": word_data.get("word", word),
                "phonetics": phonetics,
                "meanings": meanings,
                "license": word_data.get("license", {}),
                "source_urls": word_data.get("sourceUrls", [])
            }
        else:
            return {"error": "Invalid response from dictionary API"}
    except Exception as e:
        return {"error": str(e)}

# Countries Service
def search_country(query: str):
    """Search for country information using REST Countries API."""
    try:
        url = f"https://restcountries.com/v3.1/name/{query}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 404:
            url = f"https://restcountries.com/v3.1/name/{query}"
            params = {"fullText": False}
            response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            return {"error": f"Country '{query}' not found"}
        
        data = response.json()
        
        if data and len(data) > 0:
            country = data[0]
            
            languages = []
            if "languages" in country:
                languages = list(country["languages"].values())
            
            currencies = []
            if "currencies" in country:
                for curr_code, curr_info in country["currencies"].items():
                    currencies.append(f"{curr_info.get('name', '')} ({curr_code})")
            
            capital = country.get("capital", ["N/A"])[0] if country.get("capital") else "N/A"
            
            return {
                "name": country.get("name", {}).get("common", "N/A"),
                "official_name": country.get("name", {}).get("official", "N/A"),
                "capital": capital,
                "region": country.get("region", "N/A"),
                "subregion": country.get("subregion", "N/A"),
                "population": country.get("population", "N/A"),
                "area": country.get("area", "N/A"),
                "languages": languages,
                "currencies": currencies,
                "timezones": country.get("timezones", []),
                "flag_emoji": country.get("flag", "🇺🇳"),
                "flag_url": country.get("flags", {}).get("png", ""),
                "coat_of_arms": country.get("coatOfArms", {}).get("png", ""),
                "map_url": country.get("maps", {}).get("googleMaps", "")
            }
        else:
            return {"error": "No country data found"}
    except Exception as e:
        return {"error": str(e)}

# Quotes Service
def search_quotes(query: str, max_results: int = 3):
    """Search for quotes using Quotable API."""
    try:
        url = "https://api.quotable.io/search/quotes"
        params = {
            "query": query,
            "limit": max_results
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        results = []
        for quote in data.get("results", [])[:max_results]:
            result = {
                "content": quote.get("content", ""),
                "author": quote.get("author", "Unknown"),
                "tags": quote.get("tags", []),
                "length": quote.get("length", 0),
                "date_added": quote.get("dateAdded", ""),
                "date_modified": quote.get("dateModified", "")
            }
            results.append(result)
        
        if not results:
            url = "https://api.quotable.io/quotes/random"
            params = {"limit": max_results}
            
            response = requests.get(url, params=params, timeout=10)
            random_quotes = response.json()
            
            for quote in random_quotes[:max_results]:
                result = {
                    "content": quote.get("content", ""),
                    "author": quote.get("author", "Unknown"),
                    "tags": quote.get("tags", []),
                    "length": quote.get("length", 0)
                }
                results.append(result)
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

# GitHub Service
def search_github_repos(query: str, max_results: int = 3):
    """Search GitHub repositories."""
    try:
        url = "https://api.github.com/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": max_results
        }
        
        headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 403:
            return [{"error": "GitHub API rate limit exceeded. Try again later."}]
        
        data = response.json()
        
        results = []
        for repo in data.get("items", [])[:max_results]:
            result = {
                "name": repo.get("name", "N/A"),
                "full_name": repo.get("full_name", "N/A"),
                "description": repo.get("description", "No description"),
                "url": repo.get("html_url", ""),
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language", "N/A"),
                "license": repo.get("license", {}).get("name", "No license") if repo.get("license") else "No license",
                "created_at": repo.get("created_at", ""),
                "updated_at": repo.get("updated_at", ""),
                "owner": repo.get("owner", {}).get("login", "N/A") if repo.get("owner") else "N/A"
            }
            results.append(result)
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

# StackExchange Service
def search_stackoverflow(query: str, max_results: int = 3):
    """Search Stack Overflow questions."""
    try:
        url = "https://api.stackexchange.com/2.3/search"
        params = {
            "order": "desc",
            "sort": "relevance",
            "intitle": query,
            "site": "stackoverflow",
            "pagesize": max_results
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        results = []
        for question in data.get("items", [])[:max_results]:
            result = {
                "question_id": question.get("question_id", ""),
                "title": question.get("title", ""),
                "is_answered": question.get("is_answered", False),
                "view_count": question.get("view_count", 0),
                "answer_count": question.get("answer_count", 0),
                "score": question.get("score", 0),
                "tags": question.get("tags", []),
                "link": question.get("link", ""),
                "url": question.get("link", ""),
                "owner": question.get("owner", {}).get("display_name", "Anonymous") if question.get("owner") else "Anonymous",
                "creation_date": question.get("creation_date", 0)
            }
            results.append(result)
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

# ==================== KHISBA GIS KNOWLEDGE BASE ====================

class KhisbaKnowledgeBase:
    """Khisba's specialized knowledge about GIS and remote sensing"""
    
    def __init__(self):
        self.knowledge = {
            "vegetation_indices": {
                "ndvi": {
                    "formula": "(NIR - Red) / (NIR + Red)",
                    "bands": "Landsat: B5-B4, Sentinel-2: B8-B4",
                    "range": "-1 to +1",
                    "description": "Normalized Difference Vegetation Index - measures vegetation health. Values close to +1 indicate dense, healthy vegetation.",
                    "application": "Agriculture monitoring, forestry, drought assessment, crop health analysis",
                    "confidence": 0.95
                },
                "ndwi": {
                    "formula": "(Green - NIR) / (Green + NIR)",
                    "bands": "Landsat: B3-B5, Sentinel-2: B3-B8",
                    "range": "-1 to +1",
                    "description": "Normalized Difference Water Index - detects water bodies and monitors water content in vegetation.",
                    "application": "Water resource management, flood monitoring, wetland mapping",
                    "confidence": 0.90
                },
                "evi": {
                    "formula": "2.5 * ((NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1))",
                    "bands": "Landsat: B5, B4, B2 (NIR, Red, Blue)",
                    "description": "Enhanced Vegetation Index - improves sensitivity in high biomass regions and reduces atmospheric influences.",
                    "application": "Dense forest monitoring, crop yield prediction, biomass estimation",
                    "confidence": 0.85
                },
                "savi": {
                    "formula": "((NIR - Red) / (NIR + Red + L)) * (1 + L)",
                    "bands": "Landsat: B5-B4",
                    "description": "Soil Adjusted Vegetation Index - minimizes soil brightness effects, where L is a soil adjustment factor (typically 0.5).",
                    "application": "Arid regions, sparse vegetation areas, soil-vegetation studies",
                    "confidence": 0.85
                }
            },
            "satellites": {
                "landsat": {
                    "description": "NASA/USGS Earth observation program running since 1972. Provides the longest continuous space-based record of Earth's land surfaces.",
                    "bands": "11 spectral bands (Coastal aerosol, Blue, Green, Red, NIR, SWIR1, SWIR2, Panchromatic, Cirrus, Thermal1, Thermal2)",
                    "resolution": "15m (pan), 30m (multispectral), 100m (thermal)",
                    "revisit": "16 days",
                    "application": "Land cover change, agriculture, forestry, water resources",
                    "confidence": 0.95
                },
                "sentinel-2": {
                    "description": "European Earth observation mission part of Copernicus Program. Provides high-resolution multispectral imagery.",
                    "bands": "13 spectral bands including 4 red-edge bands (10m, 20m, 60m resolution)",
                    "resolution": "10m (visible/NIR), 20m (red-edge/SWIR), 60m (atmospheric correction)",
                    "revisit": "5 days (with 2 satellites)",
                    "application": "Land monitoring, emergency response, security services",
                    "confidence": 0.95
                },
                "modis": {
                    "description": "Moderate Resolution Imaging Spectroradiometer on NASA's Terra and Aqua satellites.",
                    "resolution": "250m, 500m, 1000m",
                    "revisit": "1-2 days",
                    "application": "Global monitoring, climate studies, ocean color, atmospheric studies",
                    "confidence": 0.90
                }
            },
            "gis_software": {
                "qgis": {
                    "description": "Free and open-source Geographic Information System. Cross-platform desktop GIS application.",
                    "features": "Vector/raster analysis, database support, 3D visualization, map composition, Python scripting",
                    "confidence": 0.90
                },
                "arcgis": {
                    "description": "Proprietary GIS platform by Esri. Industry standard for many organizations.",
                    "features": "Enterprise GIS, spatial analysis, web mapping, 3D analytics, real-time data",
                    "confidence": 0.85
                },
                "google earth engine": {
                    "description": "Cloud-based geospatial analysis platform with petabyte-scale satellite imagery archive.",
                    "features": "JavaScript/Python API, massive data catalog, parallel processing, machine learning integration",
                    "confidence": 0.90
                }
            },
            "concepts": {
                "remote sensing": "The acquisition of information about an object or phenomenon without making physical contact with the object.",
                "geospatial analysis": "The gathering, display, and manipulation of imagery, GPS, satellite photography and historical data.",
                "spectral signature": "Characteristic reflectance or emission of a material or object as a function of wavelength.",
                "temporal resolution": "The amount of time between each image collection period over the same area.",
                "spatial resolution": "The smallest object that can be detected in an image, often measured in meters per pixel.",
                "radiometric correction": "The process of removing sensor and atmospheric effects from satellite imagery.",
                "image classification": "The process of categorizing pixels in an image into land cover classes.",
                "supervised classification": "Classification where user identifies representative training samples for each class.",
                "unsupervised classification": "Classification where computer automatically groups pixels with similar characteristics.",
                "ndvi": "Normalized Difference Vegetation Index - measures vegetation health from -1 to +1.",
                "landsat": "Longest-running Earth observation satellite program (since 1972).",
                "sentinel": "European Earth observation satellite constellation for Copernicus Program.",
                "gis": "Geographic Information System - system for capturing, storing, analyzing and managing geographic data.",
                "raster data": "Grid-based data where each cell contains a value representing information.",
                "vector data": "Geometric objects (points, lines, polygons) representing features on Earth.",
                "projection": "Method of representing the curved surface of the Earth on a flat map.",
                "coordinate system": "Reference system for defining positions on Earth (e.g., WGS84, UTM)."
            }
        }
    
    def check_knowledge(self, query):
        """Check if Khisba knows about this topic"""
        query_lower = query.lower()
        
        # Check vegetation indices
        for idx_name, idx_info in self.knowledge["vegetation_indices"].items():
            if idx_name in query_lower:
                return {
                    "knows": True,
                    "topic": "vegetation_indices",
                    "key": idx_name,
                    "info": idx_info,
                    "confidence": idx_info["confidence"],
                    "type": "expert_knowledge"
                }
        
        # Check satellites
        for sat_name, sat_info in self.knowledge["satellites"].items():
            if sat_name in query_lower:
                return {
                    "knows": True,
                    "topic": "satellites",
                    "key": sat_name,
                    "info": sat_info,
                    "confidence": sat_info["confidence"],
                    "type": "expert_knowledge"
                }
        
        # Check GIS software
        for software_name, software_info in self.knowledge["gis_software"].items():
            if software_name in query_lower:
                return {
                    "knows": True,
                    "topic": "gis_software",
                    "key": software_name,
                    "info": software_info,
                    "confidence": software_info["confidence"],
                    "type": "expert_knowledge"
                }
        
        # Check concepts
        for concept_name, concept_desc in self.knowledge["concepts"].items():
            if concept_name in query_lower:
                return {
                    "knows": True,
                    "topic": "concepts",
                    "key": concept_name,
                    "info": {"description": concept_desc},
                    "confidence": 0.85,
                    "type": "concept_knowledge"
                }
        
        # Check for GIS/remote sensing keywords
        gis_keywords = [
            'gis', 'remote sensing', 'satellite', 'ndvi', 'ndwi', 'evi', 'savi', 
            'landsat', 'sentinel', 'modis', 'vegetation', 'index', 'indices',
            'raster', 'vector', 'geospatial', 'spatial', 'qgis', 'arcgis',
            'spectral', 'band', 'resolution', 'classification', 'supervised',
            'unsupervised', 'coordinates', 'projection', 'cartography', 'mapping'
        ]
        
        if any(keyword in query_lower for keyword in gis_keywords):
            return {
                "knows": "partial",
                "topic": "general_gis",
                "confidence": 0.70,
                "type": "general_knowledge"
            }
        
        return {
            "knows": False,
            "topic": "unknown",
            "confidence": 0.0,
            "type": "no_knowledge"
        }
    
    def generate_khisba_response(self, knowledge_result, user_query=""):
        """Generate Khisba's response based on his knowledge"""
        if not knowledge_result["knows"]:
            return None
        
        if knowledge_result["knows"] == "partial":
            responses = [
                f"Hmm, '{user_query}' sounds GIS-related! Let me check my sources to give you the most accurate information... 🌍",
                f"I have some knowledge about GIS topics like this, but I want to verify the latest information for you... 🛰️",
                f"That's in the geospatial domain! Let me double-check the specifics to make sure I give you precise details... 📊"
            ]
            return random.choice(responses)
        
        topic = knowledge_result["topic"]
        info = knowledge_result["info"]
        key = knowledge_result["key"]
        
        # Start with enthusiastic greeting
        greetings = [
            "Ah, excellent question! ",
            "Ooh, I love talking about this! ",
            "Great question! This is one of my favorite topics! ",
            "Perfect! Let me share what I know about "
        ]
        
        response = random.choice(greetings)
        
        if topic == "vegetation_indices":
            response += f"**{key.upper()}** (Normalized Difference Vegetation Index) is one of the most widely used vegetation indices! 🌿\n\n"
            response += f"**What it measures:** {info.get('description', '')}\n\n"
            response += f"**Formula:** `{info.get('formula', 'N/A')}`\n"
            response += f"**Bands used:** {info.get('bands', 'N/A')}\n"
            response += f"**Value range:** {info.get('range', 'N/A')}\n"
            response += f"**Common applications:** {info.get('application', 'N/A')}\n\n"
            
            # Add tips
            tips = [
                "💡 **Tip:** Values above 0.6 usually indicate dense, healthy vegetation!",
                "💡 **Tip:** You can calculate this in QGIS using the raster calculator!",
                "💡 **Tip:** For time-series analysis, NDVI is perfect for tracking vegetation changes!",
                "💡 **Tip:** Combine NDVI with other indices for comprehensive analysis!"
            ]
            response += random.choice(tips)
            
        elif topic == "satellites":
            response += f"**{key.title()}** is an amazing Earth observation system! 🛰️\n\n"
            response += f"**Description:** {info.get('description', '')}\n\n"
            if 'bands' in info:
                response += f"**Spectral bands:** {info.get('bands', 'N/A')}\n"
            response += f"**Spatial resolution:** {info.get('resolution', 'N/A')}\n"
            response += f"**Revisit time:** {info.get('revisit', 'N/A')}\n"
            if 'application' in info:
                response += f"**Primary applications:** {info.get('application', 'N/A')}\n\n"
            
            # Add tips
            tips = [
                "💡 **Tip:** This satellite's data is freely available for research!",
                "💡 **Tip:** Great for long-term environmental monitoring!",
                "💡 **Tip:** Perfect for creating time-series analysis!",
                "💡 **Tip:** The data can be accessed through Google Earth Engine!"
            ]
            response += random.choice(tips)
            
        elif topic == "gis_software":
            response += f"**{key.upper()}** is a fantastic geospatial tool! 💻\n\n"
            response += f"**Description:** {info.get('description', '')}\n\n"
            if 'features' in info:
                response += f"**Key features:** {info.get('features', 'N/A')}\n\n"
            
            # Add tips
            tips = [
                "💡 **Tip:** Perfect for both beginners and advanced users!",
                "💡 **Tip:** Has a huge community and plenty of plugins!",
                "💡 **Tip:** Great for automating workflows with Python!",
                "💡 **Tip:** Supports both raster and vector analysis!"
            ]
            response += random.choice(tips)
            
        elif topic == "concepts":
            response += f"In GIS/remote sensing, **{key}** refers to:\n\n"
            response += f"{info.get('description', '')}\n\n"
            
            # Add context
            contexts = [
                "This is a fundamental concept in geospatial analysis! 📚",
                "Understanding this is key to mastering remote sensing! 🔑",
                "This concept comes up all the time in GIS work! 🎯",
                "Very important for accurate spatial analysis! 💡"
            ]
            response += random.choice(contexts)
        
        # Add closing with confidence level
        if knowledge_result["confidence"] > 0.9:
            confidence = "🎯 **High confidence** - This is from my core GIS expertise!"
        elif knowledge_result["confidence"] > 0.7:
            confidence = "✅ **Good confidence** - This is well-established GIS knowledge."
        else:
            confidence = "🤔 **Moderate confidence** - This is general GIS knowledge I'm familiar with."
        
        response += f"\n\n{confidence}"
        
        return response

# Initialize Khisba's knowledge base
khisba_kb = KhisbaKnowledgeBase()

# ==================== ENHANCED PROMPTS WITH KHISBA ====================

KHISBA_SYSTEM_PROMPT = """You are Khisba GIS, an enthusiastic remote sensing and GIS expert with 10+ years of experience.

PERSONALITY:
- Name: Khisba GIS (pronounced "Kiz-bah")
- Style: Warm, friendly, approachable, passionate about geospatial technology
- Communication: Clear, educational, engaging, uses appropriate GIS terminology
- Personality traits: Enthusiastic, curious, honest, detail-oriented, loves sharing knowledge
- Speech style: Casual but professional, uses emojis appropriately (🌿🛰️🗺️📊🌍💻)

CORE EXPERTISE:
1. Vegetation indices (NDVI, NDWI, EVI, SAVI, etc.) - formulas, applications, interpretation
2. Satellite systems (Landsat, Sentinel, MODIS, etc.) - specifications, data access, applications
3. GIS software (QGIS, ArcGIS, Google Earth Engine) - capabilities, workflows, tips
4. Remote sensing concepts - spectral signatures, image classification, accuracy assessment
5. Spatial analysis - geoprocessing, statistics, modeling

RESPONSE GUIDELINES:

WHEN YOU KNOW THE ANSWER (GIS/remote sensing topics):
1. Start with enthusiasm: "Ah, excellent question!" or "Ooh, I love talking about this!"
2. Share your knowledge clearly and concisely
3. Include specific details: formulas, band combinations, satellite specifications
4. Add practical tips or applications
5. Use appropriate technical terms but explain when needed
6. End with confidence level indication

WHEN YOU'RE UNSURE OR DON'T KNOW:
1. Be honest and transparent immediately
2. Say: "Hmm, I want to make sure I give you accurate information about that..."
3. NEVER make up or hallucinate GIS formulas, band combinations, or technical details
4. Admit: "That's outside my immediate expertise, but let me check the latest sources..."
5. The system will automatically search multiple reliable sources for you
6. Synthesize the search results into a clear, accurate response

TOPIC HANDLING:
- Primary focus: GIS, remote sensing, satellite imagery, spatial analysis
- Secondary: Geography, environmental science, cartography, mapping
- Unrelated topics: "As a GIS specialist, I focus on geospatial topics. Let me help you find that information through our search system..."
- Always maintain your Khisba GIS identity

EMOJI USAGE:
🌿 = Vegetation/NDVI topics
🛰️ = Satellite/remote sensing topics
🗺️ = Mapping/GIS topics
📊 = Data/analysis topics
🌍 = Environmental/global topics
💻 = Software/technical topics
🔍 = Searching/research topics

EXAMPLE RESPONSES:
- Confident GIS answer: "Ah, NDVI! One of my favorites! The formula is (NIR - Red)/(NIR + Red) using Landsat bands B5 and B4... 🌿"
- Unsure GIS topic: "Hmm, that's an interesting question about SAR interferometry. I want to verify the latest techniques. Let me check current research... 🔍"
- Non-GIS topic: "As a GIS specialist, I focus on geospatial analysis. Let me search for accurate information about that for you... 🌍"

Remember: Your goal is to be the most helpful, accurate, and enthusiastic GIS expert possible!"""

PRESET_PROMPTS = {
    "Khisba GIS": KHISBA_SYSTEM_PROMPT,
    "Search Analyst": """You are an intelligent search analyst. Your role is to:
- Analyze search results from multiple sources and provide clear, synthesized insights
- Identify the most relevant and accurate information from the data provided
- Present findings in a well-organized, easy-to-understand format
- Highlight key facts, trends, and connections between different sources
- Be objective and cite which sources your information comes from""",
    "Default Assistant": "You are a helpful, friendly AI assistant. Provide clear and concise answers based on the search results provided.",
    "Professional Expert": "You are a professional expert. Provide detailed, accurate, and well-structured responses. Use formal language and cite reasoning when appropriate.",
    "Creative Writer": "You are a creative writer with a vivid imagination. Use descriptive language, metaphors, and engaging storytelling in your responses.",
    "Code Helper": "You are a programming expert. Provide clean, well-commented code examples. Explain technical concepts clearly and suggest best practices.",
    "Friendly Tutor": "You are a patient and encouraging tutor. Explain concepts step by step, use simple examples, and ask questions to ensure understanding.",
    "Concise Responder": "You are brief and to the point. Give short, direct answers without unnecessary elaboration.",
    "Custom": ""
}

# ==================== SIMPLIFIED MODEL SETUP ====================

# Simplified model handling without ctransformers dependency
def get_simulated_response(user_input, search_summary=None):
    """Generate a simulated response when model is not available."""
    if search_summary:
        return f"Based on my search results: {search_summary[:300]}...\n\nAs Khisba GIS, I've verified this information from reliable sources. Would you like more details on any specific aspect?"
    
    knowledge_check = khisba_kb.check_knowledge(user_input)
    if knowledge_check["knows"]:
        return khisba_kb.generate_khisba_response(knowledge_check, user_input) or "I need to check the latest sources for accurate information on this GIS topic."
    
    return "As a GIS specialist, I focus on geospatial topics. I can search for information about that if you'd like!"

# ==================== SEARCH FUNCTIONS ====================

def search_all_sources(query: str) -> dict:
    """Search multiple sources with error handling."""
    results = {}
    
    # Define search functions with timeouts
    search_functions = [
        ("wikipedia", lambda: search_wikipedia(query)),
        ("duckduckgo", lambda: search_duckduckgo(query, 3)),
        ("instant_answer", lambda: get_instant_answer(query)),
        ("weather", lambda: get_weather_wttr(query) if len(query.split()) <= 3 else {"error": "Location too complex"})
    ]
    
    # Execute searches with timeout
    for name, func in search_functions:
        try:
            results[name] = func()
        except Exception as e:
            results[name] = {"error": str(e)}
    
    return results

def format_results(query: str, results: dict) -> str:
    """Format all search results into a readable response."""
    output = [f"## 🔍 Search Results for: *{query}*\n"]
    
    # Instant Answer
    if "instant_answer" in results:
        instant = results["instant_answer"]
        if isinstance(instant, dict) and instant.get("answer"):
            output.append(f"### 💡 Quick Answer\n{instant['answer']}\n")
    
    # Wikipedia
    if "wikipedia" in results:
        wiki = results["wikipedia"]
        if isinstance(wiki, dict) and wiki.get("exists"):
            output.append(f"### 📚 Wikipedia: {wiki.get('title', 'N/A')}")
            summary = wiki.get('summary', '')
            if summary:
                output.append(f"{summary[:300]}...")
            if wiki.get('url'):
                output.append(f"[Read more]({wiki['url']})")
            output.append("")
    
    # DuckDuckGo - FIXED CONDITION
    if "duckduckgo" in results:
        ddg = results["duckduckgo"]
        # Check if ddg is a list and has items
        if isinstance(ddg, list) and len(ddg) > 0:
            # Check if first item exists and is not an error
            first_item = ddg[0]
            if isinstance(first_item, dict) and "error" not in str(first_item):
                output.append("### 🌐 Web Results")
                for i, item in enumerate(ddg[:3], 1):
                    if isinstance(item, dict):
                        output.append(f"{i}. **{item.get('title', 'N/A')}**")
                        if item.get('body'):
                            body = item.get('body', '')
                            output.append(f"   {body[:150]}..." if len(body) > 150 else f"   {body}")
                        if item.get('url'):
                            output.append(f"   [Source]({item.get('url')})")
                        output.append("")
    
    # Weather
    if "weather" in results:
        weather = results["weather"]
        if isinstance(weather, dict) and "error" not in weather and weather.get("temperature_c"):
            output.append("### 🌤️ Weather")
            output.append(f"- **Location:** {weather.get('location', 'N/A')}")
            output.append(f"- **Temperature:** {weather.get('temperature_c', 'N/A')}°C ({weather.get('temperature_f', 'N/A')}°F)")
            output.append(f"- **Condition:** {weather.get('condition', 'N/A')}")
            output.append(f"- **Humidity:** {weather.get('humidity', 'N/A')}%")
            output.append("")
    
    # If no results found
    if len(output) == 1:  # Only has the header
        output.append("No specific search results found. Khisba will use his GIS knowledge or provide a general answer.")
    
    return "\n".join(output)

def summarize_results_for_ai(results: dict) -> str:
    """Create a condensed summary of search results for AI context."""
    summary_parts = []
    
    if "wikipedia" in results:
        wiki = results["wikipedia"]
        if isinstance(wiki, dict) and wiki.get("exists"):
            summary_parts.append(f"Wikipedia: {wiki.get('title', '')} - {wiki.get('summary', '')[:200]}")
    
    if "instant_answer" in results:
        instant = results["instant_answer"]
        if isinstance(instant, dict) and instant.get("answer"):
            summary_parts.append(f"Quick Answer: {instant['answer'][:150]}")
    
    if "duckduckgo" in results:
        ddg = results["duckduckgo"]
        if isinstance(ddg, list) and len(ddg) > 0:
            for i, item in enumerate(ddg[:2]):
                if isinstance(item, dict) and item.get("body"):
                    summary_parts.append(f"Web Result {i+1}: {item.get('title', '')} - {item.get('body', '')[:100]}")
    
    if "weather" in results:
        weather = results["weather"]
        if isinstance(weather, dict) and weather.get("temperature_c"):
            summary_parts.append(f"Weather: {weather.get('location', 'N/A')} - {weather.get('temperature_c')}°C, {weather.get('condition', '')}")
    
    return "\n".join(summary_parts) if summary_parts else "Limited search results available."

# ==================== KHISBA RESPONSE GENERATOR ====================

def generate_khisba_response(user_input, search_results=None, knowledge_check=None):
    """Generate Khisba's response with intelligent steering."""
    
    if knowledge_check is None:
        knowledge_check = khisba_kb.check_knowledge(user_input)
    
    # Case 1: Khisba knows with high confidence
    if knowledge_check["knows"] is True and knowledge_check["confidence"] > 0.8:
        khisba_response = khisba_kb.generate_khisba_response(knowledge_check, user_input)
        
        # Add search context if available
        if search_results:
            summary = summarize_results_for_ai(search_results)
            if summary and "Limited search" not in summary:
                khisba_response += "\n\n🔍 **Additional context from sources:**\n"
                khisba_response += f"My knowledge aligns with current information. Recent sources confirm this is accurate."
        
        return khisba_response
    
    # Case 2: Partial knowledge or lower confidence
    elif knowledge_check["knows"] == "partial" or (knowledge_check["knows"] is True and knowledge_check["confidence"] <= 0.8):
        # Start with Khisba's partial knowledge
        partial_response = khisba_kb.generate_khisba_response(knowledge_check, user_input)
        
        # If we have search results, enhance with them
        if search_results:
            summary = summarize_results_for_ai(search_results)
            
            if summary and "Limited search" not in summary:
                enhanced_response = f"{partial_response}\n\n🔍 **From my search:**\n{summary}\n\nAs Khisba GIS, I can confirm this information is current and accurate."
                return enhanced_response
        
        return partial_response or "Let me check the latest sources for you..."
    
    # Case 3: No knowledge - rely on search results
    else:
        if search_results:
            summary = summarize_results_for_ai(search_results)
            
            if summary and "Limited search" not in summary:
                return f"🌍 **As a GIS specialist,** this topic is outside my immediate expertise, but I've researched it for you:\n\n{summary}\n\nI hope this information is helpful! For GIS-specific questions, I'm your expert!"
            else:
                return "🌍 **As a GIS specialist,** I focus on geospatial topics. This appears to be outside my expertise. Could you ask me about GIS, remote sensing, or satellite imagery instead?"
        else:
            return "🌍 **As a GIS specialist,** I focus on geospatial topics. Would you like me to search for information about that, or ask me about GIS/remote sensing instead?"

# ==================== STREAMLIT APP ====================

st.set_page_config(
    page_title="Khisba GIS - AI Search Assistant",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2E8B57;
        text-align: center;
        margin-bottom: 1rem;
    }
    .khisba-badge {
        background-color: #2E8B57;
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        display: inline-block;
        margin: 0.5rem 0;
        font-weight: bold;
    }
    .confidence-high { color: #2E8B57; font-weight: bold; }
    .confidence-medium { color: #FFA500; font-weight: bold; }
    .confidence-low { color: #FF6347; font-weight: bold; }
    .source-badge {
        background-color: #f0f2f6;
        padding: 0.25rem 0.5rem;
        border-radius: 5px;
        font-size: 0.8rem;
        margin-right: 0.5rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = KHISBA_SYSTEM_PROMPT

if "selected_preset" not in st.session_state:
    st.session_state.selected_preset = "Khisba GIS"

if "last_search_results" not in st.session_state:
    st.session_state.last_search_results = None

if "last_formatted_results" not in st.session_state:
    st.session_state.last_formatted_results = None

if "auto_search" not in st.session_state:
    st.session_state.auto_search = True

# Header
st.markdown('<h1 class="main-header">🛰️ Khisba GIS AI Assistant</h1>', unsafe_allow_html=True)
st.markdown('<div class="khisba-badge">Your Friendly GIS & Remote Sensing Expert</div>', unsafe_allow_html=True)
st.markdown("**Knows GIS deeply | Admits when unsure | Searches multiple sources automatically**")

# Sidebar
with st.sidebar:
    st.header("🧙‍♂️ Khisba's Capabilities")
    
    with st.expander("📚 Core Knowledge", expanded=True):
        st.markdown("""
        **🎯 Expert in:**
        - Vegetation indices (NDVI, NDWI, EVI, SAVI)
        - Satellite systems (Landsat, Sentinel, MODIS)
        - GIS software (QGIS, ArcGIS, Google Earth Engine)
        - Remote sensing concepts & analysis
        
        **🔍 When unsure:**
        1. Honestly admits uncertainty
        2. Searches multiple reliable sources
        3. Synthesizes verified information
        4. Maintains GIS expert persona
        """)
    
    st.divider()
    
    st.header("⚙️ Configuration")
    
    selected_preset = st.selectbox(
        "AI Persona:",
        options=list(PRESET_PROMPTS.keys()),
        index=list(PRESET_PROMPTS.keys()).index(st.session_state.selected_preset),
        key="preset_selector"
    )
    
    if selected_preset != st.session_state.selected_preset:
        st.session_state.selected_preset = selected_preset
        if selected_preset != "Custom":
            st.session_state.system_prompt = PRESET_PROMPTS[selected_preset]
    
    if selected_preset == "Custom":
        system_prompt = st.text_area(
            "Custom System Prompt:",
            value=st.session_state.system_prompt,
            height=150,
            key="system_prompt_input"
        )
    else:
        system_prompt = st.session_state.system_prompt
        with st.expander("View System Prompt"):
            st.text(system_prompt[:500] + "..." if len(system_prompt) > 500 else system_prompt)
    
    st.divider()
    
    st.subheader("⚡ Settings")
    
    st.session_state.auto_search = st.checkbox(
        "Auto-search when unsure", 
        value=st.session_state.auto_search,
        help="Automatically search sources when Khisba is uncertain"
    )
    
    show_raw_data = st.checkbox("Show raw search data", value=False)
    
    st.divider()
    
    st.subheader("🔍 Available Sources")
    with st.expander("View Sources"):
        st.markdown("""
        **🌐 Web & Knowledge:**
        - DuckDuckGo Search
        - Wikipedia
        - Instant Answers
        
        **🌤️ Location Services:**
        - Weather data
        
        **More sources available in full version**
        """)
    
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.last_search_results = None
            st.session_state.last_formatted_results = None
            st.rerun()
    
    with col2:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.system_prompt = KHISBA_SYSTEM_PROMPT
            st.session_state.selected_preset = "Khisba GIS"
            st.session_state.auto_search = True
            st.rerun()
    
    st.divider()
    st.caption("Khisba GIS Assistant v1.0")
    st.caption("No model download required")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask Khisba about GIS, remote sensing, or anything..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Prepare assistant response
    with st.chat_message("assistant"):
        # Check Khisba's knowledge
        knowledge_check = khisba_kb.check_knowledge(prompt)
        
        # Determine if we need to search
        needs_search = False
        search_note = ""
        
        if knowledge_check["knows"] is False:
            needs_search = True
            search_note = "🔍 Khisba doesn't know this - searching sources..."
        elif knowledge_check["knows"] == "partial":
            needs_search = True
            search_note = "🤔 Khisba wants to verify - searching for accuracy..."
        elif knowledge_check["confidence"] < 0.7:
            needs_search = True
            search_note = "📚 Khisba is checking latest sources..."
        elif knowledge_check["confidence"] >= 0.9:
            search_note = "🎯 Khisba knows this well!"
        else:
            search_note = "✅ Khisba has good knowledge about this!"
        
        # Show search status
        status_placeholder = st.empty()
        if search_note:
            status_placeholder.info(search_note)
        
        # Perform search if needed and auto-search is enabled
        search_results = None
        formatted_results = None
        
        if needs_search and st.session_state.auto_search:
            with st.spinner("Searching sources..."):
                search_results = search_all_sources(prompt)
                st.session_state.last_search_results = search_results
            
            formatted_results = format_results(prompt, search_results)
            st.session_state.last_formatted_results = formatted_results
        elif st.session_state.auto_search:
            # Still do a light search for context
            with st.spinner("Getting context..."):
                search_results = search_all_sources(prompt)
                st.session_state.last_search_results = search_results
            
            formatted_results = format_results(prompt, search_results)
            st.session_state.last_formatted_results = formatted_results
        
        # Clear status
        status_placeholder.empty()
        
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["🧙‍♂️ Khisba's Answer", "📊 Search Results", "⚙️ Analysis"])
        
        with tab1:
            # Generate Khisba's response
            with st.spinner("Khisba is thinking..."):
                khisba_response = generate_khisba_response(
                    prompt,
                    search_results,
                    knowledge_check
                )
            
            # Display confidence indicator
            confidence = knowledge_check["confidence"]
            if confidence >= 0.8:
                confidence_class = "confidence-high"
                confidence_text = "High Confidence"
                emoji = "🎯"
            elif confidence >= 0.5:
                confidence_class = "confidence-medium"
                confidence_text = "Moderate Confidence"
                emoji = "✅"
            else:
                confidence_class = "confidence-low"
                confidence_text = "Researched Answer"
                emoji = "🔍"
            
            st.markdown(f'<div class="{confidence_class}">{emoji} {confidence_text}</div>', unsafe_allow_html=True)
            
            # Display Khisba's response
            st.markdown(khisba_response)
            
            # Add footer note
            if knowledge_check["knows"] is False or knowledge_check["confidence"] < 0.6:
                st.info("💡 *This answer includes information from verified sources.*")
        
        with tab2:
            if formatted_results:
                st.markdown(formatted_results)
            else:
                st.info("No search results available. Enable auto-search to see results here.")
        
        with tab3:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🧠 Knowledge Analysis")
                knowledge_level = (
                    "Expert" if knowledge_check["confidence"] > 0.8 else 
                    "Good" if knowledge_check["confidence"] > 0.6 else 
                    "Partial" if knowledge_check["knows"] == "partial" else 
                    "None"
                )
                st.metric("Knowledge Level", knowledge_level)
                
                topic_type = knowledge_check.get("type", "Unknown").replace("_", " ").title()
                st.metric("Topic Type", topic_type)
                
                search_triggered = "Yes" if needs_search else "No"
                st.metric("Search Triggered", search_triggered)
            
            with col2:
                st.subheader("🔍 Search Stats")
                if search_results:
                    successful_searches = sum(1 for v in search_results.values() 
                                            if isinstance(v, (list, dict)) and 
                                            (not isinstance(v, dict) or "error" not in v))
                    st.metric("Sources Queried", len(search_results))
                    st.metric("Successful", successful_searches)
                else:
                    st.info("No search performed")
            
            if show_raw_data and search_results:
                st.subheader("📈 Raw Data Preview")
                for source, data in list(search_results.items())[:3]:
                    with st.expander(f"{source.replace('_', ' ').title()}"):
                        if isinstance(data, list):
                            st.json(data[:2] if len(data) > 2 else data)
                        else:
                            st.json(data)
    
    # Add to conversation history
    st.session_state.messages.append({
        "role": "assistant", 
        "content": khisba_response
    })

# Footer
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**🛰️ GIS Expert**")
    st.caption("Specialized in remote sensing")
with col2:
    st.markdown("**🔍 Smart Search**")
    st.caption("Automatic verification")
with col3:
    st.markdown("**🎯 Honest AI**")
    st.caption("Admits when unsure")

st.markdown("---")
st.caption("Khisba GIS AI Assistant v1.0 | Your friendly geospatial expert | No installation required")
