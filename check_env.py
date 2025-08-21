import os
from dotenv import load_dotenv
load_dotenv()
print("MONGO_URI:", os.getenv("MONGO_URI"))
print("DB_NAME:", os.getenv("DB_NAME"))
print("COLL_NAME:", os.getenv("COLL_NAME"))
print("SERPAPI_KEY present?", bool(os.getenv("SERPAPI_KEY")))
