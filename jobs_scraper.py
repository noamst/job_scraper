import json
import os
import sys
from typing import Any
import asyncio
from urllib.parse import urlparse
import httpx
from mcp.server.fastmcp import FastMCP
from laststartupScraping import LastStartupScraper  # Make sure this import works
import re

# Initialize FastMCP server
mcp = FastMCP("jobs_scraper")
job_structure_cache_path = "job_structure_cache.json"

BASE_URL = "https://www.lastartup.co.il/funding"
scraper = LastStartupScraper(BASE_URL)
# Load cache from disk
def load_structure_cache():
    if os.path.exists(job_structure_cache_path):
        with open(job_structure_cache_path, "r") as f:
            return json.load(f)
    return {}

@mcp.tool()
async def get_jobs(company: str) -> str:
    """Find jobs for a given company from LastStartup.

    Args:
        company: A company name
    """
    scraper = LastStartupScraper(BASE_URL)

    # Step 1: Match company name and extract careers URL
    try:
        all_links = scraper.get_companies(BASE_URL)
    except Exception as e:
        return f"❌ Failed to load companies: {str(e)}"

    matched_url = None
    for entry in all_links:
        try:
            data = json.loads(entry)
            if company.lower() in data["company_name"].lower():
                matched_url = data["careers_url"]
                break
        except json.JSONDecodeError:
            continue

    if not matched_url:
        return f"❌ Company '{company}' not found."

    domain = matched_url

    # Step 2: Download HTML
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(matched_url)
            response.raise_for_status()
            html = response.text
    except Exception as e:
        return f"❌ Failed to fetch {matched_url}: {str(e)}"

    cleaned_html = LastStartupScraper.clean_html_for_llm_no_spaces(html)

    # Step 3: Load cache
    job_structure_cache = load_structure_cache()
    print(domain)
    
    # Step 4: Retrieve or infer structure
    if domain in job_structure_cache:
        structure = job_structure_cache[domain]
    else:
        try:
            llm_content = LastStartupScraper.ask_llm_for_content(html,matched_url)
            structure = LastStartupScraper.extract_consistent_selectors(html, llm_content)
            job_structure_cache[domain] = structure
            #save_structure_cache(job_structure_cache)  # Save updated cache
        except Exception as e:
            return f"❌ Failed to infer structure for {domain}: {str(e)}"

    # Step 5: Extract jobs
    try:
        jobs = LastStartupScraper.extract_jobs_with_precise_schema(html, structure)
    except Exception as e:
        return f"❌ Error parsing jobs: {str(e)}"

    if not jobs:
        return f"📭 No structured jobs found for {company} on {matched_url}"

    return f"📋 Jobs at {company}:\n\n" + "\n".join(
        f"- {job['title']} ({job['location']})" for job in jobs
    )


@mcp.tool()
async def get_jobs_from_url(career_page_url: str) -> str:
    """Find jobs from a given career page url.

    Args:
        career_page_url: A career page url.
    """
    scraper = LastStartupScraper(BASE_URL)

    
    if not career_page_url:
        return f"❌ page '{career_page_url}' not found."

    domain = career_page_url

    # Step 2: Download HTML
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(career_page_url)
            response.raise_for_status()
            html = response.text
    except Exception as e:
        return f"❌ Failed to fetch {career_page_url}: {str(e)}"

    cleaned_html = LastStartupScraper.clean_html_for_llm_no_spaces(html)

    # Step 3: Load cache
    job_structure_cache = load_structure_cache()
    print(domain)
    
    # Step 4: Retrieve or infer structure
    if domain in job_structure_cache:
        structure = job_structure_cache[domain]
    else:
        try:
            llm_content = LastStartupScraper.ask_llm_for_content(html,career_page_url)
            structure = LastStartupScraper.extract_consistent_selectors(html, llm_content)
            job_structure_cache[domain] = structure
            #save_structure_cache(job_structure_cache)  # Save updated cache
        except Exception as e:
            return f"❌ Failed to infer structure for {domain}: {str(e)}"

    # Step 5: Extract jobs
    try:
        jobs = LastStartupScraper.extract_jobs_with_precise_schema(html, structure)
    except Exception as e:
        return f"❌ Error parsing jobs: {str(e)}"

    if not jobs:
        return f"📭 No structured jobs found for  {career_page_url}"

    return f"📋 Jobs at {career_page_url}:\n\n" + "\n".join(
        f"- {job['title']} ({job['location']})" for job in jobs
    )

if __name__ == "__main__":
    print("Hello from Jobs Scraper!")

    mcp.run(transport='stdio')  # Run the FastMCP instance
