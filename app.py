import streamlit as st
import requests
import json
import xml.etree.ElementTree as ET
import concurrent.futures
import arxiv
import wikipedia
from pathlib import Path
from ctransformers import AutoModelForCausalLM
import re
from datetime import datetime

# ==================== ENHANCED SERVICE FUNCTIONS ====================

# Enhanced query classification
def classify_query_intent(query: str) -> dict:
    """
    Classify the intent of the query to help organize results better.
    Returns a dictionary with intent category and confidence.
    """
    query_lower = query.lower()
    
    # Intent patterns (can be expanded)
    intent_patterns = {
        "finance": ["stock", "index", "price", "ticker", "market", "invest", "cboe", "vix", "volatility", "s&p"],
        "automotive": ["car", "vehicle", "vin", "decode", "manufacturer", "model", "year", "license"],
        "technical": ["code", "program", "github", "stack", "api", "function", "bug", "error"],
        "medical": ["health", "disease", "medical", "treatment", "symptom", "pubmed", "clinical"],
        "academic": ["research", "paper", "study", "arxiv", "university", "professor", "hypothesis"],
        "geography": ["country", "city", "location", "map", "capital", "population", "border"],
        "weather": ["weather", "temperature", "forecast", "humidity", "rain", "sunny", "climate"],
        "dictionary": ["definition", "meaning", "word", "phrase", "pronounce", "synonym"],
        "general": []  # Default category
    }
    
    scores = {intent: 0 for intent in intent_patterns}
    
    # Score each intent based on keyword matches
    for intent, keywords in intent_patterns.items():
        for keyword in keywords:
            if keyword in query_lower:
                scores[intent] += 1
    
    # Get primary intent
    primary_intent = max(scores, key=scores.get)
    confidence = scores[primary_intent] / max(len(query.split()), 1)
    
    return {
        "primary_intent": primary_intent if scores[primary_intent] > 0 else "general",
        "all_intents": {k: v for k, v in scores.items() if v > 0},
        "confidence": confidence
    }

# Enhanced ArXiv Service
def search_arxiv(query: str, max_results: int = 3):
    """
    Search arXiv for scientific papers with enhanced error handling.
    """
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
        return [{"error": f"ArXiv search failed: {str(e)}"}]

# Enhanced DuckDuckGo Services with better parsing
def search_duckduckgo(query: str, max_results: int = 5):
    """
    Search DuckDuckGo web results with improved parsing.
    """
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
                "type": "instant_answer",
                "source": "DuckDuckGo"
            })
        
        # Get related topics
        for topic in data.get("RelatedTopics", []):
            if isinstance(topic, dict) and "Text" in topic:
                if "FirstURL" in topic:
                    results.append({
                        "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else topic.get("Text", ""),
                        "body": topic.get("Text", "").split(" - ")[1] if " - " in topic.get("Text", "") else "",
                        "url": topic.get("FirstURL", ""),
                        "type": "related_topic",
                        "source": "DuckDuckGo"
                    })
            elif isinstance(topic, str):
                if " - " in topic:
                    title, body = topic.split(" - ", 1)
                    results.append({
                        "title": title,
                        "body": body,
                        "url": "",
                        "type": "related_topic",
                        "source": "DuckDuckGo"
                    })
            
            if len(results) >= max_results:
                break
        
        return results
    except Exception as e:
        return [{"error": f"DuckDuckGo search failed: {str(e)}"}]

def get_instant_answer(query: str):
    """
    Get instant answer from DuckDuckGo with enhanced parsing.
    """
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1"
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # Enhanced answer extraction
        answer = data.get("AbstractText", "")
        if not answer and "Definition" in data:
            answer = data.get("Definition", "")
        if not answer and data.get("Results"):
            answer = data["Results"][0].get("Text", "")
        
        return {
            "answer": answer,
            "heading": data.get("Heading", ""),
            "url": data.get("AbstractURL", ""),
            "image": data.get("Image", ""),
            "source": "DuckDuckGo"
        }
    except Exception as e:
        return {"error": f"Instant answer failed: {str(e)}"}

def search_news(query: str, max_results: int = 3):
    """
    Search news using DuckDuckGo with enhanced parsing.
    """
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
        
        # Enhanced regex parsing
        results = []
        
        # Try multiple patterns
        patterns = [
            r'<a[^>]*class="[^"]*result__url[^"]*"[^>]*>([^<]+)</a>',
            r'<a[^>]*class="result__a"[^>]*>([^<]+)</a>',
            r'<a[^>]*class="[^"]*result__title[^"]*"[^>]*>([^<]+)</a>'
        ]
        
        for pattern in patterns:
            titles = re.findall(pattern, response.text)
            if titles:
                break
        
        # Find snippets
        snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>([^<]+)</a>'
        snippets = re.findall(snippet_pattern, response.text)
        
        for i in range(min(len(titles), max_results, len(snippets))):
            results.append({
                "title": titles[i],
                "body": snippets[i] if i < len(snippets) else "",
                "source": "DuckDuckGo News",
                "url": f"https://duckduckgo.com/?q={query.replace(' ', '+')}",
                "date": datetime.now().strftime("%Y-%m-%d")
            })
        
        if not results:
            # Fallback to regular search
            results = search_duckduckgo(f"{query} news", max_results)
        
        return results
    except Exception as e:
        return [{"error": f"News search failed: {str(e)}"}]

# Enhanced Wikipedia Service
def search_wikipedia(query: str):
    """
    Search Wikipedia for information with enhanced disambiguation.
    """
    try:
        wikipedia.set_lang("en")
        
        # Clean query for Wikipedia
        clean_query = query.replace("indice", "index").replace("vin", "VIN")
        
        # Try multiple search strategies
        search_results = wikipedia.search(clean_query, results=5)
        
        if not search_results:
            # Try alternative search
            search_results = wikipedia.search(query, results=3)
            if not search_results:
                return {"exists": False, "message": "No Wikipedia page found", "source": "Wikipedia"}
        
        # Get the most relevant result
        try:
            page = wikipedia.page(search_results[0], auto_suggest=False)
            return {
                "exists": True,
                "title": page.title,
                "summary": page.summary,
                "url": page.url,
                "categories": page.categories[:5],
                "content": page.content[:1000],
                "source": "Wikipedia",
                "search_query": query
            }
        except wikipedia.exceptions.DisambiguationError as e:
            # Return disambiguation options
            return {
                "exists": True,
                "title": query,
                "summary": f"Multiple pages found. Select from options.",
                "url": f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}",
                "disambiguation": e.options[:10],
                "source": "Wikipedia",
                "type": "disambiguation"
            }
        except wikipedia.exceptions.PageError:
            # Try with simplified query
            try:
                simple_query = query.split()[0] if query.split() else query
                page = wikipedia.page(simple_query, auto_suggest=False)
                return {
                    "exists": True,
                    "title": page.title,
                    "summary": page.summary,
                    "url": page.url,
                    "categories": page.categories[:5],
                    "source": "Wikipedia"
                }
            except:
                return {"exists": False, "message": "Page not found", "source": "Wikipedia"}
            
    except Exception as e:
        return {"error": f"Wikipedia search failed: {str(e)}"}

# Enhanced Weather Service
def get_weather_wttr(location: str):
    """
    Get weather information using wttr.in with enhanced location handling.
    """
    try:
        # Clean location string
        clean_location = re.sub(r'[^\w\s,-]', '', location).strip()
        if not clean_location:
            clean_location = "New York"
            
        url = f"https://wttr.in/{clean_location}?format=j1"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; WeatherApp/1.0)"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        current = data.get("current_condition", [{}])[0]
        nearest_area = data.get("nearest_area", [{}])[0]
        
        return {
            "location": clean_location,
            "area_name": nearest_area.get("areaName", [{}])[0].get("value", clean_location),
            "country": nearest_area.get("country", [{}])[0].get("value", "N/A"),
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
            "observation_time": current.get("observation_time", "N/A"),
            "source": "wttr.in"
        }
    except Exception as e:
        return {"error": f"Weather service failed: {str(e)}"}

# Enhanced Air Quality Service
def get_air_quality(location: str):
    """
    Get air quality data from OpenAQ with enhanced location handling.
    """
    try:
        # Clean location for API
        clean_location = location.split(",")[0].strip() if "," in location else location.strip()
        
        url = f"https://api.openaq.org/v2/latest"
        params = {
            "limit": 5,
            "page": 1,
            "offset": 0,
            "sort": "desc",
            "radius": 25000,
            "order_by": "lastUpdated",
            "city": clean_location
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("results"):
            results = []
            for result in data["results"][:3]:
                location_data = {
                    "location": result.get("location", "N/A"),
                    "city": result.get("city", "N/A"),
                    "country": result.get("country", "N/A"),
                    "coordinates": result.get("coordinates", {}),
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
                "city": clean_location,
                "data": results,
                "count": len(results),
                "source": "OpenAQ"
            }
        else:
            # Try without city parameter
            params.pop("city", None)
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            
            if data.get("results"):
                return {
                    "city": "Global",
                    "data": data["results"][:3],
                    "count": len(data["results"][:3]),
                    "message": f"No specific data for {clean_location}, showing global data",
                    "source": "OpenAQ"
                }
            else:
                return {"message": f"No air quality data found for {clean_location}", "source": "OpenAQ"}
            
    except Exception as e:
        return {"error": f"Air quality service failed: {str(e)}"}

# Enhanced Wikidata Service
def search_wikidata(query: str, max_results: int = 3):
    """
    Search Wikidata for entities with enhanced query handling.
    """
    try:
        # Clean query for Wikidata
        clean_query = query.replace("indice", "").strip()
        
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": clean_query,
            "language": "en",
            "format": "json",
            "limit": max_results,
            "type": "item"  # Search for items specifically
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        results = []
        for entity in data.get("search", []):
            # Get more details for each entity
            entity_details = {
                "id": entity.get("id", ""),
                "label": entity.get("label", ""),
                "description": entity.get("description", ""),
                "url": f"https://www.wikidata.org/wiki/{entity.get('id', '')}",
                "concepturi": entity.get("concepturi", ""),
                "match": entity.get("match", {}).get("text", ""),
                "aliases": entity.get("aliases", []),
                "source": "Wikidata"
            }
            results.append(entity_details)
        
        return results
    except Exception as e:
        return [{"error": f"Wikidata search failed: {str(e)}"}]

# Enhanced OpenLibrary Service
def search_books(query: str, max_results: int = 5):
    """
    Search for books using OpenLibrary API with enhanced query handling.
    """
    try:
        # Clean query for book search
        clean_query = query.replace("indice", "index").replace("vin", "")
        
        url = "https://openlibrary.org/search.json"
        params = {
            "q": clean_query,
            "limit": max_results,
            "fields": "title,author_name,first_publish_year,publisher,language,subject,key,cover_i"
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
                "cover_url": f"https://covers.openlibrary.org/b/id/{doc.get('cover_i')}-M.jpg" if doc.get("cover_i") else None,
                "source": "OpenLibrary"
            }
            results.append(book)
        
        return results
    except Exception as e:
        return [{"error": f"Book search failed: {str(e)}"}]

# Enhanced PubMed Service
def search_pubmed(query: str, max_results: int = 3):
    """
    Search PubMed for medical research articles with enhanced query handling.
    """
    try:
        # Clean medical query
        clean_query = query.replace("vin", "").replace("indice", "index").strip()
        
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        # Search for article IDs
        search_url = f"{base_url}/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": clean_query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance",
            "field": "title/abstract"  # Search in title and abstract
        }
        
        search_response = requests.get(search_url, params=search_params, timeout=10)
        search_data = search_response.json()
        
        ids = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not ids:
            # Try broader search
            search_params["term"] = query
            search_response = requests.get(search_url, params=search_params, timeout=10)
            search_data = search_response.json()
            ids = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not ids:
            return [{"message": "No articles found for the query", "source": "PubMed"}]
        
        # Fetch article details
        fetch_url = f"{base_url}/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
            "rettype": "abstract"
        }
        
        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=10)
        
        # Parse XML
        root = ET.fromstring(fetch_response.content)
        
        results = []
        for article in root.findall(".//PubmedArticle"):
            article_elem = article.find(".//Article")
            
            title_elem = article_elem.find(".//ArticleTitle") if article_elem is not None else None
            title = title_elem.text if title_elem is not None else "N/A"
            
            # Extract abstract
            abstract_text = []
            for abstract_elem in article_elem.findall(".//Abstract/AbstractText") if article_elem is not None else []:
                if abstract_elem.text:
                    abstract_text.append(abstract_elem.text)
            abstract = " ".join(abstract_text) if abstract_text else "No abstract available"
            
            # Extract authors
            authors = []
            for author_elem in article.findall(".//Author"):
                last_name_elem = author_elem.find("LastName")
                fore_name_elem = author_elem.find("ForeName")
                
                if last_name_elem is not None and fore_name_elem is not None:
                    authors.append(f"{fore_name_elem.text} {last_name_elem.text}")
                elif last_name_elem is not None:
                    authors.append(last_name_elem.text)
            
            # Extract publication year
            pub_date_elem = article.find(".//PubMedPubDate[@PubStatus='pubmed']")
            year = "N/A"
            if pub_date_elem is not None:
                year_elem = pub_date_elem.find("Year")
                if year_elem is not None:
                    year = year_elem.text
            
            # Get PubMed ID
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else ""
            
            # Get journal
            journal_elem = article_elem.find(".//Journal/Title") if article_elem is not None else None
            journal = journal_elem.text if journal_elem is not None else "N/A"
            
            result = {
                "title": title,
                "abstract": abstract[:500] + "..." if len(abstract) > 500 else abstract,
                "authors": authors[:5],
                "year": year,
                "pmid": pmid,
                "journal": journal,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                "source": "PubMed"
            }
            results.append(result)
        
        return results
    except Exception as e:
        return [{"error": f"PubMed search failed: {str(e)}"}]

# Enhanced Nominatim Service (Geocoding)
def geocode_location(location: str):
    """
    Geocode a location using Nominatim with enhanced handling.
    """
    try:
        # Clean location string
        clean_location = re.sub(r'[^\w\s,-]', '', location).strip()
        
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": clean_location,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
            "namedetails": 1
        }
        
        headers = {
            "User-Agent": "AI-Search-Assistant/2.0 (research@example.com)"
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
                "address": result.get("address", {}),
                "namedetails": result.get("namedetails", {}),
                "source": "Nominatim (OpenStreetMap)"
            }
        else:
            # Try with simplified query
            simple_query = clean_location.split(",")[0] if "," in clean_location else clean_location
            params["q"] = simple_query
            response = requests.get(url, params=params, headers=headers, timeout=10)
            data = response.json()
            
            if data and len(data) > 0:
                result = data[0]
                return {
                    "display_name": result.get("display_name", "N/A"),
                    "latitude": result.get("lat", "N/A"),
                    "longitude": result.get("lon", "N/A"),
                    "type": result.get("type", "N/A"),
                    "address": result.get("address", {}),
                    "source": "Nominatim (OpenStreetMap)",
                    "note": f"Found for simplified query: {simple_query}"
                }
            else:
                return {"message": f"Location '{clean_location}' not found", "source": "Nominatim"}
    except Exception as e:
        return {"error": f"Geocoding failed: {str(e)}"}

# Enhanced Dictionary Service
def get_definition(word: str):
    """
    Get dictionary definition with enhanced word handling.
    """
    try:
        # Clean word for dictionary
        clean_word = re.sub(r'[^\w\s]', '', word).strip().lower()
        
        # Handle compound words/phrases
        if " " in clean_word:
            # For phrases, get definition of first word
            clean_word = clean_word.split()[0]
        
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{clean_word}"
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 404:
            # Try alternative dictionary
            return {"error": f"Word '{clean_word}' not found in dictionary", "source": "DictionaryAPI"}
        
        data = response.json()
        
        if isinstance(data, list) and len(data) > 0:
            word_data = data[0]
            
            # Extract phonetic pronunciations
            phonetics = []
            if "phonetics" in word_data:
                for phonetic in word_data["phonetics"]:
                    if phonetic.get("text"):
                        phonetics.append({
                            "text": phonetic["text"],
                            "audio": phonetic.get("audio", "")
                        })
            
            # Extract meanings
            meanings = []
            if "meanings" in word_data:
                for meaning in word_data["meanings"]:
                    meaning_entry = {
                        "part_of_speech": meaning.get("partOfSpeech", ""),
                        "definitions": [],
                        "synonyms": meaning.get("synonyms", [])[:5],
                        "antonyms": meaning.get("antonyms", [])[:5]
                    }
                    
                    for definition in meaning.get("definitions", []):
                        def_entry = {
                            "definition": definition.get("definition", ""),
                            "example": definition.get("example", ""),
                            "synonyms": definition.get("synonyms", [])[:3],
                            "antonyms": definition.get("antonyms", [])[:3]
                        }
                        meaning_entry["definitions"].append(def_entry)
                    
                    meanings.append(meaning_entry)
            
            return {
                "word": word_data.get("word", clean_word),
                "phonetics": phonetics,
                "meanings": meanings,
                "license": word_data.get("license", {}),
                "source_urls": word_data.get("sourceUrls", []),
                "source": "DictionaryAPI"
            }
        else:
            return {"error": "Invalid response from dictionary API", "source": "DictionaryAPI"}
    except Exception as e:
        return {"error": f"Dictionary service failed: {str(e)}"}

# Enhanced Countries Service
def search_country(query: str):
    """
    Search for country information with enhanced query handling.
    """
    try:
        # Clean query for country search
        clean_query = re.sub(r'[^\w\s]', '', query).strip()
        
        # First, try exact name
        url = f"https://restcountries.com/v3.1/name/{clean_query}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 404:
            # Try partial search
            url = f"https://restcountries.com/v3.1/name/{clean_query}"
            params = {"fullText": False}
            response = requests.get(url, params=params, timeout=10)
        
        if response.status_code != 200:
            # Try alpha code search
            url = f"https://restcountries.com/v3.1/alpha/{clean_query[:3]}"
            response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            return {"error": f"Country '{clean_query}' not found", "source": "REST Countries"}
        
        data = response.json()
        
        if data and len(data) > 0:
            country = data[0]
            
            # Extract languages
            languages = []
            if "languages" in country:
                languages = list(country["languages"].values())
            
            # Extract currencies
            currencies = []
            if "currencies" in country:
                for curr_code, curr_info in country["currencies"].items():
                    currencies.append({
                        "code": curr_code,
                        "name": curr_info.get('name', ''),
                        "symbol": curr_info.get('symbol', '')
                    })
            
            # Extract capital
            capital = country.get("capital", ["N/A"])[0] if country.get("capital") else "N/A"
            
            # Extract borders
            borders = country.get("borders", [])
            
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
                "borders": borders,
                "flag_emoji": country.get("flag", "🇺🇳"),
                "flag_url": country.get("flags", {}).get("png", ""),
                "coat_of_arms": country.get("coatOfArms", {}).get("png", ""),
                "map_url": country.get("maps", {}).get("googleMaps", ""),
                "source": "REST Countries"
            }
        else:
            return {"error": "No country data found", "source": "REST Countries"}
    except Exception as e:
        return {"error": f"Country search failed: {str(e)}"}

# Enhanced Quotes Service
def search_quotes(query: str, max_results: int = 3):
    """
    Search for quotes with enhanced query handling.
    """
    try:
        # Clean query for quotes
        clean_query = re.sub(r'[^\w\s]', '', query).strip()
        
        # First try search
        url = "https://api.quotable.io/search/quotes"
        params = {
            "query": clean_query,
            "limit": max_results,
            "fields": "content,author,tags,length"
        }
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        results = []
        if data.get("results"):
            for quote in data.get("results", [])[:max_results]:
                result = {
                    "content": quote.get("content", ""),
                    "author": quote.get("author", "Unknown"),
                    "tags": quote.get("tags", []),
                    "length": quote.get("length", 0),
                    "date_added": quote.get("dateAdded", ""),
                    "date_modified": quote.get("dateModified", ""),
                    "source": "Quotable API"
                }
                results.append(result)
        
        # If no search results or query is generic, get random quotes
        if not results or len(clean_query.split()) < 2:
            url = "https://api.quotable.io/quotes/random"
            params = {
                "limit": max_results,
                "tags": "inspirational|motivational|wisdom"
            }
            
            response = requests.get(url, params=params, timeout=10)
            random_quotes = response.json()
            
            for quote in random_quotes[:max_results]:
                result = {
                    "content": quote.get("content", ""),
                    "author": quote.get("author", "Unknown"),
                    "tags": quote.get("tags", []),
                    "length": quote.get("length", 0),
                    "source": "Quotable API (Random)"
                }
                results.append(result)
        
        return results
    except Exception as e:
        return [{"error": f"Quotes service failed: {str(e)}"}]

# Enhanced GitHub Service
def search_github_repos(query: str, max_results: int = 3):
    """
    Search GitHub repositories with enhanced query handling.
    """
    try:
        # Clean query for GitHub
        clean_query = query.replace("indice", "").strip()
        
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"{clean_query} in:name,description,readme",
            "sort": "stars",
            "order": "desc",
            "per_page": max_results
        }
        
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "AI-Search-Assistant/2.0"
        }
        
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        # Handle rate limiting
        if response.status_code == 403:
            remaining = response.headers.get("X-RateLimit-Remaining", "0")
            reset_time = response.headers.get("X-RateLimit-Reset", "0")
            return [{
                "error": f"GitHub API rate limit exceeded. Remaining: {remaining}, Resets at: {reset_time}",
                "source": "GitHub"
            }]
        
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
                "owner": repo.get("owner", {}).get("login", "N/A") if repo.get("owner") else "N/A",
                "topics": repo.get("topics", []),
                "source": "GitHub"
            }
            results.append(result)
        
        return results
    except Exception as e:
        return [{"error": f"GitHub search failed: {str(e)}"}]

# Enhanced StackExchange Service
def search_stackoverflow(query: str, max_results: int = 3):
    """
    Search Stack Overflow questions with enhanced query handling.
    """
    try:
        # Clean query for Stack Overflow
        clean_query = re.sub(r'[^\w\s]', '', query).strip()
        
        url = "https://api.stackexchange.com/2.3/search"
        params = {
            "order": "desc",
            "sort": "relevance",
            "intitle": clean_query,
            "site": "stackoverflow",
            "pagesize": max_results,
            "filter": "withbody"
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
                "creation_date": question.get("creation_date", 0),
                "body_preview": question.get("body", "")[:200] + "..." if question.get("body") else "",
                "source": "Stack Overflow"
            }
            results.append(result)
        
        return results
    except Exception as e:
        return [{"error": f"Stack Overflow search failed: {str(e)}"}]

# ==================== INTELLIGENT RESULT ORGANIZATION ====================

def organize_results_by_intent(query: str, results: dict, intent_info: dict) -> dict:
    """
    Organize search results by intent and relevance.
    """
    organized = {
        "query": query,
        "intent": intent_info,
        "primary_results": {},
        "secondary_results": {},
        "all_results": results
    }
    
    primary_intent = intent_info.get("primary_intent", "general")
    
    # Map intents to source categories
    intent_source_map = {
        "finance": ["duckduckgo", "duckduckgo_instant", "news", "wikipedia", "wikidata"],
        "automotive": ["wikipedia", "duckduckgo", "duckduckgo_instant", "geocoding"],
        "technical": ["github", "stackoverflow", "arxiv", "wikipedia"],
        "medical": ["pubmed", "wikipedia", "duckduckgo"],
        "academic": ["arxiv", "pubmed", "wikipedia", "books"],
        "geography": ["geocoding", "country", "weather", "wikipedia"],
        "weather": ["weather", "air_quality", "geocoding"],
        "dictionary": ["dictionary", "wikipedia", "duckduckgo_instant"],
        "general": ["wikipedia", "duckduckgo", "duckduckgo_instant", "news"]
    }
    
    # Get relevant sources for primary intent
    relevant_sources = intent_source_map.get(primary_intent, intent_source_map["general"])
    
    # Separate primary and secondary results
    for source, data in results.items():
        if source in relevant_sources:
            organized["primary_results"][source] = data
        else:
            organized["secondary_results"][source] = data
    
    return organized

def create_intelligent_summary(query: str, organized_results: dict) -> str:
    """
    Create an intelligent summary based on organized results.
    """
    primary_intent = organized_results["intent"].get("primary_intent", "general")
    query_lower = query.lower()
    
    summary_parts = []
    
    # Add intent-based introduction
    intent_intros = {
        "finance": f"## 📈 Financial Analysis: {query}\nBased on your query about '{query}', here's what I found related to finance and markets:\n",
        "automotive": f"## 🚗 Automotive Information: {query}\nSearching for '{query}' in automotive context revealed:\n",
        "technical": f"## 💻 Technical Information: {query}\nFor the technical query '{query}', here are the relevant findings:\n",
        "medical": f"## 🏥 Medical Research: {query}\nRegarding the medical query '{query}', here's what research shows:\n",
        "academic": f"## 📚 Academic Research: {query}\nAcademic search for '{query}' yielded these results:\n",
        "geography": f"## 🌍 Geographical Information: {query}\nGeographical data for '{query}':\n",
        "weather": f"## 🌤️ Weather Information: {query}\nWeather data related to '{query}':\n",
        "dictionary": f"## 📖 Word Analysis: {query}\nDefinition and usage of '{query}':\n",
        "general": f"## 🔍 Search Results: {query}\nComprehensive search for '{query}' across all sources:\n"
    }
    
    summary_parts.append(intent_intros.get(primary_intent, intent_intros["general"]))
    
    # Add primary results
    primary_results = organized_results["primary_results"]
    
    # Check for instant answers first
    if "duckduckgo_instant" in primary_results:
        instant = primary_results["duckduckgo_instant"]
        if isinstance(instant, dict) and instant.get("answer"):
            summary_parts.append(f"**💡 Quick Answer:** {instant['answer']}\n")
    
    # Add Wikipedia summary if available
    if "wikipedia" in primary_results:
        wiki = primary_results["wikipedia"]
        if isinstance(wiki, dict) and wiki.get("exists"):
            summary_parts.append(f"**📚 Wikipedia Summary:** {wiki.get('summary', '')[:300]}...\n")
    
    # Add other primary sources
    source_titles = {
        "duckduckgo": "🌐 Web Results",
        "news": "📰 Latest News",
        "arxiv": "🔬 Scientific Papers",
        "pubmed": "🏥 Medical Research",
        "github": "💻 GitHub Repositories",
        "stackoverflow": "🔧 Stack Overflow",
        "books": "📖 Related Books",
        "weather": "🌤️ Weather Info",
        "country": "🌍 Country Info",
        "dictionary": "📖 Dictionary Definition"
    }
    
    for source, data in primary_results.items():
        if source in source_titles and source not in ["duckduckgo_instant", "wikipedia"]:
            if isinstance(data, list) and data and "error" not in str(data[0]):
                summary_parts.append(f"**{source_titles[source]}:**")
                for item in data[:2]:
                    if isinstance(item, dict):
                        if source == "duckduckgo":
                            summary_parts.append(f"- {item.get('title', 'N/A')}: {item.get('body', '')[:100]}...")
                        elif source == "news":
                            summary_parts.append(f"- {item.get('title', 'N/A')} ({item.get('source', '')})")
                        elif source == "arxiv":
                            summary_parts.append(f"- {item.get('title', 'N/A')} ({item.get('published', 'N/A')})")
                summary_parts.append("")
    
    # Mention secondary sources if any
    secondary_count = len(organized_results["secondary_results"])
    if secondary_count > 0:
        summary_parts.append(f"\n*Additionally searched {secondary_count} other sources (view in detailed results).*\n")
    
    return "\n".join(summary_parts)

# ==================== ENHANCED SEARCH ALL FUNCTION ====================

def search_all_sources_enhanced(query: str) -> dict:
    """Search ALL sources simultaneously with intelligent handling."""
    # First, classify the query intent
    intent_info = classify_query_intent(query)
    
    results = {}
    
    def safe_search(name, func, *args, **kwargs):
        try:
            return name, func(*args, **kwargs)
        except Exception as e:
            return name, {"error": str(e), "source": name}
    
    # Search all sources in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        first_word = query.split()[0] if query.strip() else query
        
        # Prepare all search tasks
        search_tasks = [
            ("arxiv", search_arxiv, query, 3),
            ("duckduckgo", search_duckduckgo, query, 5),
            ("duckduckgo_instant", get_instant_answer, query),
            ("news", search_news, query, 3),
            ("wikipedia", search_wikipedia, query),
            ("weather", get_weather_wttr, query),
            ("air_quality", get_air_quality, query),
            ("wikidata", search_wikidata, query, 3),
            ("books", search_books, query, 5),
            ("pubmed", search_pubmed, query, 3),
            ("geocoding", geocode_location, query),
            ("dictionary", get_definition, first_word),
            ("country", search_country, query),
            ("quotes", search_quotes, query, 3),
            ("github", search_github_repos, query, 3),
            ("stackoverflow", search_stackoverflow, query, 3),
        ]
        
        # Submit all tasks
        future_to_name = {}
        for name, func, *args in search_tasks:
            future = executor.submit(safe_search, name, func, *args)
            future_to_name[future] = name
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_name):
            try:
                name, data = future.result()
                results[name] = data
            except Exception as e:
                name = future_to_name[future]
                results[name] = {"error": str(e), "source": name}
    
    # Organize results by intent
    organized_results = organize_results_by_intent(query, results, intent_info)
    
    return organized_results

# ==================== STREAMLIT APP ENHANCED ====================

st.set_page_config(
    page_title="AI Search Assistant - Enhanced",
    page_icon="🔍🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🔍🤖 Enhanced AI-Powered Multi-Source Search")
st.markdown("*Intelligent search across 16 sources with query understanding*")

# Custom CSS for better UI
st.markdown("""
<style>
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
    .stTabs [aria-selected="true"] {
        background-color: #4CAF50;
        color: white;
    }
    .source-card {
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        border-left: 4px solid #4CAF50;
    }
    .primary-source {
        background-color: #e8f5e9;
        border-left-color: #4CAF50;
    }
    .secondary-source {
        background-color: #f5f5f5;
        border-left-color: #9e9e9e;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "last_search" not in st.session_state:
    st.session_state.last_search = None

if "last_organized_results" not in st.session_state:
    st.session_state.last_organized_results = None

# Sidebar
with st.sidebar:
    st.header("🎯 Intelligent Search")
    
    with st.expander("🔍 Query Understanding", expanded=True):
        st.markdown("""
        The system automatically:
        1. **Classifies** your query intent
        2. **Prioritizes** relevant sources
        3. **Organizes** results intelligently
        4. **Summarizes** key findings
        """)
    
    st.divider()
    
    st.header("📊 All 16 Sources")
    with st.expander("View Source Categories", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
            **🌐 Web & Knowledge:**
            - DuckDuckGo Web
            - Instant Answers
            - News Search
            - Wikipedia
            - Wikidata
            
            **🔬 Science & Research:**
            - ArXiv Papers
            - PubMed Medical
            
            **📚 Reference:**
            - OpenLibrary Books
            - Dictionary API
            - REST Countries
            """)
        with col2:
            st.markdown("""
            **💬 Quotes:**
            - Quotable API
            
            **💻 Developer:**
            - GitHub Repos
            - Stack Overflow
            
            **📍 Location & Env:**
            - Geocoding
            - Weather
            - Air Quality
            """)
    
    st.divider()
    
    if st.button("🗑️ Clear Chat & Search", type="secondary", use_container_width=True):
        st.session_state.messages = []
        st.session_state.last_search = None
        st.session_state.last_organized_results = None
        st.rerun()

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Main chat interface
if prompt := st.chat_input("Ask anything... (16 sources + intelligent analysis)"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        # Step 1: Analyze query intent
        with st.status("🤔 Analyzing query intent...", expanded=False) as status:
            intent_info = classify_query_intent(prompt)
            primary_intent = intent_info.get("primary_intent", "general")
            confidence = intent_info.get("confidence", 0)
            
            intent_display = {
                "finance": "💰 Financial",
                "automotive": "🚗 Automotive", 
                "technical": "💻 Technical",
                "medical": "🏥 Medical",
                "academic": "📚 Academic",
                "geography": "🌍 Geographical",
                "weather": "🌤️ Weather",
                "dictionary": "📖 Dictionary",
                "general": "🔍 General"
            }
            
            st.write(f"**Detected Intent:** {intent_display.get(primary_intent, 'General Search')}")
            st.write(f"**Confidence:** {confidence:.0%}")
            
            if intent_info.get("all_intents"):
                st.write("**Other possible intents:**")
                for intent, score in intent_info["all_intents"].items():
                    if intent != primary_intent and score > 0:
                        st.write(f"- {intent_display.get(intent, intent)}: {score}")
            
            status.update(label=f"✅ Query understood as: {intent_display.get(primary_intent, 'General Search')}", state="complete")
        
        # Step 2: Search all sources
        with st.status("🔎 Searching all 16 sources simultaneously...", expanded=False) as status:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            organized_results = search_all_sources_enhanced(prompt)
            st.session_state.last_search = prompt
            st.session_state.last_organized_results = organized_results
            
            # Simulate progress
            for i in range(1, 17):
                progress_bar.progress(i/16)
                status_text.text(f"Searching source {i} of 16...")
            
            progress_bar.empty()
            status_text.empty()
            
            # Show source statistics
            primary_count = len(organized_results.get("primary_results", {}))
            secondary_count = len(organized_results.get("secondary_results", {}))
            
            status.update(label=f"✅ Found results from {primary_count + secondary_count} sources ({primary_count} primary, {secondary_count} secondary)", state="complete")
        
        # Step 3: Display intelligent summary
        st.markdown("### 🧠 Intelligent Summary")
        intelligent_summary = create_intelligent_summary(prompt, organized_results)
        st.markdown(intelligent_summary)
        
        # Step 4: Show detailed results in tabs
        st.markdown("---")
        tab1, tab2, tab3, tab4 = st.tabs(["🎯 Primary Results", "📋 All Results", "📊 Source Analysis", "📈 Raw Data"])
        
        with tab1:
            st.markdown("### 🎯 Most Relevant Results (Based on Query Intent)")
            
            primary_results = organized_results.get("primary_results", {})
            if primary_results:
                for source, data in primary_results.items():
                    with st.expander(f"📌 {source.replace('_', ' ').title()}", expanded=True):
                        if isinstance(data, list):
                            for item in data[:3]:
                                if isinstance(item, dict):
                                    if "error" not in item:
                                        st.markdown(f"**{item.get('title', 'No title')}**")
                                        if item.get('body'):
                                            st.markdown(f"{item.get('body', '')[:200]}...")
                                        if item.get('url'):
                                            st.markdown(f"[🔗 Source]({item.get('url')})")
                                        st.divider()
                        elif isinstance(data, dict):
                            if "error" not in data:
                                for key, value in list(data.items())[:10]:
                                    st.markdown(f"**{key.replace('_', ' ').title()}:** {str(value)[:100]}")
            else:
                st.info("No primary results to display.")
        
        with tab2:
            st.markdown("### 📋 All Search Results")
            
            all_results = organized_results.get("all_results", {})
            for source, data in all_results.items():
                source_type = "primary" if source in organized_results.get("primary_results", {}) else "secondary"
                
                with st.expander(f"{'🎯' if source_type == 'primary' else '📄'} {source.replace('_', ' ').title()}"):
                    if isinstance(data, list):
                        st.markdown(f"**Items found:** {len(data)}")
                        for i, item in enumerate(data[:5]):
                            with st.container():
                                if isinstance(item, dict):
                                    if "error" in item:
                                        st.error(f"Error: {item['error']}")
                                    else:
                                        st.markdown(f"**{i+1}. {item.get('title', 'No title')}**")
                                        if item.get('body'):
                                            st.markdown(f"{item.get('body', '')[:150]}...")
                                        if item.get('url'):
                                            st.markdown(f"[View source]({item.get('url')})")
                    elif isinstance(data, dict):
                        if "error" in data:
                            st.error(f"Error: {data['error']}")
                        else:
                            for key, value in list(data.items())[:15]:
                                st.markdown(f"**{key.replace('_', ' ').title()}:** {str(value)[:200]}")
        
        with tab3:
            st.markdown("### 📊 Source Analysis")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Primary Sources", len(organized_results.get("primary_results", {})))
            with col2:
                st.metric("Secondary Sources", len(organized_results.get("secondary_results", {})))
            with col3:
                total_sources = len(organized_results.get("all_results", {}))
                st.metric("Total Sources", total_sources)
            
            # Source effectiveness chart
            st.markdown("#### Source Results Quality")
            
            source_quality = {}
            for source, data in organized_results.get("all_results", {}).items():
                if isinstance(data, list):
                    if data and "error" not in str(data[0]):
                        source_quality[source] = {
                            "status": "✅ Good",
                            "items": len(data),
                            "type": "List"
                        }
                    else:
                        source_quality[source] = {
                            "status": "⚠️ Issues",
                            "items": 0,
                            "type": "List"
                        }
                elif isinstance(data, dict):
                    if "error" in data:
                        source_quality[source] = {
                            "status": "❌ Error",
                            "items": 0,
                            "type": "Dict"
                        }
                    else:
                        source_quality[source] = {
                            "status": "✅ Good",
                            "items": 1,
                            "type": "Dict"
                        }
            
            # Display as table
            import pandas as pd
            quality_df = pd.DataFrame.from_dict(source_quality, orient='index')
            quality_df.index.name = "Source"
            quality_df = quality_df.reset_index()
            
            st.dataframe(
                quality_df,
                column_config={
                    "Source": st.column_config.TextColumn("Source"),
                    "status": st.column_config.TextColumn("Status"),
                    "items": st.column_config.NumberColumn("Items"),
                    "type": st.column_config.TextColumn("Data Type")
                },
                hide_index=True,
                use_container_width=True
            )
        
        with tab4:
            st.markdown("### 📈 Raw Data View")
            st.json(organized_results, expanded=False)
        
        # Add to chat history
        response_content = f"""**Intelligent Search Results for:** {prompt}

**Primary Intent:** {intent_display.get(primary_intent, 'General Search')}

{intelligent_summary}

*View detailed results in the tabs above.*"""
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": response_content
        })
