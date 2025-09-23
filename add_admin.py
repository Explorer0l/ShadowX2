#!/usr/bin/env python3
"""
Script to add a second administrator to ShadowX Bot
Usage: python add_admin.py <user_id> <username>
"""

import sys
import os

def add_admin(user_id, username=None):
    """Add a new admin to the config file"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    
    # Read current config
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find ADMIN_IDS list
    lines = content.split('\n')
    new_lines = []
    in_admin_ids = False
    admin_ids_updated = False
    in_admin_usernames = False
    admin_usernames_updated = False
    
    for line in lines:
        if 'ADMIN_IDS = [' in line:
            in_admin_ids = True
            new_lines.append(line)
        elif in_admin_ids and ']' in line and not admin_ids_updated:
            # Add new admin ID before closing bracket
            new_lines.append(f'    {user_id},  # Added admin')
            new_lines.append(line)
            in_admin_ids = False
            admin_ids_updated = True
        elif 'ADMIN_USERNAMES = {' in line:
            in_admin_usernames = True
            new_lines.append(line)
        elif in_admin_usernames and '}' in line and not admin_usernames_updated:
            # Add new admin username before closing brace
            if username:
                new_lines.append(f'    {user_id}: "{username}",  # Added admin')
            new_lines.append(line)
            in_admin_usernames = False
            admin_usernames_updated = True
        else:
            new_lines.append(line)
    
    # Write updated config
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    print(f"✅ Admin {user_id} ({username or 'no username'}) added successfully!")
    print("📝 Updated config.py")
    print("🔄 Restart the bot to apply changes")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python add_admin.py <user_id> [username]")
        print("Example: python add_admin.py 123456789 @second_admin")
        sys.exit(1)
    
    try:
        user_id = int(sys.argv[1])
        username = sys.argv[2] if len(sys.argv) > 2 else None
        add_admin(user_id, username)
    except ValueError:
        print("❌ Error: user_id must be a number")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
