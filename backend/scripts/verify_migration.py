#!/usr/bin/env python3
from pymongo import MongoClient
import os

client = MongoClient(os.environ.get('MONGODB_URL'))
db = client.get_database()

print('=== FINAL VERIFICATION ===\n')
print(f'✅ Portfolio agent chats: {db.chats.count_documents({"user_id": "portfolio_agent"})}')
print(f'✅ User chats: {db.chats.count_documents({"user_id": "user_57dde4922766"})}')

# Check if any user chats still have 'Analysis' in title
analysis_in_user_chats = db.chats.count_documents({
    'user_id': 'user_57dde4922766',
    'title': {'$regex': 'Analysis$'}
})

print(f'\n❌ User chats with "Analysis" in title: {analysis_in_user_chats}')

if analysis_in_user_chats == 0:
    print('\n🎉 SUCCESS: All analysis chats are now under portfolio_agent!')
    print('   User\'s regular chat sidebar will ONLY show conversations')
    print('   Portfolio analysis sidebar will ONLY show stock analyses')
else:
    print(f'\n⚠️  WARNING: {analysis_in_user_chats} analysis chats still under user ID')

    # Show which ones
    print('\n   Remaining user analysis chats:')
    for chat in db.chats.find({'user_id': 'user_57dde4922766', 'title': {'$regex': 'Analysis$'}}):
        print(f'     - {chat["title"]} ({chat["chat_id"]})')
