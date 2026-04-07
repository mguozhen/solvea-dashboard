#!/bin/bash
# Regenerate data.json and push to GitHub Pages
cd /Users/guozhen/MailOutbound/dashboard-web
python3 generate_data.py
git add -A
git commit -m "data update $(date +%Y-%m-%d\ %H:%M)" --allow-empty
git push origin main
