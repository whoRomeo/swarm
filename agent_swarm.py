#!/usr/bin/env python3
"""
Agent Swarm Orchestrator v1.0
Runs the autonomous earnings engine.
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('swarm.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AgentSwarm:
    def __init__(self, config_path='config.json'):
        self.config = self.load_config(config_path)
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        self.backlog_file = self.data_dir / 'backlog.json'
        self.operations_file = self.data_dir / 'operations.json'
        self.results_file = self.data_dir / 'results.json'
        
    def load_config(self, path):
        if Path(path).exists():
            with open(path) as f:
                return json.load(f)
        return {
            "github_token": os.environ.get("GITHUB_TOKEN", ""),
            "youtube_api_key": os.environ.get("YOUTUBE_API_KEY", ""),
            "gumroad_api_token": os.environ.get("GUMROAD_TOKEN", ""),
            "target_niche": os.environ.get("TARGET_NICHE", "technology"),
            "min_profit_threshold": 100,
            "swarm_interval_hours": 24
        }
    
    def save_state(self):
        """Save current state to disk"""
        state = {
            "last_run": datetime.now().isoformat(),
            "config": self.config
        }
        with open('state.json', 'w') as f:
            json.dump(state, f, indent=2)
    
    def run_research_agent(self):
        """Agent 1: Research & Ideation - scans GitHub trending, Reddit, web for profitable ideas"""
        logger.info("=" * 60)
        logger.info("AGENT 1: RESEARCH & IDEATION")
        logger.info("=" * 60)
        
        ideas = []
        
        # GitHub Trending Scanner
        logger.info("Scanning GitHub trending repos...")
        try:
            import requests
            headers = {}
            if self.config.get('github_token'):
                headers['Authorization'] = f'token {self.config["github_token"]}'
            
            # Get today's trending (simulated - GitHub API doesn't have official trending endpoint)
            # We'll use search to find popular repos by stars gained recently
            repos = self._scan_github_trending(headers)
            ideas.extend(repos)
            logger.info(f"Found {len(repos)} trending GitHub projects")
        except Exception as e:
            logger.error(f"GitHub scan failed: {e}")
        
        # Web trend search
        logger.info("Searching for trending topics...")
        try:
            web_ideas = self._search_web_trends()
            ideas.extend(web_ideas)
            logger.info(f"Found {len(web_ideas)} web trends")
        except Exception as e:
            logger.error(f"Web search failed: {e}")
        
        # Save to backlog
        with open(self.backlog_file, 'w') as f:
            json.dump(ideas, f, indent=2)
        
        logger.info(f"Total ideas generated: {len(ideas)}")
        logger.info(f"Backlog saved to {self.backlog_file}")
        
        return ideas
    
    def _scan_github_trending(self, headers):
        """Scan GitHub for trending repositories"""
        import requests
        import re
        
        trending = []
        
        # Search for popular repos in tech/automation/AI niches
        queries = [
            ("stars:>1000 pushed:>2024-01-01 automation OR ai OR bot", "automation_ai"),
            ("stars:>500 pushed:>2024-06-01 python OR javascript", "programming_tools"),
            ("stars:>100 pushed:>2024-09-01", "recent_popular"),
        ]
        
        for query, category in queries:
            try:
                url = "https://api.github.com/search/repositories"
                params = {
                    'q': query,
                    'sort': 'stars',
                    'order': 'desc',
                    'per_page': 10
                }
                resp = requests.get(url, headers=headers, params=params, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get('items', []):
                        trending.append({
                            "type": "github_repo",
                            "category": category,
                            "name": item['name'],
                            "full_name": item['full_name'],
                            "url": item['html_url'],
                            "description": item.get('description', ''),
                            "stars": item['stargazers_count'],
                            "language": item.get('language', 'Unknown'),
                            "created_at": item['created_at'],
                            "profit_potential": self._assess_profit_potential(item),
                            "product_idea": self._generate_product_idea(item),
                            "content_idea": self._generate_content_idea(item),
                            "timestamp": datetime.now().isoformat()
                        })
            except Exception as e:
                logger.warning(f"Query '{query}' failed: {e}")
        
        return trending
    
    def _assess_profit_potential(self, repo):
        """Assess if a repo has profit potential"""
        score = 0
        reasons = []
        
        stars = repo.get('stargazers_count', 0)
        desc = (repo.get('description') or '').lower()
        
        if stars > 1000:
            score += 3
            reasons.append(f"High stars ({stars})")
        elif stars > 100:
            score += 2
            reasons.append(f"Growing ({stars} stars)")
        
        # Check for monetization signals
        monetization_keywords = ['commercial', 'enterprise', 'pro', 'premium', 'paid', 'pricing']
        if any(kw in desc for kw in monetization_keywords):
            score += 2
            reasons.append("Has commercial signals")
        
        # Check for problem-solving (people pay for solutions)
        problem_keywords = ['automation', 'tool', 'platform', 'dashboard', 'analytics', 
                          'monitoring', 'pipeline', 'workflow', 'cms', 'builder']
        if any(kw in desc for kw in problem_keywords):
            score += 2
            reasons.append("Solves concrete problem")
        
        # Recent activity
        if repo.get('pushed_at', '') > '2024-01-01':
            score += 1
            reasons.append("Actively maintained")
        
        return {
            "score": min(score, 10),
            "reasons": reasons,
            "verdict": "HIGH" if score >= 6 else "MEDIUM" if score >= 4 else "LOW"
        }
    
    def _generate_product_idea(self, repo):
        """Generate a digital product idea from a repo"""
        name = repo.get('name', 'project')
        desc = repo.get('description') or ''
        lang = repo.get('language', 'Python')
        
        products = []
        
        # Template/boilerplate product
        products.append({
            "type": "template",
            "title": f"{name} - Production-Ready Template",
            "description": f"A polished, documented, production-ready version of {name} with best practices, tests, and deployment config included.",
            "price_suggestion": "$29-99",
            "platform": "Gumroad",
            "effort_estimate": "4-8 hours"
        })
        
        # Tutorial/ebook product
        products.append({
            "type": "tutorial",
            "title": f"How to Build {name}: Complete Guide",
            "description": f"A step-by-step video course or ebook teaching how to use and extend {name} for real-world projects.",
            "price_suggestion": "$19-49",
            "platform": "Gumroad + YouTube",
            "effort_estimate": "6-12 hours"
        })
        
        return products
    
    def _generate_content_idea(self, repo):
        """Generate a YouTube content idea from a repo"""
        name = repo.get('name', 'project')
        desc = repo.get('description') or ''
        stars = repo.get('stargazers_count', 0)
        
        contents = []
        
        if stars > 100:
            contents.append({
                "type": "video",
                "title": f"This {name} Project is INSANE (GitHub Trending)",
                "description": f"Showcasing {name} - {desc[:100]}. This project has {stars} stars and is trending on GitHub. Let me show you why it's worth your attention.",
                "format": "showcase/review",
                "duration_estimate": "5-8 minutes",
                "monetization": ["adsense", "affiliate"]
            })
            
            contents.append({
                "type": "video",
                "title": f"Build a Business with {name} (Step by Step)",
                "description": f"How to use {name} to build something profitable. Complete walkthrough from setup to deployment.",
                "format": "tutorial",
                "duration_estimate": "10-15 minutes",
                "monetization": ["adsense", "digital_product"]
            })
        
        return contents
    
    def _search_web_trends(self):
        """Search the web for trending topics and ideas"""
        # This would use web_search tool - for now, generate from known patterns
        trends = []
        
        # Current hot topics (would be dynamically fetched in production)
        hot_topics = [
            {
                "type": "web_trend",
                "category": "ai_agents",
                "trend": "AI agents for automation",
                "search_volume": "HIGH",
                "profit_angle": "People want to build AI agents but don't know how - sell templates, courses, consultations",
                "content_ideas": [
                    "How to Build Your First AI Agent in 2024",
                    "5 AI Agent Projects You Can Sell Today",
                    "AI Agent Framework Comparison 2024"
                ],
                "product_ideas": [
                    "AI Agent Template Pack ($49)",
                    "AI Agent Starter Course ($99)",
                    "Custom AI Agent Building Service"
                ]
            },
            {
                "type": "web_trend", 
                "category": "automation",
                "trend": "No-code automation tools",
                "search_volume": "HIGH",
                "profit_angle": "Business owners want to automate without coding - sell automation setups, templates, consulting",
                "content_ideas": [
                    "Automate Your Entire Business with No Code",
                    "5 Automation Tools That Save 10 Hours/Week",
                    "Build an Automated Lead Generation System"
                ],
                "product_ideas": [
                    "Automation Template Library ($29/month)",
                    "Business Automation Audit ($99 one-time)",
                    "Pre-built Automation Workflows"
                ]
            },
            {
                "type": "web_trend",
                "category": "developer_tools", 
                "trend": "Developer productivity tools",
                "search_volume": "MEDIUM",
                "profit_angle": "Developers spend money on tools that make them faster - sell IDE extensions, CLI tools, boilerplates",
                "content_ideas": [
                    "Tools That Make Me 10x Faster as a Developer",
                    "My Entire Developer Setup 2024",
                    "Build Your Own Developer Tools (and Sell Them)"
                ],
                "product_ideas": [
                    "Developer Boilerplate Bundle ($79)",
                    "CLI Tool Collection ($29)",
                    "IDE Extension Template"
                ]
            }
        ]
        
        for trend in hot_topics:
            trend['timestamp'] = datetime.now().isoformat()
            trends.append(trend)
        
        logger.info(f"Web trends found: {len(trends)}")
        return trends
    
    def run_content_agent(self, ideas=None):
        """Agent 2: Content Production - creates scripts, voiceovers, thumbnails"""
        logger.info("=" * 60)
        logger.info("AGENT 2: CONTENT PRODUCTION")
        logger.info("=" * 60)
        
        if ideas is None:
            if self.backlog_file.exists():
                with open(self.backlog_file) as f:
                    ideas = json.load(f)
            else:
                logger.warning("No backlog found, run research first")
                return []
        
        productions = []
        
        for idea in ideas[:3]:  # Process top 3 ideas
            logger.info(f"Processing idea: {idea.get('name', idea.get('trend', 'unknown'))}")
            
            try:
                content = self._produce_content(idea)
                productions.extend(content)
                logger.info(f"Created {len(content)} content pieces")
            except Exception as e:
                logger.error(f"Content production failed for {idea}: {e}")
        
        # Save productions
        with open(self.operations_file, 'w') as f:
            json.dump(productions, f, indent=2)
        
        logger.info(f"Total productions: {len(productions)}")
        return productions
    
    def _produce_content(self, idea):
        """Produce content from an idea: scripts + voiceover + thumbnail + video"""
        productions = []

        # Generate scripts
        scripts = self._generate_scripts(idea)

        for script in scripts:
            # Generate voiceover filename
            voiceover_file = f"audio/{script['id']}_voiceover.mp3"

            # Generate thumbnail brief
            thumbnail_brief = self._generate_thumbnail_brief(script)

            # Generate video (calls video_generator module)
            video_result = self._generate_video(script)

            production = {
                **script,
                "voiceover_file": voiceover_file,
                "thumbnail_brief": thumbnail_brief,
                **video_result,
                "status": video_result.get('status', 'script_ready'),
                "created_at": datetime.now().isoformat()
            }
            productions.append(production)

            logger.info(f"  - Script: {script['title']}")
            logger.info(f"  - Voiceover: {voiceover_file}")
            logger.info(f"  - Thumbnail: {thumbnail_brief['prompt']}")
            logger.info(f"  - Video: {video_result.get('status', 'pending')} — {video_result.get('video_path', video_result.get('video_error', 'no output'))}")

        return productions
    
    def _generate_scripts(self, idea):
        """Generate video scripts for an idea"""
        scripts = []
        
        if idea.get('type') == 'github_repo':
            name = idea.get('name', 'Project')
            desc = idea.get('description', '') or 'A fascinating new project'
            stars = idea.get('stars', 0)
            url = idea.get('url', '')
            
            # Script 1: Showcase/Review
            scripts.append({
                "id": f"{name}_showcase",
                "title": f"This {name} Project is INSANE",
                "type": "showcase",
                "duration_minutes": 5,
                "script": f"""
[COLD OPEN - 0:00-0:15]
"What if I told you there's a project on GitHub right now with {stars} stars that could change how you work?"

[INTRO - 0:15-0:45]
"Hey everyone, today we're looking at {name}. This project has been making waves on GitHub and I think you need to know about it."

[BODY - 0:45-4:00]
"So what exactly is {name}? {desc}

Here's why it matters:
1. [Point 1 - unique value proposition]
2. [Point 2 - how it solves a real problem]  
3. [Point 3 - who it's for]

Let me show you how it works..."

[PROS & CONS - 4:00-4:45]
"Pros: [list 3 pros]
Cons: [list 2 cons]"

[CALL TO ACTION - 4:45-5:00]
"If you found this useful, hit subscribe. And check the description for links to try {name} yourself."

[OUTRO]
"Thanks for watching!"
                """.strip(),
                "hooks": [
                    f"{stars} stars and growing",
                    "Could change how you work",
                    "You need to see this"
                ],
                "tags": ["github", "trending", name, "tech", "review"],
                "description": f"Exploring {name} - a trending GitHub project with {stars} stars. {desc}",
                "source_url": url
            })
            
            # Script 2: Tutorial/How-to
            scripts.append({
                "id": f"{name}_tutorial",
                "title": f"How to Use {name} (Complete Tutorial)",
                "type": "tutorial",
                "duration_minutes": 10,
                "script": f"""
[INTRO - 0:00-0:30]
"Want to learn how to use {name}? In this video, I'll walk you through everything from installation to your first project."

[PREREQUISITES - 0:30-1:00]
"Before we start, you'll need: [list prerequisites]"

[INSTALLATION - 1:00-3:00]
"Step 1: Install {name}..."
"Step 2: Configure..."
"Step 3: Verify installation..."

[BASIC USAGE - 3:00-7:00]
"Let's build something real with {name}..."
[Walk through a practical example]

[ADVANCED TIPS - 7:00-9:00]
"Once you've got the basics, here are pro tips..."
[3-4 advanced tips]

[OUTRO - 9:00-10:00]
"If this helped, hit like and subscribe for more. Check the description for the repo link and any resources mentioned."
                """.strip(),
                "hooks": [
                    "Complete tutorial",
                    "From zero to working",
                    "Save hours of trial and error"
                ],
                "tags": ["tutorial", "how-to", name, "beginner", "guide"],
                "description": f"Complete tutorial for {name}. Learn how to install, configure, and use {name} for your projects.",
                "source_url": url
            })
            
        elif idea.get('type') == 'web_trend':
            trend = idea.get('trend', 'Trending Topic')
            
            scripts.append({
                "id": f"{trend.replace(' ', '_')}_explainer",
                "title": f"What is {trend}? (And Why You Should Care)",
                "type": "explainer",
                "duration_minutes": 6,
                "script": f"""
[HOOK - 0:00-0:20]
"Everyone's talking about {trend} but most people don't actually understand what it is or why it matters."

[EXPLANATION - 0:20-2:00]
"Here's the simple explanation: {trend} is..."

[WHY IT MATTERS - 2:00-3:30]
"Why should you care? Three reasons:
1. [Reason 1]
2. [Reason 2]
3. [Reason 3]"

[HOW TO GET STARTED - 3:30-5:00]
"If you want to get into {trend}, here's how to start..."
[3 actionable steps]

[CALL TO ACTION - 5:00-6:00]
"Drop a comment if you have questions about {trend}. Subscribe for more explainers. Check the description for resources."
                """.strip(),
                "hooks": [
                    "Everyone's talking about it",
                    "Most people don't understand it",
                    "Here's what you need to know"
                ],
                "tags": ["explainer", trend.lower(), "trend", "what-is", "guide"],
                "description": f"Complete explainer on {trend} - what it is, why it matters, and how to get started.",
                "source_url": ""
            })
        
        # Add metadata
        for script in scripts:
            script['voiceover_text'] = script['script']
            script['word_count'] = len(script['script'].split())
            script['estimated_duration_minutes'] = script['word_count'] / 150  # ~150 words per minute
        
        return scripts
    
    def _generate_thumbnail_brief(self, script):
        """Generate thumbnail image brief for AI image generation"""
        title = script['title']
        content_type = script['type']
        
        # Extract key visual elements from title
        visual_elements = []
        if 'GitHub' in title or 'Project' in title:
            visual_elements.append("GitHub logo, code screenshot, computer screen")
        if 'Tutorial' in title or 'How to' in title:
            visual_elements.append("Step-by-step graphics, checkmarks, progress bar")
        if 'Business' in title or 'Profit' in title:
            visual_elements.append("Money graphics, growth chart, dollar signs")
        if 'AI' in title or 'Agent' in title:
            visual_elements.append("Robot/AI graphics, neural network, futuristic")
        
        if not visual_elements:
            visual_elements.append("Clean modern design, bold text, high contrast")
        
        return {
            "prompt": f"YouTube thumbnail, {title}, {', '.join(visual_elements)}, vibrant colors, bold typography, high contrast, 1280x720, professional quality",
            "dimensions": "1280x720",
            "text_overlay": title[:50] + ("..." if len(title) > 50 else ""),
            "style": "modern_tech" if any(kw in title.lower() for kw in ['tech', 'github', 'ai', 'code', 'developer']) else "bold_minimal"
        }
    
    def run_publishing_agent(self):
        """Agent 3: Publishing - uploads to YouTube, publishes website"""
        logger.info("=" * 60)
        logger.info("AGENT 3: PUBLISHING")
        logger.info("=" * 60)
        
        if not self.operations_file.exists():
            logger.warning("No operations found, run content agent first")
            return
        
        with open(self.operations_file) as f:
            operations = json.load(f)
        
        published = []
        
        for op in operations:
            if op.get('status') == 'script_ready':
                logger.info(f"Publishing: {op['title']}")
                
                # YouTube upload
                youtube_result = self._upload_to_youtube(op)
                
                # Website publish
                website_result = self._publish_to_website(op)
                
                published.append({
                    **op,
                    "youtube": youtube_result,
                    "website": website_result,
                    "status": "published",
                    "published_at": datetime.now().isoformat()
                })
                
                logger.info(f"  YouTube: {youtube_result.get('status', 'pending')}")
                logger.info(f"  Website: {website_result.get('status', 'pending')}")
        
        # Save results
        with open(self.results_file, 'w') as f:
            json.dump(published, f, indent=2)
        
        logger.info(f"Published {len(published)} pieces")
        return published
    
    def _upload_to_youtube(self, content):
        """Upload video to YouTube via OAuth 2.0 (real API call).

        Requires: YOUTUBE_REFRESH_TOKEN, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET
        as GitHub repository secrets. Uses google-api-python-client.

        If video file doesn't exist yet, returns 'ready_to_generate' status.
        """
        import sys
        # Add parent dir to path so we can import youtube_oauth
        sys.path.insert(0, str(Path(__file__).parent))
        from youtube_oauth import upload_video, get_service

        video_file = Path('videos') / f"{content['id']}.mp4"
        thumbnail_file = Path('thumbnails') / f"{content['id']}.jpg"

        result = {
            'status': 'pending_upload',
            'video_id': None,
            'url': None,
            'upload_timestamp': None,
            'video_file': str(video_file) if video_file.exists() else None,
            'thumbnail_file': str(thumbnail_file) if thumbnail_file.exists() else None
        }

        # Check if video file exists
        if not video_file.exists():
            logger.info(f"  Video file not ready: {video_file} — needs generation first")
            result['status'] = 'ready_to_generate'
            return result

        # Try OAuth-authenticated upload
        service = get_service()
        if not service:
            logger.warning("  YouTube OAuth not configured — check YOUTUBE_REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET secrets")
            result['status'] = 'oauth_not_configured'
            return result

        logger.info(f"  Uploading to YouTube: {content['title']}")

        tags = content.get('tags', ['swarm', 'autonomous', 'ai'])
        description = content.get('description', '') or f"Auto-generated content from Autonomous Earnings Swarm.\n\n{content.get('script', '')[:500]}"

        upload_result = upload_video(
            file_path=str(video_file),
            title=content['title'][:100],
            description=description,
            tags=tags,
            category_id='22',  # People & Blogs
            privacy_status='unlisted',
            thumbnail_path=str(thumbnail_file) if thumbnail_file.exists() else None
        )

        result.update(upload_result)
        result['status'] = upload_result['status']
        result['video_id'] = upload_result.get('video_id')
        result['url'] = upload_result.get('url')

        if upload_result['status'] == 'published':
            logger.info(f"  Uploaded: {upload_result['url']}")
        else:
            logger.warning(f"  Upload failed: {upload_result.get('error', 'unknown')}")

        return result
    
    def _publish_to_website(self, content):
        """Publish content to GitHub Pages website"""
        # Generate markdown post
        md_content = self._generate_markdown_post(content)
        
        # Save to posts directory
        posts_dir = Path('website_content/posts')
        posts_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{content['id']}.md"
        filepath = posts_dir / filename
        
        with open(filepath, 'w') as f:
            f.write(md_content)
        
        logger.info(f"  Saved post: {filepath}")
        
        # In production, this commits and pushes to GitHub Pages
        result = {
            "status": "ready_to_push",
            "filepath": str(filepath),
            "commit_needed": True
        }
        
        return result
    
    def _generate_markdown_post(self, content):
        """Generate a markdown blog post from content"""
        title = content['title']
        desc = content.get('description', '')
        script = content.get('script', '')
        tags = content.get('tags', [])
        source_url = content.get('source_url', '')
        
        # Extract key points from script
        lines = script.split('\n')
        key_points = []
        for line in lines:
            line = line.strip()
            if line.startswith('[') and ']' in line:
                continue  # Skip section headers
            if line.startswith('- ') or line.startswith('1. ') or line.startswith('2. ') or line.startswith('3. '):
                key_points.append(line.strip('- 0123456789. '))
        
        md = f"""---
title: "{title}"
date: {datetime.now().strftime('%Y-%m-%d')}
tags: {json.dumps(tags)}
type: {content['type']}
source: {content.get('source_url', 'N/A')}
---

# {title}

{desc}

## Key Points

"""
        for point in key_points[:5]:
            md += f"- {point}\n"
        
        md += f"""

## Full Script

```
{script}
```

## Resources

"""
        if source_url:
            md += f"- [Original Source]({source_url})\n"
        
        md += f"\n---\n*Published by Autonomous Earnings Swarm | {datetime.now().strftime('%Y-%m-%d')}*"
        
        return md
    
    def run_product_agent(self, ideas=None):
        """Agent 4: Product Creation - creates digital products"""
        logger.info("=" * 60)
        logger.info("AGENT 4: PRODUCT CREATION")
        logger.info("=" * 60)
        
        if ideas is None:
            if self.backlog_file.exists():
                with open(self.backlog_file) as f:
                    ideas = json.load(f)
            else:
                logger.warning("No backlog found")
                return []
        
        products = []
        
        for idea in ideas[:2]:  # Create products from top 2 ideas
            logger.info(f"Creating product from: {idea.get('name', idea.get('trend', 'unknown'))}")
            
            try:
                product = self._create_product(idea)
                products.append(product)
                logger.info(f"  Product: {product['title']}")
                logger.info(f"  Platform: {product['platform']}")
            except Exception as e:
                logger.error(f"Product creation failed: {e}")
        
        # Save products
        products_file = self.data_dir / 'products.json'
        with open(products_file, 'w') as f:
            json.dump(products, f, indent=2)
        
        logger.info(f"Created {len(products)} products")
        return products
    
    def _create_product(self, idea):
        """Create a digital product from an idea"""
        if idea.get('type') == 'github_repo':
            name = idea.get('name', 'Project')
            product_ideas = idea.get('product_idea', [])
            
            if product_ideas:
                product = {
                    **product_ideas[0],
                    "idea_source": idea,
                    "status": "listed",
                    "listing_url": None,
                    "created_at": datetime.now().isoformat()
                }
            else:
                product = {
                    "type": "template",
                    "title": f"{name} Starter Kit",
                    "description": f"Get started with {name} quickly with this complete starter kit including setup guide, best practices, and example projects.",
                    "price_suggestion": "$29",
                    "platform": "Gumroad",
                    "status": "ready_to_list",
                    "idea_source": idea,
                    "created_at": datetime.now().isoformat()
                }
        else:
            product = {
                "type": "guide",
                "title": f"The Complete Guide to {idea.get('trend', 'Topic')}",
                "description": f"Everything you need to know about {idea.get('trend', 'topic')} - from beginner to advanced.",
                "price_suggestion": "$19",
                "platform": "Gumroad",
                "status": "ready_to_list",
                "idea_source": idea,
                "created_at": datetime.now().isoformat()
            }
        
        # Generate product content files
        products_dir = Path('products')
        products_dir.mkdir(exist_ok=True)
        
        product_dir = products_dir / product['id'] if 'id' in product else products_dir / f"product_{len(list(products_dir.iterdir()))+1}"
        product_dir.mkdir(exist_ok=True)
        
        # Create README
        readme = f"""# {product['title']}

{product['description']}

## What's Included

- Complete documentation
- Example usage
- Best practices
- Troubleshooting guide

## Price: {product['price_suggestion']}

## License

Personal use license. For commercial licensing, contact us.
"""
        
        with open(product_dir / 'README.md', 'w') as f:
            f.write(readme)
        
        product['files_directory'] = str(product_dir)
        
        return product
    
    def run_finance_agent(self):
        """Agent 5: Finance Tracking - monitors revenue, alerts on thresholds"""
        logger.info("=" * 60)
        logger.info("AGENT 5: FINANCE TRACKING")
        logger.info("=" * 60)
        
        finance_dir = Path('finance')
        finance_dir.mkdir(exist_ok=True)
        
        # Load or create revenue tracker
        tracker_file = finance_dir / 'revenue_tracker.json'
        if tracker_file.exists():
            with open(tracker_file) as f:
                tracker = json.load(f)
        else:
            tracker = {
                "youtube_adsense": {"earnings": 0, "views": 0, "last_updated": None},
                "gumroad_sales": {"earnings": 0, "sales_count": 0, "last_updated": None},
                "affiliate_commissions": {"earnings": 0, "clicks": 0, "conversions": 0, "last_updated": None},
                "total_earnings": 0,
                "goal": 10000,
                "monthly_breakdown": {}
            }
        
        # Simulate revenue tracking (in production, this fetches from APIs)
        logger.info("Tracking revenue across platforms...")
        
        # YouTube AdSense
        logger.info(f"  YouTube AdSense: ${tracker['youtube_adsense']['earnings']:.2f} ({tracker['youtube_adsense']['views']} views)")
        
        # Gumroad
        logger.info(f"  Gumroad Sales: ${tracker['gumroad_sales']['earnings']:.2f} ({tracker['gumroad_sales']['sales_count']} sales)")
        
        # Affiliate
        logger.info(f"  Affiliate: ${tracker['affiliate_commissions']['earnings']:.2f} ({tracker['affiliate_commissions']['conversions']} conversions)")
        
        total = (tracker['youtube_adsense']['earnings'] + 
                tracker['gumroad_sales']['earnings'] + 
                tracker['affiliate_commissions']['earnings'])
        
        tracker['total_earnings'] = total
        tracker['last_updated'] = datetime.now().isoformat()
        
        # Check threshold
        threshold = self.config.get('min_profit_threshold', 100)
        if total >= threshold:
            logger.warning(f"*** THRESHOLD REACHED: ${total:.2f} >= ${threshold:.2f} ***")
            logger.warning("Initiating payout process...")
            self._initiate_payout(tracker)
        else:
            remaining = threshold - total
            logger.info(f"Threshold check: ${total:.2f} / ${threshold:.2f} (need ${remaining:.2f} more)")
        
        # Save tracker
        with open(tracker_file, 'w') as f:
            json.dump(tracker, f, indent=2)
        
        logger.info(f"Total earnings tracked: ${total:.2f}")
        logger.info(f"Goal: ${tracker['goal']:,}")
        logger.info(f"Progress: {total/tracker['goal']*100:.1f}%")
        
        return tracker
    
    def _initiate_payout(self, tracker):
        """Initiate payout to bank account (simulated)"""
        logger.info("=" * 60)
        logger.info("PAYOUT INITIATION")
        logger.info("=" * 60)
        
        payout_info = {
            "amount": tracker['total_earnings'],
            "destination": "piyush16.shandilya@okaxis (UPI)",
            "platform": "Gumroad/PayPal (pending verification)",
            "status": "pending_manual_verification",
            "timestamp": datetime.now().isoformat(),
            "note": "Automatic payout requires: 1) Platform account verification, 2) Payment method confirmation, 3) Minimum threshold met"
        }
        
        payout_file = Path('finance/payout_request.json')
        with open(payout_file, 'w') as f:
            json.dump(payout_info, f, indent=2)
        
        logger.info(f"Payout request saved: {payout_file}")
        logger.info(f"Amount: ${payout_info['amount']:.2f}")
        logger.info(f"Destination: {payout_info['destination']}")
        
        # In production, this would call the payment platform's API
        # But verification and manual steps are required by all platforms
    
    def run_swarm(self, agents=None):
        """Run the complete agent swarm"""
        logger.info("=" * 60)
        logger.info("AUTONOMOUS EARNINGS SWARM - STARTING")
        logger.info("=" * 60)
        logger.info(f"Started at: {datetime.now().isoformat()}")
        
        if agents is None:
            agents = ['research', 'content', 'publishing', 'product', 'finance']
        
        results = {}
        
        if 'research' in agents:
            results['research'] = self.run_research_agent()
        
        if 'content' in agents and results.get('research'):
            results['content'] = self.run_content_agent(results['research'])
        
        if 'product' in agents and results.get('research'):
            results['product'] = self.run_product_agent(results['research'])
        
        if 'publishing' in agents:
            results['publishing'] = self.run_publishing_agent()
        
        if 'finance' in agents:
            results['finance'] = self.run_finance_agent()
        
        self.save_state()
        
        logger.info("=" * 60)
        logger.info("SWARM RUN COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Finished at: {datetime.now().isoformat()}")
        
        return results


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Autonomous Earnings Agent Swarm')
    parser.add_argument('--agents', nargs='+', 
                       choices=['research', 'content', 'publishing', 'product', 'finance', 'all'],
                       default=['all'],
                       help='Which agents to run')
    parser.add_argument('--config', default='config.json', help='Config file path')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    
    args = parser.parse_args()
    
    swarm = AgentSwarm(config_path=args.config)
    
    if args.agents == ['all']:
        agents = ['research', 'content', 'publishing', 'product', 'finance']
    else:
        agents = args.agents
    
    results = swarm.run_swarm(agents)
    
    # Print summary
    print("\n" + "=" * 60)
    print("SWARM RUN SUMMARY")
    print("=" * 60)
    
    for agent_name, result in results.items():
        if isinstance(result, list):
            print(f"{agent_name.capitalize()}: {len(result)} items processed")
        elif isinstance(result, dict):
            if 'total_earnings' in result:
                print(f"{agent_name.capitalize()}: ${result['total_earnings']:.2f} total earnings")
            else:
                print(f"{agent_name.capitalize()}: {len(result)} keys")
        else:
            print(f"{agent_name.capitalize()}: completed")
    
    print("=" * 60)
    print(f"Log file: swarm.log")
    print(f"Data directory: data/")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
