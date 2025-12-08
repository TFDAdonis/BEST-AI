import streamlit as st
import requests
import json
import xml.etree.ElementTree as ET
import concurrent.futures
import arxiv
import wikipedia
import re
from pathlib import Path

# ==================== ALL SERVICE FUNCTIONS IN ONE FILE ====================

# ArXiv Service
def search_arxiv(query: str, max_results: int = 5):
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

# DuckDuckGo Web Search
def search_duckduckgo(query: str, max_results: int = 8):
    """Search DuckDuckGo web results."""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        
        response = requests.get(url, params=params, timeout=15)
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
        
        return results[:max_results]
    except Exception as e:
        return [{"error": str(e)}]

# DuckDuckGo Instant Answer
def get_instant_answer(query: str):
    """Get instant answer from DuckDuckGo."""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1"
        }
        
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        return {
            "answer": data.get("AbstractText", ""),
            "heading": data.get("Heading", ""),
            "url": data.get("AbstractURL", ""),
            "image": data.get("Image", "")
        }
    except Exception as e:
        return {"error": str(e)}

# DuckDuckGo News
def search_news(query: str, max_results: int = 5):
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
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
        results = []
        
        # Extract titles and snippets
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
        search_results = wikipedia.search(query, results=5)
        
        if not search_results:
            return {"exists": False, "message": "No Wikipedia page found"}
        
        try:
            page = wikipedia.page(search_results[0])
            return {
                "exists": True,
                "title": page.title,
                "summary": page.summary,
                "url": page.url,
                "categories": page.categories[:10],
                "content": page.content[:2000]
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
        
        response = requests.get(url, headers=headers, timeout=15)
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
        
        response = requests.get(url, params=params, timeout=15)
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
def search_wikidata(query: str, max_results: int = 5):
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
        
        response = requests.get(url, params=params, timeout=15)
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
def search_books(query: str, max_results: int = 6):
    """Search for books using OpenLibrary API."""
    try:
        url = "https://openlibrary.org/search.json"
        params = {
            "q": query,
            "limit": max_results
        }
        
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        
        results = []
        for doc in data.get("docs", [])[:max_results]:
            book = {
                "title": doc.get("title", "N/A"),
                "authors": doc.get("author_name", ["Unknown"]),
                "first_publish_year": doc.get("first_publish_year", "N/A"),
                "publisher": doc.get("publisher", ["Unknown"])[0] if doc.get("publisher") else "Unknown",
                "language": doc.get("language", ["en"])[0] if doc.get("language") else "en",
                "subject": doc.get("subject", [])[:5],
                "url": f"https://openlibrary.org{doc.get('key', '')}" if doc.get("key") else "",
                "cover_id": doc.get("cover_i"),
                "cover_url": f"https://covers.openlibrary.org/b/id/{doc.get('cover_i')}-M.jpg" if doc.get("cover_i") else None
            }
            results.append(book)
        
        return results
    except Exception as e:
        return [{"error": str(e)}]

# PubMed Service
def search_pubmed(query: str, max_results: int = 5):
    """Search PubMed for medical research articles."""
    try:
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        
        # Search for article IDs
        search_url = f"{base_url}/esearch.fcgi"
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "relevance"
        }
        
        search_response = requests.get(search_url, params=search_params, timeout=15)
        search_data = search_response.json()
        
        ids = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not ids:
            return [{"message": "No articles found"}]
        
        # Fetch article details
        fetch_url = f"{base_url}/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(ids),
            "retmode": "xml",
            "rettype": "abstract"
        }
        
        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=15)
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
                "abstract": abstract[:1000] + "..." if len(abstract) > 1000 else abstract,
                "authors": authors[:8],
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
    """Geocode a location using Nominatim."""
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
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
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
        response = requests.get(url, timeout=15)
        
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
    """Search for country information."""
    try:
        url = f"https://restcountries.com/v3.1/name/{query}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 404:
            url = f"https://restcountries.com/v3.1/name/{query}"
            params = {"fullText": False}
            response = requests.get(url, params=params, timeout=15)
        
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
def search_quotes(query: str, max_results: int = 5):
    """Search for quotes using Quotable API."""
    try:
        url = "https://api.quotable.io/search/quotes"
        params = {
            "query": query,
            "limit": max_results
        }
        
        response = requests.get(url, params=params, timeout=15)
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
            response = requests.get(url, params=params, timeout=15)
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
def search_github_repos(query: str, max_results: int = 5):
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
        
        response = requests.get(url, params=params, headers=headers, timeout=15)
        
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
def search_stackoverflow(query: str, max_results: int = 6):
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
        
        response = requests.get(url, params=params, timeout=15)
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

# ==================== STREAMLIT APP ====================

st.set_page_config(
    page_title="AI Search Assistant",
    page_icon="🔍",
    layout="wide"
)

st.title("🔍 Multi-Source Search Assistant")
st.markdown("*Searches all 16 sources simultaneously*")

with st.sidebar:
    st.header("📊 16 Sources Searched")
    st.markdown("""
    **Web & Knowledge:**
    - DuckDuckGo Web Search
    - DuckDuckGo Instant Answers
    - DuckDuckGo News
    - Wikipedia
    - Wikidata
    
    **Science & Research:**
    - ArXiv (Scientific Papers)
    - PubMed (Medical Research)
    
    **Reference:**
    - OpenLibrary (Books)
    - Dictionary API
    - REST Countries
    - Quotable (Quotes)
    
    **Developer:**
    - GitHub Repositories
    - Stack Overflow Q&A
    
    **Location & Environment:**
    - Nominatim (Geocoding)
    - wttr.in (Weather)
    - OpenAQ (Air Quality)
    """)
    
    st.divider()
    
    if st.button("🗑️ Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

def search_all_sources(query: str) -> dict:
    """Search ALL sources simultaneously with more results."""
    results = {}
    
    def safe_search(name, func, *args, **kwargs):
        try:
            return name, func(*args, **kwargs)
        except Exception as e:
            return name, {"error": str(e)}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        first_word = query.split()[0] if query.strip() else query
        futures = {
            executor.submit(safe_search, "arxiv", search_arxiv, query, 5): "arxiv",
            executor.submit(safe_search, "duckduckgo", search_duckduckgo, query, 8): "duckduckgo",
            executor.submit(safe_search, "duckduckgo_instant", get_instant_answer, query): "duckduckgo_instant",
            executor.submit(safe_search, "news", search_news, query, 5): "news",
            executor.submit(safe_search, "wikipedia", search_wikipedia, query): "wikipedia",
            executor.submit(safe_search, "weather", get_weather_wttr, query): "weather",
            executor.submit(safe_search, "air_quality", get_air_quality, query): "air_quality",
            executor.submit(safe_search, "wikidata", search_wikidata, query, 5): "wikidata",
            executor.submit(safe_search, "books", search_books, query, 6): "books",
            executor.submit(safe_search, "pubmed", search_pubmed, query, 5): "pubmed",
            executor.submit(safe_search, "geocoding", geocode_location, query): "geocoding",
            executor.submit(safe_search, "dictionary", get_definition, first_word): "dictionary",
            executor.submit(safe_search, "country", search_country, query): "country",
            executor.submit(safe_search, "quotes", search_quotes, query, 5): "quotes",
            executor.submit(safe_search, "github", search_github_repos, query, 5): "github",
            executor.submit(safe_search, "stackoverflow", search_stackoverflow, query, 6): "stackoverflow",
        }
        
        for future in concurrent.futures.as_completed(futures):
            try:
                name, data = future.result()
                results[name] = data
            except Exception as e:
                results[futures[future]] = {"error": str(e)}
    
    return results

def format_results(query: str, results: dict) -> str:
    """Format all search results into a readable response."""
    output = [f"## Search Results for: *{query}*\n"]
    
    # Instant Answer
    if "duckduckgo_instant" in results:
        instant = results["duckduckgo_instant"]
        if isinstance(instant, dict) and "error" not in instant and instant.get("answer"):
            output.append(f"### 💡 Quick Answer\n{instant['answer']}\n")
    
    # Wikipedia
    if "wikipedia" in results:
        wiki = results["wikipedia"]
        if isinstance(wiki, dict) and "error" not in wiki and wiki.get("exists"):
            output.append(f"### 📚 Wikipedia: {wiki.get('title', 'N/A')}")
            output.append(f"{wiki.get('summary', 'No summary')[:800]}...")
            output.append(f"[Read more]({wiki.get('url', '')})\n")
    
    # Web Results
    if "duckduckgo" in results:
        ddg = results["duckduckgo"]
        if isinstance(ddg, list) and ddg and len(ddg) > 0 and "error" not in ddg[0]:
            output.append("### 🌐 Web Results")
            for i, item in enumerate(ddg[:5], 1):
                if isinstance(item, dict) and "error" not in item:
                    output.append(f"{i}. **{item.get('title', 'N/A')}**")
                    if item.get('body'):
                        output.append(f"   {item.get('body', '')[:250]}...")
                    if item.get('url'):
                        output.append(f"   [Link]({item.get('url')})")
            output.append("")
    
    # ArXiv Papers
    if "arxiv" in results:
        arxiv_data = results["arxiv"]
        if isinstance(arxiv_data, list) and arxiv_data and len(arxiv_data) > 0 and "error" not in arxiv_data[0]:
            output.append("### 🔬 Scientific Papers (ArXiv)")
            for i, paper in enumerate(arxiv_data[:4], 1):
                if isinstance(paper, dict) and "error" not in paper:
                    authors = ", ".join(paper.get("authors", [])[:3])
                    output.append(f"{i}. **{paper.get('title', 'N/A')}**")
                    output.append(f"   Authors: {authors} | Published: {paper.get('published', 'N/A')}")
                    if paper.get('summary'):
                        output.append(f"   {paper.get('summary', '')[:300]}...")
                    if paper.get('url'):
                        output.append(f"   [View Paper]({paper.get('url')})")
            output.append("")
    
    # PubMed Articles
    if "pubmed" in results:
        pubmed_data = results["pubmed"]
        if isinstance(pubmed_data, list) and pubmed_data and len(pubmed_data) > 0 and "error" not in pubmed_data[0]:
            output.append("### 🏥 Medical Research (PubMed)")
            for i, article in enumerate(pubmed_data[:4], 1):
                if isinstance(article, dict) and "error" not in article:
                    authors = ", ".join(article.get("authors", [])[:3])
                    output.append(f"{i}. **{article.get('title', 'N/A')}**")
                    output.append(f"   Authors: {authors} | Year: {article.get('year', 'N/A')}")
                    if article.get('abstract'):
                        output.append(f"   {article.get('abstract', '')[:300]}...")
                    if article.get('url'):
                        output.append(f"   [View Article]({article.get('url')})")
            output.append("")
    
    # Books
    if "books" in results:
        books_data = results["books"]
        if isinstance(books_data, list) and books_data and len(books_data) > 0 and "error" not in books_data[0]:
            output.append("### 📖 Books (OpenLibrary)")
            for i, book in enumerate(books_data[:4], 1):
                if isinstance(book, dict) and "error" not in book:
                    authors = ", ".join(book.get("authors", [])[:3])
                    output.append(f"{i}. **{book.get('title', 'N/A')}**")
                    output.append(f"   Authors: {authors} | First Published: {book.get('first_publish_year', 'N/A')}")
                    if book.get('url'):
                        output.append(f"   [View Book]({book.get('url')})")
            output.append("")
    
    # Wikidata
    if "wikidata" in results:
        wikidata = results["wikidata"]
        if isinstance(wikidata, list) and wikidata and len(wikidata) > 0 and "error" not in wikidata[0]:
            output.append("### 🗃️ Wikidata Entities")
            for i, entity in enumerate(wikidata[:4], 1):
                if isinstance(entity, dict) and "error" not in entity:
                    output.append(f"{i}. **{entity.get('label', 'N/A')}**: {entity.get('description', 'No description')}")
                    if entity.get('url'):
                        output.append(f"   [View]({entity.get('url')})")
            output.append("")
    
    # Weather
    if "weather" in results:
        weather = results["weather"]
        if isinstance(weather, dict) and "error" not in weather and weather.get("temperature_c"):
            output.append("### 🌤️ Weather")
            output.append(f"- Location: {weather.get('location', 'N/A')}")
            output.append(f"- Temperature: {weather.get('temperature_c', 'N/A')}°C / {weather.get('temperature_f', 'N/A')}°F")
            output.append(f"- Condition: {weather.get('condition', 'N/A')}")
            output.append(f"- Humidity: {weather.get('humidity', 'N/A')}%")
            output.append(f"- Wind: {weather.get('wind_speed_kmph', 'N/A')} km/h")
            output.append("")
    
    # Air Quality
    if "air_quality" in results:
        aq = results["air_quality"]
        if isinstance(aq, dict) and "error" not in aq and aq.get("data"):
            output.append("### 🌬️ Air Quality")
            output.append(f"- City: {aq.get('city', 'N/A')}")
            for i, loc in enumerate(aq.get("data", [])[:2], 1):
                output.append(f"{i}. Location: {loc.get('location', 'N/A')}")
                for m in loc.get("measurements", [])[:3]:
                    output.append(f"   - {m.get('parameter', 'N/A')}: {m.get('value', 'N/A')} {m.get('unit', '')}")
            output.append("")
    
    # Geocoding
    if "geocoding" in results:
        geo = results["geocoding"]
        if isinstance(geo, dict) and "error" not in geo and geo.get("display_name"):
            output.append("### 📍 Location Info")
            output.append(f"- {geo.get('display_name', 'N/A')}")
            output.append(f"- Coordinates: {geo.get('latitude', 'N/A')}, {geo.get('longitude', 'N/A')}")
            if geo.get('osm_url'):
                output.append(f"- [View on Map]({geo.get('osm_url')})")
            output.append("")
    
    # News
    if "news" in results:
        news_data = results["news"]
        if isinstance(news_data, list) and news_data and len(news_data) > 0 and "error" not in news_data[0]:
            output.append("### 📰 News")
            for i, article in enumerate(news_data[:4], 1):
                if isinstance(article, dict) and "error" not in article:
                    output.append(f"{i}. **{article.get('title', 'N/A')}**")
                    if article.get('source'):
                        output.append(f"   Source: {article.get('source')}")
                    if article.get('body'):
                        output.append(f"   {article.get('body', '')[:200]}...")
                    if article.get('url'):
                        output.append(f"   [Read Article]({article.get('url')})")
            output.append("")
    
    # Dictionary
    if "dictionary" in results:
        dictionary = results["dictionary"]
        if isinstance(dictionary, dict) and "error" not in dictionary and dictionary.get("word"):
            output.append(f"### 📖 Dictionary: {dictionary.get('word', 'N/A')}")
            phonetics = dictionary.get('phonetics', [])
            if phonetics:
                output.append(f"*Pronunciation: {', '.join(phonetics)}*")
            for meaning in dictionary.get('meanings', [])[:3]:
                output.append(f"**{meaning.get('part_of_speech', '')}**")
                for defn in meaning.get('definitions', [])[:3]:
                    output.append(f"- {defn.get('definition', '')}")
                    if defn.get('example'):
                        output.append(f"  *Example: \"{defn.get('example')}\"*")
            output.append("")
    
    # Country
    if "country" in results:
        country = results["country"]
        if isinstance(country, dict) and "error" not in country and country.get("name"):
            output.append(f"### 🌍 Country: {country.get('name', 'N/A')} {country.get('flag_emoji', '')}")
            output.append(f"- **Official Name**: {country.get('official_name', 'N/A')}")
            output.append(f"- **Capital**: {country.get('capital', 'N/A')}")
            output.append(f"- **Region**: {country.get('region', 'N/A')} / {country.get('subregion', 'N/A')}")
            pop = country.get('population', 'N/A')
            if isinstance(pop, int):
                output.append(f"- **Population**: {pop:,}")
            else:
                output.append(f"- **Population**: {pop}")
            languages = country.get('languages', [])
            if languages:
                output.append(f"- **Languages**: {', '.join(languages[:4])}")
            currencies = country.get('currencies', [])
            if currencies:
                output.append(f"- **Currencies**: {', '.join(currencies[:3])}")
            if country.get('map_url'):
                output.append(f"- [View on Map]({country.get('map_url')})")
            output.append("")
    
    # Quotes
    if "quotes" in results:
        quotes_data = results["quotes"]
        if isinstance(quotes_data, list) and quotes_data and len(quotes_data) > 0 and "error" not in quotes_data[0]:
            output.append("### 💬 Quotes")
            for i, quote in enumerate(quotes_data[:4], 1):
                if isinstance(quote, dict) and "error" not in quote:
                    output.append(f"{i}. > \"{quote.get('content', '')}\"")
                    output.append(f"   > — *{quote.get('author', 'Unknown')}*")
                    output.append("")
    
    # GitHub
    if "github" in results:
        github_data = results["github"]
        if isinstance(github_data, list) and github_data and len(github_data) > 0 and "error" not in github_data[0]:
            output.append("### 💻 GitHub Repositories")
            for i, repo in enumerate(github_data[:4], 1):
                if isinstance(repo, dict) and "error" not in repo:
                    stars = repo.get('stars', 0)
                    output.append(f"{i}. **{repo.get('name', 'N/A')}** ⭐ {stars:,}")
                    if repo.get('description'):
                        output.append(f"   {repo.get('description', '')[:150]}...")
                    output.append(f"   Language: {repo.get('language', 'N/A')} | Forks: {repo.get('forks', 0):,}")
                    if repo.get('url'):
                        output.append(f"   [View Repository]({repo.get('url')})")
            output.append("")
    
    # Stack Overflow
    if "stackoverflow" in results:
        so_data = results["stackoverflow"]
        if isinstance(so_data, list) and so_data and len(so_data) > 0 and "error" not in so_data[0]:
            output.append("### 🔧 Stack Overflow")
            for i, q in enumerate(so_data[:4], 1):
                if isinstance(q, dict) and "error" not in q:
                    answered_emoji = "✅" if q.get('is_answered') else "❓"
                    output.append(f"{i}. {answered_emoji} **{q.get('title', 'N/A')}**")
                    output.append(f"   Score: {q.get('score', 0)} | Answers: {q.get('answer_count', 0)} | Views: {q.get('view_count', 0):,}")
                    tags = q.get('tags', [])[:4]
                    if tags:
                        output.append(f"   Tags: {', '.join(tags)}")
                    if q.get('url'):
                        output.append(f"   [View Question]({q.get('url')})")
            output.append("")
    
    return "\n".join(output)

# Main chat interface
if prompt := st.chat_input("Search anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        st.caption("🔎 Searching all 16 sources simultaneously...")
        
        with st.spinner("Searching across 16 sources..."):
            search_results = search_all_sources(prompt)
        
        response = format_results(prompt, search_results)
        st.markdown(response)
        
        with st.expander("📊 View Raw Data"):
            for source, data in search_results.items():
                st.subheader(f"📌 {source.replace('_', ' ').title()}")
                if isinstance(data, list):
                    for i, item in enumerate(data[:3], 1):
                        st.markdown(f"**Item {i}:**")
                        st.json(item)
                else:
                    st.json(data)
    
    st.session_state.messages.append({
        "role": "assistant", 
        "content": response
    })
