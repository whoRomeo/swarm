# Autonomous Earnings Swarm

Self-running agent system that researches opportunities, creates content and products, publishes them, and tracks revenue.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Agent 1:       │────▶│  Agent 2:       │────▶│  Agent 3:       │
│  Research &     │     │  Content        │     │  Publishing     │
│  Ideation       │     │  Production     │     │  (YouTube + Web)│
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Agent 5:       │◀────│  Agent 4:       │◀────│  GitHub         │
│  Finance &      │     │  Product        │     │  Connector      │
│  Payout         │     │  Creation       │     │  (Billions of   │
└─────────────────┘     └─────────────────┘     │   ideas)        │
                                                  └─────────────────┘
```

## Agents

| Agent | Responsibility | Output |
|-------|---------------|--------|
| 1. Research & Ideation | Scans GitHub trending, web trends, identifies profitable opportunities | Backlog of ideas with profit potential scores |
| 2. Content Production | Creates video scripts, voiceover text, thumbnail briefs from ideas | Ready-to-produce content packages |
| 3. Publishing | Uploads to YouTube, publishes to GitHub Pages website | Live content with monetization links |
| 4. Product Creation | Builds digital products (templates, guides, code kits) from ideas | Listed products on Gumroad |
| 5. Finance & Payout | Tracks all revenue, monitors thresholds, initiates payouts | Bank deposits when profitable |

## Setup

1. Clone this repo
2. Create `config.json` with your API keys (optional for demo mode)
3. Run: `python agent_swarm.py --agents all`

## Configuration

See `config.json` for all settings. Required for full automation:
- GitHub token (optional, for enhanced scanning)
- YouTube API key (for auto-upload)
- Gumroad token (for product listing)

## Data Flow

```
GitHub Trending + Web Trends
           │
           ▼
    ┌──────────┐
    │ Research │  ──▶  ideas.json (backlog)
    └──────────┘
           │
           ▼
   ┌────────────┐
   │  Content   │  ──▶  operations.json (productions)
   └────────────┘
           │
           ▼
   ┌────────────┐
   │ Publishing │  ──▶  results.json (published content)
   └────────────┘
           │
           ▼
   ┌────────────┐
   │  Products  │  ──▶  products.json (created products)
   └────────────┘
           │
           ▼
   ┌────────────┐
   │  Finance   │  ──▶  revenue_tracker.json + payout requests
   └────────────┘
```

## Running

```bash
# Run all agents once
python agent_swarm.py --agents all

# Run specific agents
python agent_swarm.py --agents research content

# Run continuously (with interval)
# (requires cron or scheduled task setup)
```

## Project Structure

```
swarm/
├── agent_swarm.py      # Main orchestrator
├── config.json         # Configuration
├── swarm.log           # Runtime log
├── data/
│   ├── backlog.json        # Research ideas
│   ├── operations.json     # Content productions
│   ├── results.json        # Published content
│   ├── products.json       # Created products
│   └── revenue_tracker.json # Finance tracking
├── products/           # Generated product files
├── website_content/
│   └── posts/          # Blog posts for website
└── finance/
    └── payout_request.json # Payout initialization
```

## GitHub Connector

The research agent connects to GitHub's public API to scan:
- Trending repositories by stars and recent activity
- Popular projects in monetization-friendly niches
- Emerging technologies with commercial potential

This provides continuous flow of "billions of ideas" from the GitHub community.

## Revenue Model

1. **YouTube AdSense** - Ad revenue from video views
2. **Gumroad Sales** - Digital product sales
3. **Affiliate Commissions** - Referral links in content

All revenue tracked by Finance Agent. When threshold reached, payout initiated to configured bank account via platform's normal payout system.

## Status

**Phase 1: Core Engine** - Agents built, logic complete, demo mode operational
**Phase 2: API Integration** - YouTube upload, Gumroad listing (requires API keys)
**Phase 3: Automation** - Scheduled runs, full autonomous operation
**Phase 4: Scaling** - Multi-niche, increased production volume
