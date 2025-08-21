# check_counts.py
import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.getenv("MONGO_URI")
db_name = os.getenv("DB_NAME", "jobtracker")
coll_name = os.getenv("COLL_NAME", "jobs")

print("Connecting to:", uri)
client = MongoClient(uri)
col = client[db_name][coll_name]

print("Count:", col.count_documents({}))
print("By source:")
for row in col.aggregate([
    {"$group": {"_id": "$source", "n": {"$sum": 1}}},
    {"$sort": {"n": -1}}
]):
    print(f"  {row['_id']}: {row['n']}")
