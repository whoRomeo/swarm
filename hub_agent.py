#!/usr/bin/env python3
"""
Hub Agent - Orchestrates all sub-agents and manages the swarm.
This is the "brain" that coordinates everything.
"""

import os
import sys
import json
import time
import logging
import subprocess
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [HUB] %(message)s',
    handlers=[logging.FileHandler('hub.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class HubAgent:
    def __init__(self, config_path='config.json'):
        self.config = self.load_config(config_path)
        self.swarm_script = Path('agent_swarm.py')
        self.data_dir = Path('data')
        # Token from environment, not config (never commit tokens)
        self.github_token = os.environ.get('GITHUB_TOKEN', '')
        
    def load_config(self, path):
        if Path(path).exists():
            with open(path) as f:
                return json.load(f)
        return {}
    
    def run_swarm(self, agents='all'):
        """Execute the swarm with specified agents"""
        logger.info(f"Running swarm with agents: {agents}")
        
        cmd = [sys.executable, str(self.swarm_script), '--agents', agents]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info("Swarm completed successfully")
            logger.info(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return True
        else:
            logger.error(f"Swarm failed: {result.stderr}")
            return False
    
    def push_to_github(self):
        """Push all changes to GitHub using token from environment"""
        logger.info("Pushing to GitHub...")
        
        if not self.github_token:
            logger.warning("No GITHUB_TOKEN set - skipping push")
            return False
        
        try:
            # Run git commands with token in URL
            push_url = f"https://ghp_{self.github_token}@github.com/whoRomeo/swarm.git"
            
            subprocess.run(['git', 'add', '.'], cwd='.', check=False)
            subprocess.run(['git', 'commit', '-m', f"Swarm update {datetime.now().isoformat()}"], 
                         cwd='.', check=False, capture_output=True)
            result = subprocess.run(['git', 'push', push_url, 'master'], 
                                   cwd='.', capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info("GitHub push successful")
                return True
            else:
                logger.error(f"Push failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Push error: {e}")
            return False
    
    def check_github_pages(self):
        """Check if GitHub Pages is building"""
        import requests
        
        token = self.github_token
        headers = {'Authorization': f'token {token}'} if token else {}
        
        try:
            resp = requests.get(
                'https://api.github.com/repos/whoRomeo/swarm/pages',
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                url = data.get('html_url', 'https://whoromeo.github.io/swarm/')
                logger.info(f"GitHub Pages URL: {url}")
                return url
        except Exception as e:
            logger.warning(f"Could not check Pages status: {e}")
        
        return 'https://whoromeo.github.io/swarm/'
    
    def run_full_cycle(self):
        """Execute a complete swarm cycle"""
        logger.info("=" * 60)
        logger.info("HUB AGENT: Starting full cycle")
        logger.info("=" * 60)
        
        start = time.time()
        
        # Step 1: Run research + content + products
        logger.info("Phase 1: Research & Creation")
        self.run_swarm('research content product')
        
        # Step 2: Publish
        logger.info("Phase 2: Publishing")
        self.run_swarm('publishing')
        
        # Step 3: Finance check
        logger.info("Phase 3: Finance")
        self.run_swarm('finance')
        
        # Step 4: Push to GitHub
        logger.info("Phase 4: Sync to GitHub")
        self.push_to_github()
        
        elapsed = time.time() - start
        logger.info(f"Full cycle completed in {elapsed:.1f} seconds")
        
        # Report website URL
        pages_url = self.check_github_pages()
        logger.info(f"Website: {pages_url}")
        
        return {
            'duration_seconds': elapsed,
            'website_url': pages_url,
            'timestamp': datetime.now().isoformat()
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Hub Agent - Swarm Orchestrator')
    parser.add_argument('--cycle', action='store_true', help='Run full cycle')
    parser.add_argument('--swarm', nargs='+', help='Run swarm with specific agents')
    parser.add_argument('--push', action='store_true', help='Push to GitHub only')
    parser.add_argument('--status', action='store_true', help='Check status only')
    
    args = parser.parse_args()
    hub = HubAgent()
    
    if args.cycle:
        result = hub.run_full_cycle()
        print(f"\nCycle complete: {result['duration_seconds']:.1f}s")
        print(f"Website: {result['website_url']}")
    
    elif args.swarm:
        hub.run_swarm(args.swarm)
    
    elif args.push:
        hub.push_to_github()
    
    elif args.status:
        pages = hub.check_github_pages()
        print(f"Website: {pages}")
        if hub.data_dir.exists():
            files = list(hub.data_dir.glob('*.json'))
            print(f"Data files: {len(files)}")
    
    else:
        print("Hub Agent ready. Use --cycle, --swarm, --push, or --status")


if __name__ == '__main__':
    main()
