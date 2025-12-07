# AI-Powered Multi-Source Search Assistant

## Overview
A Streamlit application that combines 16 search sources with TinyLLaMA AI for intelligent analysis. Users can ask questions and get both raw search results and AI-synthesized insights.

## Features
- **16 Concurrent Search Sources**: Searches all sources simultaneously for fast results
- **TinyLLaMA AI Integration**: Analyzes search results and provides synthesized responses
- **Three Output Tabs**: AI Analysis, Search Results, Raw Data
- **Customizable AI Personas**: Multiple presets including Search Analyst, Code Helper, etc.
- **Model Settings**: Temperature and max tokens controls

## Search Sources
### Web & Knowledge
- DuckDuckGo Web Search
- DuckDuckGo Instant Answers
- DuckDuckGo News
- Wikipedia
- Wikidata

### Science & Research
- ArXiv (Scientific Papers)
- PubMed (Medical Research)

### Reference
- OpenLibrary (Books)
- Dictionary API
- REST Countries
- Quotable (Quotes)

### Developer
- GitHub Repositories
- Stack Overflow Q&A

### Location & Environment
- Nominatim (Geocoding)
- wttr.in (Weather)
- OpenAQ (Air Quality)

## Project Structure
```
├── app.py                     # Main Streamlit application
├── services/                  # Search service modules
│   ├── arxiv_service.py
│   ├── duckduckgo_service.py
│   ├── wikipedia_service.py
│   ├── weather_service.py
│   ├── openaq_service.py
│   ├── wikidata_service.py
│   ├── openlibrary_service.py
│   ├── pubmed_service.py
│   ├── nominatim_service.py
│   ├── dictionary_service.py
│   ├── countries_service.py
│   ├── quotes_service.py
│   ├── github_service.py
│   └── stackexchange_service.py
├── models/                    # TinyLLaMA model storage (auto-downloaded)
└── .streamlit/config.toml    # Streamlit configuration
```

## AI Model
- **Model**: TinyLLaMA 1.1B Chat v1.0
- **Quantization**: Q4_K_M (~637 MB)
- **Source**: Hugging Face (auto-downloaded on first run)

## Running the Application
```bash
streamlit run app.py --server.port 5000
```

## Recent Changes
- 2024-12-07: Initial creation with all 16 search sources and TinyLLaMA integration
