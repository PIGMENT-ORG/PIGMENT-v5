#!/usr/bin/env python3
"""
PIGMENT v5 - Training Data Backup Script
Backs up training data from Supabase and local storage
"""

import os
import sys
import json
import glob
import requests
import shutil
from datetime import datetime, timedelta
import argparse

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TrainingDataBackup:
    def __init__(self, backup_dir='backups'):
        self.backup_dir = backup_dir
        self.training_dir = 'training_data'
        self.supabase_url = 'https://slfxwkvhomomdcqpkfqp.supabase.co'
        self.supabase_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNsZnh3a3Zob21vbWRjcXBrZnFwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEzNzQxNzQsImV4cCI6MjA4Njk1MDE3NH0.ThDVJzCPooZCwFt68Aw608t9Dmnt-cWgxlYy9nPRhpY'
        
        # Create backup directory
        os.makedirs(backup_dir, exist_ok=True)
        
    def backup_local_data(self):
        """Backup local training_data directory"""
        print("\n📦 Backing up local training data...")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{self.backup_dir}/training_data_local_{timestamp}.tar.gz"
        
        if not os.path.exists(self.training_dir):
            print("⚠️ No local training data found")
            return None
        
        # Create tar.gz archive
        import tarfile
        with tarfile.open(backup_file, 'w:gz') as tar:
            tar.add(self.training_dir, arcname=os.path.basename(self.training_dir))
        
        # Get file size
        size = os.path.getsize(backup_file)
        print(f"✅ Local data backed up: {backup_file}")
        print(f"   Size: {size:,} bytes ({size/1024/1024:.2f} MB)")
        
        return backup_file
    
    def backup_supabase_data(self, limit=10000):
        """Backup data from Supabase"""
        print("\n☁️ Backing up Supabase training data...")
        
        headers = {
            'apikey': self.supabase_key,
            'Authorization': f'Bearer {self.supabase_key}'
        }
        
        # Fetch data from Supabase
        response = requests.get(
            f"{self.supabase_url}/rest/v1/training_data?select=*&order=created_at.desc&limit={limit}",
            headers=headers
        )
        
        if response.status_code != 200:
            print(f"❌ Failed to fetch from Supabase: {response.status_code}")
            return None
        
        data = response.json()
        print(f"✅ Fetched {len(data)} records from Supabase")
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{self.backup_dir}/training_data_supabase_{timestamp}.json"
        
        with open(backup_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        size = os.path.getsize(backup_file)
        print(f"✅ Supabase data backed up: {backup_file}")
        print(f"   Size: {size:,} bytes ({size/1024:.2f} KB)")
        
        return backup_file
    
    def backup_all(self):
        """Backup both local and Supabase data"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        manifest = {
            'timestamp': timestamp,
            'backups': []
        }
        
        # Backup local
        local_backup = self.backup_local_data()
        if local_backup:
            manifest['backups'].append({
                'type': 'local',
                'path': local_backup,
                'timestamp': timestamp
            })
        
        # Backup Supabase
        supabase_backup = self.backup_supabase_data()
        if supabase_backup:
            manifest['backups'].append({
                'type': 'supabase',
                'path': supabase_backup,
                'timestamp': timestamp
            })
        
        # Save manifest
        manifest_file = f"{self.backup_dir}/backup_manifest_{timestamp}.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"\n📋 Backup manifest saved: {manifest_file}")
        return manifest
    
    def list_backups(self):
        """List all available backups"""
        backups = glob.glob(f"{self.backup_dir}/training_data_*.tar.gz") + \
                  glob.glob(f"{self.backup_dir}/training_data_*.json") + \
                  glob.glob(f"{self.backup_dir}/backup_manifest_*.json")
        
        print(f"\n📋 Available backups in {self.backup_dir}:")
        for backup in sorted(backups, reverse=True):
            size = os.path.getsize(backup)
            modified = datetime.fromtimestamp(os.path.getmtime(backup))
            print(f"   {modified.strftime('%Y-%m-%d %H:%M')}  {size:10,} bytes  {os.path.basename(backup)}")
        
        return backups
    
    def restore_from_backup(self, backup_file, restore_dir='restored_data'):
        """Restore data from a backup file"""
        print(f"\n🔄 Restoring from {backup_file}...")
        
        os.makedirs(restore_dir, exist_ok=True)
        
        if backup_file.endswith('.tar.gz'):
            # Extract tar.gz
            import tarfile
            with tarfile.open(backup_file, 'r:gz') as tar:
                tar.extractall(restore_dir)
            print(f"✅ Restored to {restore_dir}")
            
        elif backup_file.endswith('.json'):
            # Copy JSON file
            import shutil
            dest = f"{restore_dir}/{os.path.basename(backup_file)}"
            shutil.copy2(backup_file, dest)
            print(f"✅ Restored to {dest}")
        
        return restore_dir
    
    def cleanup_old_backups(self, days=7):
        """Delete backups older than specified days"""
        print(f"\n🧹 Cleaning up backups older than {days} days...")
        
        cutoff = datetime.now() - timedelta(days=days)
        deleted = 0
        kept = 0
        
        for backup in glob.glob(f"{self.backup_dir}/training_data_*"):
            mtime = datetime.fromtimestamp(os.path.getmtime(backup))
            if mtime < cutoff:
                os.remove(backup)
                print(f"   Deleted: {os.path.basename(backup)}")
                deleted += 1
            else:
                kept += 1
        
        print(f"✅ Cleanup complete: {deleted} deleted, {kept} kept")
        return deleted

def main():
    parser = argparse.ArgumentParser(description='Backup PIGMENT training data')
    parser.add_argument('--action', choices=['backup', 'list', 'cleanup', 'restore'],
                       default='backup', help='Action to perform')
    parser.add_argument('--backup-file', help='Backup file to restore from')
    parser.add_argument('--days', type=int, default=7, help='Days to keep for cleanup')
    parser.add_argument('--backup-dir', default='backups', help='Backup directory')
    
    args = parser.parse_args()
    
    backup = TrainingDataBackup(backup_dir=args.backup_dir)
    
    if args.action == 'backup':
        backup.backup_all()
    elif args.action == 'list':
        backup.list_backups()
    elif args.action == 'cleanup':
        backup.cleanup_old_backups(days=args.days)
    elif args.action == 'restore':
        if not args.backup_file:
            print("❌ Please specify --backup-file to restore")
            sys.exit(1)
        backup.restore_from_backup(args.backup_file)

if __name__ == '__main__':
    main()
