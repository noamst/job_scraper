# 🧠 LastStartup Job Scraper

A robust, intelligent job scraping microservice that dynamically learns and caches job listing structures from startup career pages — even those styled with Tailwind CSS. Built for scalability, automation, and precision.

## 🚀 Features
- 
- 🔎 **Company Lookup**: Matches company names to their careers URL from a base index.
- 🧱 **Schema Inference**:
  - Converts deep Tailwind-style CSS selectors into XPath.
  - Uses `ask_llm_for_content()` + `extract_consistent_selectors()` to infer job card structure dynamically.
- 🧠 **LLM-Fallback**: If no schema exists, uses a language model to understand the HTML and derive a reusable structure.
- 💾 **Schema Cache**: Saves learned schemas per domain to a persistent `job_structure_cache.json`.
- ⚙️ **MCP Tool Integration**: Exposed as an MCP tool via `@mcp.tool()` for plug-and-play use in autonomous agents or pipelines.

---

## 🧩 Project Structure

```
├── jobs_scraper/
│ ├── laststartupScraping.py # Core logic: scraping, schema inference, XPath logic
│ ├── job_structure_cache.json # Persistent schema storage per domain
│ └── ...
├── jobs_scraper.py # Entrypoint with @mcp.tool(get_jobs)
└── README.md

```

## Claude Desktop Integration 
To run this job scraper as a tool inside Claude for Desktop, follow these steps:

Download and install the Claude Desktop app for your system.

Inside your Claude app configuration folder, add or update the following section in your claude_desktop_config.json file:
```
"jobs_scraper": {
    "command": "/Users/noamstopler/.local/bin/uv",
    "args": [
        "--directory",
        "/Users/noamstopler/Desktop/myProjects/RelevantJobsMCPServer/jobs_scraper",
        "run",
        "jobs_scraper.py"
    ],
    "env": {
        "GROQ_API_KEY": "your_api_key"
    }
}
```

Once configured, restart Claude Desktop. Your jobs_scraper tool should now be available as an integrated tool Claude can call via @mcp.tool().


⚠️ Disclaimer: Early Version
    This is a very early-stage prototype of the job scraper.

    🧪 It has been tested on only a small number of career pages so far.

    📄 The structure inference logic works best on sites with well-defined HTML and consistent Tailwind-style class patterns.

    💥 Some sites may still fail due to dynamic content, non-standard layouts, or aggressive bot protection.

    Expect bugs, edge cases, and limitations

🧱 Token Limitations with Free API Keys
    Some career pages are very large or contain deeply nested HTML, which makes them difficult to process using free-tier LLM API keys.

    🔐 Free Groq/OpenAI API keys typically have token limits (e.g. 4K–8K tokens).

    🧠 When using ask_llm_for_content() to analyze such pages, the model may truncate input or fail to respond fully.

🗂 Data Source
    This scraper currently pulls its list of companies from:

    🔗 https://www.lastartup.co.il/funding

    The site lists Israeli startups and companies that recently raised funding.

    Each company entry typically includes a name and a link to their careers page, which this tool uses as the starting point for scraping job listings.

    If the company has no accessible careers page, it is skipped.

    📌 Note: Support is currently limited to companies listed on this source. Future versions may expand to support additional directories or manual entry.

🛠 Limitations & Roadmap
    🔍 Careers Page Discovery (Current vs. Planned)
    In this prototype version, the scraper naively assumes that the careers page is located at:
    https://<company-domain>/careers
    This approach works for many startups, but:

    ❌ Fails when companies use non-standard paths (e.g. /jobs, /join-us, /work-with-us, etc.)

🧠 Planned Improvement
    In future versions, we plan to implement:

    📄 Sitemap Parsing with LLMs:

        Automatically detect and analyze the site's sitemap.xml

        Use a language model to infer the most likely path to the careers or jobs page

        Support fallback to subdomain-based careers pages (e.g. jobs.company.com)

        This will significantly improve accuracy and robustness when locating hiring information — especially for larger or more modern websites.
