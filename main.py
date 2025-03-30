# main.py

from fastapi import FastAPI
from pydantic import BaseModel
import requests
import bioc
import spacy
import xml.etree.ElementTree as ET
from collections import defaultdict

nlp = spacy.load("en_core_web_sm")

app = FastAPI()

# Request model
class PlantRequest(BaseModel):
    scientific_name: str


# ========= PubMed + BioC API Functions =========

def get_pubmed_ids(query, retmax=5):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {"db": "pubmed", "term": query + " medicinal", "retmode": "json", "retmax": retmax}
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])
    except:
        return []

def get_article_title(pubmed_id):
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pubmed_id}&retmode=json"
    try:
        r = requests.get(url)
        return r.json()["result"][pubmed_id]["title"]
    except:
        return ""

def get_bioc_article(pubmed_id):
    url = f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pubmed_id}/unicode"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.text if response.text.strip().startswith("<?xml") else None
    except:
        return None

def parse_bioc_xml(xml_data):
    idx = xml_data.find("<?xml")
    cleaned_xml = xml_data[idx:].strip()
    try:
        root = ET.fromstring(cleaned_xml)
        passages = []
        for doc in root.findall(".//document"):
            for passage in doc.findall(".//passage"):
                text_elem = passage.find("text")
                if text_elem is not None and text_elem.text:
                    passages.append(text_elem.text)
        return passages
    except:
        return []

def extract_medicinal_passages(passages):
    keywords = [
        "medicinal", "therapy", "treatment", "healing", "immune", "inflammation",
        "infection", "cold", "cough", "fever", "pain", "antiviral", "antibacterial",
        "antifungal", "antioxidant", "allergy", "flu", "asthma"
    ]
    return [p for p in passages if any(kw in p.lower() for kw in keywords)]


# ========= FastAPI Endpoint =========

@app.post("/medicinal")
def get_medicinal_info(request: PlantRequest):
    pubmed_ids = get_pubmed_ids(request.scientific_name)
    result_list = []

    for pid in pubmed_ids:
        title = get_article_title(pid)
        bioc_xml = get_bioc_article(pid)
        if bioc_xml:
            passages = parse_bioc_xml(bioc_xml)
            medicinal = extract_medicinal_passages(passages)
            if medicinal:
                result_list.append({
                    "article_title": title,
                    "passages": medicinal[:5],  # limit to 5 per article
                    "pubmed_id": pid
                })

    return {"plant": request.scientific_name, "results": result_list}

