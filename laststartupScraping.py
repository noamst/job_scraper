import requests
from bs4 import BeautifulSoup, NavigableString, Comment
import re
import json , os
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableSequence
from lxml import html
from collections import defaultdict


# Load Groq API key
groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    raise ValueError("GROQ_API_KEY environment variable is missing")

# Use LLaMA 3 for summarization
llm = ChatGroq(
    model="llama3-8b-8192",
    api_key=groq_api_key
)






class LastStartupScraper:
    def __init__(self, base_url):
        """
        Initializes the scraper with a base URL.
        """
        self.base_url = base_url

    def fetch_page(self, url):
        """
        Fetches the HTML content of a given URL.

        Args:
            url (str): The URL to fetch.

        Returns:
            str: The HTML content of the page, or None if an error occurs.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching page: {e}")
            return None

    def get_companies(self, url):
        """
        Extracts company links from the given URL.

        Args:
            url (str): The URL to scrape.

        Returns:
            list: A list of company links.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')

            # Find all <div> elements with role="listitem" and class="w-dyn-item"
            items = soup.find_all('div', attrs={'role': 'listitem'}, class_='w-dyn-item')

            company_links = []

            # Iterate over each item and extract the desired link
            for item in items:
                company_div = item.find('div', class_='funding-company-title')
                if not company_div:
                    continue

                # Look for <a> tags that contain a div with class 'text-block-404' and text 'אתר בית'
                links = item.find_all('a', href=True)
                for link in links:
                    text_block = link.find('div', class_='text-block-404')
                    if text_block and text_block.get_text(strip=True) == 'אתר בית':
                        company_links.append(json.dumps({'company_name':company_div.text,'careers_url':link['href'].rstrip('/')+'/careers'}))

            return company_links
        except requests.RequestException as e:
            print(f"Error scraping companies: {e}")
            return []
    



    @staticmethod
    def ask_llm_for_content(cleaned_html, domain):
        system_prompt = """
            You are a highly accurate HTML-to-JSON converter specialized in career pages.

            Your task is to extract job listings from the simplified *text* of a company's careers webpage.

            The input will be plain visible text (not raw HTML), already cleaned of irrelevant tags and attributes.

            🧠 Your goal is to:
            - Identify recurring job listing blocks.
            - Extract the following fields from each:
                - "title": The job title
                - "link": A link to the job detail page (if available in the text)
                - "location": The location (if provided)
                - "department": The department/category (if provided)

            🎯 Output Requirements:
            - Return a **list of job objects** in **pure JSON**
            - Each object must have at least the "title" field
            - No explanations. No markdown. No formatting hints.
            - Just raw valid JSON.

            Example output format:
            [
            {
                "title": "Frontend Developer",
                "link": "/careers/frontend-developer", 
                "location": "Remote",
                "department": "Engineering"
            },
            ...
            ]

            Only return valid JSON. No explanation.
            ❌ No explanations
            ❌ No code blocks
            ✅ Only valid JSON

            """

        # Build the full prompt (system + user message)
        full_prompt = PromptTemplate(
            input_variables=["cleaned_html", "domain"],
            template="""
    {system_prompt}

    📝 Domain: {domain}

    📄 Cleaned HTML text:
    {cleaned_html}
    """
        )

        chain = RunnableSequence(
            full_prompt.partial(system_prompt=system_prompt) |
            llm |
            StrOutputParser()
        )

        return chain.invoke({
            "domain": domain,
            "cleaned_html": cleaned_html
        })

    @staticmethod     
    def load_structure_cache():
        return json.load(open('job_structure_cache.json')) if os.path.exists('job_structure_cache.json') else {}
    @staticmethod
    def save_structure_cache(cache):
        with open('job_structure_cache.json', 'w') as f:
            json.dump(cache, f, indent=2)

    def get_or_learn_structure(domain, html):
        cache = LastStartupScraper.load_structure_cache()
        if domain in cache:
            return cache[domain]
        
        cleaned_html = LastStartupScraper.clean_html_for_structure_learning(html)
        response = LastStartupScraper.ask_llm_for_structure(cleaned_html, domain)

        try:
            structure = json.loads(response)
        except json.JSONDecodeError:
            print("⚠️ Failed to parse structure from LLM:", response)
            return None

        cache[domain] = structure
        LastStartupScraper.save_structure_cache(cache)
        return structure
    @staticmethod
    def scrape_jobs_with_structure(html, structure):
        soup = BeautifulSoup(html, 'html.parser')
        jobs = []
        container_selector = structure['job_container']
        print(f"🔍 Using job container selector: {container_selector}")
        
        for job in soup.select(structure['job_container']):
            print(job)
            title_el = job.select_one(structure['title'])
            link_el = job.select_one(structure['link'])
            loc_el = job.select_one(structure.get('location', ''))

            jobs.append({
                "title": title_el.get_text(strip=True) if title_el else "N/A",
                "link": link_el['href'] if link_el and link_el.has_attr('href') else "",
                "location": loc_el.get_text(strip=True) if loc_el else ""
            })

        return jobs
    @staticmethod
    def clean_html_for_llm_no_spaces(html):
        soup = BeautifulSoup(html, 'html.parser')

        # Remove noisy tags
        tags_to_remove = [
            'img', 'script', 'style', 'head', 'footer', 'svg', 'iframe',
            'noscript', 'link', 'meta', 'form', 'aside', 'nav', 'canvas',
            'object', 'video', 'audio', 'picture', 'source'
        ]
        for tag_name in tags_to_remove:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Clean attributes and inline links
        for tag in soup.find_all(True):
            if tag.name == 'a' and tag.has_attr('href'):
                tag.string = f"{tag.get_text(strip=True)} [{tag['href']}]"
                tag.attrs = {}
            else:
                tag.attrs.clear()

        # Extract and minify text
        raw_text = soup.get_text(separator='\n', strip=True)
        raw_text = re.sub(r'\s+', ' ', raw_text)           # collapse multiple spaces
        raw_text = re.sub(r'\s*\n\s*', '\n', raw_text)     # normalize newlines
        cleaned_text = raw_text.strip()                    # remove leading/trailing spaces

        return cleaned_text
    

    @staticmethod
    def get_css_selector(tag):
        """Build a CSS selector for a given tag"""
        path = []
        while tag and tag.name != '[document]':
            name = tag.name
            if tag.has_attr('class'):
                name += "." + ".".join(tag['class'])
            elif tag.has_attr('id'):
                name += f"#{tag['id']}"
            path.insert(0, name)
            tag = tag.parent
        return " > ".join(path)
    @staticmethod
    def find_tag_with_exact_text(soup, text):
        return soup.find(lambda tag: tag.string and tag.string.strip() == text.strip())
    
    @staticmethod
    def find_tag_with_exact_text_or_attribute(soup, text):
        text = text.strip()
        def match(tag):
            # Match against visible text
            if tag.string and tag.string.strip() == text:
                return True
            # Match against common attributes
            for attr in ['href', 'value', 'data-url', 'data-link']:
                if tag.has_attr(attr) and text in tag[attr].strip():
                    return True
            return False

        return soup.find(match)

    @staticmethod
    def update_schema_cache(domain, schema):
        cache_file = "job_structure_cache.json"
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        else:
            cache = {}

        cache[domain] = schema

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    @staticmethod
    def extract_consistent_selectors(html, jobs, domain):
        soup = BeautifulSoup(html, "html.parser")
        fields = ["title", "link", "location"]
        
        selectors = {field: [] for field in fields}

        for job in jobs:
            for field in fields:
                value = job.get(field)
                if not value:
                    continue
                tag = LastStartupScraper.find_tag_with_exact_text_or_attribute(soup, value)
                #print(tag)
                if tag:
                    selectors[field].append(LastStartupScraper.get_css_selector(tag))

        schema = {}
        #print(selectors['location'])
        for field, selector_list in selectors.items():
            if len(set(selector_list)) == 1:
                schema[field] = selector_list[0]
            else:
                print(f"❌ Inconsistent selectors for '{field}': {set(selector_list)}")
                return None

        # ✅ Save schema if trusted
        #print(f"✅ Trusted schema extracted: {schema}")
        LastStartupScraper.update_schema_cache(domain, schema)
        return schema
    
    @staticmethod
    def clean_selector(selector: str) -> str:
        # Remove Tailwind-style attribute values: .max-w-[100vw]
        selector = re.sub(r'\.\S*\[.*?\]', '', selector)

        # Remove Tailwind-style responsive prefixes: md:pt-24 → pt-24
        selector = re.sub(r'(\w+):([\w\-!]+)', r'\2', selector)

        # Remove bang-prefix utility classes: !rounded → rounded
        selector = re.sub(r'\.!([\w\-]+)', r'.\1', selector)

        # Remove leading html/body (not supported by lxml cssselect)
        selector = re.sub(r'^(html|body)\s*>\s*', '', selector)

        return selector.strip()
    import re
    @staticmethod
    def css_to_xpath(tailwind_selector: str) -> str:
        parts = tailwind_selector.split(" > ")
        xpath_parts = []

        for part in parts:
            tag = "div"  # default if tag is missing
            classes = []

            # Handle ID selector
            if "#" in part:
                tag, id_part = part.split("#", 1)
                id_xpath = f"{tag}[@id='{id_part}']"
                xpath_parts.append(id_xpath)
                continue

            # Extract tag and classes (e.g., div.class1.class2)
            match = re.match(r"(\w+)((?:\.\S+)+)?", part)
            if match:
                tag = match.group(1)
                class_str = match.group(2)
                if class_str:
                    class_names = class_str.strip(".").split(".")
                    class_conditions = " and ".join(
                        [f"contains(@class, '{cls}')" for cls in class_names]
                    )
                    xpath_parts.append(f"{tag}[{class_conditions}]")
                else:
                    xpath_parts.append(tag)
            else:
                xpath_parts.append(part)  # fallback

        return "/" + "/".join(xpath_parts)

    @staticmethod
    def extract_fields_from_html(html_content: str, selector_dict: dict):
        tree = html.fromstring(html_content)
        results = {}

        for key, css_selector in selector_dict.items():
            xpath = LastStartupScraper.css_to_xpath(css_selector)
            results[key] = tree.xpath(xpath)  # ⬅️ don't convert to text here

        return results

    @staticmethod
    def extract_jobs_with_precise_schema(html: str, schema: dict) -> list:
        html_content = html.encode("utf-8")
        results = LastStartupScraper.extract_fields_from_html(html, schema)

        titles = results.get("title", [])
        links = results.get("link", [])
        locations = results.get("location", [])
        
        jobs = []
        count = max(len(titles), len(links), len(locations) if locations else len(titles))

        for i in range(count):
            job = {
                "title": titles[i].text_content().strip() if i < len(titles) else "",
                "link": links[i].get("href", "") if i < len(links) else "",
                "location": locations[i].text_content().strip() if i < len(locations) else "",
            }
            jobs.append(job)

        return jobs


def extract_json_array_from_text(raw_text: str):
    """
    Extracts the first JSON array from raw LLM output, ignoring any commentary or markdown.
    """
    try:
        # Match the first valid JSON array in the string (greedy but non-overreaching)
        match = re.search(r"\[\s*{.*?}\s*\]", raw_text, re.DOTALL)
        if match:
            json_array_str = match.group(0)
            return json.loads(json_array_str)
        else:
            raise ValueError("❌ No JSON array found in LLM output.")
    except json.JSONDecodeError as e:
        raise ValueError(f"❌ Invalid JSON array: {str(e)}")
   
if __name__ == "__main__":
    base_url = "https://wsc-sports.com/careers/"  # Replace with the actual base URL
    scraper = LastStartupScraper(base_url)
    html1 = scraper.fetch_page(base_url)
    if not html1:
        print("Failed to fetch the HTML content of the base URL.")
        exit(1)
    cleaned_html = LastStartupScraper.clean_html_for_llm_no_spaces(html1)

    #llm_content = extract_json_array_from_text(LastStartupScraper.ask_llm_for_content(cleaned_html,base_url))
    llm_content = [{'title': 'Recruitment Marketing Specialist', 'link': '/career/recruitment-marketing-specialist/', 'location': 'ISRAEL', 'department': ''}, {'title': 'Employee Experience Specialist', 'link': '/career/employee-experience-specialist/', 'location': 'ISRAEL', 'department': ''}, {'title': 'Business Applications Implementer', 'link': '/career/business-applications-implementer/', 'location': '', 'department': ''}, {'title': 'GenAI Product Manager', 'link': '/career/genai-product-manager/', 'location': '', 'department': ''}, {'title': 'VP Marketing', 'link': '/career/vp-marketing/', 'location': '', 'department': ''}, {'title': 'DevOps Engineer', 'link': '/career/devops-engineer/', 'location': '', 'department': ''}, {'title': 'Product & R&D Ops Team Leader', 'link': '/career/product-rd-ops-team-leader/', 'location': '', 'department': ''}, {'title': 'QA Manual & Automation Engineer', 'link': '/career/qa-manual-automation-engineer/', 'location': '', 'department': ''}, {'title': 'New Verticals Support Specialist', 'link': '/career/new-verticals-support-specialist/', 'location': '', 'department': ''}, {'title': 'Customer Support Specialist', 'link': '/career/customer-support-specialist/', 'location': '', 'department': ''}, {'title': 'Frontend Tech Lead', 'link': '/career/frontend-tech-lead/', 'location': '', 'department': ''}, {'title': 'Backend Developer', 'link': '/career/backend-developer/', 'location': '', 'department': ''}, {'title': 'Director of Engineering', 'link': '/career/director-of-engineering/', 'location': '', 'department': ''}, {'title': 'Senior GenAI/NLP Algorithm Developer', 'link': '/career/senior-genai-nlp-algorithm-developer/', 'location': '', 'department': ''}, {'title': 'NLP Algorithm Developer', 'link': '/career/nlp-algorithm-developer/', 'location': '', 'department': ''}, {'title': 'Studio Product Manager', 'link': '/career/studio-product-manager/', 'location': '', 'department': ''}, {'title': 'NLP Team Leader', 'link': '/career/nlp-team-leader/', 'location': '', 'department': ''}, {'title': 'Technical Account Manager', 'link': '/career/technical-account-manager/', 'location': 'LONDON', 'department': ''}, {'title': 'Digital Strategy Manager', 'link': '/career/digital-strategy-manager/', 'location': '', 'department': ''}, {'title': 'Account Manager', 'link': '/career/account-manager/', 'location': 'NEW YORK', 'department': ''}, {'title': 'Client Solutions & Delivery Manager', 'link': '/career/client-solutions-delivery-manager/', 'location': '', 'department': ''}]
    #print(llm_content)
    structure = LastStartupScraper.extract_consistent_selectors(html1, llm_content,base_url)
    jobs = LastStartupScraper.extract_jobs_with_precise_schema(html1, structure)
    print(jobs)

    