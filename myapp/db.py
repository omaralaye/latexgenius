import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI",)
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB_NAME]

def get_collection(collection_name):
    return db[collection_name]

# Collections
projects_col = get_collection("projects")
templates_col = get_collection("templates")
settings_col = get_collection("settings")
features_col = get_collection("features")
statistics_col = get_collection("statistics")
testimonials_col = get_collection("testimonials")
